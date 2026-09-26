# -*- coding: utf-8 -*-
"""Gestion système du poste Windows depuis le central (livraison #633) --
logique pure des commandes :

- `windows_update` {action: status|install, kbs?: [KB…], reboot?: bool}
  (win/winupdate.ps1, API COM Microsoft.Update ; l'installation est lancée
  DÉTACHÉE, résultat dans un fichier suivi par l'agent -- une installation
  peut durer une heure, la boucle ne s'arrête pas) ;
- `protection` {firewall?: on|off, profiles?: [Domain,Private,Public], defender?: on|off}
  (win/protection.ps1 ; un antivirus tiers est signalé, jamais piloté) ;
- différé générique : tout `params.at` (ISO « 2026-09-28T02:00 » en heure
  locale du poste, ou epoch) reporte l'exécution de la commande : elle est
  acquittée « programmée », conservée dans l'état de l'agent et exécutée à
  l'heure dite (événement `deferred-run`). Sert aux mises à jour nocturnes,
  aux redémarrages planifiés, à l'image hors heures.
"""
import re
import time

WU_ACTIONS = ("status", "install")
PROFILES = ("Domain", "Private", "Public")
WU_RESULT = {0: "non démarré", 1: "en cours", 2: "réussi", 3: "réussi avec erreurs", 4: "échec", 5: "annulé"}


def parse_at(value, now=None, localtime=time.localtime, mktime=time.mktime):
    """-> (epoch, erreur). None si absent. ISO local « AAAA-MM-JJTHH:MM[:SS] » ou epoch numérique ; passé refusé."""
    if value in (None, "", 0):
        return None, None
    now = time.time() if now is None else now
    if isinstance(value, (int, float)):
        due = float(value)
    else:
        m = re.match(r"^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2}))?$", str(value).strip())
        if not m:
            return None, "at : date-heure locale AAAA-MM-JJTHH:MM (ou epoch)"
        y, mo, d, h, mi, s = (int(x or 0) for x in m.groups())
        try:
            due = mktime((y, mo, d, h, mi, s, 0, 0, -1))
        except (OverflowError, ValueError):
            return None, "at : date invalide"
    if due < now - 60:
        return None, "at : déjà passé"
    if due > now + 366 * 86400:
        return None, "at : plus d'un an"
    return due, None


def validate_update(params):
    p = params or {}
    action = str(p.get("action") or "status").strip().lower()
    if action not in WU_ACTIONS:
        return None, "action : status ou install"
    kbs = p.get("kbs") or []
    if isinstance(kbs, str):
        kbs = [k for k in re.split(r"[,\s]+", kbs) if k]
    clean = []
    for k in kbs:
        m = re.match(r"^(?:KB)?(\d{4,8})$", str(k).strip(), re.I)
        if not m:
            return None, "kbs : identifiants KB1234567"
        clean.append("KB" + m.group(1))
    return {"action": action, "kbs": clean, "reboot": bool(p.get("reboot"))}, None


def update_argv(powershell, script, plan, out_file=None):
    argv = [powershell, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", script, "-Action", plan["action"]]
    if plan["kbs"]:
        argv += ["-Kb", ",".join(plan["kbs"])]
    if out_file:
        argv += ["-Out", out_file]
    return argv


def summarize_update(data):
    """Résumé lisible d'un résultat winupdate.ps1 (état ou installation)."""
    if not isinstance(data, dict):
        return "sans résultat"
    if data.get("error"):
        return "erreur : %s" % data["error"]
    pend = data.get("pending") or []
    parts = ["%d mise(s) à jour en attente" % len(pend)]
    if data.get("reboot_required"):
        parts.append("redémarrage requis")
    inst = data.get("install")
    if inst:
        if not inst.get("count"):
            parts.append("rien à installer")
        else:
            parts.append("installation de %d : %s" % (inst["count"], WU_RESULT.get(inst.get("result"), str(inst.get("result")))))
            if inst.get("reboot_required"):
                parts.append("redémarrage requis")
    return ", ".join(parts)


def validate_protection(params):
    p = params or {}
    fw = str(p.get("firewall") or "").strip().lower() or None
    de = str(p.get("defender") or "").strip().lower() or None
    if fw not in (None, "on", "off") or de not in (None, "on", "off"):
        return None, "firewall / defender : on ou off"
    profiles = p.get("profiles") or list(PROFILES)
    if isinstance(profiles, str):
        profiles = [x for x in re.split(r"[,\s]+", profiles) if x]
    profiles = [x.capitalize() for x in profiles]
    if not all(x in PROFILES for x in profiles) or not profiles:
        return None, "profiles : Domain, Private, Public"
    return {"firewall": fw, "defender": de, "profiles": profiles, "status_only": fw is None and de is None}, None


def protection_argv(powershell, script, plan):
    argv = [powershell, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", script]
    if plan["firewall"]:
        argv += ["-Firewall", plan["firewall"], "-Profiles", ",".join(plan["profiles"])]
    if plan["defender"]:
        argv += ["-Defender", plan["defender"]]
    return argv


def summarize_protection(data):
    if not isinstance(data, dict):
        return "sans résultat"
    fw = ["%s %s" % (f.get("profile"), "actif" if f.get("enabled") else "INACTIF") for f in data.get("firewall") or []]
    d = data.get("defender")
    parts = ["pare-feu : " + (", ".join(fw) or "?")]
    if d:
        parts.append("Defender temps réel : %s%s" % ("actif" if d.get("realtime") else "INACTIF", " (falsification protégée)" if d.get("tamper_protected") else ""))
    if data.get("third_party"):
        parts.append("antivirus tiers : " + ", ".join(t.get("name", "?") for t in data["third_party"]))
    if data.get("errors"):
        parts.append("erreurs : " + " ; ".join(data["errors"]))
    return " · ".join(parts)
