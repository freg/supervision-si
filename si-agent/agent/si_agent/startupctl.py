# -*- coding: utf-8 -*-
"""Lanceurs au démarrage d'un poste Windows (livraison #613) -- mesure
`startup` (script win/startup.ps1 : clés Run / RunOnce machine et
utilisateur, dossiers Démarrage, tâches planifiées à l'ouverture de session
ou au démarrage, services automatiques) et commande du central
`startup_action` {kind, scope?, name, enable}.

Activer / désactiver, comme le Gestionnaire des tâches :
- run (clé Run) : valeur binaire dans
  HK(LM|CU)\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\StartupApproved\\Run
  (02 00… = activé, 03 00… = désactivé) -- l'entrée reste visible, Windows
  ne la lance plus ; jamais de suppression de la clé Run elle-même.
- folder (dossier Démarrage) : même mécanisme, sous-clé StartupFolder.
- task (tâche planifiée) : `schtasks /Change /TN "<nom>" /Disable|/Enable`.
- service : `sc config "<nom>" start= disabled|auto` (jamais d'arrêt ici :
  l'effet vaut pour le prochain démarrage).
Les noms sont bornés et sans caractères de commande ; les services et
tâches Microsoft (chemin \\Microsoft\\) sont refusés à la désactivation.
"""
import re

KINDS = ("run", "folder", "task", "service")
SCOPES = ("machine", "user")
NAME_RE = re.compile(r"^[^\x00-\x1f\"'&|<>^%]{1,200}$")
APPROVED = {"run": "Run", "folder": "StartupFolder"}


def _hive(scope):
    return "HKLM" if scope == "machine" else "HKCU"


def build_argv(params):
    """-> (argv, erreur). Pure."""
    p = params or {}
    kind = str(p.get("kind") or "").strip().lower()
    if kind not in KINDS:
        return None, "kind : run, folder, task ou service"
    scope = str(p.get("scope") or "machine").strip().lower()
    if scope not in SCOPES:
        return None, "scope : machine ou user"
    name = str(p.get("name") or "").strip()
    if not NAME_RE.match(name):
        return None, "name : 1-200 caractères, sans \" ' & | < > ^ %"
    enable = bool(p.get("enable"))
    if kind in APPROVED:
        key = r"%s\Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\%s" % (_hive(scope), APPROVED[kind])
        value = "020000000000000000000000" if enable else "030000000000000000000000"
        return ["reg.exe", "add", key, "/v", name, "/t", "REG_BINARY", "/d", value, "/f"], None
    if kind == "task":
        if not enable and name.lower().startswith("\\microsoft\\"):
            return None, "tâche Microsoft : désactivation refusée depuis le hub"
        return ["schtasks.exe", "/Change", "/TN", name, "/Enable" if enable else "/Disable"], None
    if not enable and name.lower() in PROTECTED_SERVICES:
        return None, "service système : désactivation refusée"
    return ["sc.exe", "config", name, "start=", "auto" if enable else "disabled"], None


PROTECTED_SERVICES = {"wuauserv", "windefend", "mpssvc", "bfe", "dhcp", "dnscache", "eventlog", "lanmanworkstation",
                      "lanmanserver", "rpcss", "winmgmt", "termservice", "wscsvc", "si-agent"}


def interpret(r, params):
    rc = getattr(r, "returncode", -1)
    out = (getattr(r, "stdout", "") or "").strip()[-500:]
    err = (getattr(r, "stderr", "") or "").strip()[-500:]
    if rc == -127:
        return {"ok": False, "error": "outil Windows absent (reg/schtasks/sc)", "returncode": rc}
    if rc != 0:
        return {"ok": False, "error": err or out or "code %s" % rc, "returncode": rc}
    return {"ok": True, "error": None, "returncode": 0, "kind": params.get("kind"), "name": params.get("name"),
            "enabled": bool(params.get("enable")),
            "message": "%s « %s » %s" % ({"run": "lanceur", "folder": "raccourci de démarrage", "task": "tâche", "service": "service"}[params.get("kind")],
                                        params.get("name"), "activé(e)" if params.get("enable") else "désactivé(e)")}


def run(cmd, params, timeout=60):
    argv, err = build_argv(params or {})
    if err:
        return {"ok": False, "error": err}
    res = interpret(cmd(argv, timeout=timeout), params)
    res["argv"] = argv
    return {"ok": res["ok"], "error": res["error"], "result": res}


def summarize(items):
    """Compte par type et par état pour la ligne de résumé du hub."""
    s = {"total": 0, "enabled": 0, "disabled": 0, "by_kind": {}}
    for it in items or []:
        s["total"] += 1
        k = it.get("kind") or "?"
        s["by_kind"][k] = s["by_kind"].get(k, 0) + 1
        if it.get("enabled") is False:
            s["disabled"] += 1
        else:
            s["enabled"] += 1
    return s
