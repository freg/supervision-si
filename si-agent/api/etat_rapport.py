# -*- coding: utf-8 -*-
"""#860 : AUDIT d'obsolescence et de support pour les décideurs -- page HTML autonome (lisible à l'écran, imprimable en
PDF depuis le navigateur), complément de l'Excel. Langage clair : pour chaque système en service, le système et les
logiciels clés, leur fin de support, qui les maintient, l'échéance et ce qu'il faut faire. Testé dans test_z_etat.py."""
import datetime as dt
import html

MAINTENEUR = {"debian": "Projet Debian", "ubuntu": "Canonical", "centos": "Red Hat / CentOS", "rocky": "Rocky Linux", "almalinux": "AlmaLinux",
              "alpine": "Alpine Linux", "windows": "Microsoft", "windows-server": "Microsoft", "proxmox-ve": "Proxmox", "proxmox-backup": "Proxmox",
              "php": "communauté PHP", "postgresql": "communauté PostgreSQL", "owncloud": "ownCloud", "nextcloud": "Nextcloud"}
NOM = {"proxmox-ve": "Proxmox VE (virtualisation)", "proxmox-backup": "Proxmox Backup (sauvegardes)", "php": "PHP (langage des sites web)",
       "postgresql": "PostgreSQL (base de données)", "owncloud": "ownCloud (partage de fichiers)", "nextcloud": "Nextcloud (partage de fichiers)"}
STYLE = """
:root { --fond:#15181d; --carte:#1d2229; --texte:#e8eaed; --doux:#9aa4b1; --bord:#2c333d; --rouge:#ff6b6b; --orange:#f5a524; --vert:#5cc98a; }
@media print { :root { --fond:#fff; --carte:#fff; --texte:#111; --doux:#555; --bord:#ccc; --rouge:#b00020; --orange:#a35b00; --vert:#1b7f3b; }
  .noprint { display:none } body { margin: 0 } section { break-inside: avoid } }
body { background:var(--fond); color:var(--texte); font:15px/1.5 system-ui, sans-serif; margin:24px auto; max-width:1100px; padding:0 16px; }
h1 { font-size:24px; margin:0 } h2 { font-size:18px; margin:28px 0 8px; border-bottom:1px solid var(--bord); padding-bottom:4px }
.doux { color:var(--doux) } .rouge { color:var(--rouge) } .orange { color:var(--orange) } .vert { color:var(--vert) }
.chiffres { display:grid; grid-template-columns:repeat(auto-fit, minmax(170px, 1fr)); gap:10px; margin:14px 0 }
.chiffre { background:var(--carte); border:1px solid var(--bord); border-radius:8px; padding:10px 12px }
.chiffre b { display:block; font-size:26px }
table { width:100%; border-collapse:collapse; font-size:14px } th, td { text-align:left; padding:6px 8px; border-bottom:1px solid var(--bord); vertical-align:top }
th { color:var(--doux); font-weight:600 } li { margin:4px 0 }
button { background:var(--carte); color:var(--texte); border:1px solid var(--bord); border-radius:6px; padding:6px 12px; cursor:pointer }
"""


def _e(x):
    return html.escape(str(x if x is not None else "—"))


def _jour(d):
    try:
        return dt.datetime.strptime(d, "%Y-%m-%d").strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return "—"


def _ts(d):
    try:
        return dt.datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=dt.timezone.utc).timestamp()
    except (TypeError, ValueError):
        return None


def echeance(fin, maintenant):
    """-> (texte, classe, rang) : « dépassée depuis 2 ans », « dans 4 mois »…"""
    t = _ts(fin)
    if t is None:
        return "inconnue", "doux", 3
    j = int((t - maintenant) // 86400)
    if j < 0:
        a = -j
        return ("dépassée depuis %s" % ("%d an(s)" % (a // 365) if a >= 365 else "%d mois" % max(1, a // 30))), "rouge", 0
    if j < 183:
        return "dans %d mois" % max(1, j // 30), "orange", 1
    if j < 730:
        return "dans %d mois" % (j // 30), "orange", 2
    return "dans %d ans" % (j // 365), "vert", 3


def elements(etat, maintenant):
    """Un élément par (système, composant suivi) : le système d'exploitation, puis les logiciels clés."""
    out = []
    for l in etat["systemes"]:
        if l["niveau"] == "inactif":
            continue
        qui = l.get("libelle") or ("serveur %s" % l["name"] if l["type"] == "nœud" else l["name"])
        roles = ", ".join(l.get("roles") or []) or "—"
        os_ = l["os"]
        if os_.get("nom"):
            txt, cls, rang = echeance(os_.get("fin"), maintenant)
            out.append({"systeme": qui, "role": roles, "quoi": "Système : %s" % os_["nom"], "maint": MAINTENEUR.get(os_.get("famille"), "—"),
                        "fin": os_.get("fin"), "echeance": txt, "cls": cls, "rang": rang, "secu": l.get("attente_secu")})
        for c in l.get("composants") or []:
            if c["statut"] == "maintenu par la distribution":
                continue
            txt, cls, rang = echeance(c.get("fin"), maintenant)
            out.append({"systeme": qui, "role": roles, "quoi": "%s %s" % (NOM.get(c["nom"], c["nom"]), c["version"]), "maint": MAINTENEUR.get(c["nom"], "—"),
                        "fin": c.get("fin"), "echeance": txt, "cls": cls, "rang": rang, "secu": None})
    out.sort(key=lambda e: (e["rang"], e["fin"] or "9999", e["systeme"]))
    return out


def page(etat, organisation="", maintenant=None):
    now = maintenant or etat.get("at")
    el = elements(etat, now)
    actifs = [l for l in etat["systemes"] if l["niveau"] != "inactif"]
    depasses = [e for e in el if e["rang"] == 0]
    six = [e for e in el if e["rang"] == 1]
    deux = [e for e in el if e["rang"] == 2]
    secu = [l for l in actifs if l.get("attente_secu")]
    expo = [l for l in actifs if l.get("expose") and l["score"] >= 3]
    inconnus = [l for l in actifs if l.get("source") == "aucune"]
    jour = dt.datetime.fromtimestamp(now, dt.timezone.utc).strftime("%d/%m/%Y")
    h = ["<!doctype html><html lang='fr'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'>",
         "<title>Audit des systèmes -- %s</title><style>%s</style></head><body>" % (_e(jour), STYLE),
         "<div class='noprint' style='float:right'><button onclick='window.print()'>Imprimer / PDF</button></div>",
         "<h1>Audit des systèmes informatiques%s</h1>" % (" -- %s" % _e(organisation) if organisation else ""),
         "<p class='doux'>Obsolescence et support des systèmes en service · situation au %s · relevé automatique</p>" % _e(jour),
         "<div class='chiffres'>",
         "<div class='chiffre'><b>%d</b>systèmes en service</div>" % len(actifs),
         "<div class='chiffre'><b class='rouge'>%d</b>éléments dont le support est terminé</div>" % len(depasses),
         "<div class='chiffre'><b class='orange'>%d</b>fins de support dans les 6 mois</div>" % len(six),
         "<div class='chiffre'><b class='orange'>%d</b>fins de support dans les 2 ans</div>" % len(deux),
         "<div class='chiffre'><b class='rouge'>%d</b>systèmes avec correctifs de sécurité non appliqués</div>" % len(secu),
         "<div class='chiffre'><b class='rouge'>%d</b>systèmes fragiles accessibles depuis Internet</div>" % len(expo), "</div>"]
    h.append("<h2>Ce qu'il faut retenir</h2><ul>")
    if depasses:
        h.append("<li><b>%d élément(s)</b> (système ou logiciel) ne reçoivent plus de correctifs de sécurité de leur éditeur : une faille découverte "
                 "aujourd'hui ne sera jamais corrigée.</li>" % len(depasses))
    if expo:
        h.append("<li><b>%d système(s)</b> dans ce cas sont accessibles depuis Internet : ce sont les plus exposés.</li>" % len(expo))
    if secu:
        h.append("<li><b>%d système(s)</b> ont des correctifs disponibles mais pas encore installés.</li>" % len(secu))
    if six or deux:
        h.append("<li><b>%d échéance(s)</b> tombent dans les deux ans : à inscrire au budget.</li>" % (len(six) + len(deux)))
    if inconnus:
        h.append("<li>%d système(s) n'ont pas pu être identifiés automatiquement (à compléter).</li>" % len(inconnus))
    if not (depasses or expo or secu or six or deux):
        h.append("<li>Aucun point critique : tous les systèmes suivis sont maintenus.</li>")
    h.append("</ul><h2>Calendrier des fins de support</h2>")
    h.append("<table><tr><th>Système</th><th>Rôle</th><th>Élément</th><th>Maintenu par</th><th>Fin du support</th><th>Échéance</th></tr>")
    for e in el:
        h.append("<tr><td>%s</td><td class='doux'>%s</td><td>%s</td><td>%s</td><td>%s</td><td class='%s'><b>%s</b></td></tr>" % (
            _e(e["systeme"]), _e(e["role"]), _e(e["quoi"]), _e(e["maint"]), _e(_jour(e["fin"])), e["cls"], _e(e["echeance"])))
    if not el:
        h.append("<tr><td colspan='6' class='doux'>Aucun système relevé.</td></tr>")
    h.append("</table><h2>Plan d'action proposé</h2><ol>")
    if depasses or expo:
        h.append("<li><b>Immédiat</b> : protéger les systèmes accessibles depuis Internet et plus maintenus (limiter l'accès), appliquer les correctifs "
                 "disponibles, puis mettre à niveau : %s.</li>" % _e(", ".join(sorted({e["systeme"] for e in depasses})[:12]) or "—"))
    if six:
        h.append("<li><b>Dans les 6 mois</b> : préparer la mise à niveau de %s.</li>" % _e(", ".join(sorted({e["systeme"] for e in six})[:12])))
    if deux:
        h.append("<li><b>Dans les 2 ans</b> : prévoir au budget la mise à niveau de %s.</li>" % _e(", ".join(sorted({e["systeme"] for e in deux})[:12])))
    h.append("<li><b>En continu</b> : correctifs appliqués chaque mois, suivi de cet audit (mis à jour automatiquement chaque jour).</li></ol>")
    h.append("<h2>Méthode</h2><p class='doux'>Relevé automatique sur chaque serveur (version du système, logiciels installés, date de la dernière "
             "mise à jour, correctifs en attente, services ouverts). Les dates de fin de support sont celles publiées par les éditeurs ; quand un "
             "logiciel est fourni par la distribution, il reste maintenu tant que la distribution l'est. Des supports étendus payants existent "
             "parfois (Debian ELTS, Ubuntu Pro, Windows ESU) : ils repoussent l'échéance mais ne remplacent pas la mise à niveau.</p>")
    h.append("</body></html>")
    return "".join(h)
