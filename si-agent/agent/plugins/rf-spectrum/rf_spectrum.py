#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sonde spectre radio (livraison #801) : un HackRF One (seul, ou dans une PortaPack mise en mode « HackRF ») balaie
les bandes Wi-Fi 2,4 et 5 GHz avec `hackrf_sweep` -- RÉCEPTION SEULE, la sonde n'appelle jamais un outil d'émission.
Elle voit ce que la carte Wi-Fi ne voit pas : tout ce qui occupe la bande sans être du Wi-Fi (four à micro-ondes,
émetteurs vidéo, Bluetooth, brouilleurs, équipements défectueux).

Par canal Wi-Fi de 20 MHz : puissance moyenne et max (dB relatifs, NON étalonnés en dBm), occupation = part des
mesures (case × balayage) au-dessus du bruit de fond de la bande (médiane) + seuil (10 dB par défaut) ; bruit de fond par bande ;
spectre résumé (pas de 2 MHz) pour le tracé. Constats : canal occupé ≥ 60 % (critique ≥ 85 %), HackRF absent.
À rapprocher de la sonde wifi-monitor : occupation au spectre élevée + peu de trames Wi-Fi = brouillage non Wi-Fi.

Usage : rf_spectrum.py [--bandes 2.4,5] [--balayages 10] [--lna 32] [--vga 20] [--seuil 10]"""
import json
import subprocess
import sys

BANDES = {"2.4": [(2400, 2500)], "5": [(5160, 5340), (5480, 5720)]}
CANAUX = [(c, 2407 + 5 * c) for c in range(1, 14)] + [(c, 5000 + 5 * c) for c in (36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140)]
INTERDITS = ("hackrf_transfer", "-t")      # garde-fou : jamais d'émission


def lancer(args, timeout=60):
    assert args[0] != INTERDITS[0], "émission interdite"
    try:
        p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")
    except (OSError, subprocess.SubprocessError) as e:
        return 127, "", str(e)


def info(texte):
    out = {}
    for cle, motif in (("serie", "Serial number:"), ("micrologiciel", "Firmware Version:"), ("carte", "Hardware Revision:"), ("carte", "Board ID Number:")):
        for ligne in texte.splitlines():
            if motif in ligne and cle not in out:
                out[cle] = ligne.split(":", 1)[1].strip()
    return out


def lire_balayage(texte):
    """Sortie CSV de hackrf_sweep -> [(MHz du centre de la case, dB)] (toutes lignes, tous balayages)."""
    out = []
    for ligne in texte.splitlines():
        f = [x.strip() for x in ligne.split(",")]
        if len(f) < 7:
            continue
        try:
            bas, largeur = float(f[2]), float(f[4])
            valeurs = [float(x) for x in f[6:]]
        except ValueError:
            continue
        for i, v in enumerate(valeurs):
            if v == v and v > -200:     # NaN / -inf écartés
                out.append(((bas + (i + 0.5) * largeur) / 1e6, v))
    return out


def centile(v, p):
    if not v:
        return None
    s = sorted(v)
    return s[min(len(s) - 1, int(p * (len(s) - 1)))]


def moyenne_db(v):
    import math
    return round(10 * math.log10(sum(10 ** (x / 10.0) for x in v) / len(v)), 1) if v else None


def analyser(mesures, bandes, seuil=10.0, pas=2):
    """-> (bandes [{nom, de, a, bruit_db}], canaux [{canal, freq, moy_db, max_db, occupation_pct}], spectre [[MHz, moy, max]])."""
    res_b, bruit = [], {}
    for nom in bandes:
        for de, a in BANDES.get(nom, []):
            v = [db for f, db in mesures if de <= f < a]
            b = centile(v, 0.50)   # #805 : médiane -- une case de FFT fluctue de ±10 dB ; le 10e centile mettait le bruit si bas
            # qu'un canal vide paraissait occupé à ~35 % (loi exponentielle : P(X > 10 × p10) = e^-1,05)
            bruit[(de, a)] = b
            res_b.append({"nom": nom, "de": de, "a": a, "bruit_db": round(b, 1) if b is not None else None, "mesures": len(v)})
    canaux = []
    for c, fc in CANAUX:
        plage = next(((de, a) for (de, a) in bruit if de <= fc < a), None)
        if not plage or bruit[plage] is None:
            continue
        v = [db for f, db in mesures if fc - 10 <= f < fc + 10]
        if not v:
            continue
        haut = sum(1 for x in v if x >= bruit[plage] + seuil)
        canaux.append({"canal": c, "freq": fc, "moy_db": moyenne_db(v), "max_db": round(max(v), 1), "occupation_pct": round(100.0 * haut / len(v), 1)})
    cases = {}
    for f, db in mesures:
        cases.setdefault(int(f // pas) * pas, []).append(db)
    spectre = [[k, moyenne_db(v), round(max(v), 1)] for k, v in sorted(cases.items())]
    return res_b, canaux, spectre


def constats(canaux):
    out = []
    for c in canaux:
        if c["occupation_pct"] >= 60:
            out.append({"code": "spectre-occupe:%s" % c["canal"], "severity": "critical" if c["occupation_pct"] >= 85 else "warning",
                        "message": "canal %s (%s MHz) occupé à %s %% au spectre (pic %s dB) : comparer avec le trafic Wi-Fi du même canal"
                                   % (c["canal"], c["freq"], c["occupation_pct"], c["max_db"])})
    return out


def collecter(bandes="2.4,5", balayages=10, lna=32, vga=20, seuil=10.0, run=lancer):
    rc, out, err = run(["hackrf_info"], timeout=15)
    if rc != 0 or "Serial number" not in out:
        return {"present": False, "alerts": [{"code": "spectre-absent", "severity": "warning",
                                              "message": "HackRF non détecté (débranché, PortaPack pas en mode HackRF, alimentation USB insuffisante ?) : %s"
                                                         % ((err or out).strip().splitlines() or ["?"])[-1][:160]}]}
    materiel = info(out)
    noms = [b.strip() for b in bandes.split(",") if b.strip() in BANDES]
    args = ["hackrf_sweep"]
    for n in noms:
        for de, a in BANDES[n]:
            args += ["-f", "%d:%d" % (de, a)]
    args += ["-w", "500000", "-l", str(int(lna)), "-g", str(int(vga)), "-N", str(int(balayages))]
    rc, out, err = run(args, timeout=90)
    mesures = lire_balayage(out)
    if not mesures:
        cause = (err.strip().splitlines() or ["?"])[-1][:200]   # #810 : un balayage vide est un constat (sinon la tuile n'affiche rien)
        return {"present": True, "hackrf": materiel, "error": "balayage vide : %s" % cause,
                "alerts": [{"code": "spectre-vide", "severity": "warning", "message": "HackRF présent mais balayage vide : %s" % cause}]}
    res_b, canaux, spectre = analyser(mesures, noms, float(seuil))
    return {"present": True, "hackrf": materiel, "bandes": res_b, "canaux": canaux,
            "spectre": spectre, "unite": "dB relatifs (non étalonnés)", "reglages": {"lna": lna, "vga": vga, "balayages": balayages, "seuil_db": seuil},
            "alerts": constats(canaux)}


def main(argv):
    o = {"bandes": "2.4,5", "balayages": 10, "lna": 32, "vga": 20, "seuil": 10.0}
    i = 0
    while i < len(argv):
        k = argv[i].lstrip("-")
        if k in o and i + 1 < len(argv):
            o[k] = argv[i + 1] if k == "bandes" else float(argv[i + 1])
            i += 2
            continue
        i += 1
    try:
        print(json.dumps(collecter(**o), ensure_ascii=False))
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"error": "balayage échoué : %s" % e}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
