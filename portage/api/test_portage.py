"""Tests portage-api (app.test_client) : fiche projet, import d'une archive de code Fat-Free (détection du type), yml produit,
décisions du PORT_SPEC, refus explicites (kit absent, exécution sans code), suppression. Aucune MariaDB ni portage-kit requis."""
import io, os, json, zipfile, tempfile, pathlib, importlib, sys

tmp = tempfile.mkdtemp(); os.environ["PORTAGE_DATA_DIR"] = tmp; os.environ["PORTAGE_KIT_DIR"] = tmp + "/no-kit"
sys.path.insert(0, os.path.dirname(__file__)); import app as appmod; importlib.reload(appmod)
c = appmod.app.test_client()

def zip_bytes(files):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        for k, v in files.items(): z.writestr(k, v)
    return b.getvalue()

def test_create_and_detect():
    r = c.post("/projects", json={"name": "Gestion Clés", "charset": "utf-8", "auth": {"test_login": "admin"}}); assert r.status_code == 201, r.json
    p = r.json["project"]; assert p["slug"] == "gestion-cl-s" and p["files"]["yml"] and not p["files"]["source"]
    assert c.post("/projects", json={"name": "Gestion Clés"}).status_code == 409
    z = zip_bytes({"monapp/index.php": "<?php $f3=require('lib/base.php'); $f3->route('GET /', 'C->a'); $f3->run();", "monapp/app/C.php": "<?php class C { function a($f3){} }"})
    r = c.post(f"/projects/{p['slug']}/code", data={"file": (io.BytesIO(z), "monapp.zip")}, content_type="multipart/form-data"); assert r.status_code == 200, r.json
    assert r.json["detected"] == {"kind": "fatfree", "entry": "index.php", "php_files": 2}
    assert (pathlib.Path(tmp) / "projects" / p["slug"] / "source" / "index.php").exists()      # dossier racine unique remonté
    y = c.get(f"/projects/{p['slug']}/report/yml").json["text"]; assert "kind: fatfree" in y and "charset: utf-8" in y and 'test_login: "admin"' in y

def test_zip_traversal_refused():
    p = c.post("/projects", json={"name": "trav"}).json["project"]
    b = io.BytesIO(); z = zipfile.ZipFile(b, "w"); z.writestr("../evil.php", "x"); z.close()
    r = c.post(f"/projects/{p['slug']}/code", data={"file": (io.BytesIO(b.getvalue()), "x.zip")}, content_type="multipart/form-data"); assert r.status_code == 400

def test_run_refusals_and_decisions():
    p = c.post("/projects", json={"name": "deux"}).json["project"]
    assert c.post(f"/projects/{p['slug']}/run", json={"steps": ["inventory"]}).status_code == 503      # kit absent
    assert c.put(f"/projects/{p['slug']}/decisions", json={"decisions": {"GET /": "différer"}}).status_code == 400
    spec = pathlib.Path(tmp) / "projects" / p["slug"] / "apps" / f"{p['slug']}.PORT_SPEC.md"
    spec.write_text("# s\n\n| unité | fichier:lignes | lit | écrit | entrées | mail | redirige | décision |\n|---|---|---|---|---|---|---|---|\n| `GET /` | a.php:1–2 | t | — | — |  | — |  |\n", encoding="utf-8")
    r = c.put(f"/projects/{p['slug']}/decisions", json={"decisions": {"GET /": "différer"}}); assert r.status_code == 200 and r.json["units"][0]["decision"] == "différer"
    assert c.put(f"/projects/{p['slug']}/decisions", json={"decisions": {"GET /": "n'importe quoi"}}).status_code == 400
    assert c.get(f"/projects/{p['slug']}/report/smoke").status_code == 404
    assert c.get(f"/projects/{p['slug']}/archive").status_code == 200
    assert c.delete(f"/projects/{p['slug']}").json["ok"] is True and c.get(f"/projects/{p['slug']}").status_code == 404

def test_list():
    r = c.get("/projects"); assert r.status_code == 200 and r.json["kit_installed"] is False and "smoke" in r.json["steps"]
