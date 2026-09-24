# -*- coding: utf-8 -*-
"""Installation / désinstallation de logiciels depuis le hub (livraison #595,
commande `software_action`) -- via le gestionnaire de paquets du poste :
apt (Debian/Ubuntu), dnf (Fedora/RHEL), brew (macOS), winget ou choco
(Windows). Paquet strictement validé (pas d'option, pas d'espace), mode
silencieux, délai borné ; jamais de script arbitraire. Logique pure
(`build_argv`, `interpret`) testable sans système."""
import platform
import re
import shutil

ACTIONS = ("install", "uninstall")
MANAGERS = ("apt", "dnf", "brew", "winget", "choco")
PKG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+@/-]{0,127}$")  # winget accepte « Editeur.Produit »


def default_manager(system=None, which=None):
    system = (system or platform.system()).lower()
    which = which or shutil.which
    if system == "windows":
        return "winget" if which("winget") else "choco" if which("choco") else None
    if system == "darwin":
        return "brew" if which("brew") else None
    for m in ("apt-get", "dnf"):
        if which(m):
            return "apt" if m == "apt-get" else "dnf"
    return None


def build_argv(params, system=None, which=None):
    """-> (argv, env, erreur)."""
    action = str((params or {}).get("action") or "").lower()
    if action not in ACTIONS:
        return None, None, "action : install ou uninstall"
    package = str((params or {}).get("package") or "").strip()
    if not PKG_RE.match(package) or package.startswith("-"):
        return None, None, "nom de paquet invalide"
    manager = str((params or {}).get("manager") or "").lower() or default_manager(system, which)
    if manager not in MANAGERS:
        return None, None, "gestionnaire de paquets inconnu ou absent (%s)" % (manager or "aucun")
    env = {}
    if manager == "apt":
        env = {"DEBIAN_FRONTEND": "noninteractive"}
        argv = ["apt-get", "-y", "-q", "install" if action == "install" else "remove", package]
    elif manager == "dnf":
        argv = ["dnf", "-y", "-q", "install" if action == "install" else "remove", package]
    elif manager == "brew":
        argv = ["brew", "install" if action == "install" else "uninstall", package]
    elif manager == "winget":
        argv = ["winget", "install" if action == "install" else "uninstall", "--id", package, "--exact", "--silent",
                "--accept-package-agreements", "--accept-source-agreements", "--disable-interactivity"]
        if action == "uninstall":
            argv = ["winget", "uninstall", "--id", package, "--exact", "--silent", "--accept-source-agreements", "--disable-interactivity"]
    else:
        argv = ["choco", "install" if action == "install" else "uninstall", package, "-y", "--no-progress"]
    return argv, env, None


def interpret(res, argv):
    out = ((res.stdout or "") + ("\n" + res.stderr if res.stderr else "")).strip()
    return {"ok": res.returncode == 0, "code": res.returncode, "error": None if res.returncode == 0 else (out.splitlines() or ["échec (code %s)" % res.returncode])[-1][:300],
            "output": out[-4000:], "argv": argv}


def run(cmd, params, timeout=900, system=None, which=None):
    argv, env, err = build_argv(params, system, which)
    if err:
        return {"ok": False, "error": err}
    res = interpret(cmd(argv, timeout=timeout, env=env or None), argv)
    return {"ok": res["ok"], "error": res["error"], "result": res}
