# -*- coding: utf-8 -*-
"""Édition des registres d'équipements depuis leur tuile (livraison #592) --
commun à mikrotik-api et cisco-api : lecture du registre courant (local
prioritaire, sinon l'exemple versionné), ajout / mise à jour par nom,
suppression, écriture ATOMIQUE de `<x>.local.json` (jamais l'exemple), avec
le propriétaire du dossier. Les identifiants restent dans le coffre : seul
le NOM de l'accès est écrit. Sans dossier accessible en écriture : erreur
explicite (montage `:ro`)."""
import json
import os
import re
import secrets

NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
HOST_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.:\-\[\]]{0,253}$")


def read_items(local_path, example_path, key):
    """-> (liste, source) ; source = local | exemple | vide."""
    for path, src in ((local_path, "local"), (example_path, "exemple")):
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            items = data.get(key) if isinstance(data, dict) else data
            if isinstance(items, list):
                return [i for i in items if isinstance(i, dict)], src
        except (OSError, ValueError):
            continue
    return [], "vide"


def write_items(local_path, key, items):
    d = os.path.dirname(local_path) or "."
    if not os.access(d, os.W_OK):
        raise PermissionError("dossier du registre non modifiable (%s) : monter le dossier sans « :ro » dans docker-compose.yml (#592)" % d)
    tmp = os.path.join(d, ".%s.%s.tmp" % (os.path.basename(local_path), secrets.token_hex(3)))
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({key: items}, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    try:
        st = os.stat(d)
        os.chown(tmp, st.st_uid, st.st_gid)
    except OSError:
        pass
    os.replace(tmp, local_path)


def validate_common(body, transports, default_ports):
    """Champs communs (nom, hôte, transport, port, accès, site, description) -> (dict, erreurs)."""
    body = body or {}
    out, errors = {}, []
    name = str(body.get("name") or "").strip()
    if not NAME_RE.match(name):
        errors.append("nom : lettres, chiffres, . _ - (64 max)")
    else:
        out["name"] = name
    host = str(body.get("host") or "").strip()
    if not HOST_RE.match(host):
        errors.append("hôte / IP invalide")
    else:
        out["host"] = host
    transport = str(body.get("transport") or transports[0]).strip().lower()
    if transport not in transports:
        errors.append("transport : %s" % " / ".join(transports))
    else:
        out["transport"] = transport
    port = body.get("port")
    if port not in (None, ""):
        try:
            port = int(port)
            if not 1 <= port <= 65535:
                raise ValueError
            if port != default_ports.get(transport):
                out["port"] = port
        except (TypeError, ValueError):
            errors.append("port : 1-65535")
    cred = str(body.get("credential") or "").strip()
    if not cred:
        errors.append("accès du coffre requis (le nom de l'accès, pas le mot de passe)")
    elif not NAME_RE.match(cred):
        errors.append("nom d'accès invalide")
    else:
        out["credential"] = cred
    for k, n in (("site", 80), ("description", 200)):
        v = str(body.get(k) or "").strip()
        if v:
            out[k] = v[:n]
    return out, errors


def upsert(items, entry):
    """Remplace l'entrée de même nom ou ajoute ; -> (liste, "updated"|"added")."""
    for i, it in enumerate(items):
        if it.get("name") == entry["name"]:
            merged = dict(it)
            merged.update(entry)
            for k in list(merged):
                if k not in entry and k in ("port", "site", "description", "enable_credential", "platform"):
                    merged.pop(k, None) if k in ("port", "site", "description") else None
            items[i] = merged
            return items, "updated"
    items.append(entry)
    return items, "added"


def remove(items, name):
    kept = [it for it in items if it.get("name") != name]
    return kept, len(kept) != len(items)
