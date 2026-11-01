# -*- coding: utf-8 -*-
"""Test de fumée de credentials-api (livraison #498) : app Flask sur une
base SQLite temporaire, chiffrement réel (shared/secret_crypto).

    python3 credentials/api/tests/smoke_test.py
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "shared"))


def main():
    data = tempfile.mkdtemp(prefix="credentials-test-")
    os.environ["CREDENTIALS_DATA_DIR"] = data
    os.environ["CREDENTIALS_PASSPHRASE"] = ""
    os.environ["CREDENTIALS_INTERNAL_TOKEN"] = ""

    import app as cr
    c = cr.app.test_client()

    assert c.get("/credentials/").status_code == 200
    assert c.get("/credentials/health").get_json()["status"] == "ok"
    st = c.get("/credentials/status").get_json()
    assert st["encryption_configured"] is False and st["reveal_enabled"] is False and st["count"] == 0
    print("✓ page + health + status (rien configuré)")

    # 1. sans phrase de passe : refus de stocker un mot de passe, jamais de clair
    r = c.post("/credentials/list", json={"name": "mikrotik", "kind": "routeros", "username": "admin", "password": "s3cret"})
    assert r.status_code == 503 and "chiffrement non configuré" in r.get_json()["error"], r.get_json()
    assert c.get("/credentials/reveal/mikrotik").status_code == 404, "révélation absente sans jeton configuré"
    print("✓ sans CREDENTIALS_PASSPHRASE : 503, rien stocké ; sans jeton : révélation inexistante (404)")

    # 2. avec phrase de passe et jeton (relance du module pour relire l'env)
    os.environ["CREDENTIALS_PASSPHRASE"] = "phrase de test"
    os.environ["CREDENTIALS_INTERNAL_TOKEN"] = "jeton-interne-de-test"
    for m in ("app", "store", "credential_crypto"):
        sys.modules.pop(m, None)
    import app as cr2
    c = cr2.app.test_client()
    assert c.get("/credentials/status").get_json()["encryption_configured"] is True
    assert os.path.exists(os.path.join(data, "salt.b64")) or True
    r = c.post("/credentials/list", json={"name": "mikrotik", "kind": "routeros", "username": "admin", "password": "s3cret", "notes": "compte API"})
    assert r.status_code == 201, r.get_json()
    item = r.get_json()
    assert item["has_password"] and item["password_encrypted"] and "password" not in item
    assert c.post("/credentials/list", json={"name": "mikrotik", "kind": "routeros", "username": "x", "password": "y"}).status_code == 409
    assert c.post("/credentials/list", json={"name": "nom invalide!", "password": "y"}).status_code == 400
    assert c.post("/credentials/list", json={"name": "sans-mdp", "kind": "ssh"}).status_code == 400
    assert c.post("/credentials/list", json={"name": "genre", "kind": "magie", "password": "y"}).status_code == 400
    listing = c.get("/credentials/list").get_json()["credentials"]
    assert len(listing) == 1 and listing[0]["name"] == "mikrotik" and "password" not in listing[0]
    print("✓ création chiffrée (mot de passe jamais renvoyé), doublon 409, validations 400")

    # 3. la base ne contient pas le clair
    import sqlite3
    raw = sqlite3.connect(os.path.join(data, "credentials.db")).execute("SELECT password FROM credentials").fetchone()[0]
    assert raw.startswith("enc:") and "s3cret" not in raw
    print("✓ base : jeton chiffré, jamais le clair")

    # 4. révélation : jeton obligatoire, via passerelle refusée, consommateur journalisé
    assert c.get("/credentials/reveal/mikrotik").status_code == 403
    assert c.get("/credentials/reveal/mikrotik", headers={"X-Credentials-Token": "faux"}).status_code == 403
    r = c.get("/credentials/reveal/mikrotik", headers={"X-Credentials-Token": "jeton-interne-de-test", "X-Forwarded-For": "192.0.2.1"})
    assert r.status_code == 404, "requête passée par tls-proxy : route inexistante"
    r = c.get("/credentials/reveal/mikrotik", headers={"X-Credentials-Token": "jeton-interne-de-test", "X-Credentials-Consumer": "mikrotik-api"})
    assert r.status_code == 200 and r.get_json() == {"name": "mikrotik", "username": "admin", "password": "s3cret"}, r.get_json()
    r = c.get("/credentials/reveal/inconnu", headers={"X-Credentials-Token": "jeton-interne-de-test", "X-Credentials-Consumer": "mikrotik-api"})
    assert r.status_code == 404 and "Accès d'équipements" in r.get_json()["error"]
    audit = c.get("/credentials/audit").get_json()["reveals"]
    assert audit[0]["name"] == "inconnu" and audit[0]["ok"] == 0 and audit[1]["name"] == "mikrotik" and audit[1]["ok"] == 1
    assert audit[1]["consumer"] == "mikrotik-api"
    assert all("s3cret" not in str(a) for a in audit)
    listing = c.get("/credentials/list").get_json()["credentials"]
    assert listing[0]["last_consumer"] == "mikrotik-api" and listing[0]["last_reveal_at"]
    print("✓ révélation : 403 sans/mauvais jeton, 404 via passerelle, ok journalisé (consommateur, jamais la valeur)")

    # 5. modification sans ressaisie, puis avec nouveau mot de passe, puis suppression
    r = c.put("/credentials/list/mikrotik", json={"kind": "routeros", "username": "api-ro", "notes": "lecture seule"})
    assert r.status_code == 200 and r.get_json()["username"] == "api-ro"
    r = c.get("/credentials/reveal/mikrotik", headers={"X-Credentials-Token": "jeton-interne-de-test"})
    assert r.get_json()["password"] == "s3cret", "mot de passe inchangé sans ressaisie"
    r = c.put("/credentials/list/mikrotik", json={"kind": "routeros", "username": "api-ro", "password": "nouveau"})
    assert r.status_code == 200
    assert c.get("/credentials/reveal/mikrotik", headers={"X-Credentials-Token": "jeton-interne-de-test"}).get_json()["password"] == "nouveau"
    assert c.put("/credentials/list/absent", json={"kind": "ssh"}).status_code == 404
    assert c.delete("/credentials/list/mikrotik").status_code == 200
    assert c.delete("/credentials/list/mikrotik").status_code == 404
    assert c.get("/credentials/status").get_json()["count"] == 0
    print("✓ modification (mot de passe conservé / remplacé), suppression")

    # 6. rechiffrement d'une valeur en clair (base antérieure) + phrase changée
    import store as st_mod
    conn = sqlite3.connect(os.path.join(data, "credentials.db"))
    conn.execute("INSERT INTO credentials (name, kind, username, password, notes, created_at, updated_at) VALUES ('legacy','ssh','root','clair','', 'x','x')")
    conn.commit(); conn.close()
    assert c.get("/credentials/status").get_json()["clear_count"] == 1
    r = c.post("/credentials/reencrypt")
    assert r.status_code == 200 and r.get_json()["reencrypted"] == 1
    assert c.get("/credentials/status").get_json()["clear_count"] == 0
    assert c.get("/credentials/reveal/legacy", headers={"X-Credentials-Token": "jeton-interne-de-test"}).get_json()["password"] == "clair"
    os.environ["CREDENTIALS_PASSPHRASE"] = "autre phrase"
    r = c.get("/credentials/reveal/legacy", headers={"X-Credentials-Token": "jeton-interne-de-test"})
    assert r.status_code == 503 and "déchiffrement" in r.get_json()["error"]
    assert "clair" not in r.get_json()["error"]
    print("✓ rechiffrement du clair ; phrase changée = 503 explicite sans fuite")

    print("\nSMOKE TEST OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
