#!/usr/bin/env python3
"""Connecteur de source datasync (livraison #652) -- posé près d'une base (MySQL/MariaDB, PostgreSQL, SQLite), il pousse
vers l'API source centrale du hub, en sens unique : /ping (présence), /schema (tables, colonnes, clés), /rows (lots).
Bibliothèque standard seule (urllib, json) + le pilote de la base (pymysql | psycopg2 | sqlite3 intégré).

Usage : python3 connector.py config.json [--once] [--ping-only]
config.json :
{ "central": "https://hub.exemple:6443/api/datasync", "token": "<jeton de la source>", "verify_tls": true,
  "db": {"driver": "mysql|postgres|sqlite", "host": "...", "port": 3306, "user": "...", "password": "...", "name": "...", "path": "..."},
  "tables": [{"name": "tickets", "pk": "id", "watermark": "last_update"}, {"name": "contacts", "pk": "id"}],
  "interval_s": 300, "ping_s": 60, "batch": 500, "state_file": "connector.state.json" }
- table sans watermark : synchronisation COMPLÈTE à chaque cycle (le central retire les lignes disparues) ;
- table avec watermark (colonne croissante : horodatage, compteur) : INCRÉMENTALE depuis la dernière valeur vue (state_file).
Aucune écriture dans la base source (SELECT seulement) ; les secrets restent dans config.json (droits 600 conseillés)."""
import sys, json, time, socket, ssl, uuid, urllib.request, urllib.error, pathlib, datetime, decimal

VERSION = "0.1.0"

def load_cfg(path):
    cfg = json.loads(pathlib.Path(path).read_text(encoding="utf-8")); cfg.setdefault("interval_s", 300); cfg.setdefault("ping_s", 60); cfg.setdefault("batch", 500)
    cfg.setdefault("state_file", str(pathlib.Path(path).with_suffix(".state.json"))); cfg.setdefault("verify_tls", True); return cfg

def post(cfg, path, body):
    data = json.dumps(body, ensure_ascii=False, default=_json_default).encode("utf-8")
    req = urllib.request.Request(cfg["central"].rstrip("/") + path, data=data, headers={"Content-Type": "application/json", "Authorization": "Bearer " + cfg["token"]}, method="POST")
    ctx = None if cfg.get("verify_tls", True) else ssl._create_unverified_context()
    try:
        with urllib.request.urlopen(req, timeout=120, context=ctx) as r: return json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e: return {"error": f"HTTP {e.code} : {e.read().decode('utf-8', 'replace')[:300]}"}
    except (urllib.error.URLError, socket.timeout) as e: return {"error": f"central injoignable : {e}"}

def _json_default(v):
    if isinstance(v, (datetime.date, datetime.datetime)): return v.isoformat(sep=" ")
    if isinstance(v, decimal.Decimal): return float(v)
    if isinstance(v, (bytes, bytearray)): return v.decode("utf-8", "replace")
    return str(v)

def connect(dbc):
    drv = dbc.get("driver", "mysql")
    if drv == "sqlite":
        import sqlite3; cn = sqlite3.connect(dbc["path"]); cn.row_factory = sqlite3.Row; return cn, "?"
    if drv == "postgres":
        import psycopg2, psycopg2.extras; cn = psycopg2.connect(host=dbc.get("host", "localhost"), port=dbc.get("port", 5432), user=dbc["user"], password=dbc.get("password", ""), dbname=dbc["name"]); return cn, "%s"
    import pymysql; cn = pymysql.connect(host=dbc.get("host", "localhost"), port=int(dbc.get("port", 3306)), user=dbc["user"], password=dbc.get("password", ""), database=dbc["name"],
                                        charset=dbc.get("charset", "utf8mb4"), cursorclass=pymysql.cursors.DictCursor, unix_socket=dbc.get("socket")); return cn, "%s"

def q(cn, drv, sql, params=()):
    cur = cn.cursor()
    if drv == "postgres":
        import psycopg2.extras; cur = cn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(sql, params); rows = cur.fetchall()
    return [dict(r) for r in rows]

def columns_of(cn, drv, table):
    if drv == "sqlite": return [dict(name=r["name"], type=r["type"]) for r in q(cn, drv, f"PRAGMA table_info(\"{table}\")")]
    if drv == "postgres": return [dict(name=r["column_name"], type=r["data_type"]) for r in q(cn, drv, "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = %s ORDER BY ordinal_position", (table,))]
    return [dict(name=r["Field"], type=r["Type"]) for r in q(cn, drv, f"SHOW COLUMNS FROM `{table}`")]

def quote(drv, name): return f'"{name}"' if drv in ("sqlite", "postgres") else f"`{name}`"

def sync_table(cfg, cn, drv, t, state, log):
    name, pk, wm = t["name"], t["pk"], t.get("watermark"); ph = "?" if drv == "sqlite" else "%s"
    mode = "incremental" if wm else "full"; last = state.get(name) if wm else None; sync_id = uuid.uuid4().hex[:12]
    where = f" WHERE {quote(drv, wm)} > {ph}" if (wm and last is not None) else ""
    order = f" ORDER BY {quote(drv, wm)}" if wm else f" ORDER BY {quote(drv, pk)}"
    off, sent, newest, done = 0, 0, last, False
    while True:
        rows = q(cn, drv, f"SELECT * FROM {quote(drv, name)}{where}{order} LIMIT {int(cfg['batch'])} OFFSET {off}", (last,) if where else ())
        done = len(rows) < cfg["batch"]                       # dernier lot (éventuellement vide) : le central clôt le cycle complet
        if not rows and mode == "incremental": break          # rien de neuf : rien à envoyer
        r = post(cfg, "/rows", dict(table=name, pk=pk, mode=mode, sync_id=sync_id, rows=rows, done=done))
        if r.get("error"): log(f"{name} : {r['error']}"); return sent, False
        sent += r.get("received", 0)
        for row in rows:
            if wm and row.get(wm) is not None and (newest is None or str(row[wm]) > str(newest)): newest = row[wm]
        if done: break
        off += cfg["batch"]
    if wm and newest is not None: state[name] = newest if isinstance(newest, (int, float, str)) else _json_default(newest)
    log(f"{name} : {sent} ligne(s) ({mode})"); return sent, True

def main():
    if len(sys.argv) < 2: sys.exit(__doc__)
    cfg = load_cfg(sys.argv[1]); once = "--once" in sys.argv; ping_only = "--ping-only" in sys.argv
    sf = pathlib.Path(cfg["state_file"]); state = json.loads(sf.read_text()) if sf.exists() else {}
    log = lambda m: print(time.strftime("%Y-%m-%d %H:%M:%S"), m, flush=True)
    last_sync = 0
    while True:
        r = post(cfg, "/ping", dict(host=socket.gethostname(), version=VERSION, db=cfg["db"].get("name") or cfg["db"].get("path"), tables=[t["name"] for t in cfg["tables"]], next_sync=int(max(0, cfg["interval_s"] - (time.time() - last_sync)))))
        if r.get("error"): log("ping : " + r["error"])
        if not ping_only and time.time() - last_sync >= cfg["interval_s"]:
            try:
                cn, _ = connect(cfg["db"]); drv = cfg["db"].get("driver", "mysql")
                post(cfg, "/schema", dict(tables=[dict(name=t["name"], pk=t["pk"], columns=columns_of(cn, drv, t["name"])) for t in cfg["tables"]]))
                for t in cfg["tables"]: sync_table(cfg, cn, drv, t, state, log)
                cn.close(); sf.write_text(json.dumps(state, default=_json_default)); last_sync = time.time()
            except Exception as e: log(f"synchronisation : {type(e).__name__} : {e}")
        if once: break
        time.sleep(cfg["ping_s"])

if __name__ == "__main__": main()
