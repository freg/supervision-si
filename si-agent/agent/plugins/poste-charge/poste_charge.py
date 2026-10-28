#!/usr/bin/env python3
"""Plugin si-agent « poste-charge » (#896) : tests de charge À LA DEMANDE (jamais planifiés) pour une panne intermittente.

Inactive par défaut : à lancer depuis le hub (fiche de l'agent › Sondes › Exécuter…). Trois épreuves successives :
- processeur : tous les cœurs à 100 % pendant --cpu-s secondes (calcul vérifié : un résultat faux = processeur ou
  mémoire instable) ;
- mémoire : --mem-pct % de la mémoire LIBRE (plafonné à --mem-max-mo) remplis d'un motif puis relus et vérifiés ;
- disque : fichier de --disque-mo Mo écrit (forcé sur le disque), relu et comparé, débits mesurés ; fichier effacé.
Sous Windows, avant et après : températures (zones ACPI) et évènements critiques apparus PENDANT le test (erreurs
matérielles WHEA, arrêts brutaux, erreurs disque, pilote graphique). Une erreur de calcul, de motif mémoire ou de
relecture disque est un constat critique : défaut matériel reproduit.

Arguments : [--cpu-s 120] [--mem-pct 60] [--mem-max-mo 8192] [--disque-mo 1024] [--dossier <temporaire>]
"""
import argparse
import hashlib
import json
import multiprocessing
import os
import subprocess
import sys
import tempfile
import time


def _travail(args):
    """Calcul déterministe pendant `duree` s ; renvoie (itérations, nombre de résultats faux)."""
    duree, graine = args
    fin, n, faux = time.time() + duree, 0, 0
    attendu = hashlib.sha256(str(graine).encode()).hexdigest()
    while time.time() < fin:
        for _ in range(2000):
            if hashlib.sha256(str(graine).encode()).hexdigest() != attendu:
                faux += 1
            n += 1
        x = 1.0
        for i in range(1, 5000):
            x = (x * 1.0000001 + i) % 1e9
    return n, faux


def epreuve_cpu(duree, coeurs=None):
    coeurs = coeurs or multiprocessing.cpu_count() or 1
    t0 = time.time()
    with multiprocessing.Pool(coeurs) as pool:
        res = pool.map(_travail, [(duree, i) for i in range(coeurs)])
    return {"coeurs": coeurs, "duree_s": round(time.time() - t0, 1), "iterations": sum(r[0] for r in res), "erreurs_calcul": sum(r[1] for r in res)}


def memoire_libre():
    """Octets de mémoire libre (Windows : GlobalMemoryStatusEx ; Linux : MemAvailable ; sinon None)."""
    if sys.platform == "win32":
        import ctypes

        class MS(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        m = MS()
        m.dwLength = ctypes.sizeof(MS)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return int(m.ullAvailPhys)
    try:
        with open("/proc/meminfo") as fh:
            for l in fh:
                if l.startswith("MemAvailable:"):
                    return int(l.split()[1]) * 1024
    except OSError:
        pass
    return None


def epreuve_memoire(pct, max_mo, libre=None):
    libre = libre if libre is not None else memoire_libre()
    taille = int(min((libre or 512 * 2 ** 20) * pct / 100.0, max_mo * 2 ** 20))
    bloc = 2 ** 20
    t0 = time.time()
    motifs, erreurs, alloue = (b"\x55", b"\xaa", b"\x00", b"\xff"), 0, 0
    tampons = []
    try:
        for i in range(taille // bloc):
            tampons.append(bytearray(motifs[i % 4] * bloc))
            alloue += bloc
    except MemoryError:
        pass
    for passe in range(2):
        for i, t in enumerate(tampons):
            attendu = motifs[(i + passe) % 4] * bloc
            if passe:
                t[:] = attendu
            if t != attendu:
                erreurs += 1
    del tampons
    return {"mo": alloue // 2 ** 20, "libre_mo": (libre or 0) // 2 ** 20, "duree_s": round(time.time() - t0, 1), "blocs_errones": erreurs}


def epreuve_disque(mo, dossier=None):
    dossier = dossier or tempfile.gettempdir()
    chemin = os.path.join(dossier, "si-agent-charge-%d.tmp" % os.getpid())
    bloc = os.urandom(2 ** 20)
    h_ecrit = hashlib.sha256()
    try:
        t0 = time.time()
        with open(chemin, "wb") as fh:
            for i in range(mo):
                b = bloc[:-4] + i.to_bytes(4, "big")
                fh.write(b)
                h_ecrit.update(b)
            fh.flush()
            os.fsync(fh.fileno())
        t1 = time.time()
        h_lu = hashlib.sha256()
        with open(chemin, "rb") as fh:
            while True:
                b = fh.read(2 ** 20)
                if not b:
                    break
                h_lu.update(b)
        t2 = time.time()
        return {"mo": mo, "dossier": dossier, "ecriture_mo_s": round(mo / max(t1 - t0, 1e-3), 1), "lecture_mo_s": round(mo / max(t2 - t1, 1e-3), 1),
                "identique": h_ecrit.hexdigest() == h_lu.hexdigest(), "erreur": None}
    except OSError as e:
        return {"mo": mo, "dossier": dossier, "identique": None, "erreur": str(e)[:200]}
    finally:
        try:
            os.remove(chemin)
        except OSError:
            pass


PS_ETAT = r"""[Console]::OutputEncoding=[Text.Encoding]::UTF8; $ErrorActionPreference='SilentlyContinue'
$t=@(); foreach($z in (Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature)){ $t+=[ordered]@{zone=$z.InstanceName; celsius=[math]::Round($z.CurrentTemperature/10-273.15,1)} }
$e=@(); if($args.Count -gt 0){ $d=[datetime]::Parse($args[0]).ToLocalTime()
 foreach($x in (Get-WinEvent -FilterHashtable @{LogName='System';StartTime=$d;Id=@(41,6008,1001,7,11,51,153,129,4101,2004)} -MaxEvents 200)){ $e+=[ordered]@{t=$x.TimeCreated.ToUniversalTime().ToString('o');source=$x.ProviderName;id=$x.Id} }
 foreach($x in (Get-WinEvent -FilterHashtable @{LogName='System';StartTime=$d;ProviderName='Microsoft-Windows-WHEA-Logger'} -MaxEvents 200)){ $e+=[ordered]@{t=$x.TimeCreated.ToUniversalTime().ToString('o');source=$x.ProviderName;id=$x.Id} } }
[ordered]@{temperatures=$t; evenements=$e} | ConvertTo-Json -Depth 4 -Compress"""


def etat_windows(depuis=None, runner=subprocess.run):
    if sys.platform != "win32":
        return {"temperatures": [], "evenements": []}
    argv = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", "& {" + PS_ETAT + "}"] + ([depuis] if depuis else [])
    try:
        p = runner(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
        s = (p.stdout or b"").decode("utf-8", "replace")
        d = json.loads(s[s.find("{"):]) if "{" in s else {}
        return {"temperatures": d.get("temperatures") or [], "evenements": d.get("evenements") or []}
    except Exception as e:  # noqa: BLE001
        return {"temperatures": [], "evenements": [], "erreur": str(e)[:200]}


def main(argv=None, runner=subprocess.run):
    ap = argparse.ArgumentParser()
    ap.add_argument("--cpu-s", type=int, default=120)
    ap.add_argument("--mem-pct", type=int, default=60)
    ap.add_argument("--mem-max-mo", type=int, default=8192)
    ap.add_argument("--disque-mo", type=int, default=1024)
    ap.add_argument("--dossier")
    a = ap.parse_args(argv)
    debut = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    avant = etat_windows(None, runner)
    cpu = epreuve_cpu(max(5, min(a.cpu_s, 1800)))
    mem = epreuve_memoire(max(5, min(a.mem_pct, 85)), a.mem_max_mo)
    dsk = epreuve_disque(max(16, min(a.disque_mo, 16384)), a.dossier)
    apres = etat_windows(debut, runner)
    al = []
    if cpu["erreurs_calcul"]:
        al.append({"code": "charge-cpu", "severity": "critical", "message": "%d erreur(s) de calcul sous charge : processeur ou mémoire instable (surchauffe, alimentation, matériel)" % cpu["erreurs_calcul"]})
    if mem["blocs_errones"]:
        al.append({"code": "charge-memoire", "severity": "critical", "message": "%d bloc(s) mémoire relu(s) différents : barrette défectueuse probable" % mem["blocs_errones"]})
    if dsk.get("identique") is False:
        al.append({"code": "charge-disque", "severity": "critical", "message": "fichier relu différent de celui écrit : disque, câble ou contrôleur défectueux"})
    if dsk.get("erreur"):
        al.append({"code": "charge-disque-erreur", "severity": "warning", "message": "épreuve disque interrompue : %s" % dsk["erreur"]})
    if apres["evenements"]:
        al.append({"code": "charge-evenements", "severity": "critical", "message": "%d évènement(s) critique(s) pendant le test (%s)" % (
            len(apres["evenements"]), ", ".join(sorted({"%s %s" % (e.get("source"), e.get("id")) for e in apres["evenements"]}))[:200])})
    tmax = max([t.get("celsius") or 0 for t in apres["temperatures"]] or [0])
    if tmax >= 90:
        al.append({"code": "charge-temperature", "severity": "warning", "message": "température atteinte en fin de test : %s °C" % tmax})
    return {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "debut": debut, "processeur": cpu, "memoire": mem, "disque": dsk,
            "temperatures_avant": avant["temperatures"], "temperatures_apres": apres["temperatures"], "evenements_pendant": apres["evenements"],
            "verdict": "défaut reproduit" if any(x["severity"] == "critical" for x in al) else "aucun défaut reproduit", "alerts": al}


if __name__ == "__main__":
    multiprocessing.freeze_support()
    print(json.dumps(main(sys.argv[1:]), ensure_ascii=False))
