# -*- coding: utf-8 -*-
"""Client CalDAV/CardDAV minimal (livraison #665) vers Radicale, bibliothèque standard : groupware-api agit avec un compte
de SERVICE (règle `[service]` du fichier de droits) et applique lui-même les partages (grants) avant chaque opération.
Chemins : /<user>/ (principal), /<user>/<collection>/ (agenda ou carnet), /<user>/<collection>/<uid>.vcf|.ics."""
import base64, re, urllib.request, urllib.error, uuid
from xml.etree import ElementTree as ET

NS = {"d": "DAV:", "c": "urn:ietf:params:xml:ns:caldav", "a": "urn:ietf:params:xml:ns:carddav"}
COLL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,60}$")


class Dav:
    def __init__(self, base, user, password, timeout=30):
        self.base, self.timeout = base.rstrip("/"), timeout
        self.auth = "Basic " + base64.b64encode(("%s:%s" % (user, password)).encode()).decode()

    def req(self, method, path, body=None, headers=None, ok=(200, 201, 204, 207)):
        h = {"Authorization": self.auth}
        h.update(headers or {})
        r = urllib.request.Request(self.base + path, data=body.encode("utf-8") if isinstance(body, str) else body, method=method, headers=h)
        try:
            with urllib.request.urlopen(r, timeout=self.timeout) as resp:
                return resp.status, resp.read().decode("utf-8", "replace"), dict(resp.headers)
        except urllib.error.HTTPError as e:
            if e.code in ok:
                return e.code, e.read().decode("utf-8", "replace"), dict(e.headers)
            raise DavError(e.code, e.read()[:300].decode("utf-8", "replace"), method, path)
        except (urllib.error.URLError, OSError) as e:
            raise DavError(503, "serveur DAV injoignable (%s)" % e, method, path)

    def ensure_principal(self, user):
        st, _, _ = self.req("PROPFIND", "/%s/" % user, headers={"Depth": "0"}, ok=(207, 404))
        if st == 404:
            self.req("MKCOL", "/%s/" % user, ok=(201,))

    def list_collections(self, user):
        """-> [{name, kind: addressbook|calendar|collection, displayname}]"""
        self.ensure_principal(user)
        body = '<?xml version="1.0"?><d:propfind xmlns:d="DAV:"><d:prop><d:resourcetype/><d:displayname/></d:prop></d:propfind>'
        _, xml, _ = self.req("PROPFIND", "/%s/" % user, body, {"Depth": "1", "Content-Type": "application/xml"}, ok=(207,))
        out = []
        for resp in ET.fromstring(xml).findall("d:response", NS):
            href = resp.findtext("d:href", "", NS)
            name = href.rstrip("/").split("/")[-1]
            if name == user or not name:
                continue
            rt = resp.find(".//d:resourcetype", NS)
            kind = "addressbook" if rt is not None and rt.find("a:addressbook", NS) is not None else "calendar" if rt is not None and rt.find("c:calendar", NS) is not None else "collection"
            out.append({"name": name, "kind": kind, "displayname": resp.findtext(".//d:displayname", "", NS) or name})
        return out

    def create_collection(self, user, name, kind, displayname=None):
        if not COLL_RE.match(name):
            raise DavError(400, "nom de collection invalide", "MKCOL", name)
        self.ensure_principal(user)
        rt = '<a:addressbook xmlns:a="urn:ietf:params:xml:ns:carddav"/>' if kind == "addressbook" else '<c:calendar xmlns:c="urn:ietf:params:xml:ns:caldav"/>'
        body = ('<?xml version="1.0"?><d:mkcol xmlns:d="DAV:"><d:set><d:prop><d:resourcetype><d:collection/>%s</d:resourcetype>'
                '<d:displayname>%s</d:displayname></d:prop></d:set></d:mkcol>') % (rt, _esc(displayname or name))
        self.req("MKCOL", "/%s/%s/" % (user, name), body, {"Content-Type": "application/xml"}, ok=(201,))
        return {"name": name, "kind": kind, "displayname": displayname or name}

    def delete_collection(self, user, name):
        self.req("DELETE", "/%s/%s/" % (user, name), ok=(200, 204))

    def list_items(self, user, coll):
        """Tous les objets (.vcf / .ics) d'une collection, avec leur contenu : [{href, etag, data}]."""
        body = ('<?xml version="1.0"?><d:propfind xmlns:d="DAV:" xmlns:a="urn:ietf:params:xml:ns:carddav" xmlns:c="urn:ietf:params:xml:ns:caldav">'
                '<d:prop><d:getetag/><a:address-data/><c:calendar-data/></d:prop></d:propfind>')
        _, xml, _ = self.req("PROPFIND", "/%s/%s/" % (user, coll), body, {"Depth": "1", "Content-Type": "application/xml"}, ok=(207,))
        out = []
        for resp in ET.fromstring(xml).findall("d:response", NS):
            href = resp.findtext("d:href", "", NS)
            if href.endswith("/"):
                continue
            data = resp.findtext(".//a:address-data", None, NS) or resp.findtext(".//c:calendar-data", None, NS)
            if not data:                                   # PROPFIND ne renvoie pas le contenu chez Radicale : GET de chaque objet
                _, data, _ = self.req("GET", href if href.startswith("/") else "/" + href, ok=(200,))
            if False:
                _, data, _ = self.req("GET", href if href.startswith("/") else "/" + href, ok=(200,))
            out.append({"href": href, "uid": href.rsplit("/", 1)[-1].rsplit(".", 1)[0], "etag": resp.findtext(".//d:getetag", "", NS), "data": data})
        return out

    def put_item(self, user, coll, uid, data, kind="vcf"):
        path = "/%s/%s/%s.%s" % (user, coll, uid, kind)
        ctype = "text/vcard; charset=utf-8" if kind == "vcf" else "text/calendar; charset=utf-8"
        st, _, h = self.req("PUT", path, data, {"Content-Type": ctype}, ok=(201, 204))
        return {"href": path, "etag": h.get("ETag", "")}

    def delete_item(self, user, coll, uid, kind="vcf"):
        self.req("DELETE", "/%s/%s/%s.%s" % (user, coll, uid, kind), ok=(200, 204))


class DavError(Exception):
    def __init__(self, code, text, method="", path=""):
        super().__init__("%s %s : HTTP %s %s" % (method, path, code, text)); self.code = code


def _esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def new_uid():
    return str(uuid.uuid4())
