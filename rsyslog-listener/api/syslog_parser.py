"""
Parseur syslog RFC 3164 (BSD, ancien) et RFC 5424 (moderne) --
livraison #177, backlog BACKLOG.md #3, étape 4/4 (dernière de
l'initiative "logs de toutes sortes"). Logique PURE, testable sans
socket ni réseau -- séparée de listener.py (la partie réseau/état).

Les deux formats partagent le même préfixe PRI (`<N>`, `N = facility
* 8 + severity`) -- la distinction se fait ensuite : RFC 5424 place
un numéro de VERSION ("1") juste après le PRI, RFC 3164 non (voir
_looks_like_5424). Aucune bibliothèque tierce (pas de dépendance
externe pour un parsing somme toute simple, et évite d'ajouter un
paquet Python de plus au Dockerfile).
"""
import re

# Sévérité syslog (RFC 5424 table 2, réutilisée telle quelle par RFC
# 3164) -- mappée sur les 3 niveaux déjà utilisés partout ailleurs
# dans ce mécanisme de logs (ERROR/WARNING/INFO). 0-3 -> ERROR (alerte
# à Erreur), 4 -> WARNING, 5-7 -> INFO (Notice/Info/Debug) -- "Notice"
# rangé en INFO plutôt qu'un 4e niveau, cohérent avec le reste du
# projet qui n'utilise que ces 3 niveaux.
_SEVERITY_TO_LEVEL = {
    0: "ERROR", 1: "ERROR", 2: "ERROR", 3: "ERROR",
    4: "WARNING",
    5: "INFO", 6: "INFO", 7: "INFO",
}

_PRI_RE = re.compile(r"^<(\d{1,3})>")
_RFC5424_VERSION_RE = re.compile(r"^<\d{1,3}>1 ")
# RFC 3164 : "Mmm dd hh:mm:ss " (jour sur 1 ou 2 chiffres, espace de
# remplissage si 1 chiffre -- ex. "Oct  1" avec DEUX espaces avant le
# jour unique, RFC 3164 section 4.1.2) puis hostname/tag/message.
_RFC3164_HEADER_RE = re.compile(
    r"^<(\d{1,3})>([A-Z][a-z]{2}\s+\d{1,2}\s\d{2}:\d{2}:\d{2})\s+(\S+)\s+(.*)$"
)
_RFC5424_HEADER_RE = re.compile(
    r"^<(\d{1,3})>1\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(?:\[.*?\]|-)\s*(.*)$"
)
_TAG_RE = re.compile(r"^([\w.\-/]+?)(\[\d+\])?:\s*(.*)$")


def _split_pri(message):
    """Extrait `(facility, severity)` depuis le préfixe `<N>` --
    `(None, None)` si absent ou hors plage (0-191, RFC 3164/5424) --
    JAMAIS une exception, une ligne malformée doit rester traitable
    en repli plutôt que de tout faire échouer."""
    match = _PRI_RE.match(message)
    if not match:
        return None, None
    pri = int(match.group(1))
    if pri > 191:
        return None, None
    return pri // 8, pri % 8


def _looks_like_5424(message):
    """RFC 5424 place un numéro de VERSION ("1") juste après le PRI
    (`<165>1 ...`) -- RFC 3164 enchaîne directement sur l'horodatage
    (`<34>Oct 11 ...`). Distinction FIABLE : aucun horodatage RFC 3164
    valide ne peut commencer par le chiffre "1" suivi d'un espace
    (le premier composant est toujours un nom de mois abrégé)."""
    return bool(_RFC5424_VERSION_RE.match(message))


def parse_syslog_message(raw_text, source_name):
    """Transforme UNE ligne syslog brute (déjà décodée) en
    `{level, logger, message}` -- jamais une exception : un message
    qui ne correspond à AUCUN des deux formats reconnus retombe en
    "brut" (logger=source_name, level=INFO, message=raw_text tel
    quel) plutôt que d'être perdu silencieusement -- un flux syslog
    réel peut contenir des lignes légèrement hors norme, jamais une
    raison de tout rejeter."""
    text = raw_text.strip()
    if not text:
        return None

    if _looks_like_5424(text):
        match = _RFC5424_HEADER_RE.match(text)
        if match:
            pri, _ts, hostname, app_name, _procid, _msgid, msg = match.groups()
            facility, severity = _split_pri(text)
            level = _SEVERITY_TO_LEVEL.get(severity, "INFO")
            logger_name = app_name if app_name != "-" else (hostname if hostname != "-" else source_name)
            # BOM UTF-8 optionnel en tête du MSG (RFC 5424 section 6.4) --
            # retiré s'il est présent, jamais laissé visible dans le message affiché.
            msg = msg.lstrip("\ufeff")
            return {"level": level, "logger": logger_name, "message": msg.strip() or text}

    match = _RFC3164_HEADER_RE.match(text)
    if match:
        _pri, _ts, hostname, rest = match.groups()
        facility, severity = _split_pri(text)
        level = _SEVERITY_TO_LEVEL.get(severity, "INFO")
        tag_match = _TAG_RE.match(rest)
        if tag_match:
            tag, _pid, msg = tag_match.groups()
            logger_name = tag or hostname
            return {"level": level, "logger": logger_name, "message": msg.strip() or rest}
        return {"level": level, "logger": hostname, "message": rest}

    # Ni RFC 3164 ni RFC 5424 reconnu -- repli "brut", jamais perdu.
    facility, severity = _split_pri(text)
    level = _SEVERITY_TO_LEVEL.get(severity, "INFO")
    body = _PRI_RE.sub("", text, count=1).strip() or text
    return {"level": level, "logger": source_name, "message": body}
