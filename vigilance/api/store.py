"""
Automates d'analyse -- vigilance cybersécurité et santé du parc/réseau
(livraison #262, backlog item 34, suite du module `classifier/`
#260). Demandé explicitement, en réponse à une proposition concrète
("pour la catégorie 'client DHCP dynamique'... croiser avec les
niveaux d'usage... pour repérer les postes WiFi qui consomment
anormalement") : "OUI j'aime c'est tout à fait le genre d'analyse que
je veux, sois créatif et si possible cible les éléments de cyber
vigilance et de santé du parc et du réseau".

Ce module NE COLLECTE RIEN lui-même -- il CROISE, en lecture, les
données déjà construites par `network-agent` (appareils, échanges,
services par appareil, historique de présence/volume, #250-251) et
`classifier` (catégorie sémantique d'un nom d'hôte, #260). La seule
donnée PROPRE à ce module est le JOURNAL DES SIGNAUX détectés --
chaque passage d'analyse qui trouve quelque chose d'anormal crée une
ligne ici, jamais recalculé à la volée à chaque consultation (permet
de voir une TENDANCE -- "signalé depuis 3 jours" a plus de valeur
qu'un simple "signalé maintenant").

Trois premiers signaux, ciblés sur les clients DHCP dynamiques
(catégorie la plus risquée -- appareils NON identifiés
individuellement, potentiellement invités/BYOD/WiFi) :
1. **Contact avec de l'infrastructure** -- un client DHCP qui échange
   du trafic avec un appareil classé "équipement d'infrastructure"
   (ex. NMS, onduleur, serveur) est un signal de violation de
   segmentation potentielle -- un invité ne devrait normalement
   jamais parler DIRECTEMENT à ce type d'équipement.
2. **Diversité de services élevée** -- un client DHCP qui utilise de
   nombreux services/ports distincts s'écarte du profil "invité
   normal" (HTTP/HTTPS/DNS, peu de ports) -- signal de scan, de
   comportement automatisé, ou simplement d'un appareil mal identifié.
3. **Croissance de volume anormale** -- un client DHCP dont le volume
   cumulé progresse fortement entre deux relevés (#251) -- signal
   d'usage intensif inattendu pour un profil normalement transitoire
   (exfiltration, mise à jour massive, appareil compromis relayant du
   trafic).

**Quatrième signal (livraison #266), cette fois sur `equipement_infrastructure`**
plutôt que les clients DHCP -- piste explicitement notée comme
"reste à faire" dès la livraison initiale (#262) : "un équipement
d'infrastructure qui cesse subitement d'émettre du trafic pourrait
aussi être un signal de santé du parc à part entière".

4. **Infrastructure silencieuse** -- un appareil classé "équipement
   d'infrastructure" (NMS, onduleur, serveur...) dont le dernier
   trafic observé remonte à plus de
   `VIGILANCE_SILENCE_THRESHOLD_HOURS` (24h par défaut) -- un
   équipement de ce type a normalement une activité RÉGULIÈRE
   (supervision, heartbeat, trafic de service) ; un silence prolongé
   peut signaler une panne, une coupure réseau, OU un signe de
   compromission (arrêt délibéré pour échapper à la détection).
"""
import sqlite3
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS vig_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_mac TEXT NOT NULL,
    device_label TEXT NOT NULL,
    signal_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    detail TEXT NOT NULL,
    detected_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_vig_signals_mac ON vig_signals(device_mac);
CREATE INDEX IF NOT EXISTS idx_vig_signals_type ON vig_signals(signal_type);
CREATE INDEX IF NOT EXISTS idx_vig_signals_detected ON vig_signals(detected_at);
"""

# Seuils -- VOLONTAIREMENT PARAMÉTRABLES (voir app.py, variables
# d'environnement) -- des valeurs de départ raisonnables, jamais
# présentées comme validées sur un vrai réseau chargé (voir
# README, "reste à faire").
DEFAULT_SERVICE_DIVERSITY_THRESHOLD = 10
DEFAULT_VOLUME_GROWTH_PERCENT_THRESHOLD = 200
DEFAULT_SILENCE_THRESHOLD_HOURS = 24


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def get_connection(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_schema(db_path):
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def record_signal(db_path, device_mac, device_label, signal_type, severity, detail):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO vig_signals (device_mac, device_label, signal_type, severity, detail, detected_at) VALUES (?, ?, ?, ?, ?, ?)",
            [device_mac, device_label, signal_type, severity, detail, now_iso()],
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def list_signals(db_path, signal_type=None, severity=None, device_mac=None, limit=200):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        clauses, params = [], []
        if signal_type:
            clauses.append("signal_type = ?")
            params.append(signal_type)
        if severity:
            clauses.append("severity = ?")
            params.append(severity)
        if device_mac:
            clauses.append("device_mac = ?")
            params.append(device_mac)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        cur.execute(f"SELECT * FROM vig_signals {where} ORDER BY detected_at DESC LIMIT ?", params)
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def signal_summary(db_path):
    """Résumé -- "santé du parc" en un coup d'œil : nombre de
    signaux PAR TYPE et PAR SÉVÉRITÉ, sur les 7 derniers jours
    (fenêtre glissante, jamais un total depuis toujours qui grandirait
    sans jamais redescendre)."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cutoff = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 7 * 86400))
        cur.execute(
            "SELECT signal_type, severity, COUNT(*) as n, COUNT(DISTINCT device_mac) as distinct_devices FROM vig_signals WHERE detected_at >= ? GROUP BY signal_type, severity",
            [cutoff],
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def purge_old_signals(db_path, older_than_iso):
    """Rétention -- même motif que les autres modules de ce projet
    (network-agent/#251, memory/#259)."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM vig_signals WHERE detected_at < ?", [older_than_iso])
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()
