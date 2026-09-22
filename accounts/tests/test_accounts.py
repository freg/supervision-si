"""accounts-api (livraison #557) -- Keycloak simulé en mémoire."""
import json
import os
import sys
import unittest
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "api"))
import kc  # noqa: E402
import app as app_mod  # noqa: E402


class Resp:
    def __init__(self, status, body=None):
        self.status_code, self._body = status, body
        self.content = b"" if body is None else json.dumps(body).encode()
        self.text = self.content.decode()

    def json(self):
        if self._body is None:
            raise ValueError
        return self._body


class FakeKeycloak:
    """Simule /admin/realms/<realm> : users, groups, membership."""
    def __init__(self):
        self.users, self.groups, self.members, self.passwords, self.calls = {}, {}, {}, {}, []

    def request(self, method, url, json=None, params=None, headers=None, timeout=None):
        self.calls.append((method, url))
        assert headers and headers["Authorization"] == "Bearer tok"
        p = url.split("/admin/realms/supervision-si", 1)[1]
        parts = [x for x in p.split("/") if x]
        if parts[0] == "groups":
            if method == "GET" and len(parts) == 1:
                return Resp(200, [{"id": k, "name": v, "path": "/" + v} for k, v in self.groups.items()])
            if method == "POST":
                if json["name"] in self.groups.values():
                    return Resp(409, {"errorMessage": "Top level group named '%s' already exists." % json["name"]})
                self.groups[str(uuid.uuid4())] = json["name"]; return Resp(201)
            if method == "DELETE":
                self.groups.pop(parts[1], None); return Resp(204)
            if len(parts) == 3 and parts[2] == "members":
                return Resp(200, [self.users[u] for u, gs in self.members.items() if parts[1] in gs])
        if parts[0] == "users":
            if method == "GET" and len(parts) == 1:
                us = list(self.users.values())
                if params and params.get("username"):
                    us = [u for u in us if u["username"] == params["username"]]
                if params and params.get("search"):
                    us = [u for u in us if params["search"] in u["username"]]
                return Resp(200, us)
            if method == "POST" and len(parts) == 1:
                if any(u["username"] == json["username"] for u in self.users.values()):
                    return Resp(409, {"errorMessage": "User exists with same username"})
                uid = str(uuid.uuid4()); rec = {k: v for k, v in json.items() if k != "credentials"}; rec["id"] = uid
                self.users[uid] = rec; self.members[uid] = set()
                if json.get("credentials"):
                    self.passwords[uid] = json["credentials"][0]["value"]
                return Resp(201)
            uid = parts[1]
            if uid not in self.users:
                return Resp(404, {"error": "User not found"})
            if len(parts) == 2:
                if method == "GET": return Resp(200, self.users[uid])
                if method == "PUT": self.users[uid].update(json); return Resp(204)
                if method == "DELETE": del self.users[uid]; return Resp(204)
            if parts[2] == "groups":
                if method == "GET": return Resp(200, [{"id": g, "name": self.groups[g]} for g in self.members[uid]])
                if method == "PUT": self.members[uid].add(parts[3]); return Resp(204)
                if method == "DELETE": self.members[uid].discard(parts[3]); return Resp(204)
            if parts[2] == "reset-password":
                self.passwords[uid] = json["value"]; return Resp(204)
            if parts[2] in ("execute-actions-email", "logout"):
                return Resp(204)
        return Resp(500, {"error": "non simulé " + p})

    def post(self, url, data=None, timeout=None):
        assert url.endswith("/realms/master/protocol/openid-connect/token") and data["grant_type"] == "client_credentials"
        return Resp(200, {"access_token": "tok"})


def make_client():
    fake = FakeKeycloak()
    c = kc.Keycloak(base_url="http://kc/auth", realm="supervision-si", client_id="svc", client_secret="s", session=fake)
    return c, fake


class Lib(unittest.TestCase):
    def test_cycle_complet(self):
        c, fake = make_client()
        g = c.create_group("site-alpha"); c.create_group("techniciens")
        self.assertEqual([x["name"] for x in c.groups()], ["site-alpha", "techniciens"])
        with self.assertRaises(kc.KeycloakError):
            c.create_group("site-alpha")  # 409 -> « déjà existant »
        u = c.create_user("Alice", "alice@exemple.fr", "Alice", "Martin", True, ["site-alpha"], "Secret-123", True)
        self.assertEqual(u["username"], "alice"); self.assertEqual(u["groups"], ["site-alpha"]); self.assertFalse(u["federated"])
        self.assertEqual(fake.passwords[u["id"]], "Secret-123")
        self.assertNotIn("password", json.dumps(u))
        self.assertEqual(c.set_groups(u["id"], ["techniciens"]), ["techniciens"])
        self.assertEqual(c.user(u["id"])["groups"], ["techniciens"])
        with self.assertRaises(kc.KeycloakError):
            c.set_groups(u["id"], ["inconnu"])
        u2 = c.update_user(u["id"], enabled=False, email="a@exemple.fr")
        self.assertFalse(u2["enabled"]); self.assertEqual(u2["email"], "a@exemple.fr")
        with self.assertRaises(kc.KeycloakError):
            c.set_password(u["id"], "court")
        c.set_password(u["id"], "Nouveau-Mdp-1", temporary=False)
        self.assertEqual([m["username"] for m in c.group_members(c.group_by_name("techniciens")["id"])], ["alice"])
        c.delete_user(u["id"]); self.assertEqual(c.users(), [])
        with self.assertRaises(kc.KeycloakError):
            c.user(u["id"])
        c.delete_group(g["id"]); self.assertEqual([x["name"] for x in c.groups()], ["techniciens"])


class Api(unittest.TestCase):
    def setUp(self):
        c, self.fake = make_client()
        app_mod._kc = c
        self.app = app_mod.app.test_client()

    def test_droits_et_routes(self):
        r = self.app.post("/groups", json={"name": "site-alpha"})
        self.assertEqual(r.status_code, 403)
        r = self.app.post("/groups", json={"name": "site-alpha", "groups": ["techniciens"]})
        self.assertEqual(r.status_code, 403)
        r = self.app.post("/groups", json={"name": "site-alpha", "groups": ["admin_hub"], "user": "freg"})
        self.assertEqual(r.status_code, 201); gid = r.get_json()["group"]["id"]
        r = self.app.post("/users", json={"username": "bob", "email": "bob@exemple.fr", "member_of": ["site-alpha"], "password": "Passe-123", "user": "freg"})
        self.assertEqual(r.status_code, 403)  # sans groupes d'appelant : refus
        r = self.app.post("/users", json={"username": "bob", "email": "bob@exemple.fr", "member_of": ["site-alpha"], "password": "Passe-123", "groups": ["administrateurs"], "user": "freg"})
        self.assertEqual(r.status_code, 201)
        uid = r.get_json()["user"]["id"]
        self.assertEqual(r.get_json()["user"]["groups"], ["site-alpha"])
        r = self.app.put(f"/users/{uid}/groups", json={"member_of": [], "groups": ["administrateurs"]})
        self.assertEqual(r.status_code, 200); self.assertEqual(r.get_json()["groups"], [])
        r = self.app.put(f"/users/{uid}/password", json={"password": "Autre-Mdp-9", "groups": ["admin_hub"]})
        self.assertEqual(r.status_code, 200); self.assertNotIn("Autre", r.get_data(as_text=True))
        r = self.app.put(f"/users/{uid}/groups", json={"member_of": ["zzz"], "groups": ["administrateurs"]})
        self.assertEqual(r.status_code, 502); self.assertIn("inconnu", r.get_json()["error"])
        self.assertEqual(self.app.get("/users").get_json()["users"][0]["username"], "bob")
        self.assertEqual(self.app.get(f"/groups/{gid}/members").status_code, 200)
        r = self.app.get("/info"); self.assertIn("ldap_writable", r.get_json())


if __name__ == "__main__":
    unittest.main()
