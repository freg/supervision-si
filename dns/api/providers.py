# -*- coding: utf-8 -*-
"""Fournisseurs DNS du module dns-api (livraison #656) -- une interface commune, trois mises en œuvre :
- OvhProvider : API OVH (signature SHA1 app secret + consumer key + méthode + URL + corps + horodatage), zone /domain/zone/<z>/record ;
- ScalewayProvider : API Domains Scaleway (ex-Online), /domain/v2beta1/dns-zones/<z>/records, jeton X-Auth-Token ;
- BindProvider : DNS intranet, mises à jour dynamiques `nsupdate` avec clé TSIG (serveur, nom de clé, secret) ; lecture par AXFR `dig`.
Chaque fournisseur : list_records(zone) -> [{name, type, value, ttl, id}], set_record(zone, name, type, value, ttl), delete_record(zone, name, type, value).
`name` est relatif à la zone ("www", "@" pour l'apex). Les secrets arrivent par le coffre des accès (credentials-api), jamais en clair ici.
Transport HTTP injectable (http) pour les tests ; les commandes nsupdate/dig passent par `run` injectable."""
import json, time, hashlib, urllib.request, urllib.parse, subprocess, re

NAME_RE = re.compile(r"^(@|[A-Za-z0-9_*]([A-Za-z0-9_.-]{0,61}[A-Za-z0-9_])?)$")
TYPES = ("A", "AAAA", "CNAME", "TXT", "MX", "SRV", "NS", "PTR")

def _http(method, url, headers=None, body=None, timeout=15):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=dict({"Content-Type": "application/json", "Accept": "application/json"}, **(headers or {})))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8") or "null"; return r.status, json.loads(raw)
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read().decode("utf-8") or "null")
        except Exception: return e.code, {"error": str(e)}

class ProviderError(Exception): pass

class OvhProvider:
    kind = "ovh"
    def __init__(self, app_key, app_secret, consumer_key, endpoint="https://eu.api.ovh.com/1.0", http=_http):
        self.ak, self.asec, self.ck, self.ep, self.http = app_key, app_secret, consumer_key, endpoint.rstrip("/"), http; self._delta = None
    def _call(self, method, path, body=None):
        url = self.ep + path; ts = int(time.time() + (self._delta or 0)); b = json.dumps(body, separators=(",", ":")) if body is not None else ""
        sig = "$1$" + hashlib.sha1(("+".join([self.asec, self.ck, method, url, b, str(ts)])).encode()).hexdigest()
        st, data = self.http(method, url, {"X-Ovh-Application": self.ak, "X-Ovh-Consumer": self.ck, "X-Ovh-Timestamp": str(ts), "X-Ovh-Signature": sig}, body)
        if st >= 400: raise ProviderError("OVH %s %s : %s" % (method, path, (data or {}).get("message") if isinstance(data, dict) else data))
        return data
    def list_records(self, zone):
        ids = self._call("GET", "/domain/zone/%s/record" % zone) or []
        out = []
        for i in ids:
            r = self._call("GET", "/domain/zone/%s/record/%s" % (zone, i))
            out.append(dict(id=str(i), name=r.get("subDomain") or "@", type=r.get("fieldType"), value=r.get("target"), ttl=r.get("ttl")))
        return out
    def set_record(self, zone, name, rtype, value, ttl=300):
        sub = "" if name == "@" else name
        existing = [r for r in self.list_records(zone) if r["name"] == name and r["type"] == rtype]
        if existing:
            self._call("PUT", "/domain/zone/%s/record/%s" % (zone, existing[0]["id"]), {"target": value, "ttl": ttl, "subDomain": sub})
            for r in existing[1:]: self._call("DELETE", "/domain/zone/%s/record/%s" % (zone, r["id"]))
        else:
            self._call("POST", "/domain/zone/%s/record" % zone, {"fieldType": rtype, "subDomain": sub, "target": value, "ttl": ttl})
        self._call("POST", "/domain/zone/%s/refresh" % zone); return True
    def delete_record(self, zone, name, rtype, value=None):
        for r in self.list_records(zone):
            if r["name"] == name and r["type"] == rtype and (value is None or r["value"] == value): self._call("DELETE", "/domain/zone/%s/record/%s" % (zone, r["id"]))
        self._call("POST", "/domain/zone/%s/refresh" % zone); return True

class ScalewayProvider:
    kind = "scaleway"
    def __init__(self, secret_key, endpoint="https://api.scaleway.com/domain/v2beta1", http=_http):
        self.key, self.ep, self.http = secret_key, endpoint.rstrip("/"), http
    def _call(self, method, path, body=None):
        st, data = self.http(method, self.ep + path, {"X-Auth-Token": self.key}, body)
        if st >= 400: raise ProviderError("Scaleway %s %s : %s" % (method, path, (data or {}).get("message") if isinstance(data, dict) else data))
        return data
    def list_records(self, zone):
        data = self._call("GET", "/dns-zones/%s/records?page_size=1000" % zone) or {}
        return [dict(id=r.get("id"), name=r.get("name") or "@", type=r.get("type"), value=r.get("data"), ttl=r.get("ttl")) for r in data.get("records", [])]
    def set_record(self, zone, name, rtype, value, ttl=300):
        n = "" if name == "@" else name
        self._call("PATCH", "/dns-zones/%s/records" % zone, {"changes": [{"set": {"id_fields": {"name": n, "type": rtype}, "records": [{"name": n, "type": rtype, "data": value, "ttl": ttl}]}}]}); return True
    def delete_record(self, zone, name, rtype, value=None):
        n = "" if name == "@" else name
        self._call("PATCH", "/dns-zones/%s/records" % zone, {"changes": [{"delete": {"id_fields": {"name": n, "type": rtype, **({"data": value} if value else {})}}}]}); return True

class BindProvider:
    """DNS intranet (BIND ou tout serveur acceptant les mises à jour dynamiques RFC 2136 avec TSIG)."""
    kind = "bind"
    def __init__(self, server, key_name, key_secret, algorithm="hmac-sha256", run=None, port=53):
        self.server, self.key_name, self.secret, self.algo, self.port = server, key_name, key_secret, algorithm, int(port); self.run = run or self._run
    @staticmethod
    def _run(argv, stdin=None):
        r = subprocess.run(argv, input=stdin, capture_output=True, text=True, timeout=30); return r.returncode, r.stdout, r.stderr
    def _key(self): return "%s:%s:%s" % (self.algo, self.key_name, self.secret)
    def list_records(self, zone):
        rc, out, err = self.run(["dig", "@%s" % self.server, "-p", str(self.port), "-y", self._key(), zone, "AXFR", "+noall", "+answer"])
        if rc != 0: raise ProviderError("dig AXFR %s : %s" % (zone, (err or out).strip()[:200]))
        recs = []
        for line in out.splitlines():
            p = line.split(None, 4)
            if len(p) < 5 or p[3] in ("SOA", "RRSIG", "NSEC"): continue
            fqdn = p[0].rstrip("."); name = "@" if fqdn == zone else fqdn[: -len(zone) - 1] if fqdn.endswith("." + zone) else fqdn
            recs.append(dict(id=None, name=name, type=p[3], value=p[4].strip().strip('"'), ttl=int(p[1]) if p[1].isdigit() else None))
        return recs
    def _fqdn(self, zone, name): return zone + "." if name == "@" else "%s.%s." % (name, zone)
    def set_record(self, zone, name, rtype, value, ttl=300):
        v = '"%s"' % value if rtype == "TXT" else value
        script = "server %s %d\nzone %s.\nupdate delete %s %s\nupdate add %s %d %s %s\nsend\n" % (self.server, self.port, zone, self._fqdn(zone, name), rtype, self._fqdn(zone, name), int(ttl), rtype, v)
        rc, out, err = self.run(["nsupdate", "-y", self._key()], stdin=script)
        if rc != 0: raise ProviderError("nsupdate : %s" % (err or out).strip()[:200])
        return True
    def delete_record(self, zone, name, rtype, value=None):
        script = "server %s %d\nzone %s.\nupdate delete %s %s%s\nsend\n" % (self.server, self.port, zone, self._fqdn(zone, name), rtype, (" " + value) if value else "")
        rc, out, err = self.run(["nsupdate", "-y", self._key()], stdin=script)
        if rc != 0: raise ProviderError("nsupdate : %s" % (err or out).strip()[:200])
        return True

def build(spec, creds, http=_http, run=None):
    """spec : {kind, credential, endpoint?, server?, port?, algorithm?} ; creds(name) -> (user, password) ou lève ProviderError.
    Conventions du coffre : ovh = identifiant « <app_key>/<consumer_key> », mot de passe = app secret ; scaleway = mot de passe = secret key ;
    bind = identifiant = nom de la clé TSIG, mot de passe = secret."""
    k = spec.get("kind")
    user, pw = creds(spec.get("credential") or "")
    if k == "ovh":
        if "/" not in (user or ""): raise ProviderError("coffre ovh : identifiant attendu « app_key/consumer_key »")
        ak, ck = user.split("/", 1); return OvhProvider(ak, pw, ck, spec.get("endpoint") or "https://eu.api.ovh.com/1.0", http)
    if k == "scaleway": return ScalewayProvider(pw, spec.get("endpoint") or "https://api.scaleway.com/domain/v2beta1", http)
    if k == "bind": return BindProvider(spec.get("server") or "", user, pw, spec.get("algorithm") or "hmac-sha256", run, spec.get("port") or 53)
    raise ProviderError("fournisseur inconnu : %s" % k)
