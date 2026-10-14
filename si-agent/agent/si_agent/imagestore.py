# -*- coding: utf-8 -*-
"""Réception d'un gros fichier envoyé par un agent (livraison #634) -- côté
central (si-agent-api et central local, même code, copié au build de l'API) :
morceaux ajoutés dans l'ordre (`.part`, décalage vérifié -> reprise), clôture
avec taille et SHA-256 vérifiés, puis fichier final sous <racine>/<agent>/<nom>.
Aucune dépendance : stdlib. La signature des requêtes est vérifiée par
l'appelant (face agents signée HMAC), pas ici."""
import hashlib
import json
import os
import threading
import time

# #748 : relais direct source -> cible (virtualisation pilotée par les deux agents) -- le central ne garde qu'une FENÊTRE
# de l'image : la cible lit au fil de l'eau (lecture à partir de N = tout ce qui précède est chez elle), le central
# libère ce qu'elle a déjà (perforation du fichier, FALLOC_FL_PUNCH_HOLE), et refuse un morceau de la source (429)
# tant que l'écart envoyé - lu dépasse la fenêtre. Ni la source, ni le central, ni la cible ne saturent.
DEFAULT_WINDOW = 4 * 2**30
RELAY_STALE_S = 7 * 86400


def punch_hole(fd, offset, length):
    """Libère [offset, offset+length) sans changer la taille du fichier (Linux, ext4/xfs/btrfs). -> True si fait."""
    if length <= 0:
        return True
    try:
        import ctypes
        import ctypes.util
        libc = ctypes.CDLL(ctypes.util.find_library("c") or "libc.so.6", use_errno=True)
        libc.fallocate.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_longlong, ctypes.c_longlong]
        return libc.fallocate(fd, 0x01 | 0x02, offset, length) == 0     # FALLOC_FL_KEEP_SIZE | FALLOC_FL_PUNCH_HOLE
    except Exception:  # noqa: BLE001 -- système sans fallocate : la fenêtre reste bornée côté envoi, pas sur disque
        return False


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

    # ---------------------------------------------------------------- #748 : relais direct
    def _relay_path(self, aid):
        d = os.path.join(self.root, aid)
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, ".relay.json")

    def relay_get(self, aid):
        p = self._relay_path(aid)
        try:
            with open(p) as fh:
                r = json.load(fh)
            return r if time.time() - r.get("opened", 0) < RELAY_STALE_S else None
        except (OSError, ValueError):
            return None

    def _relay_put(self, aid, r):
        p = self._relay_path(aid)
        with open(p + ".tmp", "w") as fh:
            json.dump(r, fh)
        os.replace(p + ".tmp", p)

    def relay_open(self, aid, consumer, window=None):
        """Ouvre (ou rouvre pour le même consommateur) le relais des images de l'agent `aid` vers `consumer`."""
        with self.lock:
            r = self.relay_get(aid)
            if r and r.get("consumer") == consumer and not r.get("done"):
                return r
            r = {"consumer": consumer, "window": int(window or DEFAULT_WINDOW), "name": None, "acked": 0, "punched": 0,
                 "complete": False, "total": None, "sha256": None, "opened": time.time(), "done": False}
            self._relay_put(aid, r)
            return r

    def relay_read(self, aid, consumer, offset, max_bytes=8 * 2**20):
        """Lecture par la cible -> (statut, en-têtes, octets). 204 = rien de neuf (attendre) ; tout ce qui précède
        `offset` est acquis par la cible : libéré ici."""
        with self.lock:
            r = self.relay_get(aid)
            if not r:
                return 404, {}, b""
            if r["consumer"] != consumer:
                return 403, {}, b""
            name = r.get("name")
            hdr = {"X-Relay-Name": name or "", "X-Relay-Complete": "1" if r["complete"] else "0", "X-Relay-Total": str(r["total"] or ""),
                   "X-Relay-Sha256": r["sha256"] or ""}
            if not name:
                hdr["X-Relay-Available"] = "0"
                return 204, hdr, b""
            part, final = self._part(aid, name)
            path = final if os.path.exists(final) else part
            avail = os.path.getsize(path) if os.path.exists(path) else 0
            hdr["X-Relay-Available"] = str(avail)
            off = max(0, int(offset))
            if off > avail:
                return 416, hdr, b""
            if off > r["acked"]:
                r["acked"] = off
            data = b""
            with open(path, "r+b") as fh:
                if r["acked"] > r["punched"]:
                    punch_hole(fh.fileno(), r["punched"], r["acked"] - r["punched"])
                    r["punched"] = r["acked"]
                if off < avail:
                    fh.seek(off)
                    data = fh.read(min(int(max_bytes), avail - off))
            if r["complete"] and off >= (r["total"] or 0):
                r["done"] = True                             # la cible a tout : le fichier du central n'a plus d'usage
                try:
                    os.remove(path)
                except OSError:
                    pass
            self._relay_put(aid, r)
            return (200 if data else 204), hdr, data

    def relay_window_full(self, aid, name, cur):
        """Côté envoi : True si la source doit attendre (écart envoyé - lu au-delà de la fenêtre)."""
        r = self.relay_get(aid)
        if not r or r.get("done"):
            return False
        if not r.get("name"):
            r["name"] = name
            self._relay_put(aid, r)
        return r.get("name") == name and cur - r["acked"] >= r["window"]

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
            if self.relay_window_full(aid, name, cur):                       # #748 : la cible n'a pas encore suivi
                return 429, {"error": "fenêtre du relais pleine : la cible lit encore", "size": cur, "retry_after": 15}
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
            r = self.relay_get(aid)
            if r and r.get("name") == name and not r.get("done"):
                # #748 : fichier perforé au fil de l'eau -- le condensé est vérifié par la CIBLE, qui a tout
                r.update(complete=True, total=got, sha256=str(sha256 or "").lower())
                self._relay_put(aid, r)
                os.replace(part, final)
                return 200, {"ok": True, "path": final, "size": got, "sha256": r["sha256"], "relay": r["consumer"]}
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
                if f.startswith("."):
                    continue
                p = os.path.join(d, f)
                out.append({"agent_id": aid, "name": f[:-5] if f.endswith(".part") else f, "size": os.path.getsize(p), "complete": not f.endswith(".part"), "path": p,
                            "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(os.path.getmtime(p)))})
        return out


