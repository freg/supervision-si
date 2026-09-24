# -*- coding: utf-8 -*-
"""Connecteur ownCloud « ancienne version » (#600) -- lecture par WebDAV
(`remote.php/webdav`, ownCloud 8 / 9 / 10 et Nextcloud) d'un dossier de
FICHES utilisateurs (fichiers texte : identifiant, adresse, clés de licence,
comptes…) et de son sous-dossier « anciens utilisateurs ». Lecture seule,
authentification Basic avec un accès du coffre (jamais stocké ici). Les
clés de licence relevées sont MASQUÉES dans ce qui est mémorisé ; le texte
complet n'est lu qu'à la demande (administrateur, journalisé)."""
import os
import posixpath
import re
import xml.etree.ElementTree as ET

import requests

TEXT_EXT = (".txt", ".md", ".text", ".ini", ".cfg", ".conf", ".yaml", ".yml", ".json", ".csv")
D = "{DAV:}"


def webdav_root(base_url):
    """https://cloud.exemple/ -> https://cloud.exemple/remote.php/webdav (ownCloud 9), déjà complet sinon."""
    b = base_url.rstrip("/")
    if "remote.php" in b:
        return b
    return b + "/remote.php/webdav"


def _href_to_rel(href, root_path):
    p = requests.utils.unquote(href)
    i = p.find(root_path)
    rel = p[i + len(root_path):] if i >= 0 else p
    return rel.strip("/")


def parse_propfind(xml_text, root_path):
    """Réponse PROPFIND -> [{path, dir, size, modified}] (chemins relatifs au dossier interrogé)."""
    out = []
    try:
        tree = ET.fromstring(xml_text)
    except ET.ParseError:
        return out
    for resp in tree.iter(D + "response"):
        href = (resp.findtext(D + "href") or "").strip()
        is_dir = resp.find(".//" + D + "collection") is not None
        size = resp.findtext(".//" + D + "getcontentlength")
        modified = resp.findtext(".//" + D + "getlastmodified") or ""
        rel = _href_to_rel(href, root_path)
        out.append({"path": rel, "dir": is_dir, "size": int(size) if size and size.isdigit() else 0, "modified": modified})
    return out


class OwnCloud:
    def __init__(self, base_url, username, password, verify=True, timeout=20, http=None):
        self.root = webdav_root(base_url)
        self.auth = (username, password)
        self.verify = verify
        self.timeout = timeout
        self.http = http or requests

    def _url(self, folder):
        return self.root + "/" + "/".join(requests.utils.quote(p) for p in folder.strip("/").split("/") if p)

    def list(self, folder, depth=1):
        r = self.http.request("PROPFIND", self._url(folder), auth=self.auth, headers={"Depth": str(depth)}, verify=self.verify, timeout=self.timeout)
        if r.status_code == 404:
            raise FileNotFoundError("dossier introuvable : %s" % folder)
        if r.status_code not in (207, 200):
            raise RuntimeError("PROPFIND %s : HTTP %s" % (folder, r.status_code))
        root_path = "/" + self.root.split("://", 1)[-1].split("/", 1)[-1].strip("/") + "/" + folder.strip("/")
        items = parse_propfind(r.text, root_path.rstrip("/"))
        return [i for i in items if i["path"]]  # sans l'entrée du dossier lui-même

    def read(self, path, max_bytes=200000):
        r = self.http.get(self._url(path), auth=self.auth, verify=self.verify, timeout=self.timeout)
        if r.status_code != 200:
            raise RuntimeError("GET %s : HTTP %s" % (path, r.status_code))
        data = r.content[:max_bytes]
        for enc in ("utf-8-sig", "cp1252", "latin-1"):
            try:
                return data.decode(enc)
            except UnicodeDecodeError:
                continue
        return data.decode("utf-8", "replace")


# -- fiches texte -------------------------------------------------------------------------------
MAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
KEY_RE = re.compile(r"\b(?:[A-Z0-9]{4,6}-){2,7}[A-Z0-9]{4,6}\b|\b[A-Z0-9]{16,}\b")
FIELD_RE = re.compile(r"^\s*([A-Za-zÀ-ÿ0-9 _./()'-]{2,40}?)\s*[:=]\s*(.+?)\s*$")
SECRET_WORDS = ("mot de passe", "password", "mdp", "pass", "pwd", "clé", "cle", "key", "licence", "license", "serial", "série", "serie", "token", "secret", "pin", "code")


def mask(value):
    v = str(value or "").strip()
    if len(v) <= 4:
        return "••••"
    return "•" * max(4, len(v) - 4) + v[-4:]


def parse_fiche(text, filename=""):
    """Fiche texte -> {name, mails, fields:[{label, value, secret}], licenses:[{product, key_masked}], software:[...]}.
    Les valeurs des champs « secrets » (mot de passe, clé, licence, série…) et
    toute clé de licence reconnue sont masquées ; rien d'autre n'est inventé."""
    name = os.path.splitext(os.path.basename(filename))[0].replace("_", " ").strip()
    fields, licenses, software = [], [], []
    mails = sorted(set(MAIL_RE.findall(text or "")))
    for line in (text or "").splitlines():
        m = FIELD_RE.match(line)
        if not m:
            continue
        label, value = m.group(1).strip(), m.group(2).strip()
        low = label.lower()
        secret = any(w in low for w in SECRET_WORDS) or bool(KEY_RE.search(value))
        fields.append({"label": label, "value": mask(value) if secret else value[:200], "secret": secret})
        if any(w in low for w in ("licence", "license", "serial", "série", "serie", "clé", "cle", "key")):
            product = re.sub(r"\b(licence|license|serial|série|serie|clé|cle|key|n°|numéro|de|du|d')\b", " ", low).strip(" :-")
            licenses.append({"product": product or label, "key_masked": mask(value)})
            if product:
                software.append(product)
    for k in KEY_RE.findall(text or ""):
        if not any(l["key_masked"] == mask(k) for l in licenses):
            licenses.append({"product": "", "key_masked": mask(k)})
    return {"name": name, "mails": mails, "fields": fields, "licenses": licenses, "software": sorted(set(software))}


def is_text_file(item):
    return not item["dir"] and item["path"].lower().endswith(TEXT_EXT)


def scan(client, folder, former_subfolder="anciens utilisateurs"):
    """Lit le dossier des fiches et le sous-dossier des anciens ->
    [{path, name, former, modified, size, fiche}] (texte non conservé)."""
    out = []
    for former, sub in ((False, ""), (True, former_subfolder)):
        target = posixpath.join(folder.strip("/"), sub) if sub else folder.strip("/")
        try:
            items = client.list(target)
        except FileNotFoundError:
            if former:
                continue
            raise
        for it in items:
            if not is_text_file(it):
                continue
            if not former and former_subfolder and it["path"].lower().startswith(former_subfolder.lower() + "/"):
                continue  # sous-dossier des anciens lu au passage suivant
            if "/" in it["path"] and not former:
                continue  # fiches à la racine du dossier seulement (les autres sous-dossiers ne sont pas des personnes)
            text = client.read(posixpath.join(target, it["path"]))
            fiche = parse_fiche(text, it["path"])
            out.append({"path": posixpath.join(target, it["path"]), "name": fiche["name"], "former": former, "modified": it["modified"], "size": it["size"], "fiche": fiche})
    return out
