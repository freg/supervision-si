"""Tests qa-api sans navigateur : runner simulé (FakeRunner) et module Tickets simulé (Flask dans un thread).
Scénarios : site + connexion (mot de passe masqué en lecture, conservé en écriture), scénario (validation des étapes),
exécution avec captures, campagne de non-régression, ticket incident depuis une exécution (le scénario devient
non-régression, pas de doublon), suppression en cascade."""
import os, sys, json, tempfile, threading, pathlib, importlib
tmp = tempfile.mkdtemp(); os.environ["QA_DATA_DIR"] = tmp
from flask import Flask, jsonify, request as freq
fake = Flask("tickets"); created = []
@fake.route("/types")
def types(): return jsonify([{"id": 1, "label": "Incident"}, {"id": 2, "label": "Évolution"}])
@fake.route("/tickets", methods=["POST"])
def tk(): created.append(freq.get_json()); return jsonify(status="ok", id=100 + len(created)), 201
import socket; s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
threading.Thread(target=lambda: fake.run(port=port, use_reloader=False), daemon=True).start()
os.environ["TICKETS_API_INTERNAL_URL"] = f"http://127.0.0.1:{port}"
sys.path.insert(0, os.path.dirname(__file__)); import app as appmod; importlib.reload(appmod)

class FakeRunner:
    fail_at = None
    css_calls = []
    def run(self, base_url, login, steps, shots_dir, timeout_ms, mask=None, css=None):
        self.mask = mask
        if css: self.css_calls.append(css)
        pathlib.Path(shots_dir).mkdir(parents=True, exist_ok=True); res = []
        for i, st in enumerate(login, 1): res.append(dict(index=-(len(login) - i + 1), action=st["action"], ok=True, error="", duration_ms=1, shot="", login=True))
        for i, st in enumerate(steps, 1):
            ok = self.fail_at != i; (pathlib.Path(shots_dir) / f"step{i}.png").write_bytes(b"png")
            res.append(dict(index=i, action=st["action"], ok=ok, error="" if ok else "texte absent", duration_ms=2, shot=f"step{i}.png", login=False))
            if not ok: break
        return res, base_url + "/fin"
    def probe(self, url, t): return dict(title="Accueil", forms=[], links=[], headings=[], status=200, url=url)
appmod.RUNNER = FakeRunner(); c = appmod.app.test_client()

def test_site_and_login_masking():
    r = c.post("/sites", json={"name": "Site A", "base_url": "https://a.example/", "login_steps": [{"action": "goto", "value": "/login"}, {"action": "fill", "selector": "#login", "value": "u"}, {"action": "fill", "selector": "#pass", "value": "secret"}, {"action": "click", "selector": "#submit"}]})
    assert r.status_code == 201, r.json; site = r.json["site"]; assert site["base_url"] == "https://a.example" and site["login_steps"][2]["value"] == "••••" and site["has_login"]
    r = c.put(f"/sites/{site['id']}", json={"name": "Site A2", "login_steps": site["login_steps"]}); assert r.status_code == 200
    import sqlite3; cn = sqlite3.connect(appmod.DB_PATH); assert json.loads(cn.execute("SELECT login_steps FROM sites").fetchone()[0])[2]["value"] == "secret"
    assert c.post("/sites", json={"name": "x", "base_url": "ftp://x"}).status_code == 400
    assert c.post(f"/sites/{site['id']}/probe").json["probe"]["title"] == "Accueil"

def test_scenario_run_campaign_ticket():
    sid = c.get("/sites").json["sites"][0]["id"]
    assert c.post(f"/sites/{sid}/scenarios", json={"name": "bad", "steps": [{"action": "teleport"}]}).status_code == 400
    assert "sélecteur manquant" in c.post(f"/sites/{sid}/scenarios", json={"name": "bad", "steps": [{"action": "click"}]}).json["error"]
    x = c.post(f"/sites/{sid}/scenarios", json={"name": "Créer un ticket", "steps": [{"action": "goto", "value": "/tickets"}, {"action": "click", "selector": "a.new"}, {"action": "expect_text", "value": "Nouveau"}]}).json["scenario"]
    assert x["kind"] == "qa" and len(x["steps"]) == 3
    r = c.post(f"/scenarios/{x['id']}/run", json={"by_user": "freg"}).json["run"]; assert r["status"] == "ok" and r["summary"]["passed"] == 3 and r["results"][0]["login"]
    assert c.get(f"/runs/{r['id']}/shot/step1.png").status_code == 200 and c.get(f"/runs/{r['id']}/shot/../x.png").status_code == 404
    appmod.RUNNER.fail_at = 3
    r2 = c.post(f"/scenarios/{x['id']}/run").json["run"]; assert r2["status"] == "ko" and r2["summary"]["failed_index"] == 3 and "texte absent" in r2["summary"]["first_failure"]
    t = c.post(f"/runs/{r2['id']}/ticket", json={"kind": "incident", "comment": "Vu en recette"}); assert t.status_code == 201, t.json
    assert t.json["ticket_id"] == 101 and t.json["scenario"]["kind"] == "non-regression" and t.json["scenario"]["ticket_id"] == 101
    assert created[-1]["type_id"] == 1 and created[-1]["source_type"] == "qa" and "Vu en recette" in created[-1]["description"] and "✘ 3." in created[-1]["description"]
    assert c.post(f"/runs/{r2['id']}/ticket", json={"kind": "incident"}).status_code == 409
    appmod.RUNNER.fail_at = None
    camp = c.post(f"/sites/{sid}/campaign", json={"by_user": "freg"}); assert camp.status_code == 200, camp.json
    assert camp.json["campaign"]["total"] == 1 and camp.json["campaign"]["passed"] == 1 and camp.json["runs"][0]["scenario_name"] == "Créer un ticket"
    assert len(c.get(f"/scenarios/{x['id']}/runs").json["runs"]) == 3 and len(c.get(f"/sites/{sid}/campaigns").json["campaigns"]) == 1
    e = c.post(f"/runs/{camp.json['runs'][0]['id']}/ticket", json={"kind": "evolution"}).json; assert e["kind"] == "evolution" and created[-1]["type_id"] == 2 and "Évolution demandée" in created[-1]["description"]
    assert c.delete(f"/sites/{sid}").json["ok"] and c.get("/sites").json["sites"] == [] and not (pathlib.Path(tmp) / "runs" / str(r["id"])).exists()

def test_catalog():
    r = c.get("/catalog"); assert r.status_code == 200 and any(a["id"] == "expect_text" for a in r.json["actions"])

def test_hub_tour():
    """#721 : tour du hub généré depuis la liste des vues, régénéré sans doublon, audit accepté par le catalogue."""
    sid = c.post("/sites", json={"name": "Hub", "base_url": "https://hub.example"}).json["site"]["id"]
    assert c.post(f"/sites/{sid}/hub-tour", json={"views": [{"view": "../x"}]}).status_code == 400
    r = c.post(f"/sites/{sid}/hub-tour", json={"views": [{"view": "ups", "label": "Onduleurs"}, {"view": "cortex", "label": "Cortex"}]})
    assert r.status_code == 201 and r.json["views"] == 2 and [s["action"] for s in r.json["scenario"]["steps"]] == ["goto", "wait", "audit"] * 2
    r2 = c.post(f"/sites/{sid}/hub-tour", json={"views": [{"view": "ups"}]}); assert r2.status_code == 200 and r2.json["scenario"]["id"] == r.json["scenario"]["id"]
    assert len(c.get(f"/sites/{sid}/scenarios").json["scenarios"]) == 1
    assert c.post(f"/sites/{sid}/scenarios", json={"name": "a", "steps": [{"action": "audit", "value": "tout"}]}).status_code == 400
    assert any(a["id"] == "audit" for a in c.get("/catalog").json["actions"])
    run = c.post(f"/scenarios/{r.json['scenario']['id']}/run").json["run"]; assert run["status"] == "ok"
    c.delete(f"/sites/{sid}")

def test_reference_and_diff():
    """#727 : référence visuelle, écarts calculés entre deux exécutions, image de différence servie."""
    from PIL import Image, ImageDraw
    sid = c.post("/sites", json={"name": "Hub2", "base_url": "https://hub.example"}).json["site"]["id"]
    x = c.post(f"/sites/{sid}/scenarios", json={"name": "Accueil", "steps": [{"action": "goto", "value": "/"}, {"action": "screenshot"}]}).json["scenario"]
    assert c.put(f"/scenarios/{x['id']}", json={"mask": ".horloge, #compteur"}).json["scenario"]["mask"] == ".horloge, #compteur"
    r1 = c.post(f"/scenarios/{x['id']}/run").json["run"]; assert appmod.RUNNER.mask == [".horloge", "#compteur"]
    assert c.get(f"/runs/{r1['id']}/diff").status_code == 400                                   # pas de référence
    for rid, box in ((r1["id"], None), (None, (5, 5, 14, 14))):
        pass
    for i in (1, 2): Image.new("RGB", (40, 20), "white").save(pathlib.Path(tmp) / "runs" / str(r1["id"]) / f"step{i}.png")
    assert c.put(f"/scenarios/{x['id']}/reference", json={"run_id": r1["id"]}).json["scenario"]["ref_run_id"] == r1["id"]
    assert c.put(f"/scenarios/{x['id']}/reference", json={"run_id": 99999}).status_code == 400
    r2 = c.post(f"/scenarios/{x['id']}/run").json["run"]
    im = Image.new("RGB", (40, 20), "white"); ImageDraw.Draw(im).rectangle((5, 5, 14, 14), fill="blue"); im.save(pathlib.Path(tmp) / "runs" / str(r2["id"]) / "step2.png")
    Image.new("RGB", (40, 20), "white").save(pathlib.Path(tmp) / "runs" / str(r2["id"]) / "step1.png")
    dd = c.get(f"/runs/{r2['id']}/diff").json
    assert dd["against"] == r1["id"] and dd["significant"] == 1 and [s["ratio"] > 0 for s in dd["steps"]] == [False, True], dd
    assert c.get(f"/runs/{r2['id']}/shot/{dd['steps'][1]['diff']}").status_code == 200
    assert c.get(f"/runs/{r2['id']}/diff?against={r2['id']}").json["significant"] == 0           # rejouer contre une exécution choisie
    c.delete(f"/sites/{sid}")


def test_mockups():
    """#728 : maquette depuis une exécution avec audit -> variantes calculées, rendu (CSS injecté), présentation,
    exécutions de maquette hors historique, décision validée -> ticket évolution avec le correctif CSS."""
    sid = c.post("/sites", json={"name": "Hub M", "base_url": "https://hub.example"}).json["site"]["id"]
    x = c.post(f"/sites/{sid}/scenarios", json={"name": "Vue X", "steps": [{"action": "goto", "value": "/?view=x"}, {"action": "audit"}]}).json["scenario"]
    assert "Jouez d'abord" in c.post(f"/scenarios/{x['id']}/mockups", json={}).json["error"]
    base = c.post(f"/scenarios/{x['id']}/run").json["run"]
    import sqlite3; cn = sqlite3.connect(appmod.DB_PATH)
    res = base["results"]; res[-1].update(findings=[{"rule": "contraste", "severity": "erreur", "message": "m", "el": "span.muted", "fg": "rgb(170, 170, 170)", "bg": "rgb(255, 255, 255)", "need": 4.5}], score=85)
    cn.execute("UPDATE runs SET results = ? WHERE id = ?", (json.dumps(res), base["id"])); cn.commit()
    r = c.post(f"/scenarios/{x['id']}/mockups", json={"by_user": "freg"}); assert r.status_code == 201, r.json
    mk = r.json["mockup"]; assert [v["name"] for v in mk["variants"]] == ["Corrections de conformité", "Contraste renforcé (AAA)"] and mk["base_run_id"] == base["id"]
    assert [s["kind"] for s in mk["slides"]] == ["avant", "proposition", "variante", "regles", "decision"] and mk["slides"][0]["score"] == 85
    assert c.post(f"/mockups/{mk['id']}/decision", json={"status": "validee", "variant": 0}).status_code == 400   # pas encore rendue
    assert c.put(f"/mockups/{mk['id']}", json={"variants": [{"name": "x", "css": "<script>"}]}).status_code == 400
    n0 = len(appmod.RUNNER.css_calls); mk = c.post(f"/mockups/{mk['id']}/render").json["mockup"]
    assert len(appmod.RUNNER.css_calls) == n0 + 2 and "span.muted { color: #" in appmod.RUNNER.css_calls[-2] and mk["status"] == "presentee"
    assert mk["slides"][1]["rendered"] and mk["slides"][1]["run_id"] and mk["slides"][1]["diff"] is not None
    assert [r["id"] for r in c.get(f"/scenarios/{x['id']}/runs").json["runs"]] == [base["id"]]           # hors historique
    c.post(f"/mockups/{mk['id']}/render?variant=1"); assert len(appmod.RUNNER.css_calls) == n0 + 3
    assert cn.execute("SELECT COUNT(*) FROM runs WHERE mockup_id = ?", (mk["id"],)).fetchone()[0] == 2     # rendu remplacé, pas empilé
    d = c.post(f"/mockups/{mk['id']}/decision", json={"status": "validee", "variant": 0, "comment": "go"}); assert d.status_code == 200, d.json
    assert d.json["ticket_id"] and created[-1]["type_id"] == 2 and created[-1]["subject"] == "[QA maquette] Vue X — Corrections de conformité" and "span.muted" in created[-1]["description"]
    assert d.json["mockup"]["status"] == "validee" and d.json["mockup"]["chosen"] == 0
    assert c.put(f"/mockups/{mk['id']}", json={"name": "z"}).status_code == 409
    assert c.get(f"/scenarios/{x['id']}/mockups").json["mockups"][0]["ticket_id"] == d.json["ticket_id"]
    rids = [r[0] for r in cn.execute("SELECT id FROM runs WHERE mockup_id = ?", (mk["id"],))]
    assert c.delete(f"/mockups/{mk['id']}").json["ok"] and not (pathlib.Path(tmp) / "runs" / str(rids[0])).exists()
