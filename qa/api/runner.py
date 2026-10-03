"""Exécution d'un scénario dans Chromium (Playwright). Isolé d'app.py pour être remplacé dans les tests (FakeRunner).
run(base_url, login, steps, shots_dir) -> (results, final_url) ; chaque résultat : {index, action, ok, error, duration_ms, shot}."""
import time, pathlib

def _abs(base, v): return v if v.startswith(("http://", "https://")) else base.rstrip("/") + "/" + v.lstrip("/")

def run(base_url, login, steps, shots_dir, timeout_ms=15000, width=1366, height=900):
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    shots = pathlib.Path(shots_dir); shots.mkdir(parents=True, exist_ok=True); results = []
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--ignore-certificate-errors"]); pg = b.new_page(viewport={"width": width, "height": height}, ignore_https_errors=True)
        pg.set_default_timeout(timeout_ms)
        all_steps = list(login or []) + list(steps)
        n_login = len(login or [])
        for i, st in enumerate(all_steps, 1):
            t0 = time.time(); ok, err = True, ""
            a, sel, val = st["action"], st.get("selector", ""), st.get("value", "")
            try:
                if a == "goto": pg.goto(_abs(base_url, val), wait_until="domcontentloaded")
                elif a == "click": pg.click(sel); pg.wait_for_load_state("domcontentloaded")
                elif a == "fill": pg.fill(sel, val)
                elif a == "select": pg.select_option(sel, val)
                elif a == "check": pg.check(sel)
                elif a == "press": pg.press(sel, val); pg.wait_for_load_state("domcontentloaded")
                elif a == "wait": pg.wait_for_timeout(int(val))
                elif a == "expect_visible": pg.wait_for_selector(sel, state="visible")
                elif a == "expect_absent": pg.wait_for_selector(sel, state="detached")
                elif a == "expect_text":
                    txt = pg.inner_text(sel) if sel else pg.inner_text("body")
                    if val not in txt: ok, err = False, f"texte « {val} » absent" + (f" de {sel}" if sel else " de la page")
                elif a == "expect_url":
                    if val not in pg.url: ok, err = False, f"URL « {pg.url} » ne contient pas « {val} »"
                elif a == "expect_value":
                    v = pg.input_value(sel)
                    if v != val: ok, err = False, f"valeur « {v} » au lieu de « {val} »"
                elif a == "screenshot": pass
            except PWTimeout as e: ok, err = False, "délai dépassé : " + str(e).split("\n")[0][:200]
            except Exception as e: ok, err = False, type(e).__name__ + " : " + str(e).split("\n")[0][:200]
            shot = ""
            if a in ("screenshot", "goto", "click", "press") or not ok:
                shot = f"step{i}.png"
                try: pg.screenshot(path=str(shots / shot), full_page=False)
                except Exception: shot = ""
            results.append(dict(index=i - n_login if i > n_login else -(n_login - i + 1), action=a, ok=ok, error=err, duration_ms=int((time.time() - t0) * 1000), shot=shot, login=i <= n_login))
            if not ok: break
        url = pg.url; b.close()
    return results, url

def probe(base_url, timeout_ms=15000):
    """Reconnaissance d'un site (porté ou non) : titre, formulaires et champs, liens — pour écrire les étapes."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--ignore-certificate-errors"]); pg = b.new_page(ignore_https_errors=True); pg.set_default_timeout(timeout_ms)
        r = pg.goto(base_url, wait_until="domcontentloaded")
        info = pg.evaluate("""() => ({
          title: document.title,
          forms: [...document.querySelectorAll('form')].slice(0, 10).map(f => ({ action: f.getAttribute('action') || '', method: (f.method || 'get').toLowerCase(),
             fields: [...f.querySelectorAll('input,select,textarea,button')].slice(0, 30).map(e => ({ tag: e.tagName.toLowerCase(), type: e.type || '', name: e.name || '', id: e.id || '', text: (e.value || e.textContent || '').trim().slice(0, 40) })) })),
          links: [...document.querySelectorAll('a[href]')].slice(0, 60).map(a => ({ text: a.textContent.trim().slice(0, 50), href: a.getAttribute('href') })),
          headings: [...document.querySelectorAll('h1,h2,h3')].slice(0, 20).map(h => h.textContent.trim().slice(0, 80)) })""")
        info["status"] = r.status if r else None; info["url"] = pg.url; b.close()
    return info
