# -*- coding: utf-8 -*-
"""Questions sur le hub (#715) -- « micro-IA » qui répond aux questions pratiques sur le hub et ses API
en interrogeant les API elles-mêmes, SANS modèle de langage (réponse en quelques secondes, même sur CPU) :

  « où trouver le dernier redémarrage du pc XXX ? »          -> agents hôtes (si-agent) : dernier démarrage + lien
  « l'ip 192.0.2.10 est-elle visible quelque part ? »        -> balayage des API sources (adresse exacte ou sous-réseau)
  « quelle API donne les zones DNS ? »                        -> index des routes Flask du dépôt (construit dans l'image)
  « où sont les onduleurs ? »                                 -> catalogue des vues du hub (hubThemes.js), lien ?view=

Le reste part, sur demande, au RAG + modèle existant (/ask). Logique pure (détection, recherche dans un
JSON, appariement de noms, mise en forme) séparée des appels HTTP (fonction `fetch` injectable)."""
import concurrent.futures
import datetime as dt
import ipaddress
import json
import os
import re
import unicodedata
import urllib.request

try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo(os.environ.get("TZ") or "Europe/Paris")
except Exception:  # pragma: no cover - tzdata absent
    TZ = dt.timezone.utc

IPV4 = re.compile(r"(?<![\d.])((?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3})(?!\.?\d)")
CIDR = re.compile(r"(?<![\d.])((?:\d{1,3}\.){3}\d{1,3}/\d{1,2})(?!\d)")
MAC = re.compile(r"(?<![0-9A-Fa-f:-])([0-9A-Fa-f]{2}(?:[:-][0-9A-Fa-f]{2}){5})(?![0-9A-Fa-f:-])")
BOOT_WORDS = ("redemarr", "reboot", "demarr", "boot", "uptime", "allume", "eteint", "relanc")
STOP = {"le", "la", "les", "de", "du", "des", "un", "une", "est", "ou", "pc", "poste", "machine", "serveur", "hote", "sous",
        "dans", "hub", "quel", "quelle", "quels", "trouver", "dernier", "derniere", "windows", "linux", "mac", "sur", "pour",
        "qui", "que", "elle", "il", "api", "route", "vue", "page", "tuile", "menu", "comment", "the", "a", "et", "en", "au"}
LABEL_KEYS = ("hostname", "label", "name", "agent_id", "site_name", "site", "title", "router", "device", "zone", "description",
              "comment", "mac", "ip", "address", "host")


def norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^a-z0-9@._:/-]+", " ", s).split())


def words(s):
    return [w for w in re.split(r"[\s._:/-]+", norm(s)) if len(w) >= 2 and w not in STOP]


# ------------------------------------------------------------------ détection
def detect(question):
    """-> {intent: locate|boot|api|where|other, ips, macs}"""
    q = norm(question)
    ips = IPV4.findall(question or "")
    macs = sorted({m.lower().replace("-", ":") for m in MAC.findall(question or "")})
    if ips or macs:
        return {"intent": "locate", "ips": ips, "macs": macs}
    if re.search(r"\b(sauvegard\w*|backups?|snapshots?|instantanes?|vzdump|pbs)\b", q):   # #726 (avant « boot » : « backup »)
        return {"intent": "backup", "snapshot": bool(re.search(r"\b(snapshots?|instantanes?)\b", q)),
                "vmids": [int(x) for x in re.findall(r"\b(\d{3,6})\b", q)]}
    if any(w in q for w in BOOT_WORDS):
        return {"intent": "boot"}
    if re.search(r"\b(api|apis|route|routes|endpoint|endpoints)\b", q):
        return {"intent": "api"}
    if re.search(r"\b(ou|trouver|tuile|menu|vue|ecran|page|onglet|acceder)\b", q):
        return {"intent": "where"}
    return {"intent": "other"}


# ------------------------------------------------------------------ recherche dans un JSON
def _context(d):
    if not isinstance(d, dict):
        return ""
    parts = []
    for k in LABEL_KEYS:
        v = d.get(k)
        if isinstance(v, (str, int, float)) and str(v).strip() and len(str(v)) <= 120:
            parts.append("%s=%s" % (k, v))
        if len(parts) >= 4:
            break
    return ", ".join(parts)


def find_in_json(doc, ips=(), macs=(), limit=8):
    """Occurrences d'adresses dans un document JSON : valeur exacte (IP, MAC sous toutes ses écritures) ou
    sous-réseau CIDR contenant l'IP. -> [{needle, how, path, value, context}] (une par objet englobant)."""
    pats = [(ip, "ip", re.compile(r"(?<![\d.])%s(?!\.?\d)" % re.escape(ip))) for ip in ips]
    pats += [(m, "mac", re.compile(r"(?<![0-9a-f])%s(?![0-9a-f])" % re.escape(m))) for m in macs]
    objs = []
    for ip in ips:
        try:
            objs.append((ip, ipaddress.ip_address(ip)))
        except ValueError:
            pass
    hits, seen = [], set()

    def add(needle, how, path, value, ctx):
        key = (needle, id(ctx) if isinstance(ctx, dict) else path)
        if key in seen or len(hits) >= limit:
            return
        seen.add(key)
        hits.append({"needle": needle, "how": how, "path": path, "value": str(value)[:160], "context": _context(ctx)})

    def walk(node, path, ctx):
        if len(hits) >= limit:
            return
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, path + "." + str(k) if path else str(k), node)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, "%s[%d]" % (path, i), ctx)
        elif isinstance(node, str):
            low = node.lower()
            for needle, kind, pat in pats:
                hay = low.replace("-", ":") if kind == "mac" else node
                if pat.search(hay):
                    add(needle, "exacte", path, node, ctx)
            for ip, obj in objs:
                for c in CIDR.findall(node):
                    try:
                        net = ipaddress.ip_network(c, strict=False)
                    except ValueError:
                        continue
                    if net.prefixlen >= 8 and obj in net and str(net.network_address) != ip:
                        add(ip, "sous-réseau %s" % c, path, node, ctx)
    walk(doc, "", None)
    return hits


# ------------------------------------------------------------------ sources
def env_url(name, default):
    return (os.environ.get(name) or default).rstrip("/")


def default_sources():
    sa = env_url("SI_AGENT_API_URL", "http://si-agent-api:5000")
    return [
        {"id": "si-agent-fleet", "label": "Agents hôtes", "url": sa + "/fleet", "view": "si-agent"},
        {"id": "si-agent-windows", "label": "Postes Windows vus par les sondes des agents", "url": sa + "/windows-hosts", "view": "si-agent"},
        {"id": "si-agent-netview", "label": "Vue réseau passive des agents", "url": sa + "/netview", "view": "si-agent"},
        {"id": "si-agent-proxmox", "label": "Hyperviseurs Proxmox (agents)", "url": sa + "/proxmox", "view": "proxmox"},
        {"id": "ipam", "label": "IPAM", "url": env_url("IPAM_API_URL", "http://ipam-api:5000") + "/ip_list", "view": "external-bases"},
        {"id": "network-agent", "label": "Exploration réseau (appareils)", "url": env_url("NETWORK_AGENT_API_URL", "http://network-agent-api:5000") + "/devices", "view": "network-agent"},
        {"id": "network-equipment", "label": "Équipements réseau", "url": env_url("NETWORK_EQUIPMENT_API_URL", "http://network-equipment-api:5000") + "/equipment", "view": "network-equipment"},
        {"id": "nebula-devices", "label": "Nebula (équipements)", "url": env_url("NEBULA_API_URL", "http://nebula-api:5000") + "/imported/devices", "view": "nebula"},
        {"id": "nebula-clients", "label": "Nebula (clients Wi-Fi)", "url": env_url("NEBULA_API_URL", "http://nebula-api:5000") + "/imported/clients", "view": "nebula"},
        {"id": "mikrotik", "label": "Routeurs MikroTik", "url": env_url("MIKROTIK_API_URL", "http://mikrotik-api:5000") + "/mikrotik/routers", "front": "mikrotik"},
        {"id": "mikrotik-nat", "label": "Redirections NAT", "url": env_url("MIKROTIK_API_URL", "http://mikrotik-api:5000") + "/mikrotik/nat-map", "view": "nat-map"},
        {"id": "cisco", "label": "Équipements Cisco", "url": env_url("CISCO_API_URL", "http://cisco-api:5000") + "/cisco/switches", "front": "cisco"},
        {"id": "netprobe", "label": "Sondes réseau (cibles)", "url": env_url("NETPROBE_API_URL", "http://netprobe-api:5000") + "/targets", "view": "netprobe"},
        {"id": "dns", "label": "Zones DNS", "url": env_url("DNS_API_URL", "http://dns-api:5000") + "/zones", "view": "synthese"},
    ]


def load_sources(override_path=None):
    """Sources par défaut, complétées/remplacées par identifiant depuis un JSON local (liste d'objets
    {id, label, url, view|front} ; `"disabled": true` pour en retirer une)."""
    by_id = {s["id"]: s for s in default_sources()}
    if override_path and os.path.isfile(override_path):
        try:
            for s in json.load(open(override_path, encoding="utf-8")):
                if isinstance(s, dict) and s.get("id"):
                    by_id[s["id"]] = dict(by_id.get(s["id"], {}), **s)
        except (OSError, ValueError):
            pass
    return [s for s in by_id.values() if s.get("url") and not s.get("disabled")]


def fetch_json(url, timeout=6, max_bytes=20_000_000):
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError("réponse trop volumineuse")
    return json.loads(data.decode("utf-8", "replace"))


def link(hub_url, src):
    if src.get("view"):
        return "%s?view=%s" % (hub_url, src["view"])
    return None


# ------------------------------------------------------------------ « où est cette adresse ? »
def locate(ips, macs, sources, fetch=fetch_json, hub_url="/"):
    found, absent, errors = [], [], []

    def one(src):
        try:
            return src, find_in_json(fetch(src["url"]), ips, macs), None
        except Exception as e:  # source arrêtée, protégée, profil compose absent…
            return src, None, str(e)[:160]
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        for src, hits, err in ex.map(one, sources):
            if err is not None:
                errors.append({"source": src["label"], "error": err})
            elif hits:
                found.append({"source": src["label"], "link": link(hub_url, src), "front": src.get("front"), "hits": hits})
            else:
                absent.append(src["label"])
    return {"found": found, "absent": absent, "errors": errors}


def format_locate(needles, res):
    what = ", ".join(needles)
    if not res["found"]:
        lines = ["%s n'apparaît dans aucune des %d sources consultées." % (what, len(res["absent"]))]
    else:
        lines = ["%s apparaît dans %d source(s) :" % (what, len(res["found"]))]
        for f in res["found"]:
            where = f["link"] or ("tuile %s" % f["front"] if f.get("front") else "")
            lines.append("• %s%s" % (f["source"], " → " + where if where else ""))
            for h in f["hits"][:4]:
                lines.append("    - %s%s (%s, champ %s)" % (h["context"] or h["value"], "" if h["how"] == "exacte" else " — " + h["how"], h["needle"], h["path"]))
    if res["absent"] and res["found"]:
        lines.append("Absente de : %s." % ", ".join(res["absent"]))
    if res["errors"]:
        lines.append("Non consultées (service arrêté ou protégé) : %s." % ", ".join(e["source"] for e in res["errors"]))
    return "\n".join(lines)


# ------------------------------------------------------------------ dernier démarrage
def match_hosts(question, agents):
    """Agents dont le nom (agent_id, hostname, libellé) figure dans la question ; meilleurs d'abord."""
    q = norm(question)
    toks = set(words(question))
    scored = []
    for a in agents:
        best = 0
        for n in {norm(a.get(k)) for k in ("agent_id", "hostname", "label") if a.get(k)}:
            if len(n) >= 3 and re.search(r"(?<![a-z0-9])%s(?![a-z0-9])" % re.escape(n), q):
                best = max(best, 100 + len(n))
            else:
                common = [p for p in words(n) if len(p) >= 3 and p in toks]
                best = max(best, sum(len(p) for p in common))
        if best:
            scored.append((best, a))
    scored.sort(key=lambda x: -x[0])
    return [a for s, a in scored if s >= scored[0][0] * 0.8][:5] if scored else []


def parse_iso(s):
    if not s:
        return None
    try:
        d = dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def boot_info(agent, latest=None):
    """Dernier démarrage : champ `system.last_boot` de la dernière mesure host (Windows) sinon relevé - uptime."""
    summ = agent.get("summary") or {}
    system = ((((latest or {}).get("host") or {}).get("data") or {}).get("system") or {}) if latest else {}
    measured = parse_iso(summ.get("host_at") or ((latest or {}).get("host") or {}).get("at"))
    up = system.get("uptime_seconds", summ.get("uptime_seconds"))
    boot, how = parse_iso(system.get("last_boot")), "mesure"
    if not boot and measured and isinstance(up, (int, float)):
        boot, how = measured - dt.timedelta(seconds=up), "relevé moins durée de fonctionnement"
    return {"agent_id": agent.get("agent_id"), "hostname": agent.get("hostname"), "label": agent.get("label"), "site": agent.get("site"),
            "os": agent.get("os"), "online": agent.get("online"), "last_boot": boot.isoformat() if boot else None, "how": how if boot else None,
            "uptime_seconds": up, "measured_at": measured.isoformat() if measured else None,
            "reboot_required": system.get("reboot_required")}


def _fmt_dt(s):
    d = parse_iso(s)
    return d.astimezone(TZ).strftime("%d/%m/%Y %H:%M") if d else "?"


def _fmt_age(seconds):
    if not isinstance(seconds, (int, float)):
        return ""
    j, r = divmod(int(seconds), 86400)
    return "%d j %d h" % (j, r // 3600) if j else "%d h %02d min" % (r // 3600, (r % 3600) // 60)


def format_boot(infos, hub_url="/", unmatched_names=None):
    if not infos:
        names = ", ".join(unmatched_names[:12]) if unmatched_names else "aucun agent enregistré"
        return ("Aucun agent hôte ne correspond au nom cité. Le dernier démarrage d'un poste se lit dans Agents hôtes "
                "(%s?view=si-agent), fiche de l'agent, bloc Système (« dernier démarrage », durée de fonctionnement) -- "
                "à condition qu'un agent y soit installé. Agents connus : %s." % (hub_url, names))
    out = []
    for i in infos:
        name = i["hostname"] or i["label"] or i["agent_id"]
        head = "%s (agent %s, site %s%s)" % (name, i["agent_id"], i["site"] or "?", ", " + i["os"] if i.get("os") else "")
        if i["last_boot"]:
            out.append("%s : dernier démarrage le %s (en marche depuis %s), relevé du %s%s." % (
                head, _fmt_dt(i["last_boot"]), _fmt_age(i["uptime_seconds"]), _fmt_dt(i["measured_at"]),
                " -- redémarrage requis (mises à jour)" if i.get("reboot_required") else ""))
        else:
            out.append("%s : pas encore de mesure « host » (agent %s)." % (head, i.get("online") or "?"))
    out.append("Détail : Agents hôtes → %s?view=si-agent (fiche de l'agent, bloc Système)." % hub_url)
    return "\n".join(out)


# ------------------------------------------------------------------ catalogue des vues et routes d'API
def _score(q_words, text):
    t = set(words(text))
    return sum(len(w) for w in q_words if w in t or any(x.startswith(w[:5]) for x in t if len(w) >= 5))


def search_catalog(question, catalog, hub_url="/", k=5):
    qw = words(question)
    scored = []
    for e in catalog:
        s = 3 * _score(qw, " ".join([e.get("label", ""), e.get("view") or e.get("front") or ""])) + _score(qw, e.get("theme", "") + " " + e.get("description", ""))
        if s:
            scored.append((s, e))
    scored.sort(key=lambda x: -x[0])
    return [dict(e, link=("%s?view=%s" % (hub_url, e["view"])) if e.get("view") else None) for s, e in scored[:k]]


def format_catalog(hits, hub_url="/"):
    if not hits:
        return "Aucune vue du hub ne correspond ; la liste complète des vues est dans le menu de l'en-tête et l'accueil du hub (%s)." % hub_url
    return "\n".join(["Dans le hub :"] + ["• %s › %s%s" % (h.get("theme", "?"), h["label"], " → " + h["link"] if h.get("link") else " (tuile « %s »)" % h.get("front"))
                                         for h in hits])


def search_routes(question, routes, k=8):
    qw = words(question)
    scored = []
    for r in routes:
        s = _score(qw, " ".join([r.get("module", ""), r.get("path", "").replace("/", " "), r.get("function", "").replace("_", " "), r.get("doc", "")]))
        if s:
            scored.append((s, r))
    scored.sort(key=lambda x: (-x[0], x[1].get("module", ""), x[1].get("path", "")))
    return [r for s, r in scored[:k]]


def format_routes(hits):
    if not hits:
        return "Aucune route d'API ne correspond. Chaque module documente ses routes dans son README (onglet Historique du hub)."
    return "\n".join(["Routes d'API (service interne <module>-api:5000, exposées par la passerelle sous /api/<module>/) :"] +
                     ["• %s %s  [%s]%s" % (r.get("methods", "GET"), r["path"], r["module"], " -- " + r["doc"] if r.get("doc") else "") for r in hits])


# ------------------------------------------------------------------ sauvegardes et snapshots (#726)
def backup_answer(question, rows, vmids=(), snapshot=False, now=None, k=12):
    """Inventaire unifié (/maint/backups, #724) -> lignes correspondant aux CT/VM cités et aux noms (nœud, CT) présents
    dans la question ; la plus récente par (source, nœud, CT/VM, type). -> (lignes, filtre appliqué)."""
    toks = set(words(question))
    sel = [r for r in rows or [] if (not snapshot or r.get("kind") == "snapshot")]
    if vmids:
        sel = [r for r in sel if r.get("vmid") in set(vmids)]
    named = [r for r in sel if toks & (set(words(r.get("node") or "")) | set(words(r.get("name") or "")))]
    if named and not vmids:
        sel = named
    best = {}
    for r in sel:
        key = (r.get("source"), r.get("node"), r.get("vmid"), r.get("name") if r.get("vmid") is None else None, r.get("kind"))
        if key not in best or (r.get("at") or 0) > (best[key].get("at") or 0):
            best[key] = r
    out = sorted(best.values(), key=lambda r: -(r.get("at") or 0))
    return out[:k], {"vmids": list(vmids), "snapshot": snapshot, "named": bool(named), "total": len(out)}


SOURCE_TXT = {"agent": "PVE", "ssh": "PVE distant", "pbs": "PBS", "tirée": "tirée"}


def format_backups(rows, info, hub_url="/", now=None):
    import time as _t
    now = now or _t.time()
    link = "%s?view=pve-maint" % hub_url
    if not rows:
        return ("Aucune %s trouvée%s. L'inventaire complet est dans Maintenance des Proxmox › Sauvegardes (%s)." %
                ("snapshot" if info.get("snapshot") else "sauvegarde ni snapshot", " pour " + ", ".join(map(str, info["vmids"])) if info.get("vmids") else "", link))
    lines = ["%d résultat(s)%s :" % (info["total"], " (les %d plus récents)" % len(rows) if info["total"] > len(rows) else "")]
    for r in rows:
        age = "il y a %d j" % ((now - r["at"]) // 86400) if r.get("at") else ""
        lines.append("• %s %s / %s%s : %s du %s %s%s" % (
            SOURCE_TXT.get(r.get("source"), r.get("source")), r.get("node"), r.get("vmid") if r.get("vmid") is not None else "",
            " (%s)" % r["name"] if r.get("name") else "", r.get("kind"), r.get("at_text") or _fmt_dt(dt.datetime.fromtimestamp(r["at"], dt.timezone.utc).isoformat() if r.get("at") else None),
            age, " — %s" % r["where"] if r.get("where") else ""))
    lines.append("Détail : Maintenance des Proxmox › Sauvegardes → %s" % link)
    return "\n".join(lines)
