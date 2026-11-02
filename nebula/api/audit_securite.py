"""Audit de sécurité réseau d'un site (#958) -- logique PURE, testée (tests/test_audit_securite.py).

Entrées : collecte Nebula (inventaire, états, SSID, carte VLAN, NAT, micrologiciels, licences, clients), historiques
déjà accumulés (clients vus, anomalies), relevés shell (hyperviseur Proxmox, hôtes non gérés : tools/audit-*.sh),
constats saisis à la main. Sortie : constats cotés (probabilité × impact, 1..4 chacun), matrice 4×4, préconisations
priorisées, rapport Markdown. Aucune donnée précise de site dans ce fichier : tout vient des entrées.
"""
import re
from collections import Counter

DOMAINES = {"wifi": "Wi-Fi", "segmentation": "Segmentation / VLAN", "exposition": "Exposition Internet", "equipements": "Équipements réseau",
            "acces": "Accès et comptes", "hyperviseur": "Hyperviseur", "iot": "Objets et équipements non gérés", "inventaire": "Inventaire / visibilité",
            "exploitation": "Exploitation / sauvegardes"}
NIVEAUX = (("critique", 12), ("eleve", 8), ("modere", 4), ("faible", 0))
LIBELLE_NIVEAU = {"critique": "Critique", "eleve": "Élevé", "modere": "Modéré", "faible": "Faible"}
EFFORTS = ("faible", "moyen", "fort")
ETATS = ("a_traiter", "en_cours", "accepte", "traite")
LIBELLE_ETAT = {"a_traiter": "À traiter", "en_cours": "En cours", "accepte": "Risque accepté", "traite": "Traité"}

IOT_RX = re.compile(r"multitech|espressif|tuya|sonoff|shelly|raspberry|hikvision|dahua|axis|oculus|meta platforms|pico|htc|sonos|philips|signify|"
                    r"lifx|xiaomi|tp-?link|d-?link|ubiquiti|teltonika|honeywell|bosch|siemens|schneider|legrand|somfy|netatmo|bticino|crestron|"
                    r"barco|samsung electronics|lg electronics|epson|brother|canon|hp inc|ricoh|kyocera|lexmark|zebra|konica", re.I)
PORTS_SENSIBLES = {21: ("FTP", 3, 3), 23: ("Telnet", 4, 4), 69: ("TFTP", 3, 3), 80: ("HTTP administration en clair", 2, 3), 111: ("RPC", 2, 3),
                   135: ("RPC Windows", 2, 3), 139: ("NetBIOS", 3, 3), 161: ("SNMP", 2, 3), 445: ("SMB", 3, 4), 512: ("rexec", 4, 4), 513: ("rlogin", 4, 4),
                   1433: ("SQL Server", 2, 4), 1883: ("MQTT sans TLS", 3, 3), 3306: ("MySQL", 2, 4), 3389: ("RDP", 3, 4), 5432: ("PostgreSQL", 2, 4),
                   5900: ("VNC", 3, 4), 6379: ("Redis", 3, 4), 8080: ("HTTP alternatif", 2, 2), 9100: ("impression brute", 2, 2), 27017: ("MongoDB", 3, 4),
                   1700: ("transfert LoRa (UDP, non chiffré)", 2, 3)}


def niveau(score):
    for nom, seuil in NIVEAUX:
        if score >= seuil:
            return nom
    return "faible"


def _constat(cid, domaine, titre, preuve, p, i, preconisation, effort="moyen", source="nebula", element=None):
    p, i = max(1, min(4, int(p))), max(1, min(4, int(i)))
    return {"id": cid, "domaine": domaine, "titre": titre, "preuve": preuve, "probabilite": p, "impact": i, "score": p * i, "niveau": niveau(p * i),
            "preconisation": preconisation, "effort": effort if effort in EFFORTS else "moyen", "source": source, "element": element}


def _cles(d, rx, depth=3):
    """Toutes les paires (clé, valeur) scalaires dont la clé correspond à rx, en profondeur (listes comprises)."""
    out = {}
    if depth < 0:
        return out
    if isinstance(d, dict):
        for k, v in d.items():
            if isinstance(v, (dict, list)):
                out.update(_cles(v, rx, depth - 1))
            elif rx.search(str(k)):
                out[str(k)] = v
    elif isinstance(d, list):
        for x in d:
            out.update(_cles(x, rx, depth - 1))
    return out


SEC_RX = re.compile(r"auth|security|encrypt|wpa|psk|open", re.I)
ISO_RX = re.compile(r"isolat", re.I)
PORTAL_RX = re.compile(r"captive|portal|splash", re.I)


def securite_ssid(w):
    """Mode de sécurité d'un SSID brut -> 'ouvert' | 'wep' | 'wpa' | 'wpa2' | 'wpa3' | 'mixte' | '802.1x' | 'inconnu'."""
    vals = " ".join(str(v) for v in _cles(w, SEC_RX).values() if not isinstance(v, bool)).lower()
    if w.get("open") is True or re.search(r"\bopen\b|\bnone\b", vals):
        return "ouvert"
    if "wep" in vals:
        return "wep"
    if "802.1x" in vals or "enterprise" in vals or "radius" in vals or "eap" in vals:
        return "802.1x"
    if "wpa3" in vals and "wpa2" in vals:
        return "mixte"
    if "wpa3" in vals:
        return "wpa3"
    if "wpa2" in vals:
        return "wpa2"
    if "wpa" in vals:
        return "wpa"
    return "inconnu"


# ----------------------------------------------------------------- Nebula
def analyser_nebula(c):
    """c : {devices, online{devId:bool}, wlans[], vlan_map{}, nat[] (gwpolicy.parse_nat), firmware[], licenses[], clients[]}."""
    out = []
    vmap = c.get("vlan_map") or {}
    vlans = {v.get("vid"): v for v in vmap.get("vlans") or []}
    gestion = {vid for vid, v in vlans.items() if v.get("management")}
    for w in c.get("wlans") or []:
        if not isinstance(w, dict) or w.get("enabled") is False:
            continue
        nom = w.get("name") or w.get("ssid") or "?"
        sec, vid, invite = securite_ssid(w), w.get("vlan"), bool(w.get("guestNetwork"))
        if sec in ("ouvert", "wep"):
            out.append(_constat("ssid-ouvert:%s" % nom, "wifi", "SSID « %s » %s" % (nom, "ouvert (sans chiffrement)" if sec == "ouvert" else "en WEP (cassable en minutes)"),
                                "sécurité annoncée par Nebula : %s" % sec, 4, 4 if not invite else 2,
                                "passer en WPA2/WPA3 ; pour un réseau d'accueil : portail captif + isolation des clients + VLAN dédié", "faible", element=nom))
        elif sec in ("wpa", "wpa2", "mixte") and not invite:
            out.append(_constat("ssid-psk:%s" % nom, "wifi", "SSID « %s » en %s à clé partagée" % (nom, sec.upper()),
                                "une seule clé pour tous les usagers : fuite = accès durable, pas de révocation individuelle", 3, 3,
                                "WPA3 ou WPA2-Entreprise (802.1X, comptes individuels) pour le personnel ; clé tournée à chaque départ sinon", "moyen", element=nom))
        elif sec == "inconnu":
            out.append(_constat("ssid-inconnu:%s" % nom, "wifi", "SSID « %s » : mode de sécurité non lu par l'API" % nom, "à vérifier dans Nebula (Configure › SSID)", 1, 3,
                                "relever le mode à la main et le reporter en constat manuel", "faible", element=nom))
        iso = _cles(w, ISO_RX)
        if invite and iso and not any(bool(v) for v in iso.values()):
            out.append(_constat("ssid-invite-isolation:%s" % nom, "wifi", "SSID d'accueil « %s » sans isolation des clients" % nom, "les visiteurs se voient entre eux (%s)" % ", ".join(iso),
                                3, 2, "activer l'isolation L2 (client isolation) sur le SSID d'accueil", "faible", element=nom))
        if vid is None:
            out.append(_constat("ssid-sans-vlan:%s" % nom, "segmentation", "SSID « %s » sans VLAN : clients sur le VLAN natif" % nom, "aucun VLAN affecté au SSID",
                                3, 3, "affecter un VLAN dédié au SSID (profil de port des bornes à compléter)", "faible", element=nom))
        elif vid in gestion:
            out.append(_constat("ssid-vlan-gestion:%s" % nom, "segmentation", "SSID « %s » sur le VLAN de gestion %s" % (nom, vid),
                                "VLAN %s porte l'IP de gestion de : %s" % (vid, ", ".join(vlans[vid]["management"])), 3, 4,
                                "déplacer le SSID sur un VLAN utilisateurs ; réserver le VLAN de gestion aux équipements et au poste d'administration", "moyen", element=nom))
    for vid, v in vlans.items():
        if v.get("management") and (v.get("clients") or 0) > 0:
            out.append(_constat("vlan-gestion-partage:%s" % vid, "segmentation", "VLAN de gestion %s partagé avec %d client(s)" % (vid, v["clients"]),
                                "gestion de : %s ; sous-réseau %s" % (", ".join(v["management"]), v.get("subnet") or "?"), 3, 4,
                                "VLAN de gestion dédié (accès admin des commutateurs, bornes, pare-feu) joignable seulement depuis un poste d'administration", "moyen", element="VLAN %s" % vid))
    n_anom = len(vmap.get("anomalies") or [])
    if n_anom:
        out.append(_constat("vlan-anomalies", "segmentation", "%d anomalie(s) de propagation des VLAN" % n_anom, "; ".join((vmap.get("anomalies") or [])[:3]) + (" …" if n_anom > 3 else ""),
                            2, 2, "traiter les anomalies de la carte des VLAN (vue Nebula › Carte des VLAN)", "faible", element="carte VLAN"))
    liens = {(l.get("a"), str(l.get("a_port"))) for l in vmap.get("links") or []} | {(l.get("b"), str(l.get("b_port"))) for l in vmap.get("links") or []}
    noms = {d.get("devId"): d.get("name") or d.get("devId") for d in c.get("devices") or []}
    for dev, ports in (c.get("ports_by_sw") or {}).items():
        libres = [str(p.get("portNum")) for p in ports or [] if isinstance(p, dict) and p.get("enabled", True) and p.get("trunk")
                  and (not p.get("allowedVLAN") or any(str(x).lower() in ("all", "*", "") for x in p.get("allowedVLAN") or [])) and (dev, str(p.get("portNum"))) not in liens]
        if libres:
            out.append(_constat("trunk-libre:%s" % dev, "segmentation", "%s : %d port(s) trunk « tous VLAN » sans voisin connu" % (noms.get(dev, dev), len(libres)),
                                "ports %s : une prise libre donne accès à tous les VLAN" % ", ".join(libres[:8]), 2, 4,
                                "restreindre les VLAN autorisés aux liaisons réelles ; désactiver les ports non brassés", "faible", element=noms.get(dev, dev)))
    for r in c.get("nat") or []:
        if not r.get("enabled", True):
            continue
        cible = "%s → %s" % (r.get("public_ip") or r.get("interface") or "WAN", r.get("private_ip") or "?")
        if r.get("all_ports"):
            out.append(_constat("nat-tous-ports:%s" % (r.get("private_ip") or r.get("name")), "exposition", "NAT %s : TOUS les ports exposés" % cible,
                                "règle « %s » (%s)" % (r.get("name") or "sans nom", r.get("kind")), 4, 4, "limiter aux ports strictement nécessaires, filtrer par source, ou passer par un VPN", "faible", element=cible))
        elif r.get("any_remote"):
            out.append(_constat("nat-ouvert:%s:%s" % (r.get("private_ip") or r.get("name"), ",".join(map(str, r.get("ports") or []))), "exposition",
                                "Redirection %s ports %s ouverte à tout Internet" % (cible, ", ".join(map(str, (r.get("ports") or [])[:6])) or "?"),
                                "règle « %s », aucune restriction de source" % (r.get("name") or "sans nom"), 3, 3,
                                "restreindre les adresses sources ; sinon VPN ; journaliser et surveiller les tentatives", "faible", element=cible))
    hors = [noms.get(d, d) for d, ok in (c.get("online") or {}).items() if ok is False]
    if hors:
        out.append(_constat("equipements-hors-ligne", "equipements", "%d équipement(s) Nebula hors ligne" % len(hors), ", ".join(sorted(hors)[:8]), 2, 2,
                            "vérifier alimentation PoE / câblage ; retirer de Nebula les équipements abandonnés", "faible", element="Nebula"))
    for t in c.get("firmware") or []:
        vers = [v for v in (t.get("versions") or {}) if v != "?"]
        if len(vers) > 1:
            out.append(_constat("fw-mixte:%s" % t.get("model"), "equipements", "%s : %d versions de micrologiciel" % (t.get("model"), len(vers)), ", ".join(sorted(vers)), 2, 3,
                                "aligner les micrologiciels (Nebula › Firmware), fenêtre de maintenance planifiée", "faible", element=t.get("model")))
    for l in c.get("licenses") or []:
        j = l.get("days_left")
        if j is not None and j <= 90:
            out.append(_constat("licence:%s" % l.get("field"), "exploitation", "Licence « %s » %s" % (l.get("field"), "échue depuis %d j" % -j if j < 0 else "échoit dans %d j" % j),
                                str(l.get("value")), 3 if j <= 30 else 2, 3, "renouveler avant l'échéance (perte des fonctions de sécurité / de l'API à l'échéance)", "faible", element="Nebula"))
    clients = c.get("clients") or []
    if clients:
        sans_nom = [x for x in clients if not (x.get("description") or x.get("osHostname") or x.get("os_hostname") or x.get("name"))]
        if len(sans_nom) >= max(5, len(clients) // 3):
            out.append(_constat("clients-sans-nom", "inventaire", "%d client(s) sur %d sans nom ni description" % (len(sans_nom), len(clients)),
                                "identification impossible en cas d'incident", 3, 2, "nommer les équipements fixes dans Nebula (description) ; IP fixes pour l'Ethernet", "moyen", element="clients"))
    return out


# ----------------------------------------------------------------- historiques accumulés
def analyser_historiques(h, reglages=None):
    """h : {clients_vus[]: {mac, manufacturer, vlan, ssid, name, first_seen, last_seen, seen_count}, anomalies[]: {severity, message}}"""
    out, reg = [], reglages or {}
    vus = h.get("clients_vus") or []
    iot = [x for x in vus if IOT_RX.search(str(x.get("manufacturer") or ""))]
    par_vlan = Counter(str(x.get("vlan") or "?") for x in vus)
    iot_vlan = Counter(str(x.get("vlan") or "?") for x in iot)
    vl_serveurs = {str(v) for v in reg.get("vlans_serveurs") or []}
    vl_iot = {str(v) for v in reg.get("vlans_iot") or []}
    for vid, n in iot_vlan.items():
        if vid in vl_iot:
            continue
        autres = par_vlan[vid] - n
        if vid in vl_serveurs:
            p, i, titre = 3, 4, "VLAN %s (serveurs) : %d objet(s) connecté(s) / équipement(s) embarqué(s)" % (vid, n)
        elif autres >= 3:
            p, i, titre = 2, 3, "VLAN %s : %d objet(s) connecté(s) mêlé(s) à %d autres clients" % (vid, n, autres)
        else:
            continue
        fab = Counter(str(x.get("manufacturer")) for x in iot if str(x.get("vlan") or "?") == vid)
        out.append(_constat("iot-vlan:%s" % vid, "iot", titre, "fabricants : " + ", ".join("%s ×%d" % kv for kv in fab.most_common(5)), p, i,
                            "VLAN « objets » dédié, règles sortantes limitées (destinations connues), pas de route vers les serveurs", "moyen", "historique", element="VLAN %s" % vid))
    inconnus = [x for x in vus if not x.get("name") and not x.get("manufacturer")]
    if len(vus) >= 10 and len(inconnus) >= len(vus) // 4:
        out.append(_constat("clients-inconnus", "inventaire", "%d client(s) sur %d jamais identifiés dans l'historique" % (len(inconnus), len(vus)),
                            "ni nom ni fabricant reconnu", 3, 2, "campagne d'identification (repérage physique) ; filtrage par MAC ou 802.1X à terme", "moyen", "historique", element="historique"))
    ephem = [x for x in vus if (x.get("seen_count") or 0) == 1 and x.get("ssid")]
    if len(vus) >= 20 and len(ephem) >= len(vus) // 3:
        out.append(_constat("clients-ephemeres", "wifi", "%d client(s) Wi-Fi vus une seule fois" % len(ephem), "forte rotation : réseau partagé avec des visiteurs ?", 2, 2,
                            "SSID d'accueil distinct (portail, isolation, VLAN) séparé du SSID du personnel", "moyen", "historique", element="Wi-Fi"))
    graves = [a for a in h.get("anomalies") or [] if str(a.get("severity") or "").lower() in ("haute", "high", "critique")]
    if graves:
        out.append(_constat("anomalies-hautes", "equipements", "%d anomalie(s) de sévérité haute en attente" % len(graves), "; ".join(str(a.get("message"))[:90] for a in graves[:3]), 2, 3,
                            "traiter ou acquitter les anomalies de la vue Nebula", "faible", "historique", element="anomalies"))
    return out


# ----------------------------------------------------------------- Proxmox (sortie de tools/audit-proxmox.sh)
def analyser_proxmox(p):
    out = []
    if not p:
        return out
    hote = p.get("hostname") or "hyperviseur"
    ver = str(p.get("pveversion") or "")
    m = re.search(r"pve-manager/(\d+)\.(\d+)", ver) or re.search(r"(\d+)\.(\d+)", ver)
    if m and int(m.group(1)) < 8:
        out.append(_constat("pve-version", "hyperviseur", "%s : Proxmox VE %s.%s (fin de support)" % (hote, m.group(1), m.group(2)), ver, 3, 4,
                            "migrer vers la version supportée (sauvegarde complète avant)", "fort", "proxmox", element=hote))
    maj = p.get("updates_pending")
    if isinstance(maj, int) and maj > 0:
        out.append(_constat("pve-maj", "hyperviseur", "%s : %d mise(s) à jour en attente" % (hote, maj), "dont sécurité : %s" % p.get("updates_security", "?"), 3 if maj > 20 else 2, 3,
                            "fenêtre de maintenance mensuelle ; mises à jour de sécurité automatiques (unattended-upgrades)", "faible", "proxmox", element=hote))
    prl = str(p.get("ssh_permit_root_login") or "").lower()
    if prl in ("yes", "") and p.get("ssh_password_auth", "yes") != "no":
        out.append(_constat("pve-ssh-root", "acces", "%s : SSH root par mot de passe autorisé" % hote, "PermitRootLogin=%s, PasswordAuthentication=%s" % (prl or "défaut (yes)", p.get("ssh_password_auth", "défaut")),
                            3, 4, "clés SSH uniquement (PermitRootLogin prohibit-password, PasswordAuthentication no), fail2ban, accès limité au VLAN d'administration", "faible", "proxmox", element=hote))
    sans_2fa = [u.get("user") for u in p.get("users") or [] if u.get("enabled", True) and not u.get("tfa") and ("admin" in str(u.get("roles") or "").lower() or str(u.get("user", "")).startswith("root@"))]
    if sans_2fa:
        out.append(_constat("pve-2fa", "acces", "%s : %d compte(s) administrateur sans double authentification" % (hote, len(sans_2fa)), ", ".join(sans_2fa[:6]), 3, 4,
                            "activer TOTP/WebAuthn sur chaque compte admin ; un compte nominatif par administrateur", "faible", "proxmox", element=hote))
    fw = p.get("firewall") or {}
    if fw and not fw.get("cluster_enabled"):
        out.append(_constat("pve-firewall", "hyperviseur", "%s : pare-feu Proxmox désactivé" % hote, "Datacenter › Firewall : enable=0", 2, 3,
                            "activer le pare-feu au niveau datacenter avec une règle d'administration (8006/22 depuis le VLAN admin seulement)", "moyen", "proxmox", element=hote))
    ecoute = [x for x in p.get("listening") or [] if str(x.get("addr") or "").startswith(("0.0.0.0", "*", "::", "[::]"))]
    admin = [x for x in ecoute if str(x.get("port")) in ("8006", "22", "3128", "111")]
    if admin:
        out.append(_constat("pve-ecoute", "hyperviseur", "%s : interface d'administration à l'écoute sur toutes les adresses" % hote,
                            ", ".join("%s/%s" % (x.get("port"), x.get("proc") or "?") for x in admin), 2, 3,
                            "restreindre par pare-feu aux réseaux d'administration (l'écoute globale est le défaut Proxmox)", "faible", "proxmox", element=hote))
    if p.get("backup_jobs") == 0 or (isinstance(p.get("backup_jobs"), list) and not p["backup_jobs"]):
        out.append(_constat("pve-sauvegarde", "exploitation", "%s : aucune tâche de sauvegarde planifiée" % hote, "vzdump / Proxmox Backup Server : aucun job", 3, 4,
                            "sauvegarde quotidienne des VM (PBS ou stockage externe), test de restauration", "moyen", "proxmox", element=hote))
    for vm in p.get("vms") or []:
        if vm.get("status") == "running" and vm.get("firewall") is False and vm.get("gpu"):
            out.append(_constat("vm-gpu:%s" % vm.get("vmid"), "hyperviseur", "VM %s (%s) avec GPU, sans pare-feu VM" % (vm.get("vmid"), vm.get("name")), "interfaces : %s" % ", ".join(vm.get("bridges") or []),
                                2, 3, "règles pare-feu VM : n'exposer que le port du service IA, journaliser", "faible", "proxmox", element=vm.get("name")))
    if p.get("repos_enterprise") is False and not p.get("repos_no_subscription"):
        out.append(_constat("pve-depots", "hyperviseur", "%s : aucun dépôt de mises à jour actif" % hote, "ni enterprise ni no-subscription", 3, 3, "activer pve-no-subscription (ou souscription)", "faible", "proxmox", element=hote))
    return out


# ----------------------------------------------------------------- hôtes non gérés (tools/audit-hote.sh)
def analyser_hotes(hotes):
    out = []
    for h in hotes or []:
        nom = h.get("nom") or h.get("ip") or "?"
        for pr in h.get("ports") or []:
            try:
                num = int(pr.get("port"))
            except (TypeError, ValueError):
                continue
            if num in PORTS_SENSIBLES:
                lib, p, i = PORTS_SENSIBLES[num]
                out.append(_constat("hote-port:%s:%s" % (nom, num), "iot", "%s : service %s ouvert (port %d)" % (nom, lib, num), (pr.get("banner") or pr.get("service") or "")[:120] or "détecté par balayage",
                                    p, i, "désactiver ou restreindre par pare-feu/VLAN ; remplacer par un protocole chiffré (SSH/HTTPS/MQTTS)", "faible", "hote", element=nom))
        if h.get("defaut_identifiants"):
            out.append(_constat("hote-defaut:%s" % nom, "acces", "%s : identifiants par défaut acceptés" % nom, str(h.get("defaut_identifiants"))[:120], 4, 4, "changer immédiatement, puis isoler", "faible", "hote", element=nom))
        if h.get("sorties_externes"):
            out.append(_constat("hote-sortie:%s" % nom, "iot", "%s : flux sortants vers l'extérieur (%s)" % (nom, ", ".join(map(str, h["sorties_externes"][:4]))), "destinations non maîtrisées par le site", 2, 2,
                                "autoriser explicitement les destinations (règle sortante nominative), journaliser", "moyen", "hote", element=nom))
    return out


# ----------------------------------------------------------------- assemblage
def analyser(collecte, etats=None, reglages=None):
    """collecte : {nebula, historiques, proxmox[], hotes[], manuels[]} ; etats : {id: {etat, probabilite?, impact?, note?}}."""
    constats = analyser_nebula(collecte.get("nebula") or {}) + analyser_historiques(collecte.get("historiques") or {}, reglages)
    for p in collecte.get("proxmox") or []:
        constats += analyser_proxmox(p)
    constats += analyser_hotes(collecte.get("hotes") or [])
    for m in collecte.get("manuels") or []:
        c, err = valider_manuel(m)
        if c:
            constats.append(c)
    for c in constats:
        e = (etats or {}).get(c["id"]) or {}
        if e.get("probabilite"):
            c["probabilite"] = max(1, min(4, int(e["probabilite"])))
        if e.get("impact"):
            c["impact"] = max(1, min(4, int(e["impact"])))
        c["score"], c["niveau"] = c["probabilite"] * c["impact"], niveau(c["probabilite"] * c["impact"])
        c["etat"], c["note"] = e.get("etat") if e.get("etat") in ETATS else "a_traiter", e.get("note") or ""
    constats.sort(key=lambda c: (-c["score"], c["domaine"], c["titre"]))
    return constats


def valider_manuel(m):
    titre = str(m.get("titre") or "").strip()
    if not titre:
        return None, "titre requis"
    dom = m.get("domaine") if m.get("domaine") in DOMAINES else "acces"
    cid = "manuel:%s" % re.sub(r"[^a-z0-9]+", "-", titre.lower())[:40].strip("-")
    return _constat(cid, dom, titre, str(m.get("preuve") or "")[:300], m.get("probabilite") or 2, m.get("impact") or 2, str(m.get("preconisation") or "")[:300],
                    m.get("effort") or "moyen", "manuel", element=str(m.get("element") or "")[:80] or None), None


def matrice(constats):
    """Grille 4×4 : cases[impact][probabilite] = liste d'ids (impact 4 en haut)."""
    cases = {i: {p: [] for p in (1, 2, 3, 4)} for i in (1, 2, 3, 4)}
    for c in constats:
        cases[c["impact"]][c["probabilite"]].append(c["id"])
    return {"cases": cases, "par_niveau": dict(Counter(c["niveau"] for c in constats)), "total": len(constats)}


def preconisations(constats):
    """Actions priorisées : score décroissant, effort faible d'abord à score égal ; constats traités/acceptés exclus."""
    ordre = {"faible": 0, "moyen": 1, "fort": 2}
    act = [c for c in constats if c.get("etat") in (None, "a_traiter", "en_cours")]
    act.sort(key=lambda c: (-c["score"], ordre.get(c["effort"], 1), c["titre"]))
    return [{"rang": n + 1, "id": c["id"], "action": c["preconisation"], "constat": c["titre"], "niveau": c["niveau"], "score": c["score"], "effort": c["effort"], "domaine": c["domaine"]}
            for n, c in enumerate(act)]


def rapport_markdown(site, constats, sources=None, date=None):
    m, pre = matrice(constats), preconisations(constats)
    L = ["# Audit de sécurité réseau — %s" % site, "", "_%s_" % (date or ""), "", "## Synthèse", ""]
    for niv, _ in NIVEAUX:
        L.append("- %s : %d" % (LIBELLE_NIVEAU[niv], m["par_niveau"].get(niv, 0)))
    L += ["", "## Matrice des risques (impact ↓ × probabilité →)", "", "| Impact \\ Probabilité | 1 rare | 2 possible | 3 probable | 4 certain |", "|---|---|---|---|---|"]
    for i in (4, 3, 2, 1):
        L.append("| **%d** | " % i + " | ".join(str(len(m["cases"][i][p])) or "" for p in (1, 2, 3, 4)) + " |")
    L += ["", "## Constats", ""]
    for dom, lib in DOMAINES.items():
        cs = [c for c in constats if c["domaine"] == dom]
        if not cs:
            continue
        L += ["### %s" % lib, ""]
        for c in cs:
            L.append("- **[%s %d]** %s — _%s_%s" % (LIBELLE_NIVEAU[c["niveau"]], c["score"], c["titre"], c["preuve"], " (%s)" % LIBELLE_ETAT[c["etat"]] if c.get("etat") and c["etat"] != "a_traiter" else ""))
        L.append("")
    L += ["## Préconisations priorisées", "", "| # | Action | Niveau | Effort | Constat |", "|---|---|---|---|---|"]
    for p in pre:
        L.append("| %d | %s | %s (%d) | %s | %s |" % (p["rang"], p["action"], LIBELLE_NIVEAU[p["niveau"]], p["score"], p["effort"], p["constat"]))
    if sources:
        L += ["", "## Sources des données", ""] + ["- %s" % s for s in sources]
    return "\n".join(L) + "\n"


def constats_csv(constats):
    import csv
    import io
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["id", "domaine", "niveau", "score", "probabilite", "impact", "titre", "preuve", "preconisation", "effort", "source", "element", "etat", "note"])
    for c in constats:
        w.writerow([c["id"], DOMAINES.get(c["domaine"], c["domaine"]), LIBELLE_NIVEAU[c["niveau"]], c["score"], c["probabilite"], c["impact"], c["titre"], c["preuve"],
                    c["preconisation"], c["effort"], c["source"], c.get("element") or "", LIBELLE_ETAT.get(c.get("etat") or "a_traiter"), c.get("note") or ""])
    return "﻿" + buf.getvalue()
