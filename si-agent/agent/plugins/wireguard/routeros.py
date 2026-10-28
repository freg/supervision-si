"""#889 : client minimal de l'API RouterOS (MikroTik), LECTURE SEULE, sans dépendance (Python 3.5+).

Protocole « API » (port 8728, ou 8729 en TLS) : phrases de mots préfixés par leur longueur ; réponses !re (ligne),
!done (fin), !trap (erreur). Connexion par /login nom + mot de passe (RouterOS >= 6.43 ; repli défi MD5 sinon).
Seules des commandes .../print sont envoyées (le module refuse toute autre commande).
"""
import hashlib
import socket
import ssl


def enc_len(n):
    if n < 0x80:
        return bytes([n])
    if n < 0x4000:
        return (n | 0x8000).to_bytes(2, "big")
    if n < 0x200000:
        return (n | 0xC00000).to_bytes(3, "big")
    if n < 0x10000000:
        return (n | 0xE0000000).to_bytes(4, "big")
    return b"\xf0" + n.to_bytes(4, "big")


def phrase(mots):
    out = b""
    for m in mots:
        b = m.encode("utf-8")
        out += enc_len(len(b)) + b
    return out + b"\x00"


class Api:
    def __init__(self, sock):
        self.s = sock

    def _lire(self, n):
        buf = b""
        while len(buf) < n:
            x = self.s.recv(n - len(buf))
            if not x:
                raise ConnectionError("connexion RouterOS fermée")
            buf += x
        return buf

    def _len(self):
        c = self._lire(1)[0]
        if c & 0x80 == 0:
            return c
        if c & 0xC0 == 0x80:
            return ((c & 0x3F) << 8) + self._lire(1)[0]
        if c & 0xE0 == 0xC0:
            return ((c & 0x1F) << 16) + int.from_bytes(self._lire(2), "big")
        if c & 0xF0 == 0xE0:
            return ((c & 0x0F) << 24) + int.from_bytes(self._lire(3), "big")
        return int.from_bytes(self._lire(4), "big")

    def _phrase(self):
        mots = []
        while True:
            n = self._len()
            if n == 0:
                return mots
            mots.append(self._lire(n).decode("utf-8", "replace"))

    def cmd(self, mots):
        """-> (lignes !re en dicts, attributs de !done) ; !trap -> RuntimeError."""
        self.s.sendall(phrase(mots))
        lignes, erreur = [], None
        while True:
            p = self._phrase()
            if not p:
                continue
            attrs = {}
            for m in p[1:]:
                if m.startswith("="):
                    k, _, v = m[1:].partition("=")
                    attrs[k] = v
            if p[0] == "!re":
                lignes.append(attrs)
            elif p[0] == "!trap":
                erreur = attrs.get("message") or "erreur RouterOS"
            elif p[0] in ("!done", "!fatal"):
                if erreur or p[0] == "!fatal":
                    raise RuntimeError(erreur or attrs.get("message") or " ".join(p[1:]) or "erreur fatale RouterOS")
                return lignes, attrs

    def login(self, user, pwd):
        _, fin = self.cmd(["/login", "=name=" + user, "=password=" + pwd])
        if "ret" in fin:   # RouterOS < 6.43 : défi MD5
            defi = bytes.fromhex(fin["ret"])
            rep = "00" + hashlib.md5(b"\x00" + pwd.encode("utf-8") + defi).hexdigest()
            self.cmd(["/login", "=name=" + user, "=response=" + rep])

    def lire(self, chemin):
        if not chemin.endswith("/print"):
            raise ValueError("lecture seule : seules les commandes …/print sont permises")
        return self.cmd([chemin])[0]


def connecter(host, port=None, tls=False, timeout=15):
    port = port or (8729 if tls else 8728)
    s = socket.create_connection((host, port), timeout=timeout)
    if tls:   # certificat du routeur souvent auto-signé : chiffrement sans vérification (réseau interne, adresse fixée)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        s = ctx.wrap_socket(s, server_hostname=host)
    return Api(s)


def duree_s(txt):
    """Durée RouterOS « 1w2d3h4m5s », « 2m10s », « 00:01:05 » ou « 350ms » -> secondes (None si vide)."""
    t = str(txt or "").strip()
    if not t:
        return None
    if ":" in t:
        h, m, s = (t.split(":") + ["0", "0"])[:3]
        return int(h) * 3600 + int(m) * 60 + int(float(s))
    tot, num = 0.0, ""
    unites = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}
    i = 0
    while i < len(t):
        c = t[i]
        if c.isdigit() or c == ".":
            num += c
        elif t[i:i + 2] == "ms":
            tot += float(num or 0) / 1000
            num, i = "", i + 1
        elif c in unites:
            tot += float(num or 0) * unites[c]
            num = ""
        i += 1
    return int(tot)
