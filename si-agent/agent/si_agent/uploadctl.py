# -*- coding: utf-8 -*-
"""Transfert d'un gros fichier du poste vers le central (livraison #634) --
l'image P2V (`image_host` {…, transfer: true, delete_after?: bool}) part vers
le serveur qui fait office de central (Mac du test, mini-PC Linux du site)
par le canal habituel de l'agent : HTTPS, requêtes SIGNÉES (HMAC, chaque
morceau porte le condensé de son corps), reprise sur coupure.

Protocole (préfixe /api/v1/agents/<id>/images/<nom>) :
  GET  …/status            -> {size} déjà reçu (0 si rien)   [reprise]
  PUT  …?offset=N           corps = morceau (CHUNK octets), refusé si N != taille reçue
  POST …/complete          {size, sha256} -> vérification, fichier final
Pure ici : découpage, reprise, condensé glissant. Réseau et fichiers dans l'agent
(`Agent._upload_worker`, un fil d'exécution à part : la boucle continue).
"""
import hashlib
import re

CHUNK = 8 * 1024 * 1024  # 8 Mo : passe sous les limites usuelles des mandataires, ~1 requête / 80 ms en Gigabit
NAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,120}$")


def safe_name(path):
    """Nom de fichier transmis au central : dernier segment, caractères sûrs."""
    name = re.split(r"[\\/]", str(path or ""))[-1]
    name = re.sub(r"[^A-Za-z0-9._-]", "-", name)[:120]
    return name if NAME_RE.match(name or "") and not name.startswith(".") else None


def plan_chunks(total, offset=0, chunk=CHUNK):
    """Morceaux restants -> [(offset, taille)] (générateur paresseux)."""
    pos = max(0, int(offset))
    while pos < total:
        n = min(chunk, total - pos)
        yield pos, n
        pos += n


def prefix_digest(read, offset, chunk=CHUNK):
    """Condensé SHA-256 des `offset` premiers octets (reprise : on rattrape le condensé)."""
    h = hashlib.sha256()
    pos = 0
    while pos < offset:
        data = read(pos, min(chunk, offset - pos))
        if not data:
            break
        h.update(data)
        pos += len(data)
    return h


def progress(sent, total, started, now):
    pct = round(100.0 * sent / total, 1) if total else 100.0
    rate = (sent / (now - started)) if now > started else 0.0
    eta = int((total - sent) / rate) if rate > 0 else None
    return {"sent": sent, "total": total, "percent": pct, "rate_mbps": round(rate * 8 / 1e6, 1), "eta_seconds": eta}


def check_offset(expected, requested):
    """Côté central : le morceau doit commencer exactement à la taille déjà reçue."""
    try:
        r = int(requested)
    except (TypeError, ValueError):
        return "offset entier requis"
    if r != expected:
        return "offset %d attendu (reçu %d) : reprendre depuis GET …/status" % (expected, r)
    return None
