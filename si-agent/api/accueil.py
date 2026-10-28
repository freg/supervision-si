"""#899 : installation d'un agent depuis l'accueil du hub, SANS authentification, strictement encadrée.

Un administrateur OUVRE l'installation pour un agent pré-configuré (fiche de l'agent, durée bornée, 24 h par défaut).
Tant que la fenêtre est ouverte ET que l'agent n'a jamais contacté le central depuis l'ouverture, le nom exact de
l'agent saisi sur l'accueil donne ses éléments d'installation (secret compris : c'est l'objet même). La fenêtre se
referme d'elle-même au premier contact de l'agent, à l'échéance, ou à la main. Demandes limitées par adresse.
Logique pure (horloge et état injectés) : testée sans Flask.
"""
import calendar
import re
import time

CLE = "accueil_installation"
NOM = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,62}$")
MAX_HEURES = 72


def ouvrir(etat, agent_id, heures, now=None):
    now = now or time.time()
    etat = dict(etat or {})
    h = max(0.0, min(float(heures or 0), MAX_HEURES))
    if h <= 0:
        etat.pop(agent_id, None)
    else:
        etat[agent_id] = {"depuis": now, "jusqua": now + h * 3600}
    return etat


def _epoch(iso):
    if not iso:
        return None
    try:
        return calendar.timegm(time.strptime(str(iso)[:19], "%Y-%m-%dT%H:%M:%S"))   # horodatages du central : UTC
    except ValueError:
        return None


def statut(etat, agent_id, agent, now=None):
    """-> (ouvert, motif) ; agent = ligne de l'agent (None si inconnu)."""
    now = now or time.time()
    f = (etat or {}).get(agent_id)
    if agent is None or f is None:
        return False, "inconnu ou non ouvert"
    if now > f["jusqua"]:
        return False, "fenêtre échue"
    vu = _epoch(agent.get("last_seen_at"))
    if vu is not None and vu >= f["depuis"]:
        return False, "agent déjà installé (contact reçu)"
    return True, None


class Limiteur:
    """N demandes par adresse et par fenêtre glissante."""
    def __init__(self, n=10, fenetre_s=600):
        self.n, self.f, self.vus = n, fenetre_s, {}

    def accepte(self, ip, now=None):
        now = now or time.time()
        l = [t for t in self.vus.get(ip, []) if now - t < self.f]
        if len(l) >= self.n:
            self.vus[ip] = l
            return False
        l.append(now)
        self.vus[ip] = l
        if len(self.vus) > 5000:
            self.vus = {k: v for k, v in self.vus.items() if v and now - v[-1] < self.f}
        return True
