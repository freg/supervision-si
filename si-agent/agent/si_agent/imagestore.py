# -*- coding: utf-8 -*-
"""Réception d'un gros fichier envoyé par un agent (livraison #634) -- côté
central (si-agent-api et central local, même code, copié au build de l'API) :
morceaux ajoutés dans l'ordre (`.part`, décalage vérifié -> reprise), clôture
avec taille et SHA-256 vérifiés, puis fichier final sous <racine>/<agent>/<nom>.
Aucune dépendance : stdlib. La signature des requêtes est vérifiée par
l'appelant (face agents signée HMAC), pas ici."""
import hashlib
import os
import threading
import time


def check_offset(expected, requested):
    try:
        r = int(requested)
    except (TypeError, ValueError):
        return "offset entier requis"
    if r != expected:
        return "offset %d attendu (reçu %d) : reprendre depuis GET …/status" % (expected, r)
    return None


class ImageStore:
    def __init__(self, root):
        self.root = root
        os.makedirs(root, exist_ok=True)
        self.lock = threading.Lock()

    def _part(self, aid, name):
        d = os.path.join(self.root, aid)
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, name + ".part"), os.path.join(d, name)

    def size(self, aid, name):
        part, final = self._part(aid, name)
        if os.path.exists(final):
            return os.path.getsize(final), True
        return (os.path.getsize(part) if os.path.exists(part) else 0), False

    def append(self, aid, name, offset, data):
        with self.lock:
            part, final = self._part(aid, name)
            cur, done = self.size(aid, name)
            if done:
                return 409, {"error": "fichier déjà complet", "size": cur}
            err = check_offset(cur, offset)
            if err:
                return 409, {"error": err, "size": cur}
            with open(part, "ab") as fh:
                fh.write(data)
            return 201, {"size": cur + len(data)}

    def complete(self, aid, name, size, sha256):
        with self.lock:
            part, final = self._part(aid, name)
            if not os.path.exists(part):
                return 404, {"error": "aucun transfert en cours pour %s" % name}
            got = os.path.getsize(part)
            if got != int(size or -1):
                return 409, {"error": "taille reçue %d != annoncée %s" % (got, size), "size": got}
            h = hashlib.sha256()
            with open(part, "rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b""):
                    h.update(chunk)
            if h.hexdigest() != str(sha256 or "").lower():
                return 409, {"error": "condensé différent : transfert corrompu, à reprendre", "size": got}
            os.replace(part, final)
            return 200, {"ok": True, "path": final, "size": got, "sha256": h.hexdigest()}

    def list(self):
        out = []
        for aid in sorted(os.listdir(self.root)) if os.path.isdir(self.root) else []:
            d = os.path.join(self.root, aid)
            if not os.path.isdir(d):
                continue
            for f in sorted(os.listdir(d)):
                p = os.path.join(d, f)
                out.append({"agent_id": aid, "name": f[:-5] if f.endswith(".part") else f, "size": os.path.getsize(p), "complete": not f.endswith(".part"), "path": p,
                            "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(os.path.getmtime(p)))})
        return out


