# -*- coding: utf-8 -*-
"""Banc d'installation des agents sur un pool de VM (livraison #825, BACKLOG 133).

Un pool = un nœud Proxmox (son agent), une plage de vmid réservée aux clones, des modèles de VM (Debian, Ubuntu, Rocky,
Windows 10/11, Windows Server…) avec l'agent invité QEMU, et, par OS, les commandes d'installation / vérification /
désinstallation à jouer dans l'invité (ligne d'installation affichée par le hub ou le central local, MSI…).
Un passage (run) sur un modèle : cloner (clone lié « banc-<modèle>-<n> ») -> démarrer -> attendre l'agent invité ->
installer -> vérifier -> désinstaller -> arrêter -> détruire. Un échec saute au nettoyage (arrêter, détruire) : aucune
VM de banc ne reste. Chaque étape est une commande `vm_action` à l'agent du nœud ; le central avance les passages
toutes les 30 s. L'exécution dans l'invité est refusée par l'agent du nœud si la VM ne s'appelle pas « banc-… ».
Pur et testé : valider_pool, masquer, vmid_libre, nouveau_run, params_etape, avancer."""
import re

try:   # #826 : recettes des modèles de VM (copie de si_agent/bancmod.py dans l'image, source unique)
    import si_agent_bancmod as bancmod
except ImportError:   # tests : dépôt
    import os
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agent"))
    from si_agent import bancmod

ETAPES = ["cloner", "demarrer", "attendre_invite", "installer", "verifier", "desinstaller", "arreter", "detruire"]
NETTOYAGE = ETAPES.index("arreter")
LIBELLES = {"cloner": "cloner le modèle", "demarrer": "démarrer", "attendre_invite": "attendre l'agent invité", "installer": "installer l'agent",
            "verifier": "vérifier", "desinstaller": "désinstaller", "arreter": "arrêter", "detruire": "détruire le clone"}
DELAIS = {"cloner": 1800, "attendre_invite": 900, "installer": 1800, "verifier": 600, "desinstaller": 900, "detruire": 900}
DEFAUT_DELAI = 600
VERIFIER = {"linux": "systemctl is-active si-agent || docker ps --filter name=si-agent --format '{{.Status}}' | grep -q Up",
            "windows": "if ((Get-ScheduledTask -TaskName si-agent).State -ne 'Running') { exit 1 }"}
DESINSTALLER = {"linux": "", "windows": "& \"$env:ProgramFiles\\si-agent\\uninstall.ps1\""}
_NOM = re.compile(r"^[a-z0-9][a-z0-9-]{0,30}$")
_AGENT = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_SECRET = re.compile(r"(?i)(token=|-EnrollToken\s+[\"']?|TOKEN=|secret=|-Secret\s+[\"']?)([^\s\"'&]+)")


def valider_pool(b):
    b = b or {}
    noeud = str(b.get("noeud") or "")
    if not _AGENT.match(noeud):
        return None, "noeud : identifiant de l'agent du nœud Proxmox"
    try:
        lo, hi = int(b.get("vmid_min")), int(b.get("vmid_max"))
    except (TypeError, ValueError):
        return None, "vmid_min / vmid_max entiers"
    if not (100 <= lo <= hi <= 999999999) or hi - lo > 500:
        return None, "plage de vmid invalide (100 ≤ min ≤ max, 500 au plus)"
    modeles = []
    for m in b.get("modeles") or []:
        nom, os_ = str((m or {}).get("nom") or ""), str((m or {}).get("os") or "")
        if not _NOM.match(nom):
            return None, "modèle : nom en minuscules, chiffres, tirets (31 max) : %r" % nom
        if os_ not in ("linux", "windows"):
            return None, "modèle %s : os linux ou windows" % nom
        try:
            vmid = int(m.get("vmid"))
        except (TypeError, ValueError):
            return None, "modèle %s : vmid entier" % nom
        if lo <= vmid <= hi:
            return None, "modèle %s : son vmid est dans la plage des clones" % nom
        modeles.append({"nom": nom, "os": os_, "vmid": vmid})
    if not modeles:
        return None, "au moins un modèle"
    if len({m["nom"] for m in modeles}) != len(modeles):
        return None, "noms de modèles en double"
    cmds = {}
    for os_ in ("linux", "windows"):
        c = (b.get("commandes") or {}).get(os_) or {}
        cmds[os_] = {"installer": str(c.get("installer") or "")[:3000], "verifier": str(c.get("verifier") or VERIFIER[os_])[:2000],
                     "desinstaller": str(c.get("desinstaller") if c.get("desinstaller") is not None else DESINSTALLER[os_])[:2000]}
    for m in modeles:
        if not cmds[m["os"]]["installer"]:
            return None, "commande d'installation %s absente (modèle %s)" % (m["os"], m["nom"])
    stockage = str(b.get("stockage") or "")
    if stockage and not re.match(r"^[A-Za-z][A-Za-z0-9_.-]{0,62}$", stockage):
        return None, "stockage invalide"
    return {"noeud": noeud, "vmid_min": lo, "vmid_max": hi, "stockage": stockage, "modeles": modeles, "commandes": cmds,
            "complet": bool(b.get("complet"))}, None


def masquer(texte):
    """Jetons et secrets d'une ligne de commande -> « ••• »."""
    return _SECRET.sub(lambda m: m.group(1) + "•••", texte or "")


def pool_public(pool):
    if not pool:
        return None
    p = dict(pool, commandes={o: {k: masquer(v) for k, v in c.items()} for o, c in (pool.get("commandes") or {}).items()})
    return p


def vmid_libre(pool, utilises):
    for v in range(pool["vmid_min"], pool["vmid_max"] + 1):
        if v not in utilises:
            return v
    return None


def nouveau_run(pool, modele, rid, utilises, maintenant):
    newid = vmid_libre(pool, utilises)
    if newid is None:
        return None, "plage de vmid épuisée"
    return {"id": rid, "modele": modele["nom"], "os": modele["os"], "vmid_modele": modele["vmid"], "vmid": newid,
            "nom": "banc-%s-%d" % (modele["nom"], rid), "debut": maintenant, "fin": None, "etape": 0, "echec": None,
            "etapes": [{"id": e, "etat": "attente", "commande": None, "debut": None, "fin": None, "detail": None, "essais": 0} for e in ETAPES]}, None


def _argv(os_, cmd):
    if os_ == "windows":
        return ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", cmd]
    return ["sh", "-c", cmd]


def params_etape(run, pool):
    """Paramètres `vm_action` de l'étape courante ; None = étape sans geste (sautée)."""
    e = ETAPES[run["etape"]]
    v = run["vmid"]
    if e == "cloner":
        p = {"vmid": run["vmid_modele"], "action": "clone", "newid": v, "name": run["nom"], "full": bool(pool.get("complet"))}
        if pool.get("stockage"):
            p["storage"] = pool["stockage"]
        return p
    if e == "demarrer":
        return {"vmid": v, "action": "start"}
    if e == "attendre_invite":
        return {"vmid": v, "action": "guest_ping"}
    if e in ("installer", "verifier", "desinstaller"):
        cmd = ((pool.get("commandes") or {}).get(run["os"]) or {}).get(e) or ""
        if not cmd:
            return None
        return {"vmid": v, "action": "guest_exec", "argv": _argv(run["os"], cmd), "timeout": min(1800, DELAIS.get(e, DEFAUT_DELAI))}
    if e == "arreter":
        return {"vmid": v, "action": "stop"}
    if e == "detruire":
        return {"vmid": v, "action": "destroy", "confirm": str(v)}
    return None


def _ok(c):
    r = (c or {}).get("result") or {}
    return (c or {}).get("status") == "done" and r.get("ok", True) is not False


def _err(c):
    r = (c or {}).get("result") or {}
    return str(r.get("error") or (c or {}).get("error") or (c or {}).get("status") or "?")[:400]


def avancer(run, commande, maintenant):
    """Fait progresser un passage d'après l'état de la commande de l'étape courante (None : rien d'envoyé encore).
    -> (run, geste) ; geste = "envoyer" (le central envoie params_etape), "sauter" (étape sans geste) ou None."""
    if run.get("fin"):
        return run, None
    i = run["etape"]
    st = run["etapes"][i]
    nom = ETAPES[i]
    if st["commande"] is None:
        st["etat"], st["debut"] = "en_cours", maintenant if st["debut"] is None else st["debut"]
        return run, "envoyer"
    if commande is None or commande.get("status") in ("pending", "sent", "acked"):
        if maintenant - (maintenant if st["debut"] is None else st["debut"]) > DELAIS.get(nom, DEFAUT_DELAI):
            return _echouer(run, "délai dépassé (%d s)" % DELAIS.get(nom, DEFAUT_DELAI), maintenant)
        return run, None
    if _ok(commande):
        st["etat"], st["fin"] = "fait", maintenant
        ex = ((commande.get("result") or {}).get("result") or {}).get("exec") or {}
        st["detail"] = (ex.get("out") or "")[-300:] or None
        return _suivante(run, maintenant)
    # échec de la commande
    if nom == "attendre_invite" and maintenant - (maintenant if st["debut"] is None else st["debut"]) < DELAIS["attendre_invite"]:
        st["commande"], st["essais"] = None, st["essais"] + 1     # l'invité démarre encore : on redemande
        return run, None
    if nom in ("arreter", "detruire"):
        st["etat"], st["fin"], st["detail"] = "echec", maintenant, _err(commande)
        if nom == "arreter":                                         # VM déjà arrêtée ou absente : on détruit quand même
            return _suivante(run, maintenant)
        run["fin"] = maintenant
        run["echec"] = run["echec"] or "nettoyage : %s" % _err(commande)
        return run, None
    return _echouer(run, _err(commande), maintenant)


def _suivante(run, maintenant):
    run["etape"] += 1
    if run["etape"] >= len(ETAPES):
        run["fin"] = maintenant
        return run, None
    return run, None


def _echouer(run, err, maintenant):
    i = run["etape"]
    st = run["etapes"][i]
    st["etat"], st["fin"], st["detail"] = "echec", maintenant, err
    run["echec"] = run["echec"] or "%s : %s" % (LIBELLES.get(ETAPES[i], ETAPES[i]), err)
    if i >= NETTOYAGE:
        run["fin"] = maintenant
        return run, None
    if i == 0:                                                      # rien n'a été cloné : rien à nettoyer
        for x in run["etapes"][1:]:
            x["etat"] = "saute"
        run["fin"] = maintenant
        return run, None
    for x in run["etapes"][i + 1:NETTOYAGE]:
        x["etat"] = "saute"
    run["etape"] = NETTOYAGE
    return run, None


def sauter(run, maintenant):
    st = run["etapes"][run["etape"]]
    st["etat"], st["fin"], st["detail"] = "saute", maintenant, "aucune commande pour cet OS"
    return _suivante(run, maintenant)


def resultat(run):
    if not run.get("fin"):
        return "en cours (%s)" % LIBELLES.get(ETAPES[min(run["etape"], len(ETAPES) - 1)])
    return "échec — %s" % run["echec"] if run.get("echec") else "réussi"


def recettes():
    return [{"id": k, "titre": v["titre"], "os": v["os"], "url": v["url"]} for k, v in sorted(bancmod.RECETTES.items())]


def modeles_du_noeud(vms):
    """Modèles (« template ») vus par la sonde proxmox du nœud -> [{vmid, nom, os, recette}]."""
    out = []
    for v in vms or []:
        if not v.get("template"):
            continue
        nom = str(v.get("name") or "")
        rec = nom[len("banc-modele-"):] if nom.startswith("banc-modele-") else None
        os_ = (bancmod.RECETTES.get(rec) or {}).get("os") or ("windows" if re.search(r"(?i)win", nom) else "linux")
        out.append({"vmid": v.get("vmid"), "nom": nom, "os": os_, "recette": rec, "type": v.get("type")})
    return sorted(out, key=lambda x: x["vmid"] or 0)
