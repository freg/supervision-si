# -*- coding: utf-8 -*-
"""Garde-fou anti-force-brute du bastion si-proxy (livraison #453) --
« fail2ban maison ». Le relais voit lui-même les échecs d'authentification
(jeton refusé, CN non autorisé, rôle inconnu) : ce garde compte les échecs
par adresse IP et BANNIT l'IP au-delà d'un seuil dans une fenêtre glissante,
pour une durée donnée. Une IP bannie est rejetée AVANT même la lecture du
HELLO.

Logique PURE (horloge injectable) : testable sans réseau. Le relais s'en
sert ; le journal JSONL (audit.py) reste par ailleurs exploitable par un
vrai fail2ban tapant dans le pare-feu du host si on le préfère.
"""
import time


class Guard(object):
    def __init__(self, threshold=5, window_s=300, ban_s=900, clock=time.monotonic, max_tracked=4096):
        self.threshold = threshold          # échecs tolérés dans la fenêtre
        self.window_s = window_s            # fenêtre glissante
        self.ban_s = ban_s                  # durée de bannissement
        self.clock = clock
        self.max_tracked = max_tracked
        self._fails = {}                    # ip -> [timestamps d'échec récents]
        self._bans = {}                     # ip -> expiration (monotone)

    def is_banned(self, ip):
        exp = self._bans.get(ip)
        if exp is None:
            return False
        if self.clock() >= exp:
            self._bans.pop(ip, None)
            return False
        return True

    def record_failure(self, ip):
        """Enregistre un échec d'auth pour `ip` ; retourne True si cette IP
        vient d'être bannie (seuil atteint)."""
        if not ip:
            return False
        now = self.clock()
        if self.is_banned(ip):
            return False
        xs = [t for t in self._fails.get(ip, []) if now - t < self.window_s]
        xs.append(now)
        self._fails[ip] = xs
        self._gc(now)
        if len(xs) >= self.threshold:
            self._bans[ip] = now + self.ban_s
            self._fails.pop(ip, None)
            return True
        return False

    def record_success(self, ip):
        """Un succès efface les échecs récents de l'IP (elle n'est pas hostile)."""
        self._fails.pop(ip, None)

    def unban(self, ip):
        return self._bans.pop(ip, None) is not None

    def banned(self):
        """[{ip, seconds_left}] des bannissements en cours."""
        now = self.clock()
        out = []
        for ip, exp in sorted(self._bans.items()):
            if exp > now:
                out.append({"ip": ip, "seconds_left": int(exp - now)})
        return out

    def _gc(self, now):
        if len(self._fails) <= self.max_tracked:
            return
        for ip in [ip for ip, xs in self._fails.items() if not xs or now - xs[-1] >= self.window_s]:
            self._fails.pop(ip, None)
