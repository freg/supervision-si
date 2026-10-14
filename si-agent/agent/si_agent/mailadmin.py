# -*- coding: utf-8 -*-
"""Serveur de messagerie -- exploitation (livraison #752, tuile « Serveur de messagerie ») : file d'attente et échecs de
distribution vers les serveurs distants, listes blanches / grises / noires (tables d'accès Postfix, postscreen, postgrey,
listes DNS), réglages antispam et Postfix. Actions de la commande `mail` (mailctl.run_action) :

  queue_list        file Postfix (postqueue -j) : messages, regroupements par domaine distant et par motif
  queue_action      flush | requeue | hold | release | deliver | delete (n° de file, ou « ALL deferred » pour requeue)   [motif]
  delivery_failures reports (deferred) et rebonds (bounced) du journal, par domaine / code DSN / motif normalisé
  lists             tables d'accès découvertes dans postconf (client, expéditeur, destinataire, HELO, postscreen), listes
                    blanches postgrey, listes DNS (reject_rbl_client, postscreen_dnsbl_sites) -- entrées classées
                    blanche / noire / grise
  list_set          ajout / modification / retrait d'une entrée (table découverte seulement ; sauvegarde, postmap,
                    rechargement)                                                                                     [motif]
  settings_get      réglages Postfix et Amavis (liste fermée de clés) avec leur valeur courante
  settings_set      modification (liste fermée, valeurs contrôlées) ; sauvegarde, `postfix check` / redémarrage
                    d'Amavis vérifié, retour à l'état antérieur en cas d'échec                                        [motif]
Toutes les écritures exigent un motif et sont journalisées par mailctl (acteur, motif, paramètres)."""
import ipaddress
import json
import os
import re
import shutil
import time

QID_OK = re.compile(r"^[0-9A-Za-z]{6,20}$")
DSN_RE = re.compile(r"dsn=(?P<d>\d\.\d{1,3}\.\d{1,3})")
RELAY_RE = re.compile(r"relay=(?P<r>[^,\s]+)")
TO_RE = re.compile(r"to=<(?P<t>[^>]*)>")
STATUS_RE = re.compile(r"status=(?P<s>deferred|bounced)\b")
REASON_RE = re.compile(r"status=\w+ \((?P<r>.*)\)\s*$")
QUEUE_OPS = ("flush", "requeue", "hold", "release", "deliver", "delete")

# ------------------------------------------------------------------ file d'attente


def domain_of(addr):
    return addr.rsplit("@", 1)[-1].lower() if "@" in (addr or "") else (addr or "").lower() or "(local)"


def normalize_reason(text):
    """Motif d'échec débarrassé de ce qui varie d'un message à l'autre (IP, n°, identifiants) : regroupable."""
    t = str(text or "")
    t = re.sub(r"\[?\b\d{1,3}(?:\.\d{1,3}){3}\b\]?", "[ip]", t)
    t = re.sub(r"\[?\b[0-9a-fA-F]{0,4}(?::[0-9a-fA-F]{0,4}){2,7}\b\]?", "[ip]", t)
    t = re.sub(r"\b[0-9A-Za-z]{10,}\b", lambda m: m.group(0) if m.group(0).isalpha() else "…", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t[:200]


def parse_postqueue_json(text):
    """postqueue -j : un objet JSON par ligne (Postfix ≥ 3.1)."""
    items = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            o = json.loads(line)
        except ValueError:
            continue
        rcpts = [{"address": r.get("address", ""), "reason": r.get("delay_reason", "")} for r in o.get("recipients") or []]
        items.append({"queue_id": o.get("queue_id"), "queue": o.get("queue_name"), "arrival": o.get("arrival_time"),
                      "size": o.get("message_size"), "sender": o.get("sender", ""), "recipients": rcpts, "forced": bool(o.get("forced_expire"))})
    return items


def queue_summary(items, now):
    by_queue, dom, rsn = {}, {}, {}
    for it in items:
        by_queue[it["queue"]] = by_queue.get(it["queue"], 0) + 1
        age = max(0, int(now - (it["arrival"] or now)))
        for r in it["recipients"]:
            d = dom.setdefault(domain_of(r["address"]), {"domain": domain_of(r["address"]), "messages": 0, "oldest_age_s": 0, "reasons": {}})
            d["messages"] += 1; d["oldest_age_s"] = max(d["oldest_age_s"], age)
            n = normalize_reason(r["reason"]) or "(en attente, sans motif)"
            d["reasons"][n] = d["reasons"].get(n, 0) + 1
            g = rsn.setdefault(n, {"reason": n, "messages": 0, "domains": set()})
            g["messages"] += 1; g["domains"].add(d["domain"])
    domains = sorted(({**d, "reasons": sorted(({"reason": k, "count": v} for k, v in d["reasons"].items()), key=lambda x: -x["count"])} for d in dom.values()),
                     key=lambda d: (-d["messages"], d["domain"]))
    reasons = sorted(({**g, "domains": sorted(g["domains"])} for g in rsn.values()), key=lambda g: -g["messages"])
    oldest = max((int(now - (i["arrival"] or now)) for i in items), default=0)
    return {"total": len(items), "by_queue": by_queue, "oldest_age_s": oldest, "domains": domains[:100], "reasons": reasons[:50]}


def queue_argv(op, ids):
    """-> (liste d'argv, erreur)."""
    if op not in QUEUE_OPS:
        return None, "op : %s" % ", ".join(QUEUE_OPS)
    if op == "flush":
        return [["postqueue", "-f"]], None
    ids = [str(i) for i in (ids or [])][:200]
    if op == "requeue" and ids == ["ALL deferred"]:
        return [["postsuper", "-r", "ALL", "deferred"]], None
    if not ids or not all(QID_OK.match(i) for i in ids):
        return None, "n° de file invalides (ou « ALL deferred » pour requeue)"
    if op == "deliver":
        return [["postqueue", "-i", i] for i in ids], None
    flag = {"requeue": "-r", "hold": "-h", "release": "-H", "delete": "-d"}[op]
    return [["postsuper", flag, "-"]], None          # n° passés sur l'entrée standard (un par ligne)


# ------------------------------------------------------------------ échecs de distribution


def delivery_failures(lines, now, hours, parse_time):
    """Reports et rebonds par (domaine, état, DSN, motif normalisé) ; dernier vu, relais, destinataires (échantillon)."""
    since, groups = now - hours * 3600, {}
    for line in lines:
        if "status=deferred" not in line and "status=bounced" not in line:
            continue
        p = parse_time(line, now)
        if not p or p[0] < since:
            continue
        msg = p[2]
        st, to = STATUS_RE.search(msg), TO_RE.search(msg)
        if not st or not to:
            continue
        dsn, relay, reason = DSN_RE.search(msg), RELAY_RE.search(msg), REASON_RE.search(msg)
        key = (domain_of(to.group("t")), st.group("s"), dsn.group("d") if dsn else "", normalize_reason(reason.group("r") if reason else ""))
        g = groups.setdefault(key, {"domain": key[0], "status": key[1], "dsn": key[2], "reason": key[3], "count": 0, "first": p[0], "last": p[0],
                                    "relays": set(), "recipients": set()})
        g["count"] += 1; g["last"] = max(g["last"], p[0]); g["first"] = min(g["first"], p[0])
        if relay:
            g["relays"].add(relay.group("r"))
        if len(g["recipients"]) < 5:
            g["recipients"].add(to.group("t"))
    rows = [dict(g, relays=sorted(g["relays"])[:5], recipients=sorted(g["recipients"]), kind=classify_failure(g)) for g in groups.values()]
    rows.sort(key=lambda g: (g["status"] != "bounced", -g["count"]))
    return {"hours": hours, "deferred": sum(g["count"] for g in rows if g["status"] == "deferred"),
            "bounced": sum(g["count"] for g in rows if g["status"] == "bounced"), "groups": rows[:300]}


FAILURE_KINDS = (
    ("réputation / liste noire", r"block|blacklist|spamhaus|listed|reputation|rbl|poor reputation|5\.7\.1"),
    ("authentification (SPF / DKIM / DMARC)", r"spf|dkim|dmarc|authenticat|5\.7\.(?:23|25|26|27)"),
    ("boîte inexistante", r"user unknown|no such user|does not exist|unknown user|recipient address rejected|5\.1\.1"),
    ("boîte pleine", r"quota|mailbox full|over quota|5\.2\.2|4\.2\.2"),
    ("limitation de débit / greylisting", r"greylist|try again later|too many|rate limit|throttl|4\.7\.0|4\.2\.0|451"),
    ("serveur injoignable / DNS", r"connection timed out|connection refused|host not found|no route|name service|lost connection|network is unreachable"),
    ("TLS", r"tls|certificate|ssl"),
)


def classify_failure(g):
    t = ("%s %s" % (g.get("reason", ""), g.get("dsn", ""))).lower()
    for label, rx in FAILURE_KINDS:
        if re.search(rx, t):
            return label
    return "autre"


# ------------------------------------------------------------------ listes blanches / grises / noires

RESTRICTION_KEYS = ("smtpd_client_restrictions", "smtpd_helo_restrictions", "smtpd_sender_restrictions", "smtpd_relay_restrictions",
                    "smtpd_recipient_restrictions", "smtpd_data_restrictions", "smtpd_end_of_data_restrictions")
ROLE = {"check_client_access": "client (IP / nom)", "check_reverse_client_hostname_access": "nom inverse du client", "check_sender_access": "expéditeur",
        "check_recipient_access": "destinataire", "check_helo_access": "HELO", "postscreen_access_list": "postscreen (IP)"}
EDITABLE_TYPES = ("hash", "lmdb", "btree", "cidr", "texthash")
POSTGREY_FILES = ("/etc/postgrey/whitelist_clients.local", "/etc/postgrey/whitelist_recipients.local",
                  "/etc/postgrey/whitelist_clients", "/etc/postgrey/whitelist_recipients")
VALUE_OK = re.compile(r"^(OK|PERMIT|DUNNO|REJECT|DISCARD|HOLD|WARN|FILTER|PREPEND|permit|reject|dunno|[45]\d\d)(?: [^\n\r]{0,160})?$")
KEY_OK = re.compile(r"^[A-Za-z0-9@._:+/=-]{1,200}$")


def parse_postconf(text):
    out = {}
    for line in (text or "").splitlines():
        if " = " in line:
            k, v = line.split(" = ", 1)
            out[k.strip()] = v.strip()
        elif line.rstrip().endswith(" ="):
            out[line.rstrip()[:-2].strip()] = ""
    return out


def _tokens(v):
    return [t for t in re.split(r"[\s,]+", v or "") if t]


def discover(conf):
    """postconf (dict) -> {maps: [{restriction, role, type, path}], dnsbl: {...}}."""
    maps, seen, smtpd_rbl = [], set(), []
    for key in RESTRICTION_KEYS:
        toks = _tokens(conf.get(key))
        for i, t in enumerate(toks):
            if t in ROLE and i + 1 < len(toks) and ":" in toks[i + 1]:
                typ, path = toks[i + 1].split(":", 1)
                if (typ, path) not in seen:
                    seen.add((typ, path)); maps.append({"restriction": key, "check": t, "role": ROLE[t], "type": typ, "path": path})
            if t in ("reject_rbl_client", "reject_rhsbl_client", "reject_rhsbl_sender", "reject_rhsbl_helo", "reject_rhsbl_reverse_client") and i + 1 < len(toks):
                smtpd_rbl.append({"check": t, "zone": toks[i + 1]})
    for t in _tokens(conf.get("postscreen_access_list")):
        if ":" in t and not t.startswith("permit"):
            typ, path = t.split(":", 1)
            if (typ, path) not in seen:
                seen.add((typ, path)); maps.append({"restriction": "postscreen_access_list", "check": "postscreen_access_list", "role": ROLE["postscreen_access_list"], "type": typ, "path": path})
    dnsbl = {"smtpd": smtpd_rbl, "postscreen_sites": _tokens(conf.get("postscreen_dnsbl_sites")),
             "postscreen_action": conf.get("postscreen_dnsbl_action"), "postscreen_threshold": conf.get("postscreen_dnsbl_threshold")}
    return {"maps": maps, "dnsbl": dnsbl}


def colour(value):
    v = (value or "").split(" ", 1)[0]
    if v.upper() in ("OK", "PERMIT") or v == "permit":
        return "blanche"
    if v.upper() in ("REJECT", "DISCARD") or v == "reject" or re.match(r"^5\d\d$", v):
        return "noire"
    if re.match(r"^4\d\d$", v) or v.upper() in ("HOLD", "WARN"):
        return "grise"
    return "neutre"


def parse_map(text):
    out = []
    for n, line in enumerate((text or "").splitlines(), 1):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        parts = s.split(None, 1)
        out.append({"key": parts[0], "value": parts[1] if len(parts) > 1 else "", "line": n, "list": colour(parts[1] if len(parts) > 1 else "")})
    return out


def parse_postgrey(text):
    return [{"key": l.strip(), "value": "", "line": n, "list": "blanche"} for n, l in enumerate((text or "").splitlines(), 1) if l.strip() and not l.strip().startswith("#")]


def set_entry(text, key, value, sep=" "):
    """Remplace / ajoute / retire (value None) l'entrée `key` ; les commentaires et l'ordre sont gardés."""
    lines, done, out = (text or "").splitlines(), False, []
    for line in lines:
        s = line.strip()
        if s and not s.startswith("#") and s.split(None, 1)[0] == key:
            if value is not None and not done:
                out.append(("%s%s%s" % (key, sep, value)).rstrip())
            done = True
            continue
        out.append(line)
    if value is not None and not done:
        out.append(("%s%s%s" % (key, sep, value)).rstrip())
    return "\n".join(out) + "\n"


def check_entry(m, key, value):
    """-> erreur ou None (m = table découverte, ou {"type": "postgrey"})."""
    if m["type"] == "postgrey":
        return None if re.match(r"^[A-Za-z0-9@._/:-]{1,200}$|^/.{1,200}/$", key) else "entrée postgrey : nom, domaine, IP ou /expression/"
    if m["type"] not in EDITABLE_TYPES:
        return "table %s:%s non modifiable depuis le hub (types : %s)" % (m["type"], m["path"], ", ".join(EDITABLE_TYPES))
    if m["type"] == "cidr":
        try:
            ipaddress.ip_network(key, strict=False)
        except ValueError:
            return "clé cidr : adresse ou réseau IP"
    elif not KEY_OK.match(key):
        return "clé : adresse, @domaine, domaine ou IP, sans espace"
    if value is not None and not VALUE_OK.match(value):
        return "action : OK, REJECT [texte], DUNNO, DISCARD, HOLD, 4xx/5xx [texte], permit, reject, dunno"
    return None


def backup(path, now=None):
    b = "%s.si-bak-%s" % (path, time.strftime("%Y%m%d-%H%M%S", time.localtime(now or time.time())))
    shutil.copy2(path, b)
    return b


# ------------------------------------------------------------------ réglages

TIME_RE = r"^\d{1,6}[smhdw]?$"
INT_RE = r"^\d{1,10}$"
POSTFIX_KEYS = {
    "message_size_limit": (INT_RE, "taille maximale d'un message (octets)"),
    "maximal_queue_lifetime": (TIME_RE, "durée de vie en file avant rebond"),
    "bounce_queue_lifetime": (TIME_RE, "durée de vie d'un rebond en file"),
    "minimal_backoff_time": (TIME_RE, "délai minimal entre deux essais"),
    "maximal_backoff_time": (TIME_RE, "délai maximal entre deux essais"),
    "queue_run_delay": (TIME_RE, "passage du gestionnaire de file"),
    "smtpd_proxy_timeout": (TIME_RE, "délai du filtre avant file (Amavis)"),
    "smtpd_client_connection_rate_limit": (INT_RE, "connexions / client / minute (0 = illimité)"),
    "smtpd_client_message_rate_limit": (INT_RE, "messages / client / minute"),
    "smtpd_client_connection_count_limit": (INT_RE, "connexions simultanées / client"),
    "default_process_limit": (INT_RE, "processus Postfix maximum"),
    "smtp_destination_concurrency_limit": (INT_RE, "envois simultanés / domaine distant"),
    "smtp_destination_rate_delay": (TIME_RE, "pause entre deux envois vers un domaine"),
    "postscreen_dnsbl_action": (r"^(ignore|enforce|drop)$", "postscreen : action sur liste DNS"),
    "postscreen_dnsbl_threshold": (INT_RE, "postscreen : score DNS de blocage"),
    "postscreen_greet_action": (r"^(ignore|enforce|drop)$", "postscreen : client trop pressé"),
    "smtp_tls_security_level": (r"^(none|may|encrypt|dane|verify|secure)$", "TLS sortant"),
    "smtpd_tls_security_level": (r"^(none|may|encrypt)$", "TLS entrant"),
}
NUM_RE = r"^(undef|-?\d{1,3}(?:\.\d{1,2})?)$"
AMAVIS_KEYS = {
    "max_servers": (r"^\d{1,2}$", "processus Amavis (≈ messages analysés en parallèle)"),
    "sa_tag_level_deflt": (NUM_RE, "score : en-têtes X-Spam ajoutés (undef = toujours)"),
    "sa_tag2_level_deflt": (NUM_RE, "score : marqué spam (sujet, en-tête)"),
    "sa_kill_level_deflt": (NUM_RE, "score : bloqué (quarantaine / destin du spam)"),
    "sa_dsn_cutoff_level": (NUM_RE, "score : plus d'avis de non-remise au-delà"),
    "final_spam_destiny": (r"^D_(PASS|DISCARD|BOUNCE|REJECT)$", "spam bloqué : PASS / DISCARD / BOUNCE / REJECT"),
    "final_virus_destiny": (r"^D_(PASS|DISCARD|BOUNCE|REJECT)$", "virus"),
    "final_banned_destiny": (r"^D_(PASS|DISCARD|BOUNCE|REJECT)$", "pièce jointe interdite"),
    "final_bad_header_destiny": (r"^D_(PASS|DISCARD|BOUNCE|REJECT)$", "en-tête invalide"),
    "sa_spam_subject_tag": (r"^[A-Za-z0-9*\[\]() :_.-]{0,30}$", "préfixe du sujet d'un spam"),
}
AMAVIS_VAR_RE = re.compile(r"^\s*\$(?P<k>\w+)\s*=\s*(?P<v>.+?)\s*;\s*(?:#.*)?$")


def amavis_values(files):
    """[(chemin, texte)] dans l'ordre de lecture -> {clé: {value, file}} (la dernière définition gagne)."""
    out = {}
    for path, text in files:
        for line in (text or "").splitlines():
            m = AMAVIS_VAR_RE.match(line)
            if m and m.group("k") in AMAVIS_KEYS:
                out[m.group("k")] = {"value": m.group("v").strip().strip("'\""), "file": path}
    return out


def amavis_literal(key, value):
    if key == "sa_spam_subject_tag":
        return "'%s'" % value
    return value


def set_amavis_var(text, key, value):
    """Remplace `$key = …;` (dernière occurrence) ou l'insère avant la ligne finale `1;`."""
    lines = (text or "").splitlines()
    new = "$%s = %s;   # si-agent (hub)" % (key, amavis_literal(key, value))
    idx = [i for i, l in enumerate(lines) if AMAVIS_VAR_RE.match(l) and AMAVIS_VAR_RE.match(l).group("k") == key]
    if idx:
        lines[idx[-1]] = new
    else:
        end = [i for i, l in enumerate(lines) if re.match(r"^\s*1;\s*(#.*)?$", l)]
        lines.insert(end[-1] if end else len(lines), new)
        if not end:
            lines.append("1;  # ensure a defined return")
    return "\n".join(lines) + "\n"


def check_settings(postfix, amavis):
    errs = []
    for k, v in (postfix or {}).items():
        if k not in POSTFIX_KEYS:
            errs.append("Postfix : %s non modifiable depuis le hub" % k)
        elif not re.match(POSTFIX_KEYS[k][0], str(v)):
            errs.append("Postfix : valeur refusée pour %s" % k)
    for k, v in (amavis or {}).items():
        if k not in AMAVIS_KEYS:
            errs.append("Amavis : %s non modifiable depuis le hub" % k)
        elif not re.match(AMAVIS_KEYS[k][0], str(v)):
            errs.append("Amavis : valeur refusée pour %s" % k)
    return errs


# ------------------------------------------------------------------ exécution (hôte)

def amavis_files(dirs):
    files = []
    for d in dirs:
        if os.path.isdir(d):
            for f in sorted(os.listdir(d)):
                p = os.path.join(d, f)
                if os.path.isfile(p) and not f.startswith(".") and ".si-bak-" not in f and not f.endswith(("~", ".dpkg-old", ".dpkg-dist")):
                    files.append(p)
            if files:
                return files
        elif os.path.isfile(d + ".conf"):
            return [d + ".conf"]
    return files


def _read(p):
    try:
        with open(p, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


def _write(p, text):
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(text)


def _err(code, out, err, what):
    return "%s : %s" % (what, ((err or out or "").strip().splitlines() or ["code %s" % code])[-1][:300])


def run_admin(action, params, now, runner, log_lines=None, parse_time=None, amavis_dirs=("/etc/amavis/conf.d",), postgrey_files=POSTGREY_FILES):
    if action == "queue_list":
        code, out, err = runner(["postqueue", "-j"], timeout=120)
        if code != 0:
            return {"ok": False, "error": _err(code, out, err, "postqueue -j")}
        items = parse_postqueue_json(out)
        q = str(params.get("queue") or "")
        shown = [i for i in items if not q or i["queue"] == q]
        dom = str(params.get("domain") or "").lower()
        if dom:
            shown = [i for i in shown if any(domain_of(r["address"]) == dom for r in i["recipients"])]
        limit = max(1, min(500, int(params.get("limit") or 200)))
        return {"ok": True, "summary": queue_summary(items, now), "rows": sorted(shown, key=lambda i: i["arrival"] or 0)[:limit], "total": len(shown)}
    if action == "queue_action":
        op = str(params.get("op") or "")
        ids = params.get("ids") or ([params["id"]] if params.get("id") else [])
        argvs, err = queue_argv(op, ids)
        if err:
            return {"ok": False, "error": err}
        outs = []
        for argv in argvs:
            stdin = ("\n".join(ids) + "\n").encode() if argv[-1] == "-" else None
            code, out, e = runner(argv, timeout=300, stdin=stdin)
            if code != 0:
                return {"ok": False, "error": _err(code, out, e, " ".join(argv[:2])), "done": outs}
            outs.append((out + e).strip()[-300:])
        return {"ok": True, "op": op, "count": len(ids) if op != "flush" else None, "output": " | ".join(o for o in outs if o)[:600]}
    if action == "delivery_failures":
        hours = max(1, min(24 * 14, int(params.get("hours") or 24)))
        return dict(delivery_failures(log_lines(hours), now, hours, parse_time), ok=True)
    if action in ("lists", "list_set"):
        code, out, err = runner(["postconf"], timeout=60)
        if code != 0:
            return {"ok": False, "error": _err(code, out, err, "postconf")}
        disc = discover(parse_postconf(out))
        if action == "lists":
            for m in disc["maps"]:
                text = _read(m["path"])
                m.update(readable=text is not None, editable=m["type"] in EDITABLE_TYPES, entries=parse_map(text)[:2000] if text is not None else [])
            disc["postgrey"] = [{"path": p, "editable": p.endswith(".local"), "entries": parse_postgrey(_read(p))[:2000]} for p in postgrey_files if _read(p) is not None]
            return dict(disc, ok=True)
        path, key = str(params.get("path") or ""), str(params.get("key") or "").strip()
        value = None if params.get("remove") else str(params.get("value") or "").strip()
        m = next((x for x in disc["maps"] if x["path"] == path), None)
        if m is None and path in postgrey_files and path.endswith(".local"):
            m = {"type": "postgrey", "path": path}
        if m is None:
            return {"ok": False, "error": "table inconnue de la configuration Postfix / postgrey : %s" % path}
        err = check_entry(m, key, value if m["type"] != "postgrey" else None)
        if err:
            return {"ok": False, "error": err}
        text, bak = _read(path), None
        if text is None:
            if value is None:
                return {"ok": False, "error": "%s absent" % path}
            text = ""
        else:
            bak = backup(path, now)
        _write(path, set_entry(text, key, value if m["type"] != "postgrey" else ("" if value is not None else None), sep=" " if m["type"] != "postgrey" else ""))
        steps = []
        if m["type"] in ("hash", "lmdb", "btree"):
            steps.append(["postmap", "%s:%s" % (m["type"], path)])
        steps.append(["systemctl", "reload", "postgrey"] if m["type"] == "postgrey" else ["postfix", "reload"])
        for argv in steps:
            code, out, e = runner(argv, timeout=120)
            if code != 0:
                if text:
                    _write(path, text)
                    if argv[0] != "postmap" and m["type"] in ("hash", "lmdb", "btree"):
                        runner(["postmap", "%s:%s" % (m["type"], path)], timeout=120)
                return {"ok": False, "error": _err(code, out, e, " ".join(argv)) + " -- état antérieur rétabli"}
        return {"ok": True, "path": path, "key": key, "value": value, "removed": value is None, "backup": bak,
                "entries": (parse_postgrey if m["type"] == "postgrey" else parse_map)(_read(path))[:2000]}
    if action == "settings_get":
        code, out, err = runner(["postconf"] + list(POSTFIX_KEYS), timeout=60)
        pf = parse_postconf(out) if code == 0 else {}
        am = amavis_values([(p, _read(p)) for p in amavis_files(amavis_dirs)])
        return {"ok": True, "postfix": [{"key": k, "value": pf.get(k), "label": POSTFIX_KEYS[k][1]} for k in POSTFIX_KEYS],
                "amavis": [{"key": k, "value": (am.get(k) or {}).get("value"), "file": (am.get(k) or {}).get("file"), "label": AMAVIS_KEYS[k][1]} for k in AMAVIS_KEYS],
                "postconf_error": None if code == 0 else _err(code, out, err, "postconf")}
    if action == "settings_set":
        pf, am = dict(params.get("postfix") or {}), dict(params.get("amavis") or {})
        errs = check_settings(pf, am)
        if errs or not (pf or am):
            return {"ok": False, "error": " ; ".join(errs) or "aucun réglage"}
        done = []
        if pf:
            code, out, e = runner(["postconf", "-h", "config_directory"], timeout=30)
            main_cf = os.path.join(out.strip() or "/etc/postfix", "main.cf")
            old = _read(main_cf)
            if old is None:
                return {"ok": False, "error": "main.cf illisible"}
            bak = backup(main_cf, now)
            for argv in [["postconf", "-e"] + ["%s=%s" % (k, v) for k, v in pf.items()], ["postfix", "check"], ["postfix", "reload"]]:
                code, out, e = runner(argv, timeout=120)
                if code != 0:
                    _write(main_cf, old); runner(["postfix", "reload"], timeout=120)
                    return {"ok": False, "error": _err(code, out, e, " ".join(argv[:2])) + " -- main.cf rétabli"}
            done.append({"postfix": pf, "backup": bak})
        if am:
            files = amavis_files(amavis_dirs)
            target = next((p for p in files if os.path.basename(p) == "50-user"), files[-1] if files else None)
            if not target:
                return {"ok": False, "error": "configuration Amavis introuvable", "done": done}
            old = _read(target) or ""
            bak = backup(target, now)
            text = old
            for k, v in am.items():
                text = set_amavis_var(text, k, v)
            _write(target, text)
            code, out, e = runner(["systemctl", "restart", "amavis"], timeout=180)
            code2, out2, e2 = runner(["systemctl", "is-active", "amavis"], timeout=30)
            if code != 0 or out2.strip() != "active":
                _write(target, old); runner(["systemctl", "restart", "amavis"], timeout=180)
                return {"ok": False, "error": _err(code or code2, out or out2, e or e2, "redémarrage d'Amavis") + " -- configuration rétablie", "done": done}
            done.append({"amavis": am, "file": target, "backup": bak})
        return {"ok": True, "done": done}
    return None
