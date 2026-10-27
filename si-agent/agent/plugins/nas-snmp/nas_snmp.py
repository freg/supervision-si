#!/usr/bin/env python3
"""Plugin si-agent « nas-snmp » (#883) : état et alertes d'un NAS par SNMP en LECTURE SEULE (QNAP QTS / QuTS d'abord).

Aucun réglage du NAS n'est modifié : la sonde interroge l'agent SNMP déjà actif avec les réglages existants (ceux de
Zenoss, par exemple) ; plusieurs outils peuvent lire en même temps. Relevé (MIB QNAP 1.3.6.1.4.1.55062, repli 24681) :
disques (modèle, série, état, température, capacité, heures de fonctionnement, attributs SMART critiques), RAID (niveau,
état), réserve de stockage, volumes (taille, libre), ventilateurs, applications (version installée / disponible),
micrologiciel. Constats : volume plein (80 / 90 %), disque en défaut ou chaud, secteurs réalloués / en attente /
illisibles, disque âgé (heures), RAID dégradé ou sans redondance, ventilateur arrêté, mises à jour disponibles.

Réglages : /etc/si-agent/nas-snmp.json (lisible par root seulement : la communauté est un secret) :
  [{"name": "nas-1", "host": "192.0.2.92", "community": "…", "version": "2c"}]
Arguments : [--config /etc/si-agent/nas-snmp.json] [--warn-pct 80] [--crit-pct 90] [--hours-old 50000]
Exige snmpwalk (paquet snmp).
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time

Q = "1.3.6.1.4.1.55062.1"
OLD = "1.3.6.1.4.1.24681.1"
SMART_CRIT = {5: "secteurs réalloués", 187: "erreurs non corrigées signalées", 197: "secteurs en attente", 198: "secteurs illisibles"}
LIGNE = re.compile(r"^(?:iso|\.?1)\.([0-9.]+)\s*=\s*(?:([A-Za-z0-9-]+):\s*)?(.*)$")


def parse_walk(texte):
    """Sortie snmpwalk (numérique) -> {oid: valeur}. « iso.3.6… » ou « .1.3.6… » ; chaînes sans guillemets, nombres en int."""
    out = {}
    for ligne in (texte or "").splitlines():
        m = LIGNE.match(ligne.strip())
        if not m:
            continue
        oid = "1." + m.group(1) if ligne.strip().startswith("iso.") else m.group(1).lstrip(".")
        if not oid.startswith("1."):
            oid = "1." + oid
        typ, val = (m.group(2) or "").upper(), m.group(3).strip()
        if typ == "STRING" or (val.startswith('"') and val.endswith('"')):
            val = val[1:-1] if val.startswith('"') and val.endswith('"') else val
        elif typ in ("INTEGER", "COUNTER32", "COUNTER64", "GAUGE32", "UNSIGNED32", "TIMETICKS"):
            try:
                val = int(re.match(r"-?\d+", val.split("(")[-1].rstrip(")")).group(0)) if typ == "TIMETICKS" else int(val.split()[0])
            except (ValueError, AttributeError):
                pass
        out[oid] = val
    return out


def table(d, base, colonnes):
    """Colonnes d'une table SNMP -> [{nom: valeur}] par index."""
    lignes = {}
    for oid, v in d.items():
        if not oid.startswith(base + "."):
            continue
        reste = oid[len(base) + 1:].split(".", 1)
        if len(reste) != 2 or not reste[0].isdigit():
            continue
        col, idx = int(reste[0]), reste[1]
        if col in colonnes:
            lignes.setdefault(idx, {"_idx": idx})[colonnes[col]] = v
    return [lignes[k] for k in sorted(lignes, key=lambda x: [int(p) for p in x.split(".") if p.isdigit()])]


def releve(d, warn_pct=80, crit_pct=90, hours_old=50000):
    """{oid: valeur} -> {disques, raid, reserves, volumes, ventilateurs, applications, systeme, alertes}."""
    disques = table(d, Q + ".10.2.1", {2: "emplacement", 3: "marque", 4: "modele", 5: "serie", 6: "interface", 7: "etat", 8: "temperature", 9: "octets"})
    smart = table(d, Q + ".10.3.1", {2: "dev", 3: "attribut", 4: "id", 5: "valeur", 6: "pire", 7: "seuil", 8: "brut", 9: "etat"})
    raid = table(d, Q + ".10.5.1", {2: "id", 3: "dev", 4: "etat", 5: "octets", 7: "niveau"})
    reserves = table(d, Q + ".10.7.1", {2: "id", 3: "octets", 4: "libre_octets", 5: "etat"})
    volumes = table(d, Q + ".10.9.1", {2: "id", 3: "ko", 4: "libre_ko", 5: "etat", 7: "leger", 8: "nom"})
    fans = table(d, Q + ".12.9.1", {2: "nom", 3: "tours"})
    apps = table(d, Q + ".15.1.1", {2: "nom", 3: "version", 4: "date", 5: "disponible", 6: "actif"})
    if not disques:   # micrologiciel plus ancien : ancienne MIB
        disques = [dict(x, octets=None) for x in table(d, OLD + ".3.11.1", {2: "emplacement", 3: "temperature", 5: "modele", 6: "octets", 7: "etat"})
                   if str(x.get("modele", "--")) != "--"]
    if not volumes:
        volumes = table(d, OLD + ".3.17.1", {2: "nom", 4: "ko", 5: "libre_ko", 6: "etat"})
    # SMART : les lignes sont rangées par disque (/dev/sda…) dans l'ordre des disques présents
    devs = list(dict.fromkeys(s.get("dev") for s in smart if s.get("dev")))
    par_dev = {dev: [s for s in smart if s.get("dev") == dev] for dev in devs}
    for i, disque in enumerate(disques):
        attrs = par_dev.get(devs[i], []) if i < len(devs) else []
        brut = {int(s["id"]): s.get("brut") for s in attrs if str(s.get("id", "")).isdigit()}
        disque["heures"] = brut.get(9)
        disque["smart"] = {SMART_CRIT[k]: brut[k] for k in SMART_CRIT if k in brut}
        disque["smart_ko"] = [s.get("attribut") for s in attrs if str(s.get("etat", "Good")).lower() not in ("good", "ok", "")]
    for v in volumes:
        if isinstance(v.get("ko"), int) and v["ko"] > 0 and isinstance(v.get("libre_ko"), int):
            v["pct"] = round(100.0 * (v["ko"] - v["libre_ko"]) / v["ko"], 1)
    alertes = []

    def alerte(code, gravite, message):
        alertes.append({"code": code, "severity": gravite, "message": message})
    for v in volumes:
        p = v.get("pct")
        if p is not None and p >= crit_pct:
            alerte("nas-volume-plein@%s" % v.get("nom"), "critical", "volume %s rempli à %s %%" % (v.get("nom"), p))
        elif p is not None and p >= warn_pct:
            alerte("nas-volume-plein@%s" % v.get("nom"), "warning", "volume %s rempli à %s %%" % (v.get("nom"), p))
        if str(v.get("etat", "Ready")).lower() not in ("ready", "ok", "normal"):
            alerte("nas-volume-etat@%s" % v.get("nom"), "critical", "volume %s : état %s" % (v.get("nom"), v.get("etat")))
    for disque in disques:
        nom = "disque %s (%s)" % (disque.get("emplacement"), disque.get("modele") or "?")
        if str(disque.get("etat", "Good")).lower() not in ("good", "ok"):
            alerte("nas-disque-etat@%s" % disque.get("emplacement"), "critical", "%s : état %s" % (nom, disque.get("etat")))
        t = disque.get("temperature")
        if isinstance(t, int) and t >= 60:
            alerte("nas-disque-chaud@%s" % disque.get("emplacement"), "critical", "%s à %d °C" % (nom, t))
        elif isinstance(t, int) and t >= 50:
            alerte("nas-disque-chaud@%s" % disque.get("emplacement"), "warning", "%s à %d °C" % (nom, t))
        for lib, n in (disque.get("smart") or {}).items():
            if isinstance(n, int) and n > 0:
                grave = "critical" if lib in ("secteurs en attente", "secteurs illisibles") else "warning"
                alerte("nas-disque-smart@%s" % disque.get("emplacement"), grave, "%s : %d %s" % (nom, n, lib))
        if disque.get("smart_ko"):
            alerte("nas-disque-smart@%s" % disque.get("emplacement"), "critical", "%s : attributs SMART en défaut (%s)" % (nom, ", ".join(disque["smart_ko"][:5])))
        h = disque.get("heures")
        if isinstance(h, int) and h >= hours_old:
            alerte("nas-disque-age@%s" % disque.get("emplacement"), "warning",
                   "%s : %d h de fonctionnement (%.1f ans) -- remplacement à prévoir" % (nom, h, h / 8766.0))
    for r in raid:
        if str(r.get("etat", "Ready")).lower() not in ("ready", "ok", "normal"):
            alerte("nas-raid@%s" % r.get("dev"), "critical", "RAID %s (%s) : état %s" % (r.get("dev"), r.get("niveau"), r.get("etat")))
        if str(r.get("niveau", "")).lower() in ("single", "0", "jbod"):
            alerte("nas-raid-redondance@%s" % r.get("dev"), "warning", "RAID %s en %s : aucune redondance (vérifier s'il porte des données ou un cache)" % (r.get("dev"), r.get("niveau")))
    for f in fans:
        if isinstance(f.get("tours"), int) and f["tours"] == 0:
            alerte("nas-ventilateur@%s" % f.get("nom"), "critical", "%s arrêté" % f.get("nom"))
    maj = [a for a in apps if a.get("disponible") and a.get("version") and a["disponible"] != a["version"]]
    for a in apps:
        a["actif"] = a.get("actif") == 1 if isinstance(a.get("actif"), int) else a.get("actif")
        a["mise_a_jour"] = bool(a.get("disponible") and a.get("version") and a["disponible"] != a["version"])
    if maj:
        alerte("nas-applications-maj", "info", "mise(s) à jour d'applications disponible(s) : %s" % ", ".join(
            "%s %s → %s" % (a["nom"], a["version"], a["disponible"]) for a in maj))
    systeme = {k: d.get("%s.12.%d.0" % (Q, n)) for k, n in (("modele", 3), ("nom", 4), ("micrologiciel", 6), ("maj_micrologiciel", 7),
                                                             ("temp_cpu", 10), ("temp_systeme", 11), ("alimentation", 19))}
    if str(systeme.get("maj_micrologiciel") or "").lower() in ("1", "yes", "true", "available"):
        alerte("nas-micrologiciel", "warning", "mise à jour du système du NAS disponible")
    return {"disques": disques, "raid": raid, "reserves": reserves, "volumes": volumes, "ventilateurs": fans, "applications": apps,
            "systeme": systeme, "alertes": alertes}


def lire(cible, runner=subprocess.run, exe="snmpwalk"):
    args = [exe, "-v", str(cible.get("version") or "2c"), "-c", cible["community"], "-On", "-t", "5", "-r", "1", cible["host"]]
    texte = ""
    for base in (Q, OLD + ".3", OLD + ".4"):
        p = runner(args + [base], capture_output=True, text=True, timeout=120)
        if p.returncode != 0 and not p.stdout:
            raise RuntimeError((p.stderr or "snmpwalk en échec").strip()[:200])
        texte += p.stdout
    sget = runner([exe.replace("snmpwalk", "snmpget")] + args[1:] + ["%s.12.%d.0" % (Q, n) for n in (3, 4, 6, 7, 10, 11, 19)],
                  capture_output=True, text=True, timeout=60)
    return texte + (sget.stdout or "")


def main(argv=None, runner=subprocess.run, which=shutil.which):
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="/etc/si-agent/nas-snmp.json")
    ap.add_argument("--warn-pct", type=float, default=80)
    ap.add_argument("--crit-pct", type=float, default=90)
    ap.add_argument("--hours-old", type=int, default=50000)
    a = ap.parse_args(argv)
    out = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "nas": [], "alerts": []}
    exe = which("snmpwalk")
    if not exe:
        out["alerts"].append({"code": "nas-snmp-outil", "severity": "warning", "message": "snmpwalk absent sur l'hôte de l'agent (Debian : apt install snmp)"})
        return out
    try:
        with open(a.config, encoding="utf-8") as fh:
            cibles = [c for c in json.load(fh) if isinstance(c, dict) and c.get("host") and c.get("community")]
    except (OSError, ValueError) as e:
        out["alerts"].append({"code": "nas-snmp-config", "severity": "warning", "message": "réglages illisibles (%s) : %s" % (a.config, e)})
        return out
    for c in cibles:
        nom = c.get("name") or c["host"]
        try:
            r = releve(parse_walk(lire(c, runner, exe)), a.warn_pct, a.crit_pct, a.hours_old)
            r.update(name=nom, host=c["host"], ok=True, error=None)
            for x in r["alertes"]:
                out["alerts"].append(dict(x, code=x["code"] + "#" + nom, message="%s : %s" % (nom, x["message"])))
        except Exception as e:  # noqa: BLE001 -- un NAS injoignable n'empêche pas les autres
            r = {"name": nom, "host": c["host"], "ok": False, "error": str(e)[:200]}
            out["alerts"].append({"code": "nas-injoignable#" + nom, "severity": "critical", "message": "%s injoignable en SNMP : %s" % (nom, str(e)[:150])})
        out["nas"].append(r)
    return out


if __name__ == "__main__":
    print(json.dumps(main(sys.argv[1:]), ensure_ascii=False))
