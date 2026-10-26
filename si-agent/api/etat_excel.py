# -*- coding: utf-8 -*-
"""#857 : état des lieux des systèmes -> classeur Excel pour les décideurs : court, en clair, sans jargon.
Feuilles : Synthèse (chiffres clés, priorités), Systèmes (un par ligne, niveau et action proposée), Dépendances,
Évolution (suivi dans le temps). Testé dans test_z_etat.py."""
import datetime as dt
import io

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

TEINTES = {"urgent": "F4B6B6", "à planifier": "F9D9A8", "à surveiller": "FFF2B3", "ok": "CDEBC5", "inactif": "E0E0E0"}
LIBELLE_NIVEAU = {"urgent": "Urgent", "à planifier": "À planifier", "à surveiller": "À surveiller", "ok": "À jour", "inactif": "Arrêté"}
TYPE = {"nœud": "Serveur physique", "VM": "Machine virtuelle", "CT": "Conteneur", "serveur": "Serveur", "poste": "Poste de travail"}
USAGE = {"fort": "Forte", "moyen": "Moyenne", "faible": "Faible", "nul": "Arrêté"}
TITRE = Font(bold=True, size=14)
GRAS = Font(bold=True)
ENTETE = PatternFill("solid", fgColor="D9E1F2")


def _jour(t):
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%d/%m/%Y") if t else "—"


def _fin(d):
    try:
        return dt.datetime.strptime(d, "%Y-%m-%d").strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return "—"


def nom(l):
    return l.get("libelle") or ("%s (%s)" % (l["name"], l["key"]) if l["type"] != "nœud" else "Serveur %s" % l["name"])


def raisons_claires(l):
    """Raisons sans jargon technique (pas de numéros de port, pas de noms de paquets)."""
    out = []
    if l["os"]["statut"] == "obsolète":
        out.append("système d'exploitation qui ne reçoit plus de correctifs depuis le %s" % _fin(l["os"]["fin"]))
    elif l["os"]["statut"] == "fin proche":
        out.append("fin des correctifs le %s" % _fin(l["os"]["fin"]))
    if l.get("attente_secu"):
        out.append("correctifs de sécurité disponibles mais non appliqués")
    if l.get("maj_jours") is not None and l["maj_jours"] > 365:
        out.append("pas mis à jour depuis plus d'un an")
    if any(c["statut"] == "obsolète" for c in l["composants"]):
        out.append("logiciel installé dans une version qui n'est plus maintenue")
    elif any(c["statut"] == "fin proche" for c in l["composants"]):
        out.append("logiciel installé dont le support se termine bientôt")
    if l["os"]["statut"] in ("inconnu", "non relevé") and l["status"] == "running":
        out.append("système non identifié automatiquement")
    if l.get("expose") and l["score"] >= 3:
        out.append("accessible depuis Internet")
    if l["dependants"]:
        out.append("d'autres systèmes en dépendent")
    return "; ".join(out) or "—"


def _clair(t):
    """Action sans nom de logiciel ni numéro de version technique."""
    import re
    m = re.match(r"^planifier le remplacement de .* avant le (\d{4}-\d{2}-\d{2})$", t)
    if m:
        return "planifier la mise à jour d'un logiciel installé avant le %s" % _fin(m.group(1))
    if t.startswith("remplacer "):
        return "remplacer un logiciel installé par une version maintenue"
    if t.startswith("mettre à niveau le système"):
        return "mettre à niveau le système d'exploitation vers une version maintenue"
    if t.startswith("planifier la mise à niveau du système avant le "):
        return "planifier la mise à niveau du système avant le %s" % _fin(t.rsplit(" ", 1)[-1])
    return t


def action_claire(l):
    a = list(dict.fromkeys(_clair(x) for x in l.get("actions") or []))
    if not a:
        return "Aucune action" if l["niveau"] == "ok" else "Surveiller"
    t = a[0]
    return t[0].upper() + t[1:] + (" (et %d autre(s) action(s))" % (len(a) - 1) if len(a) > 1 else "")


def _largeurs(ws, largeurs):
    for i, w in enumerate(largeurs, 1):
        ws.column_dimensions[get_column_letter(i)].width = w


def _entete(ws, ligne, valeurs):
    for i, v in enumerate(valeurs, 1):
        c = ws.cell(row=ligne, column=i, value=v)
        c.font, c.fill = GRAS, ENTETE
        c.alignment = Alignment(wrap_text=True, vertical="top")


def classeur(etat, tendance=None, organisation="", maintenant=None):
    """-> octets du fichier .xlsx."""
    now = maintenant or etat.get("at")
    actifs = [l for l in etat["systemes"] if l["niveau"] != "inactif"]
    r = etat["resume"]
    wb = Workbook()
    ws = wb.active
    ws.title = "Synthèse"
    ws["A1"] = "État des lieux des systèmes informatiques%s" % (" -- %s" % organisation if organisation else "")
    ws["A1"].font = TITRE
    ws["A2"] = "Situation au %s" % _jour(now)
    ws["A4"], ws["A4"].font = "Systèmes en service", GRAS
    lignes = [("Urgent : à traiter sans attendre", r.get("urgent", 0), "urgent"), ("À planifier dans les prochains mois", r.get("à planifier", 0), "à planifier"),
              ("À surveiller", r.get("à surveiller", 0), "à surveiller"), ("À jour", r.get("ok", 0), "ok"), ("Arrêtés (non utilisés)", r.get("inactif", 0), "inactif")]
    for i, (lib, n, niv) in enumerate(lignes, 5):
        ws.cell(row=i, column=1, value=lib).fill = PatternFill("solid", fgColor=TEINTES[niv])
        ws.cell(row=i, column=2, value=n)
    ws["A11"], ws["A11"].font = "Points clés", GRAS
    cles = []
    if r.get("obsoletes"):
        cles.append("%d système(s) en service ne reçoivent plus de correctifs de sécurité de leur éditeur." % r["obsoletes"])
    if r.get("secu"):
        cles.append("%d système(s) ont des correctifs de sécurité disponibles mais non appliqués." % r["secu"])
    if r.get("exposes"):
        cles.append("%d système(s) sont accessibles depuis Internet." % r["exposes"])
    dep = sum(1 for l in actifs if len(l["dependants"]) >= 2)
    if dep:
        cles.append("%d système(s) sont utilisés par plusieurs autres : une panne aurait des effets en chaîne." % dep)
    if not cles:
        cles.append("Aucun point critique relevé.")
    for i, t in enumerate(cles, 12):
        ws.cell(row=i, column=1, value="• " + t)
    base = 13 + len(cles)
    ws.cell(row=base, column=1, value="Priorités").font = GRAS
    _entete(ws, base + 1, ["Système", "Pourquoi", "Action proposée", "Niveau"])
    prio = [l for l in actifs if l["niveau"] in ("urgent", "à planifier")][:10]
    for i, l in enumerate(prio, base + 2):
        ws.cell(row=i, column=1, value=nom(l))
        ws.cell(row=i, column=2, value=raisons_claires(l)).alignment = Alignment(wrap_text=True, vertical="top")
        ws.cell(row=i, column=3, value=action_claire(l)).alignment = Alignment(wrap_text=True, vertical="top")
        c = ws.cell(row=i, column=4, value=LIBELLE_NIVEAU[l["niveau"]])
        c.fill = PatternFill("solid", fgColor=TEINTES[l["niveau"]])
    if not prio:
        ws.cell(row=base + 2, column=1, value="Aucune priorité.")
    _largeurs(ws, [48, 60, 50, 14])

    ws2 = wb.create_sheet("Systèmes")
    cols = ["Système", "Nature", "Rôle", "Système d'exploitation", "Fin des correctifs", "Dernière mise à jour", "Correctifs de sécurité en attente",
            "Utilisation", "Accessible depuis Internet", "Utilisé par (nombre de systèmes)", "Niveau", "Pourquoi", "Action proposée"]
    _entete(ws2, 1, cols)
    for i, l in enumerate(etat["systemes"], 2):
        vals = [nom(l), TYPE.get(l["type"], l["type"]), ", ".join(l["roles"]) or "—", l["os"]["nom"] or "non relevé", _fin(l["os"]["fin"]),
                _jour(l["maj_at"]), l["attente_secu"] if l["attente_secu"] is not None else "—", USAGE.get(l["usage"], l["usage"]),
                "Oui" if l["expose"] else "Non", len(l["dependants"]), LIBELLE_NIVEAU[l["niveau"]], raisons_claires(l), action_claire(l)]
        for j, v in enumerate(vals, 1):
            c = ws2.cell(row=i, column=j, value=v)
            c.alignment = Alignment(wrap_text=True, vertical="top")
        ws2.cell(row=i, column=11).fill = PatternFill("solid", fgColor=TEINTES[l["niveau"]])
    ws2.freeze_panes = "B2"
    ws2.auto_filter.ref = "A1:%s%d" % (get_column_letter(len(cols)), max(1, len(etat["systemes"]) + 1))
    _largeurs(ws2, [34, 16, 30, 26, 14, 14, 12, 12, 12, 12, 13, 50, 44])

    ws3 = wb.create_sheet("Dépendances")
    _entete(ws3, 1, ["Système", "utilise", "pour"])
    noms = {l["key"]: nom(l) for l in etat["systemes"]}
    for i, d in enumerate(etat.get("dependances") or [], 2):
        ws3.cell(row=i, column=1, value=noms.get(d["de"], d["de"]))
        ws3.cell(row=i, column=2, value=noms.get(d["vers"], d["vers"]))
        ws3.cell(row=i, column=3, value=d["nature"])
    if not etat.get("dependances"):
        ws3.cell(row=2, column=1, value="Aucune dépendance relevée entre les systèmes suivis.")
    _largeurs(ws3, [40, 40, 30])

    ws4 = wb.create_sheet("Évolution")
    _entete(ws4, 1, ["Jour", "Urgent", "À planifier", "À surveiller", "À jour", "Arrêtés", "Plus maintenus", "Correctifs en attente"])
    for i, t in enumerate((tendance or [])[-120:], 2):
        for j, k in enumerate(["jour", "urgent", "à planifier", "à surveiller", "ok", "inactif", "obsoletes", "secu"], 1):
            ws4.cell(row=i, column=j, value=_fin(t.get(k)) if k == "jour" else t.get(k))
    if not tendance:
        ws4.cell(row=2, column=1, value="Le suivi commence aujourd'hui : une ligne est ajoutée chaque jour.")
    _largeurs(ws4, [14, 10, 12, 12, 10, 10, 14, 18])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
