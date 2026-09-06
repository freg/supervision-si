"""
Alertes optionnelles lors de l'usage de la phrase de passe maîtresse
(livraison #206, suite du PRA #203 -- "une passe phrase et un SMS
avec code au travers de la partie non authentifiée de la passerelle
sms, plus une alerte mail sur des adresses non personnelles").

**Entièrement OPTIONNEL** : si les variables d'environnement d'un
canal ne sont pas toutes renseignées, ce canal est SILENCIEUSEMENT
IGNORÉ (jamais une erreur qui bloquerait un déchiffrement par ailleurs
réussi -- l'alerte est un plus, jamais une condition pour accéder à
ses propres secrets). Best-effort des deux côtés : un canal qui échoue
à l'envoi (réseau, service injoignable) est signalé sur stderr mais
NE FAIT JAMAIS échouer le script appelant.

Uniquement des modules de la BIBLIOTHÈQUE STANDARD (urllib, smtplib)
-- ce module tourne sur la machine de la personne (via
scripts/run.sh, HORS Docker), jamais l'occasion d'imposer une
dépendance supplémentaire (`requests` etc.) à installer sur son poste
en plus de `cryptography`, déjà nécessaire pour secret_crypto.py.

**Canal SMS** -- vérifié contre le VRAI code du projet trb140-sms-relay
(fourni par la personne, #203) : route `/send`, authentification par
clé de service (`RELAY_API_KEY`), INDÉPENDANTE de Keycloak -- voir
docs/pra-secrets-demarrage.docx pour le raisonnement complet (reste
fonctionnel même si Keycloak est indisponible).

**Canal courriel** -- SMTP direct (`smtplib`), même motif que
`email_sender.py` du projet trb140-sms-relay (jamais réutilisé tel
quel : sa fonction d'envoi y est strictement interne, non exposée en
service réutilisable, vérifié lors de la rédaction du PRA).
"""
import json
import logging
import os
import smtplib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from email.message import EmailMessage

# Traces DEBUG (livraison #217, suite de #215-216). RÈGLE ABSOLUE :
# ni la clé d'API SMS, ni le mot de passe SMTP n'apparaissent JAMAIS
# dans une trace -- seule leur PRÉSENCE (booléen), jamais leur valeur.
_log = logging.getLogger("secrets_alert")


def _env(name):
    return os.environ.get(name, "").strip()


def send_sms_alert(message, timeout=10):
    """Renvoie True si l'envoi a réussi, False s'il a échoué OU si le
    canal n'est pas configuré (les deux cas ne sont JAMAIS distingués
    par une exception -- voir docstring du module)."""
    base_url = _env("SECRETS_ALERT_SMS_URL")
    api_key = _env("SECRETS_ALERT_SMS_KEY")
    number = _env("SECRETS_ALERT_SMS_NUMBER")
    if not (base_url and api_key and number):
        _log.debug("send_sms_alert : canal NON CONFIGURÉ -- ignoré (pas une erreur)")
        return False  # canal non configuré -- pas une erreur

    query = urllib.parse.urlencode({"number": number, "message": message, "key": api_key})
    url = f"{base_url.rstrip('/')}/send?{query}"
    _log.debug("send_sms_alert : envoi démarré vers %s (clé d'API présente, jamais sa valeur ici)", base_url)
    start = time.monotonic()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            if resp.status != 200:
                _log.debug("send_sms_alert : ÉCHEC HTTP %s après %d ms", resp.status, elapsed_ms)
                print(f"Alerte SMS : réponse HTTP {resp.status} de la passerelle", file=sys.stderr)
                return False
            body = resp.read().decode("utf-8", errors="replace")
            try:
                json.loads(body)  # confirme une réponse JSON exploitable, jamais interprétée plus finement (format propre au TRB140, non garanti)
            except ValueError:
                pass
            _log.debug("send_sms_alert : succès en %d ms", elapsed_ms)
            return True
    except (urllib.error.URLError, TimeoutError) as exc:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        _log.debug("send_sms_alert : ÉCHEC réseau après %d ms -- %s", elapsed_ms, exc)
        print(f"Alerte SMS : envoi échoué ({exc}) -- n'empêche pas la suite.", file=sys.stderr)
        return False


def send_email_alert(subject, body, timeout=10):
    """Même contrat que send_sms_alert : True si envoyé, False sinon
    (non configuré OU échec réseau/SMTP), jamais une exception qui
    remonterait à l'appelant."""
    host = _env("SECRETS_ALERT_SMTP_HOST")
    to_addr = _env("SECRETS_ALERT_EMAIL_TO")
    from_addr = _env("SECRETS_ALERT_SMTP_FROM")
    if not (host and to_addr and from_addr):
        _log.debug("send_email_alert : canal NON CONFIGURÉ -- ignoré (pas une erreur)")
        return False  # canal non configuré -- pas une erreur

    port = int(_env("SECRETS_ALERT_SMTP_PORT") or "587")
    username = _env("SECRETS_ALERT_SMTP_USER")
    password = _env("SECRETS_ALERT_SMTP_PASSWORD")
    use_tls = _env("SECRETS_ALERT_SMTP_USE_TLS").lower() != "false"  # true par défaut

    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(body)

    _log.debug("send_email_alert : envoi démarré vers %s:%s (TLS=%s, identifiants SMTP présents=%s, jamais leur valeur ici)",
               host, port, use_tls, bool(username))
    start = time.monotonic()
    try:
        with smtplib.SMTP(host, port, timeout=timeout) as smtp:
            if use_tls:
                smtp.starttls()
            if username:
                smtp.login(username, password)
            smtp.send_message(msg)
        elapsed_ms = int((time.monotonic() - start) * 1000)
        _log.debug("send_email_alert : succès en %d ms", elapsed_ms)
        return True
    except (smtplib.SMTPException, OSError) as exc:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        _log.debug("send_email_alert : ÉCHEC après %d ms -- %s", elapsed_ms, exc)
        print(f"Alerte courriel : envoi échoué ({exc}) -- n'empêche pas la suite.", file=sys.stderr)
        return False


def send_deployment_alerts(context_message):
    """Point d'entrée unique -- appelle les deux canaux (chacun
    ignoré silencieusement si non configuré), renvoie un résumé
    {"sms": bool, "email": bool} PUREMENT INFORMATIF -- jamais utilisé
    par l'appelant pour décider de continuer ou non (voir
    scripts/secrets_tool.py : un déchiffrement réussi ne doit JAMAIS
    échouer à cause d'une alerte qui n'a pas pu partir)."""
    sms_ok = send_sms_alert(f"[supervision-si] {context_message}")
    email_ok = send_email_alert(
        subject="[supervision-si] Secrets de démarrage déchiffrés",
        body=f"{context_message}\n\nCeci est une alerte automatique -- voir docs/pra-secrets-demarrage.docx.",
    )
    return {"sms": sms_ok, "email": email_ok}
