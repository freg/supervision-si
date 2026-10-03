# -*- coding: utf-8 -*-
"""#656 : bascule de rôle par keepalived (VRRP) -- commande `vrrp_set` du central : {instance, priority}.
L'agent modifie la ligne `priority N` de l'instance VRRP désignée dans /etc/keepalived/keepalived.conf (copie de
sauvegarde horodatée à côté), vérifie la configuration (`keepalived -t`) puis recharge le service. Le candidat
qui doit répondre reçoit la priorité haute, les autres la basse : le VIP suit. Fonctions pures testées :
`rewrite_priority(text, instance, priority)` ; l'exécution passe par `run`."""
import re, time, pathlib

CONF = "/etc/keepalived/keepalived.conf"
INST_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")

def rewrite_priority(text, instance, priority):
    """-> (nouveau texte, trouvé). Ne touche que le bloc `vrrp_instance <instance> { … }`."""
    m = re.search(r"(vrrp_instance\s+%s\s*\{)(.*?)(\n\})" % re.escape(instance), text, re.S)
    if not m: return text, False
    body = m.group(2)
    if re.search(r"^\s*priority\s+\d+", body, re.M): body2 = re.sub(r"^(\s*priority\s+)\d+", lambda x: x.group(1) + str(priority), body, count=1, flags=re.M)
    else: body2 = body + "\n    priority %d" % priority
    return text[:m.start(2)] + body2 + text[m.end(2):], True

def run(cmd, params, conf=CONF, read=None, write=None):
    inst = str(params.get("instance") or ""); 
    try: prio = int(params.get("priority"))
    except (TypeError, ValueError): return {"ok": False, "error": "priority entier requis"}
    if not INST_RE.match(inst): return {"ok": False, "error": "instance VRRP invalide"}
    if not 1 <= prio <= 254: return {"ok": False, "error": "priority entre 1 et 254"}
    p = pathlib.Path(conf)
    try: text = read(p) if read else p.read_text(encoding="utf-8")
    except OSError as e: return {"ok": False, "error": "keepalived.conf illisible : %s" % e}
    new, found = rewrite_priority(text, inst, prio)
    if not found: return {"ok": False, "error": "instance VRRP « %s » absente de keepalived.conf" % inst}
    backup = str(p) + ".bak-" + time.strftime("%Y%m%d%H%M%S")
    try:
        (write or (lambda path, t: pathlib.Path(path).write_text(t, encoding="utf-8")))(backup, text)
        (write or (lambda path, t: pathlib.Path(path).write_text(t, encoding="utf-8")))(str(p), new)
    except OSError as e: return {"ok": False, "error": "écriture : %s" % e}
    r = cmd(["keepalived", "-t", "-f", str(p)], timeout=20)
    if getattr(r, "returncode", 1) != 0:
        (write or (lambda path, t: pathlib.Path(path).write_text(t, encoding="utf-8")))(str(p), text)
        return {"ok": False, "error": "configuration refusée par keepalived -t, ancienne configuration restaurée : %s" % ((r.stderr or r.stdout or "").strip()[-200:])}
    r = cmd(["systemctl", "reload", "keepalived"], timeout=30)
    if getattr(r, "returncode", 1) != 0: return {"ok": False, "error": "rechargement keepalived : %s" % ((r.stderr or r.stdout or "").strip()[-200:])}
    return {"ok": True, "result": {"instance": inst, "priority": prio, "backup": backup}}
