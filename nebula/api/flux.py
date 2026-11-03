"""Supervision des flux sortants exigés par les éditeurs (#962) -- logique PURE, testée (tests/test_flux.py).

Les tests réseau sont faits SUR LE SITE par `nebula/tools/test-flux.sh` (agent, mini-PC, sonde) qui envoie ses résultats au
hub ; ici : listes de cibles, reclassement « port non servi », bilan, alertes ouvertes / rétablies, et analyse croisée avec
Nebula (où sont les appareils concernés, quels VLAN ont été testés). Aucune donnée de site dans ce fichier.
"""
import ipaddress
import re

STATUTS = ("OK", "KO", "NS", "INSPECTE", "OUVERT", "CERT", "?")
# OUVERT : port qui devrait être fermé (5e champ « ferme ») ; CERT : certificat expiré ou à moins de 14 jours.
ALERTANT = ("KO", "INSPECTE", "OUVERT", "CERT")
FERME = ("ferme", "fermé", "closed", "close", "!")

# Liste Google Android Enterprise (support.google.com/work/android/answer/10513641, relevé du 03/11/2026) ; les jokers
# (*.x) sont testés sur un hôte représentatif. Le format est celui du script : groupe;hôte;proto;ports.
GOOGLE = """google-appareils;play.google.com;tcp;443,5228-5230
google-appareils;android.com;tcp;443
google-appareils;www.google-analytics.com;tcp;443
google-appareils;lh3.googleusercontent.com;tcp;443
google-appareils;www.gstatic.com;tcp;443,5228-5230
google-appareils;redirector.gvt1.com;tcp;443,5228-5230
google-appareils;lh3.ggpht.com;tcp;443
google-appareils;dl.google.com;tcp;443
google-appareils;dl-ssl.google.com;tcp;443
google-appareils;android.apis.google.com;tcp;443,5228-5230
google-appareils;beacons.gvt2.com;tcp;443
google-appareils;www.googleapis.com;tcp;443
google-appareils;m.google.com;tcp;443
google-appareils;accounts.google.com;tcp;443
google-appareils;accounts.google.fr;tcp;443
google-appareils;gcm-http.googleapis.com;tcp;443,5228-5230
google-appareils;android.googleapis.com;tcp;443,5228-5230
google-appareils;fcm.googleapis.com;tcp;443,5228-5230
google-appareils;fcm-xmpp.googleapis.com;tcp;443,5228-5230,5235,5236
google-appareils;gcm-xmpp.googleapis.com;tcp;443,5228-5230,5235,5236
google-appareils;firebaseinstallations.googleapis.com;tcp;443,5228-5230
google-appareils;firebaselogging.googleapis.com;tcp;443
google-appareils;pki.google.com;tcp;443
google-appareils;clients1.google.com;tcp;443
google-appareils;clients2.google.com;tcp;443
google-appareils;clients3.google.com;tcp;443
google-appareils;clients4.google.com;tcp;443
google-appareils;clients5.google.com;tcp;443
google-appareils;clients6.google.com;tcp;443
google-appareils;chromiumdash.appspot.com;tcp;443
google-appareils;connectivitycheck.android.com;tcp;443
google-appareils;connectivitycheck.gstatic.com;tcp;443
google-appareils;www.google.com;tcp;443
google-appareils;ota.googlezip.net;tcp;443
google-appareils;ota-cache1.googlezip.net;tcp;443
google-appareils;ota-cache3.googlezip.net;tcp;443
google-appareils;mtalk.google.com;tcp;443,5228-5230
google-appareils;mtalk4.google.com;tcp;443,5228-5230
google-appareils;alt1-mtalk.google.com;tcp;443,5228-5230
google-appareils;alt8-mtalk.google.com;tcp;443,5228-5230
google-appareils;device-provisioning.googleapis.com;tcp;443,5228-5230
google-appareils;time.google.com;udp;123
google-appareils;android-safebrowsing.google.com;tcp;443
google-appareils;safebrowsing.google.com;tcp;443
google-console;androidmanagement.googleapis.com;tcp;443
google-console;fonts.googleapis.com;tcp;443
google-console;accounts.youtube.com;tcp;443
google-console;crl.pki.goog;tcp;443
google-console;ocsp.pki.goog;tcp;443
google-console;apis.google.com;tcp;443
google-console;ajax.googleapis.com;tcp;443
google-console;payments.google.com;tcp;443
google-console;google.com;tcp;443
google-console;ogs.google.com;tcp;443
google-console;notifications.google.com;tcp;443
google-console;enterprise.google.com;tcp;443"""
LISTES_INTEGREES = {"google": {"id": "google", "nom": "Google Android Enterprise", "editeur": "Google",
                               "source": "https://support.google.com/work/android/answer/10513641", "texte": GOOGLE, "integree": True}}

HOTE_RX = re.compile(r"^[A-Za-z0-9*]([A-Za-z0-9.*-]{0,251}[A-Za-z0-9])?$")
# Fabricants / systèmes typiques des terminaux mobiles gérés (tablettes, téléphones) pour l'analyse Nebula.
MOBILE_RX = re.compile(r"android|samsung|lenovo|xiaomi|huawei|honor|motorola|oppo|realme|oneplus|google|zebra|apple|ipad|iphone|tablet", re.I)


def ports(spec):
    """« 443,5228-5230 » -> [443, 5228, 5229, 5230] (bornes 1..65535, plage de 200 ports au plus)."""
    out = []
    for p in str(spec or "").replace(" ", "").split(","):
        if not p:
            continue
        m = re.match(r"^(\d+)-(\d+)$", p)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if not (1 <= a <= b <= 65535) or b - a > 200:
                raise ValueError("plage de ports invalide : %s" % p)
            out += list(range(a, b + 1))
        elif p.isdigit() and 1 <= int(p) <= 65535:
            out.append(int(p))
        else:
            raise ValueError("port invalide : %s" % p)
    return sorted(set(out))


def lire_liste(texte):
    """Texte « groupe;hôte;proto;ports[;ferme] » (ou « hôte proto ports », ou « hôte:port ») -> (lignes, erreurs).
    Accepte les copies d'une page d'éditeur : séparateurs ; , tabulation ou espaces, commentaires #.
    5e champ « ferme » : le port doit être FERMÉ vu de ce point (ex. SSH ou base de données vus d'Internet)."""
    lignes, erreurs = [], []
    for n, l in enumerate(str(texte or "").splitlines(), 1):
        l = l.strip()
        if not l or l.startswith("#"):
            continue
        champs = [c.strip() for c in re.split(r"[;\t]", l)] if re.search(r"[;\t]", l) else l.split()
        if len(champs) == 1 and re.match(r"^[^:]+:\d+$", champs[0]):
            h, p = champs[0].rsplit(":", 1); champs = ["", h, "tcp", p]
        if len(champs) == 3:
            champs = [""] + champs
        attendu = "ferme" if len(champs) > 4 and champs[4].strip().lower() in FERME else "ouvert"
        if len(champs) < 4:
            erreurs.append("ligne %d : 4 champs attendus (groupe;hôte;proto;ports)" % n); continue
        grp, hote, proto, pl = champs[0] or "cibles", champs[1].lower(), champs[2].lower(), champs[3]
        hote = re.sub(r"^https?://", "", hote).split("/")[0]
        if not HOTE_RX.match(hote):
            erreurs.append("ligne %d : hôte invalide « %s »" % (n, hote)); continue
        if proto not in ("tcp", "udp"):
            erreurs.append("ligne %d : protocole tcp ou udp attendu" % n); continue
        try:
            ps = ports(pl)
        except ValueError as e:
            erreurs.append("ligne %d : %s" % (n, e)); continue
        if not ps:
            erreurs.append("ligne %d : aucun port" % n); continue
        lignes.append({"groupe": re.sub(r"[^\w.-]", "-", grp)[:40], "hote": hote, "proto": proto, "ports": pl.replace(" ", ""), "attendu": attendu})
    return lignes, erreurs


def texte_liste(lignes):
    return "\n".join("%s;%s;%s;%s%s" % (l["groupe"], l["hote"], l["proto"], l["ports"], ";ferme" if l.get("attendu") == "ferme" else "") for l in lignes) + "\n"


def valider_resultats(d):
    """Résultats envoyés par le script -> (passage, erreur). passage = {source, iface, ip_source, ip_publique, lignes[]}."""
    if not isinstance(d, dict):
        return None, "objet attendu"
    src = str(d.get("source") or "").strip()[:60]
    if not src:
        return None, "source requise"
    lignes = []
    for r in d.get("resultats") or []:
        if not isinstance(r, dict):
            continue
        st = str(r.get("statut") or "").upper()
        if st not in STATUTS:
            continue
        try:
            port = int(r.get("port"))
        except (TypeError, ValueError):
            continue
        lignes.append({"groupe": str(r.get("groupe") or "")[:40], "hote": str(r.get("hote") or "")[:253].lower(), "ip": str(r.get("ip") or "")[:45],
                       "proto": "udp" if str(r.get("proto")).lower() == "udp" else "tcp", "port": port, "statut": st, "detail": str(r.get("detail") or "")[:200],
                       "attendu": "ferme" if str(r.get("attendu") or "").lower() in FERME else "ouvert"})
    if not lignes:
        return None, "aucun résultat exploitable"
    return {"source": src, "iface": str(d.get("iface") or "")[:30] or None, "ip_source": str(d.get("ip_source") or "").split("/")[0][:45] or None,
            "ip_publique": str(d.get("ip_publique") or "")[:45] or None, "lignes": reclasser_ns(lignes)}, None


def reclasser_ns(lignes):
    """Un port refusé par un hôte mais accepté par un autre n'est pas filtré : l'hôte ne le sert pas -> NS."""
    ouverts = {(l["proto"], l["port"]) for l in lignes if l["statut"] == "OK" and l.get("attendu") != "ferme"}
    out = []
    for l in lignes:
        l = dict(l)
        if l["statut"] == "KO" and l.get("attendu") != "ferme" and "DNS" not in l["detail"].upper() and (l["proto"], l["port"]) in ouverts:
            l["statut"], l["detail"] = "NS", "port ouvert vers d'autres hôtes : non servi par celui-ci (pas un blocage)"
        out.append(l)
    return out


def bilan(lignes):
    b = {s: 0 for s in STATUTS}
    for l in lignes:
        b[l["statut"]] = b.get(l["statut"], 0) + 1
    b["total"] = len(lignes)
    b["etat"] = "alerte" if any(b[s] for s in ALERTANT) else "ok"
    return b


def cle(l, source):
    return "%s|%s|%s/%d" % (source, l["hote"], l["proto"], l["port"])


def diff_alertes(ouvertes, lignes, source, now):
    """ouvertes : {cle: alerte} de cette source. -> (nouvelles, retablies, maintenues). Une alerte = flux KO / inspecté."""
    vus = {cle(l, source): l for l in lignes}
    nouvelles, retablies, maintenues = [], [], []
    for k, l in vus.items():
        if l["statut"] in ALERTANT:
            if k in ouvertes:
                maintenues.append(dict(ouvertes[k], dernier=now, detail=l["detail"], statut=l["statut"]))
            else:
                nouvelles.append({"cle": k, "source": source, "hote": l["hote"], "proto": l["proto"], "port": l["port"], "groupe": l["groupe"],
                                  "statut": l["statut"], "detail": l["detail"], "debut": now, "dernier": now})
    for k, a in ouvertes.items():
        l = vus.get(k)
        if l is not None and l["statut"] not in ALERTANT:
            retablies.append(dict(a, fin=now, statut_fin=l["statut"]))
    return nouvelles, retablies, maintenues


def matrice(lignes):
    """Vue « hôte × ports » du dernier passage : [{groupe, hote, ip, cellules: {"tcp/443": statut}}], colonnes triées."""
    hotes, cols = {}, set()
    for l in lignes:
        c = "%s/%d" % (l["proto"], l["port"])
        cols.add(c)
        h = hotes.setdefault(l["hote"], {"groupe": l["groupe"], "hote": l["hote"], "ip": l.get("ip"), "cellules": {}, "details": {}})
        h["cellules"][c] = l["statut"]; h["details"][c] = l["detail"]
    colonnes = sorted(cols, key=lambda c: (c.split("/")[0], int(c.split("/")[1])))
    return {"colonnes": colonnes, "lignes": sorted(hotes.values(), key=lambda h: (h["groupe"], h["hote"]))}


# ----------------------------------------------------------------- analyse Nebula (campus)
def _reseau(cidr):
    try:
        return ipaddress.ip_network(str(cidr), strict=False)
    except ValueError:
        return None


def analyse_nebula(vmap, clients, passages, gw_anomalies=None):
    """Croise : où sont les terminaux mobiles (SSID, VLAN, sous-réseau) selon Nebula, et quels VLAN ont été testés
    (adresse source des derniers passages par source). -> {vlans: [...], constats: [...], terminaux, couverts}."""
    vlans = []
    for v in (vmap or {}).get("vlans") or []:
        vlans.append({"vid": v.get("vid"), "subnet": v.get("subnet"), "net": _reseau(v.get("subnet")) if v.get("subnet") else None,
                      "ssids": [s.get("name") for s in v.get("ssids") or [] if s.get("enabled", True)], "guest": bool(v.get("guest")),
                      "gateway_interface": v.get("gateway_interface")})
    par_vid = {v["vid"]: v for v in vlans}

    def vlan_de_ip(ip):
        try:
            a = ipaddress.ip_address(str(ip))
        except ValueError:
            return None
        for v in vlans:
            if v["net"] and a in v["net"]:
                return v["vid"]
        return None

    mobiles = {}
    for c in clients or []:
        txt = " ".join(str(c.get(k) or "") for k in ("fabricant", "manufacturer", "os", "nom", "description"))
        if not MOBILE_RX.search(txt):
            continue
        vid = c.get("vlan")
        try:
            vid = int(vid) if vid not in (None, "") else vlan_de_ip(c.get("ip"))
        except (TypeError, ValueError):
            vid = vlan_de_ip(c.get("ip"))
        e = mobiles.setdefault(vid, {"n": 0, "ssids": set(), "fabricants": {}})
        e["n"] += 1
        if c.get("ssid"):
            e["ssids"].add(c["ssid"])
        f = str(c.get("fabricant") or c.get("manufacturer") or "?")
        e["fabricants"][f] = e["fabricants"].get(f, 0) + 1

    tests = {}
    for p in passages or []:
        vid = vlan_de_ip(p.get("ip_source")) if p.get("ip_source") else None
        t = tests.setdefault(vid, {"sources": set(), "dernier": None, "etat": None})
        t["sources"].add(p.get("source"))
        if not t["dernier"] or p["at"] > t["dernier"]["at"]:
            t["dernier"] = p

    lignes, constats = [], []
    for vid in sorted(set(mobiles) | {k for k in tests if k is not None}, key=lambda x: (x is None, x or 0)):
        v = par_vid.get(vid) or {}
        m = mobiles.get(vid) or {"n": 0, "ssids": set(), "fabricants": {}}
        t = tests.get(vid)
        etat = (t["dernier"]["bilan"]["etat"] if t and t["dernier"] and t["dernier"].get("bilan") else None)
        lignes.append({"vlan": vid, "subnet": v.get("subnet"), "ssids": sorted(set(v.get("ssids") or []) | m["ssids"]), "guest": v.get("guest", False),
                       "terminaux": m["n"], "fabricants": sorted(m["fabricants"].items(), key=lambda kv: -kv[1])[:5],
                       "teste": bool(t), "sources": sorted(t["sources"]) if t else [], "dernier_at": t["dernier"]["at"] if t else None, "etat": etat})
        nom = "VLAN %s" % vid if vid is not None else "VLAN inconnu"
        if m["n"] and not t:
            constats.append({"niveau": "alerte", "texte": "%s : %d terminal(aux) mobile(s) (%s) mais aucun test de flux depuis ce VLAN — les règles du pare-feu peuvent différer du VLAN testé."
                             % (nom, m["n"], ", ".join(sorted(m["ssids"])) or "filaire"), "vlan": vid})
        elif m["n"] and etat == "alerte":
            constats.append({"niveau": "critique", "texte": "%s : %d terminal(aux) mobile(s) et des flux éditeurs fermés ou inspectés au dernier test." % (nom, m["n"]), "vlan": vid})
        if m["n"] and v.get("guest"):
            constats.append({"niveau": "info", "texte": "%s est un réseau invité : la zone invité du pare-feu s'applique (vérifier qu'elle autorise les ports 5228-5230 et 5235-5236)." % nom, "vlan": vid})
    for a in gw_anomalies or []:
        if a.get("kind") in ("ssid_guest_not_isolated", "nat_any_remote", "nat_all_ports"):
            constats.append({"niveau": "info", "texte": a.get("message"), "vlan": None})
    constats.append({"niveau": "info", "texte": "Les règles de sécurité de la passerelle (security policies) ne sont pas lisibles par l'OpenAPI Nebula : "
                     "la preuve d'ouverture vient des tests depuis chaque VLAN, la règle elle-même se vérifie dans Nebula › Firewall."})
    return {"vlans": lignes, "constats": constats, "terminaux": sum(m["n"] for m in mobiles.values()),
            "couverts": sum(1 for l in lignes if l["terminaux"] and l["teste"]), "a_couvrir": sum(1 for l in lignes if l["terminaux"])}


def csv_passage(lignes):
    import csv
    import io
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["groupe", "hote", "ip", "proto", "port", "statut", "detail"])
    for l in lignes:
        w.writerow([l["groupe"], l["hote"], l.get("ip") or "", l["proto"], l["port"], l["statut"], l["detail"]])
    return "﻿" + buf.getvalue()


# ----------------------------------------------------------------- flux ignorés (#964)
def cle_ignore(hote, proto, port):
    return "%s|%s/%d" % (str(hote).lower(), str(proto).lower(), int(port))


def appliquer_ignores(lignes, ignores):
    """ignores : ensemble de clés cle_ignore -> lignes avec `ignore` (le statut mesuré est conservé)."""
    return [dict(l, ignore=cle_ignore(l["hote"], l["proto"], l["port"]) in (ignores or set())) for l in lignes]


def bilan_ignores(lignes):
    """Bilan qui ne compte pas les flux ignorés (comptés à part dans IGN)."""
    b = bilan([l for l in lignes if not l.get("ignore")])
    b["IGN"] = sum(1 for l in lignes if l.get("ignore"))
    b["total"] = len(lignes)
    return b


def alertants(lignes):
    """Lignes qui ouvrent une alerte : statut alertant et non ignorées (une ligne ignorée ferme son alerte)."""
    return [dict(l, statut=("IGN" if l.get("ignore") else l["statut"])) for l in lignes]


# ----------------------------------------------------------------- récapitulatif quotidien (#964)
def recap(sites, avec_ns=True, maintenant=None):
    """sites : [{site_id, nom, sources: [{source, at, lignes}]}] -> (sujet, texte, nombre de lignes signalées).
    Liste par site et par source les flux KO / OUVERT / CERT / INSPECTE (et NS si demandé), hors ignorés."""
    import datetime
    garder = set(ALERTANT) | ({"NS"} if avec_ns else set())
    blocs, n = [], 0
    for s in sites:
        lignes_site = []
        for src in s.get("sources") or []:
            sel = [l for l in src.get("lignes") or [] if l["statut"] in garder and not l.get("ignore")]
            if not sel:
                continue
            quand = datetime.datetime.fromtimestamp(src["at"]).strftime("%d/%m %H:%M") if src.get("at") else "?"
            lignes_site.append("  Source %s (dernier passage %s) :" % (src["source"], quand))
            for l in sorted(sel, key=lambda x: (x["statut"] == "NS", x["hote"], x["port"])):
                lignes_site.append("    %-8s %s %s/%d — %s" % (l["statut"], l["hote"], l["proto"], l["port"], l["detail"]))
                n += 1
        if lignes_site:
            blocs.append("%s (%s)\n%s" % (s.get("nom") or s["site_id"], s["site_id"], "\n".join(lignes_site)))
    if not blocs:
        return "[flux] récapitulatif : aucun flux fermé%s" % (" ni non servi" if avec_ns else ""), "Tous les flux suivis sont ouverts (hors flux ignorés).", 0
    sujet = "[flux] récapitulatif : %d flux à examiner" % n
    texte = ("Flux sortants exigés par les éditeurs — lignes KO (fermé / filtré / DNS), OUVERT (devrait être fermé), CERT "
             "(certificat), INSPECTE (inspection SSL)%s. Les flux marqués « ignorer » dans le hub n'apparaissent pas.\n\n" % (", NS (port non servi par l'hôte)" if avec_ns else "")) + "\n\n".join(blocs)
    return sujet, texte, n


# ----------------------------------------------------------------- pare-feu du site Nebula (#964)
def synthese_nat(nat_rules, clients_vus, maintenant):
    """Règles NAT (gwpolicy.parse_nat) + dernière présence de la cible dans l'historique des clients -> lignes + suggestions."""
    import gwpolicy
    vus = {}
    for c in clients_vus or []:
        ip = c.get("ip")
        if ip and (c.get("last_seen") or 0) > vus.get(ip, 0):
            vus[ip] = c.get("last_seen") or 0
    lignes, sugg = [], []
    for r in nat_rules or []:
        ip = r.get("private_ip")
        dv = vus.get(ip)
        sensibles = sorted(p for p in r.get("explicit_ports", r.get("ports") or []) if p in gwpolicy.SENSITIVE)
        l = {"type": r.get("kind"), "nom": r.get("name") or "", "actif": bool(r.get("enabled")), "interface": r.get("interface"), "ip_publique": r.get("public_ip"),
             "ip_privee": ip, "ports": "tous" if r.get("all_ports") else ",".join(str(p) for p in r.get("ports") or []), "ports_prives": ",".join(map(str, r.get("private_ports") or [])),
             "protocole": r.get("protocol"), "origine": "toute origine" if r.get("any_remote") else ", ".join(r.get("remote") or []),
             "sensibles": ["%d (%s)" % (p, gwpolicy.SENSITIVE[p]) for p in sensibles], "cible_vue": dv, "cible_inactive": bool(ip and dv is not None and maintenant - dv > 30 * 86400)}
        lignes.append(l)
        nom = l["nom"] or "%s → %s" % (l["type"], ip or "?")
        if not l["actif"]:
            sugg.append({"niveau": "info", "texte": "Règle NAT « %s » désactivée : la supprimer si elle n'a plus d'usage (lisibilité de la configuration)." % nom})
        elif ip and dv is None and clients_vus:
            sugg.append({"niveau": "alerte", "texte": "Règle NAT « %s » vers %s : cette adresse n'a jamais été vue parmi les clients du site (cible obsolète ou hors réseau supervisé ?)." % (nom, ip)})
        elif l["cible_inactive"]:
            sugg.append({"niveau": "alerte", "texte": "Règle NAT « %s » vers %s : cible absente depuis plus de 30 jours — publication à fermer si le service n'existe plus." % (nom, ip)})
        if l["actif"] and l["origine"] == "toute origine" and sensibles:
            sugg.append({"niveau": "critique", "texte": "Règle NAT « %s » : service(s) sensible(s) %s publiés sans restriction d'origine — limiter aux adresses sources connues ou passer par le VPN." % (nom, ", ".join(l["sensibles"]))})
        elif l["actif"] and l["origine"] == "toute origine" and l["ports"] == "tous":
            sugg.append({"niveau": "critique", "texte": "Règle NAT « %s » : tous les ports publiés sans restriction d'origine." % nom})
    return lignes, sugg


def zones(vmap):
    out = []
    for v in (vmap or {}).get("vlans") or []:
        out.append({"vlan": v.get("vid"), "sous_reseau": v.get("subnet"), "interface": v.get("gateway_interface"), "zone": "invité" if v.get("guest") else ("LAN" if v.get("gateway_interface") else "sans interface passerelle"),
                    "ssids": [s.get("name") for s in v.get("ssids") or [] if s.get("enabled", True)], "clients": v.get("clients") or 0})
    return out


def suggestions_zones(zs):
    s = []
    for z in zs:
        if z["zone"] == "sans interface passerelle" and (z["clients"] or z["ssids"]):
            s.append({"niveau": "info", "texte": "VLAN %s (%s) sans interface sur la passerelle : son trafic ne passe pas par le pare-feu (routé ailleurs ou VLAN isolé) — vérifier que c'est voulu." % (z["vlan"], ", ".join(z["ssids"]) or "filaire")})
    return s


def resume_journal(evenements, n=20):
    """Événements de la passerelle (forme variable) -> [{message, n, dernier}] les plus fréquents, catégories mises à plat."""
    cpt = {}
    for e in evenements or []:
        if not isinstance(e, dict):
            continue
        msg = str(e.get("message") or e.get("msg") or e.get("description") or e.get("event") or e.get("category") or "")[:160]
        msg = re.sub(r"\b\d{1,3}(\.\d{1,3}){3}(:\d+)?\b", "<ip>", msg)
        msg = re.sub(r"\b[0-9a-f]{2}(:[0-9a-f]{2}){5}\b", "<mac>", msg, flags=re.I)
        if not msg:
            continue
        t = e.get("timestamp") or e.get("time") or e.get("ts") or 0
        c = cpt.setdefault(msg, {"message": msg, "n": 0, "dernier": 0})
        c["n"] += 1
        try:
            c["dernier"] = max(c["dernier"], float(t) / (1000 if float(t) > 1e11 else 1))
        except (TypeError, ValueError):
            pass
    return sorted(cpt.values(), key=lambda c: -c["n"])[:n]


def diff_regles(ancien, nouveau):
    import difflib
    return "\n".join(difflib.unified_diff((ancien or "").splitlines(), (nouveau or "").splitlines(), "version précédente", "nouvelle version", lineterm="", n=1))
