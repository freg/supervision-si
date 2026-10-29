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

Épreuves sélectionnables (--epreuves cpu,memoire,disque) pour (re)jouer une partie. Chaque épreuve est bornée
(--max-s, défaut 300 s) et interruptible (sentinelle --stop) : plus de blocage de 30 min sur un disque qui cale.
Progression/tension écrite en continu en NDJSON (--live <fichier>) pour un suivi en direct depuis le hub.

Arguments : [--cpu-s 120] [--mem-pct 60] [--mem-max-mo 8192] [--disque-mo 1024] [--dossier T] [--epreuves L]
            [--max-s 300] [--live F] [--stop F]
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


def _stop_demande(chemin):
    """Sentinelle d'arrêt : vrai dès que le fichier `chemin` existe (créé par l'agent sur ordre du hub)."""
    return bool(chemin) and os.path.exists(chemin)


def _ecrire_live(chemin, data):
    """Ajoute un échantillon de tension/progression (NDJSON) au fichier de suivi direct. Jamais fatal."""
    if not chemin:
        return
    try:
        with open(chemin, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(dict(data, t=time.time()), ensure_ascii=False) + "\n")
    except OSError:
        pass


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


def epreuve_cpu(duree, coeurs=None, stop=None, live=None, max_s=None):
    """Tous les cœurs à 100 %. Interruptible (stop) et bornée (max_s) : surveillance pendant que la grappe tourne."""
    coeurs = coeurs or multiprocessing.cpu_count() or 1
    t0 = time.time()
    statut = "ok"
    pool = multiprocessing.Pool(coeurs)
    futur = pool.map_async(_travail, [(duree, i) for i in range(coeurs)])
    while not futur.ready():
        el = time.time() - t0
        _ecrire_live(live, {"phase": "processeur", "elapsed_s": round(el, 1), "cible_s": duree,
                            "pct": min(100, round(100 * el / max(duree, 1))), "coeurs": coeurs})
        if _stop_demande(stop):
            statut = "interrompu"; pool.terminate(); break
        if max_s and el > max_s:
            statut = "calé"; pool.terminate(); break
        time.sleep(1.0)
    if statut == "ok":
        res = futur.get()
        pool.close(); pool.join()
        return {"statut": "ok", "coeurs": coeurs, "duree_s": round(time.time() - t0, 1),
                "iterations": sum(r[0] for r in res), "erreurs_calcul": sum(r[1] for r in res)}
    pool.join()
    return {"statut": statut, "coeurs": coeurs, "duree_s": round(time.time() - t0, 1), "iterations": None, "erreurs_calcul": 0}


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


def epreuve_memoire(pct, max_mo, libre=None, stop=None, live=None, max_s=None):
    libre = libre if libre is not None else memoire_libre()
    taille = int(min((libre or 512 * 2 ** 20) * pct / 100.0, max_mo * 2 ** 20))
    bloc = 2 ** 20
    t0 = time.time()
    motifs, erreurs, alloue = (b"\x55", b"\xaa", b"\x00", b"\xff"), 0, 0
    tampons = []
    statut = "ok"
    try:
        for i in range(taille // bloc):
            tampons.append(bytearray(motifs[i % 4] * bloc))
            alloue += bloc
            if (i & 63) == 0:
                el = time.time() - t0
                _ecrire_live(live, {"phase": "mémoire", "sous": "allocation", "mo_faits": alloue // 2 ** 20,
                                    "mo_cible": taille // 2 ** 20, "pct": round(100 * (i + 1) / max(taille // bloc, 1)), "elapsed_s": round(el, 1)})
                if _stop_demande(stop):
                    statut = "interrompu"; break
                if max_s and el > max_s:
                    statut = "calé"; break
    except MemoryError:
        pass
    if statut == "ok":
        for passe in range(2):
            for i, t in enumerate(tampons):
                attendu = motifs[(i + passe) % 4] * bloc
                if passe:
                    t[:] = attendu
                if t != attendu:
                    erreurs += 1
            el = time.time() - t0
            _ecrire_live(live, {"phase": "mémoire", "sous": "vérification %d/2" % (passe + 1),
                                "mo_cible": alloue // 2 ** 20, "blocs_errones": erreurs, "elapsed_s": round(el, 1)})
            if _stop_demande(stop):
                statut = "interrompu"; break
            if max_s and el > max_s:
                statut = "calé"; break
    del tampons
    return {"statut": statut, "mo": alloue // 2 ** 20, "libre_mo": (libre or 0) // 2 ** 20,
            "duree_s": round(time.time() - t0, 1), "blocs_errones": erreurs}


def epreuve_disque(mo, dossier=None, stop=None, live=None, max_s=None):
    """Écrit puis relit un fichier, par blocs de 1 Mo avec contrôle entre blocs : un disque qui RALENTIT (débit qui
    s'effondre) est borné par max_s et rapporté « calé » au lieu de bloquer. (Un appel write/fsync TOTALEMENT figé
    ne peut être coupé que par l'agent -- voir la commande stop côté central.)"""
    dossier = dossier or tempfile.gettempdir()
    chemin = os.path.join(dossier, "si-agent-charge-%d.tmp" % os.getpid())
    bloc = os.urandom(2 ** 20)
    h_ecrit = hashlib.sha256()
    statut = "ok"
    ecrits = lus = 0
    t0 = t1 = t2 = time.time()
    try:
        with open(chemin, "wb") as fh:
            for i in range(mo):
                b = bloc[:-4] + i.to_bytes(4, "big")
                fh.write(b)
                h_ecrit.update(b)
                ecrits += 1
                if (i & 31) == 0:
                    el = time.time() - t0
                    _ecrire_live(live, {"phase": "disque", "sous": "écriture", "mo_faits": ecrits, "mo_cible": mo,
                                        "pct": round(100 * ecrits / max(mo, 1)), "mo_s": round(ecrits / max(el, 1e-3), 1), "elapsed_s": round(el, 1)})
                    if _stop_demande(stop):
                        statut = "interrompu"; break
                    if max_s and el > max_s:
                        statut = "calé"; break
            fh.flush()
            os.fsync(fh.fileno())
        t1 = time.time()
        if statut == "ok":
            h_lu = hashlib.sha256()
            with open(chemin, "rb") as fh:
                while True:
                    b = fh.read(2 ** 20)
                    if not b:
                        break
                    h_lu.update(b)
                    lus += 1
                    if (lus & 31) == 0:
                        el = time.time() - t1
                        _ecrire_live(live, {"phase": "disque", "sous": "lecture", "mo_faits": lus, "mo_cible": ecrits,
                                            "pct": round(100 * lus / max(ecrits, 1)), "mo_s": round(lus / max(el, 1e-3), 1), "elapsed_s": round(el, 1)})
                        if _stop_demande(stop):
                            statut = "interrompu"; break
                        if max_s and (time.time() - t0) > max_s:
                            statut = "calé"; break
            t2 = time.time()
        if statut != "ok":
            return {"statut": statut, "mo": ecrits, "dossier": dossier, "ecriture_mo_s": round(ecrits / max(t1 - t0, 1e-3), 1),
                    "lecture_mo_s": (round(lus / max(t2 - t1, 1e-3), 1) if lus else None), "identique": None, "erreur": statut}
        return {"statut": "ok", "mo": mo, "dossier": dossier, "ecriture_mo_s": round(mo / max(t1 - t0, 1e-3), 1),
                "lecture_mo_s": round(mo / max(t2 - t1, 1e-3), 1), "identique": h_ecrit.hexdigest() == h_lu.hexdigest(), "erreur": None}
    except OSError as e:
        return {"statut": "erreur", "mo": ecrits, "dossier": dossier, "identique": None, "erreur": str(e)[:200]}
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
    ap.add_argument("--epreuves", default="cpu,memoire,disque")   # sous-ensemble à (re)jouer
    ap.add_argument("--max-s", type=int, default=300)             # plafond PAR épreuve (anti-calage)
    ap.add_argument("--live")                                     # fichier NDJSON de progression/tension (suivi direct)
    ap.add_argument("--stop")                                     # sentinelle d'arrêt (fichier créé par l'agent)
    a = ap.parse_args(argv)
    sel = [x.strip() for x in (a.epreuves or "").split(",") if x.strip()]
    mx = max(10, a.max_s)
    debut = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _ecrire_live(a.live, {"phase": "début", "epreuves": sel, "max_s": mx})
    avant = etat_windows(None, runner)
    cpu = epreuve_cpu(max(5, min(a.cpu_s, 1800)), stop=a.stop, live=a.live, max_s=mx) if "cpu" in sel else None
    mem = epreuve_memoire(max(5, min(a.mem_pct, 85)), a.mem_max_mo, stop=a.stop, live=a.live, max_s=mx) if "memoire" in sel else None
    dsk = epreuve_disque(max(16, min(a.disque_mo, 16384)), a.dossier, stop=a.stop, live=a.live, max_s=mx) if "disque" in sel else None
    apres = etat_windows(debut, runner)
    al = []
    if cpu and cpu.get("erreurs_calcul"):
        al.append({"code": "charge-cpu", "severity": "critical", "message": "%d erreur(s) de calcul sous charge : processeur ou mémoire instable (surchauffe, alimentation, matériel)" % cpu["erreurs_calcul"]})
    if mem and mem.get("blocs_errones"):
        al.append({"code": "charge-memoire", "severity": "critical", "message": "%d bloc(s) mémoire relu(s) différents : barrette défectueuse probable" % mem["blocs_errones"]})
    if dsk and dsk.get("identique") is False:
        al.append({"code": "charge-disque", "severity": "critical", "message": "fichier relu différent de celui écrit : disque, câble ou contrôleur défectueux"})
    if dsk and dsk.get("statut") == "erreur" and dsk.get("erreur"):
        al.append({"code": "charge-disque-erreur", "severity": "warning", "message": "épreuve disque en erreur : %s" % dsk["erreur"]})
    for nom, r in (("processeur", cpu), ("mémoire", mem), ("disque", dsk)):
        if r and r.get("statut") == "calé":
            al.append({"code": "charge-calage", "severity": "critical", "message": "épreuve %s calée (aucune fin en %d s) : I/O ou système bloqué sous charge — signature d'un disque/contrôleur qui lâche" % (nom, mx)})
        elif r and r.get("statut") == "interrompu":
            al.append({"code": "charge-interrompu", "severity": "info", "message": "épreuve %s interrompue à la demande" % nom})
    if apres["evenements"]:
        al.append({"code": "charge-evenements", "severity": "critical", "message": "%d évènement(s) critique(s) pendant le test (%s)" % (
            len(apres["evenements"]), ", ".join(sorted({"%s %s" % (e.get("source"), e.get("id")) for e in apres["evenements"]}))[:200])})
    tmax = max([t.get("celsius") or 0 for t in apres["temperatures"]] or [0])
    if tmax >= 90:
        al.append({"code": "charge-temperature", "severity": "warning", "message": "température atteinte en fin de test : %s °C" % tmax})
    statuts = [r.get("statut") for r in (cpu, mem, dsk) if r]
    if any(x["severity"] == "critical" for x in al):
        verdict = "défaut reproduit"
    elif "interrompu" in statuts:
        verdict = "interrompu"
    elif not sel:
        verdict = "aucune épreuve"
    else:
        verdict = "aucun défaut reproduit"
    _ecrire_live(a.live, {"phase": "fini", "verdict": verdict})
    return {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "debut": debut, "epreuves": sel, "processeur": cpu, "memoire": mem, "disque": dsk,
            "temperatures_avant": avant["temperatures"], "temperatures_apres": apres["temperatures"], "evenements_pendant": apres["evenements"],
            "verdict": verdict, "alerts": al}


if __name__ == "__main__":
    multiprocessing.freeze_support()
    print(json.dumps(main(sys.argv[1:]), ensure_ascii=False))
