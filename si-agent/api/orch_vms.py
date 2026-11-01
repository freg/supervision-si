# -*- coding: utf-8 -*-
"""VM à la demande de la tuile Orchestration (livraison #836) -- le volet « machines » du OpenStack maison.

Une VM = un clone d'un modèle Proxmox (les modèles du nœud vus par sa sonde proxmox, ceux du Banc compris), nommé
« orch-<nom> », dans une plage de vmid réservée (distincte de celle du Banc), réglée (cœurs, mémoire, description
avec l'expiration), démarrée ; durée de vie (TTL) : à l'échéance elle est arrêtée puis détruite. Chaque étape est une
commande `vm_action` à l'agent du nœud ; le central avance les VM toutes les 30 s (même boucle que le Banc). Un échec
pendant la création déclenche le nettoyage (arrêt, destruction) : pas de clone orphelin.
Pur et testé : valider_config, nouvelle_vm, avancer, a_expirer, detruire, resume."""
import re

_NOM = re.compile(r"^[a-z0-9][a-z0-9-]{0,30}$")
_NOEUD = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_STOCKAGE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
DELAI = {"cloner": 1800, "demarrer": 600, "arreter": 300, "detruire": 900}
DEFAUT_DELAI = 600


def valider_config(b):
    b = b or {}
    noeud = str(b.get("noeud") or "")
    if not _NOEUD.match(noeud):
        return None, "noeud : agent du nœud Proxmox"
    try:
        vmin, vmax = int(b.get("vmid_min")), int(b.get("vmid_max"))
    except (TypeError, ValueError):
        return None, "vmid_min / vmid_max entiers"
    if not (100 <= vmin <= vmax <= 999999999) or vmax - vmin > 10000:
        return None, "plage de vmid : 100 ≤ min ≤ max, 10 000 au plus"
    st = str(b.get("stockage") or "")
    if st and not _STOCKAGE.match(st):
        return None, "stockage invalide"
    try:
        ttl = int(b.get("ttl_max_h") or 24 * 30)
    except (TypeError, ValueError):
        return None, "ttl_max_h entier"
    return {"noeud": noeud, "vmid_min": vmin, "vmid_max": vmax, "stockage": st or None, "complet": bool(b.get("complet")),
            "ttl_max_h": max(1, min(ttl, 24 * 365))}, None


def _etape(eid, params):
    return {"id": eid, "params": params, "commande": None, "etat": "attente", "debut": None, "fin": None, "detail": None}


def _destruction(vm):
    v = vm["vmid"]
    return [_etape("arreter", {"vmid": v, "action": "stop"}), _etape("detruire", {"vmid": v, "action": "destroy", "confirm": str(v)})]


def nouvelle_vm(cfg, modele, b, vid, utilises, maintenant):
    """cfg : configuration ; modele : {vmid, nom, os} ; b : {nom, ttl_h, cores, memoire} -> (vm, None) ou (None, erreur)."""
    nom = str(b.get("nom") or "")
    if not _NOM.match(nom):
        return None, "nom : minuscules, chiffres, tirets (31 max)"
    try:
        ttl = int(b.get("ttl_h")) if b.get("ttl_h") not in (None, "") else None
        cores = int(b.get("cores")) if b.get("cores") not in (None, "") else None
        mem = int(b.get("memoire")) if b.get("memoire") not in (None, "") else None
    except (TypeError, ValueError):
        return None, "ttl_h, cores, memoire : entiers"
    if ttl is not None and not 1 <= ttl <= cfg["ttl_max_h"]:
        return None, "durée de vie : 1 à %d h" % cfg["ttl_max_h"]
    if cores is not None and not 1 <= cores <= 64 or mem is not None and not 256 <= mem <= 262144:
        return None, "cœurs 1-64, mémoire 256-262144 Mio"
    vmid = next((x for x in range(cfg["vmid_min"], cfg["vmid_max"] + 1) if x not in utilises), None)
    if vmid is None:
        return None, "plage de vmid épuisée"
    expire = int(maintenant + ttl * 3600) if ttl else None
    clone = {"vmid": modele["vmid"], "action": "clone", "newid": vmid, "name": "orch-" + nom, "full": cfg["complet"]}
    if cfg.get("stockage"):
        clone["storage"] = cfg["stockage"]
    opts = {"description": "si-orchestration%s" % (" expire=%d" % expire if expire else "")}
    if cores:
        opts["cores"] = cores
    if mem:
        opts["memory"] = mem
    return {"id": vid, "vmid": vmid, "nom": "orch-" + nom, "noeud": cfg["noeud"], "modele": modele.get("nom"), "modele_vmid": modele["vmid"],
            "os": modele.get("os"), "cores": cores, "memoire": mem, "expire": expire, "cree": maintenant, "phase": "creation", "echec": None,
            "etapes": [_etape("cloner", clone), _etape("regler", {"vmid": vmid, "action": "set", "options": opts}),
                       _etape("demarrer", {"vmid": vmid, "action": "start"})]}, None


def _ok(c):
    r = (c or {}).get("result") or {}
    return (c or {}).get("status") == "done" and r.get("ok", True) is not False


def _err(c):
    r = (c or {}).get("result") or {}
    return str(r.get("error") or (c or {}).get("status") or "?")[:300]


def courante(vm):
    return next((e for e in vm["etapes"] if e["etat"] in ("attente", "en_cours")), None)


def avancer(vm, commande, maintenant):
    """-> (vm, geste) ; geste « envoyer » : le central envoie courante(vm)["params"] et note l'id de commande."""
    e = courante(vm)
    if e is None:
        return vm, None
    if e["commande"] is None:
        e["etat"], e["debut"] = "en_cours", e["debut"] or maintenant
        return vm, "envoyer"
    if commande is None or commande.get("status") in ("pending", "sent", "acked"):
        if maintenant - (e["debut"] or maintenant) > DELAI.get(e["id"], DEFAUT_DELAI):
            return _echec(vm, e, "délai dépassé", maintenant)
        return vm, None
    if _ok(commande):
        e["etat"], e["fin"] = "fait", maintenant
        if courante(vm) is None:
            vm["phase"] = {"creation": "en_service", "destruction": "detruite"}.get(vm["phase"], vm["phase"])
            vm["fin_phase"] = maintenant
        return vm, None
    return _echec(vm, e, _err(commande), maintenant)


def _echec(vm, e, detail, maintenant):
    e["etat"], e["fin"], e["detail"] = "echec", maintenant, detail
    if vm["phase"] == "creation":
        vm["echec"] = "%s : %s" % (e["id"], detail)
        if e["id"] == "cloner":                     # rien n'a été créé
            vm["phase"] = "echec"
            return vm, None
        for x in vm["etapes"]:
            if x["etat"] == "attente":
                x["etat"] = "annule"
        vm["phase"] = "destruction"                 # nettoyage : pas de clone orphelin
        vm["etapes"] += _destruction(vm)
        return vm, None
    if e["id"] == "arreter":                        # déjà arrêtée ou absente : on détruit quand même
        return vm, None
    vm["phase"] = "echec"
    vm["echec"] = "%s : %s" % (e["id"], detail)
    return vm, None


def detruire(vm, raison, maintenant):
    """Arrêt puis destruction (TTL, ou demande) ; sans effet si déjà en destruction ou détruite."""
    if vm["phase"] in ("destruction", "detruite") or vm["phase"] == "echec" and not any(e["id"] == "cloner" and e["etat"] == "fait" for e in vm["etapes"]):
        return False
    clone = vm["etapes"][0]
    if vm["phase"] == "creation" and clone["commande"] is None:   # rien d'envoyé encore : abandon sans geste
        clone["etat"], vm["phase"], vm["raison_fin"] = "annule", "detruite", raison
        for e in vm["etapes"][1:]:
            e["etat"] = "annule"
        return True
    for e in vm["etapes"]:
        if e["etat"] in ("attente", "en_cours"):
            e["etat"], e["detail"] = "annule", raison
    vm["phase"], vm["raison_fin"] = "destruction", raison
    vm["etapes"] += _destruction(vm)
    return True


def a_expirer(vms, maintenant):
    return [v for v in vms if v.get("expire") and v["expire"] <= maintenant and v["phase"] in ("creation", "en_service")]


def resume(vm):
    e = courante(vm)
    return dict({k: vm.get(k) for k in ("id", "vmid", "nom", "noeud", "modele", "os", "cores", "memoire", "expire", "cree", "phase", "echec", "raison_fin")},
                etape=e["id"] if e else None, etapes=[{k: x[k] for k in ("id", "etat", "detail")} for x in vm["etapes"]])
