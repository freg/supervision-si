"""Tests datasync : matching (pur), API centrale (test_client) et connecteur réel (SQLite -> API servie dans un thread) :
deux sources (un gestionnaire de tickets, un annuaire clients), ping/présence, schéma, lots complets et incrémentaux
(retrait des lignes disparues), statistiques, analyse (profils, correspondances inter-sources, relations déduites),
validation des liens, recherche plein texte (accents, préfixe), recherche relationnelle à 2 niveaux, suppression."""
import os, sys, json, time, sqlite3, tempfile, threading, pathlib, importlib, socket
tmp = tempfile.mkdtemp(); os.environ["DATASYNC_DATA_DIR"] = tmp; os.environ["DATASYNC_PRESENCE_S"] = "2"
sys.path.insert(0, os.path.dirname(__file__)); import app as appmod; importlib.reload(appmod); import matching
c = appmod.app.test_client()
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "connector")); import connector

def test_matching_pure():
    assert matching.tokens("id_contact") == ["contact"] and matching.tokens("contactId") == ["contact"] and matching.tokens("tts_tickets") == ["ticket"]
    assert matching.name_score("email", "courriel") == 1.0 and matching.bare_id("id") and matching.bare_id("num_ref") and not matching.bare_id("id_site")
    assert matching.profile(["a@b.fr", "c@d.org"])["kind"] == "email" and matching.profile(["0612345678", "+33 6 12 34 56 78"])["kind"] == "phone" and matching.profile([None, ""])["kind"] == "empty"
    assert matching.overlap([1, 2, 3], ["2", "3", "4"]) == (0.67, 0.67)
    assert "subject Panne" in matching.flatten_for_fts({"id": 1, "subject": "Panne", "n": None})

def _src(name, kind):
    r = c.post("/sources", json={"name": name, "kind": kind}); assert r.status_code == 201, r.json; return r.json["source"], r.json["token"]

def test_sources_and_ingest():
    s1, t1 = _src("Tickets A", "mysql"); s2, t2 = _src("Annuaire B", "postgres")
    assert "token_hash" not in s1 and s1["presence"] == "jamais" and c.post("/sources", json={"name": "Tickets A"}).status_code == 409
    assert c.post("/ping", json={}).status_code == 401
    H = lambda t: {"Authorization": "Bearer " + t}
    assert c.post("/ping", json={"host": "srv1", "version": "0.1.0"}, headers=H(t1)).json["ok"]
    assert c.post("/schema", json={"tables": [{"name": "tickets", "pk": "id", "columns": [{"name": "id", "type": "int"}]}, {"name": "bad name", "pk": "id"}]}, headers=H(t1)).status_code == 400
    rows = [{"id": 1, "subject": "Panne écran", "id_contact": 10, "last_update": "2026-10-01 10:00"}, {"id": 2, "subject": "Accès refusé", "id_contact": 11, "last_update": "2026-10-02 09:00"}, {"id": 3, "subject": "Imprimante", "id_contact": 10, "last_update": "2026-10-02 11:00"}]
    r = c.post("/rows", json={"table": "tickets", "pk": "id", "mode": "full", "sync_id": "aaa", "rows": rows, "done": True}, headers=H(t1)); assert r.json == {"ok": True, "received": 3, "total": 3, "removed": 0}, r.json
    r = c.post("/rows", json={"table": "contacts", "pk": "id", "mode": "full", "sync_id": "bbb", "rows": [{"id": 10, "contact": "Dupont", "email": "dupont@exemple.fr", "id_site": 5}, {"id": 11, "contact": "Martin", "email": "martin@exemple.fr", "id_site": 5}, {"id": 12, "contact": "Ancien", "email": "x@exemple.fr", "id_site": 6}], "done": True}, headers=H(t1)); assert r.json["total"] == 3
    r = c.post("/rows", json={"table": "clients", "pk": "num", "mode": "full", "sync_id": "ccc", "rows": [{"num": 10, "societe": "Dupont SARL", "courriel": "dupont@exemple.fr", "tel": "0612345678"}, {"num": 11, "societe": "Martin & Cie", "courriel": "martin@exemple.fr", "tel": "0698765432"}], "done": True}, headers=H(t2)); assert r.json["total"] == 2
    # cycle complet suivant sans la ligne 12 -> retirée ; incrémental -> ajout
    r = c.post("/rows", json={"table": "contacts", "pk": "id", "mode": "full", "sync_id": "ddd", "rows": [{"id": 10, "contact": "Dupont", "email": "dupont@exemple.fr", "id_site": 5}, {"id": 11, "contact": "Martin", "email": "martin@exemple.fr", "id_site": 5}], "done": True}, headers=H(t1)); assert r.json["removed"] == 1 and r.json["total"] == 2
    r = c.post("/rows", json={"table": "tickets", "pk": "id", "mode": "incremental", "rows": [{"id": 4, "subject": "Réseau lent", "id_contact": 11, "last_update": "2026-10-03 08:00"}]}, headers=H(t1)); assert r.json["total"] == 4
    L = c.get("/sources").json; a = next(s for s in L["sources"] if s["slug"] == "tickets-a"); assert a["presence"] == "present" and a["rows_total"] == 6 and next(t for t in a["tables"] if t["name"] == "tickets")["batches"] == 2
    assert len(c.get(f"/sources/{a['id']}/log").json["log"]) == 4
    time.sleep(3.2); assert next(s for s in c.get("/sources").json["sources"] if s["slug"] == "tickets-a")["presence"] == "absent"

def test_analysis_search_relations():
    srcs = {s["slug"]: s for s in c.get("/sources").json["sources"]}; a, b = srcs["tickets-a"], srcs["annuaire-b"]
    prof = c.get("/analysis/profiles").json["tables"]; tk = next(t for t in prof if t["table"] == "tickets"); assert next(col for col in tk["columns"] if col["name"] == "subject")["kind"] == "text"
    r = c.post("/analysis/run").json; assert r["relations"] >= 1 and r["fields"] >= 1, r
    links = c.get("/links").json["links"]
    rel = [l for l in links if l["kind"] == "relation"]; assert any(l["a_table"] == "tickets" and l["a_column"] == "id_contact" and l["b_table"] == "contacts" for l in rel), rel
    assert any(l["a_table"] == "tickets" and l["b_table"] == "clients" and l["b_source"] == b["id"] for l in rel)     # inter-sources
    fld = [l for l in links if l["kind"] == "field"]; assert any({l["a_column"], l["b_column"]} == {"email", "courriel"} for l in fld), fld
    f = next(l for l in fld if {l["a_column"], l["b_column"]} == {"email", "courriel"}); assert c.put(f"/links/{f['id']}", json={"status": "confirmed", "by_user": "freg"}).json["ok"]
    assert c.post("/analysis/run").json["new"] == 0 and next(l for l in c.get("/links").json["links"] if l["id"] == f["id"])["status"] == "confirmed"
    assert c.post("/links", json={"kind": "relation", "a_source": a["id"], "a_table": "contacts", "a_column": "id_site", "b_source": a["id"], "b_table": "sites", "b_column": "id"}).status_code == 201
    # plein texte : accents, préfixe, filtre
    r = c.get("/search?q=panne").json; assert r["total"] == 1 and r["results"][0]["table"] == "tickets" and "[Panne]" in r["results"][0]["snippet"]
    assert c.get("/search?q=acces").json["total"] == 1 and c.get("/search?q=dup").json["total"] >= 2 and c.get(f"/search?q=dup&source={b['id']}").json["total"] == 1
    assert c.get("/search?q=exemple.fr").json["total"] >= 4 and c.get("/search?q=").json["total"] == 0
    # relationnel : ticket 1 -> contact 10 (A) et client 10 (B) ; niveau 2 : tickets du contact 10 (1 et 3)
    r = c.get(f"/rows/{a['id']}/tickets/1/related?depth=2").json; keys = {(n["table"], n["pk"]) for n in r["nodes"]}
    assert ("contacts", "10") in keys and ("clients", "10") in keys and ("tickets", "3") in keys and ("tickets", "2") not in keys, keys
    assert any(e["direction"] == "←" for e in r["edges"]) and next(n for n in r["nodes"] if n["table"] == "clients")["source"] == "annuaire-b"
    r = c.get(f"/rows/{a['id']}/contacts/10/related").json; assert {(n["table"], n["pk"]) for n in r["nodes"] if n["level"] == 1} == {("tickets", "1"), ("tickets", "3")}
    assert c.get(f"/rows/{a['id']}/tickets/999/related").status_code == 404 and c.get(f"/rows/{a['id']}/tickets").json["total"] == 4
    assert c.post(f"/sources/{a['id']}/rotate-token").json["token"] and c.delete(f"/sources/{b['id']}").json["ok"] and c.get("/search?q=sarl").json["total"] == 0

def test_connector_real_sqlite():
    """Le connecteur réel contre l'API servie dans un thread : source SQLite avec une table à watermark et une sans."""
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    threading.Thread(target=lambda: appmod.app.run(port=port, use_reloader=False), daemon=True).start(); time.sleep(0.8)
    src, tok = _src("Source SQLite", "sqlite")
    dbp = os.path.join(tmp, "src.db"); cn = sqlite3.connect(dbp)
    cn.executescript("CREATE TABLE events (id INTEGER PRIMARY KEY, ts INTEGER, body TEXT); CREATE TABLE sites (id INTEGER PRIMARY KEY, site_name TEXT);"
                     "INSERT INTO events VALUES (1, 100, 'ouverture'), (2, 200, 'relance'); INSERT INTO sites VALUES (5, 'Siège'), (6, 'Agence');"); cn.commit()
    cfgp = os.path.join(tmp, "c.json"); json.dump({"central": f"http://127.0.0.1:{port}", "token": tok, "db": {"driver": "sqlite", "path": dbp}, "tables": [{"name": "events", "pk": "id", "watermark": "ts"}, {"name": "sites", "pk": "id"}], "batch": 1, "interval_s": 0, "ping_s": 0}, open(cfgp, "w"))
    sys.argv = ["connector", cfgp, "--once"]; connector.main()
    st = json.load(open(os.path.join(tmp, "c.state.json"))); assert st == {"events": 200}, st
    a = next(x for x in c.get("/sources").json["sources"] if x["slug"] == "source-sqlite"); assert a["rows_total"] == 4 and a["presence"] == "present" and a["last_ping_info"]["version"] == connector.VERSION
    cn.execute("INSERT INTO events VALUES (3, 300, 'clôture')"); cn.execute("DELETE FROM sites WHERE id = 6"); cn.commit(); connector.main()
    a = next(x for x in c.get("/sources").json["sources"] if x["slug"] == "source-sqlite"); tabs = {t["name"]: t for t in a["tables"]}
    assert tabs["events"]["rows"] == 3 and tabs["events"]["last_batch_rows"] == 1 and tabs["sites"]["rows"] == 1, tabs      # incrémental : 1 seule ligne envoyée ; complet : ligne disparue retirée
    assert json.load(open(os.path.join(tmp, "c.state.json"))) == {"events": 300}
