# -*- coding: utf-8 -*-
"""#919 : analyse technique à distance -- scripts PowerShell envoyés par le central (commande `shell`).

Modes, du plus sûr au plus large :
  off          -- refus (défaut) ;
  lecture      -- le poste vérifie AVANT d'exécuter que le script ne fait que lire (`garde.ps1` : analyse de l'arbre
                  syntaxique PowerShell -- cmdlets Get-* et de mise en forme, exécutables de diagnostic aux arguments
                  contrôlés, ni écriture de fichier, ni appel dynamique, ni méthode qui agit) ;
  intervention -- tout script (le hub demande confirmation ; tout est journalisé).
Le mode autorisé vient du central (réglage par agent dans le hub) et peut être plafonné sur le poste par
`remote_shell_max` dans agent.json -- l'administrateur local garde le dernier mot.

Chaque tâche tourne dans son thread : la sortie est relevée au fil de l'eau ; l'agent la pousse au central (mesure
`shell:<id>`) pendant l'exécution et à la fin ; délai maximal et arrêt à la demande (arbre de processus tué)."""
import hashlib
import os
import shutil
import subprocess
import sys
import threading
import time

MODES = ("off", "lecture", "intervention")
SORTIE_MAX = 400000        # caractères gardés (la fin de la sortie)
SORTIE_DIRECT = 64000      # caractères poussés pendant l'exécution
DELAI_MIN, DELAI_MAX, DELAI_DEFAUT = 5, 3600, 300
EN_COURS_MAX = 3           # tâches simultanées par poste
GARDE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "garde.ps1")
REFUS = "SI-SHELL-REFUS"


def rang(mode):
    return MODES.index(mode) if mode in MODES else 0


def mode_autorise(central, local_max=None):
    """Mode effectif : celui du central, plafonné par le maximum fixé sur le poste."""
    m = central if central in MODES else "off"
    if local_max in MODES and rang(local_max) < rang(m):
        m = local_max
    return m


def interpreteur(which=shutil.which, windows=None):
    windows = (sys.platform == "win32") if windows is None else windows
    if windows:
        return which("powershell.exe") or os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32",
                                                       "WindowsPowerShell", "v1.0", "powershell.exe")
    return which("pwsh")


def empreinte(script):
    return hashlib.sha256((script or "").encode("utf-8")).hexdigest()


def _tuer_arbre(proc):
    if proc is None or proc.poll() is not None:
        return
    if sys.platform == "win32":
        try:
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
            return
        except Exception:  # noqa: BLE001
            pass
    try:
        proc.kill()
    except Exception:  # noqa: BLE001
        pass


class Tache(object):
    """Une commande à distance : script écrit dans le dossier de l'agent, exécuté par la garde, sortie relevée."""

    def __init__(self, tid, script, mode="lecture", titre=None, delai=DELAI_DEFAUT, dossier=".", fmt="texte",
                 analyse=None, interp=None, clock=time.time):
        self.id, self.script, self.mode = tid, script or "", mode
        self.titre = (titre or "commande").strip()[:120]
        self.delai = max(DELAI_MIN, min(int(delai or DELAI_DEFAUT), DELAI_MAX))
        self.dossier, self.fmt, self.analyse, self.interp, self.clock = dossier, fmt, analyse, interp, clock
        self.statut, self.code, self.motif = "en_cours", None, None
        self.debut, self.fin = clock(), None
        self._morceaux, self._taille, self.tronque = [], 0, False
        self.version = 0                       # change à chaque nouvelle sortie / changement d'état
        self._lock = threading.Lock()
        self._arret = threading.Event()
        self._delai_depasse = False
        self._fini = False                     # posé en DERNIER (après fin / statut / code)
        self.proc = None
        self.thread = None

    # -- sortie -----------------------------------------------------------------------------------------------
    def _ajouter(self, texte):
        with self._lock:
            self._morceaux.append(texte)
            self._taille += len(texte)
            if self._taille > SORTIE_MAX * 2:                     # on compacte : on ne garde que la fin
                tout = "".join(self._morceaux)
                self._morceaux, self._taille, self.tronque = [tout[-SORTIE_MAX:]], SORTIE_MAX, True
            self.version += 1

    def sortie(self, limite=SORTIE_MAX):
        with self._lock:
            tout = "".join(self._morceaux)
        tronque = self.tronque or len(tout) > limite
        return (tout[-limite:] if len(tout) > limite else tout), tronque

    # -- exécution --------------------------------------------------------------------------------------------
    def demarrer(self, popen=subprocess.Popen):
        self.thread = threading.Thread(target=self._executer, args=(popen,), name="si-agent-shell-" + self.id, daemon=True)
        self.thread.start()

    def _executer(self, popen):
        chemin = None
        try:
            if not self.interp:
                raise RuntimeError("PowerShell introuvable sur ce poste")
            os.makedirs(self.dossier, exist_ok=True)
            chemin = os.path.join(self.dossier, "%s.ps1" % self.id)
            with open(chemin, "w", encoding="utf-8-sig") as fh:          # BOM : accents lus correctement par PowerShell 5.1
                fh.write(self.script)
            argv = [self.interp, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", GARDE,
                    "-Script", chemin, "-Mode", "intervention" if self.mode == "intervention" else "lecture"]
            kw = {"stdout": subprocess.PIPE, "stderr": subprocess.STDOUT, "stdin": subprocess.DEVNULL}
            if sys.platform == "win32":
                kw["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            self.proc = popen(argv, **kw)
            minuteur = threading.Timer(self.delai, self._depasse)
            minuteur.daemon = True
            minuteur.start()
            try:
                for brut in iter(self.proc.stdout.readline, b""):
                    self._ajouter(brut.decode("utf-8", "replace").replace("\r\n", "\n"))
                self.code = self.proc.wait()
                self.proc.stdout.close()
            finally:
                minuteur.cancel()
            premiere = self.sortie(2000)[0].lstrip()
            if self._arret.is_set():
                self.statut = "interrompu"
            elif self._delai_depasse:
                self.statut, self.motif = "delai", "délai de %d s dépassé" % self.delai
            elif self.code == 3 and premiere.startswith(REFUS):
                self.statut, self.motif = "refuse", "refusé par la garde du poste (mode lecture)"
            elif self.code == 0:
                self.statut = "fini"
            else:
                self.statut, self.motif = "erreur", "code de sortie %s" % self.code
        except Exception as exc:  # noqa: BLE001
            self.statut, self.motif = "erreur", str(exc)[:300]
        finally:
            if chemin:
                try:
                    os.remove(chemin)
                except OSError:
                    pass
            self.fin = self.clock()
            with self._lock:
                self.version += 1
                self._fini = True

    def _depasse(self):
        self._delai_depasse = True
        _tuer_arbre(self.proc)

    def arreter(self):
        self._arret.set()
        _tuer_arbre(self.proc)

    @property
    def termine(self):
        return self._fini

    def etat(self):
        """Données de la mesure `shell:<id>` (sortie complète à la fin, fin de sortie pendant l'exécution)."""
        sortie, tronque = self.sortie(SORTIE_MAX if self.termine else SORTIE_DIRECT)
        return {"id": self.id, "titre": self.titre, "mode": self.mode, "statut": self.statut, "code": self.code,
                "motif": self.motif, "debut": self.debut, "fin": self.fin, "delai": self.delai, "format": self.fmt,
                "analyse": self.analyse, "sha256": empreinte(self.script), "sortie": sortie, "tronque": tronque}
