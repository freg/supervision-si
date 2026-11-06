#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Nœuds IA (livraison #996) : registre deploy/ia-noeuds.json (hors dépôt, écrit par la tour quand on déploie un nœud
depuis le hub) -> publications du bastion pour les nœuds joints par un shim (SI_PROXY_PUBLISH du .env).

  python3 scripts/ia_registre.py publier     # ajoute / garde « PORT=shim:adresse:port » pour chaque nœud « bastion »,
                                           # copie de sécurité .env.bak-<date> si le .env change ; code 0
  python3 scripts/ia_registre.py voir        # registre et publications, sans rien écrire

Registre : {"noeuds": [{"nom", "acces": "direct"|"bastion", "adresse", "port", "shim"?, "publie"?}]}. La passerelle
(tls-proxy/render_nginx_conf.py) lit le même registre : direct -> http://adresse:port, bastion -> http://si-proxy:<publie>.
Le jeton de chaque nœud n'est jamais écrit : HMAC(IA_NOEUDS_SECRET, nom), recalculé au rendu."""
import json
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRE = os.path.join(ROOT, "deploy", "ia-noeuds.json")
ENV = os.path.join(ROOT, ".env")
PORTS = range(6491, 6500)
NOM_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,30}$")
HOTE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,252}$")


def valider(e):
    """Entrée du registre -> message d'erreur ou None."""
    if not NOM_RE.match(str(e.get("nom") or "")):
        return "nom invalide (minuscules, chiffres, tirets)"
    if e.get("acces") not in ("direct", "bastion"):
        return "accès : direct ou bastion"
    if not HOTE_RE.match(str(e.get("adresse") or "")):
        return "adresse invalide (IP ou nom)"
    try:
        p = int(e.get("port") or 8092)
    except (TypeError, ValueError):
        return "port numérique"
    if not 1024 <= p <= 65535:
        return "port entre 1024 et 65535"
    if e.get("acces") == "bastion" and not NOM_RE.match(str(e.get("shim") or "")):
        return "shim du bastion requis (ex. campus)"
    return None


def charger(path=REGISTRE):
    try:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
        return [e for e in d.get("noeuds") or [] if isinstance(e, dict) and not valider(e)]
    except (OSError, ValueError):
        return []


def enregistrer(noeuds, path=REGISTRE):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"noeuds": noeuds}, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def declarer(noeuds, e):
    """Ajoute ou remplace (même nom) une entrée validée ; garde le port publié si la cible ne change pas."""
    e = {k: e.get(k) for k in ("nom", "acces", "adresse", "port", "shim") if e.get(k) not in (None, "")}
    e["port"] = int(e.get("port") or 8092)
    out, ancien = [], None
    for x in noeuds:
        if x.get("nom") == e["nom"]:
            ancien = x
        else:
            out.append(x)
    if ancien and ancien.get("publie") and (ancien.get("shim"), ancien.get("adresse"), ancien.get("port")) == (e.get("shim"), e.get("adresse"), e["port"]):
        e["publie"] = ancien["publie"]
    out.append(e)
    return sorted(out, key=lambda x: x["nom"])


def publications(spec, noeuds, ports=PORTS):
    """SI_PROXY_PUBLISH actuel + registre -> (nouvelle valeur, noeuds avec « publie », changé ?). Les autres
    publications restent telles quelles ; une cible déjà publiée garde son port."""
    items = [x.strip() for x in (spec or "").split(",") if x.strip()]
    par_cible, pris = {}, set()
    for it in items:
        port, _, cible = it.partition("=")
        if port.strip().isdigit():
            pris.add(int(port))
            par_cible[cible.strip()] = int(port)
    change, out = False, []
    for e in noeuds:
        e = dict(e)
        if e.get("acces") == "bastion":
            cible = "%s:%s:%d" % (e["shim"], e["adresse"], int(e.get("port") or 8092))
            if cible in par_cible:
                e["publie"] = par_cible[cible]
            else:
                libre = next((p for p in ports if p not in pris), None)
                if libre is None:
                    raise ValueError("plus de port libre pour publier %s (%d-%d)" % (e["nom"], ports[0], ports[-1]))
                pris.add(libre)
                par_cible[cible] = libre
                items.append("%d=%s" % (libre, cible))
                e["publie"] = libre
                change = True
        else:
            e.pop("publie", None)
        out.append(e)
    return ",".join(items), out, change


def env_remplacer(texte, cle, valeur):
    """Remplace (ou ajoute) « CLE=valeur » dans le texte d'un .env, sans toucher au reste."""
    lignes, vu = texte.splitlines(), False
    for i, l in enumerate(lignes):
        if re.match(r"^%s=" % re.escape(cle), l):
            lignes[i], vu = "%s=%s" % (cle, valeur), True
    if not vu:
        lignes.append("%s=%s" % (cle, valeur))
    return "\n".join(lignes) + "\n"


def env_valeur(texte, cle):
    val = ""
    for l in texte.splitlines():
        if re.match(r"^%s=" % re.escape(cle), l):
            val = l.split("=", 1)[1].strip().strip("\"'")
    return val


def main(argv):
    action = argv[1] if len(argv) > 1 else "voir"
    noeuds = charger()
    try:
        with open(ENV, encoding="utf-8") as fh:
            texte = fh.read()
    except OSError:
        print("✗ .env introuvable (%s)" % ENV)
        return 1
    spec, noeuds2, change = publications(env_valeur(texte, "SI_PROXY_PUBLISH"), noeuds)
    for e in noeuds2:
        print("  %-12s %-8s %s:%s%s" % (e["nom"], e["acces"], e["adresse"], e.get("port"), ("  -> publié sur si-proxy:%s (shim %s)" % (e["publie"], e["shim"])) if e.get("publie") else ""))
    if action != "publier":
        return 0
    if change:
        sauvegarde = ENV + ".bak-" + time.strftime("%Y%m%d-%H%M%S")
        with open(sauvegarde, "w", encoding="utf-8") as fh:
            fh.write(texte)
        os.chmod(sauvegarde, 0o600)
        with open(ENV, "w", encoding="utf-8") as fh:
            fh.write(env_remplacer(texte, "SI_PROXY_PUBLISH", spec))
        print("✓ SI_PROXY_PUBLISH mis à jour (copie : %s)" % os.path.basename(sauvegarde))
    else:
        print("✓ publications du bastion déjà à jour")
    enregistrer(noeuds2)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
