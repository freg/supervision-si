"""Logique pure du module portage (testée à part, jamais enfouie dans app.py) :
- construction du apps/<app>.yml attendu par portage-kit depuis la fiche projet ;
- lecture/écriture de la colonne « décision » du PORT_SPEC.md produit par kit/inventory.py ;
- détection du type d'application (monolithe à switch($mode) ou Fat-Free) dans le code importé."""
import re, pathlib

DECISIONS = ["", "porter tel quel", "porter en simplifiant", "différer", "ne pas porter (mort)"]
ROW_RE = re.compile(r"^\|\s*`([^`]+)`\s*\|(.*)\|\s*$")

def slugify(name):
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return s or "projet"

def env_prefix(slug):
    return re.sub(r"[^A-Z0-9]+", "_", slug.upper()).strip("_") or "APP"

def build_app_yml(project, source_dir, db):
    """Fichier apps/<slug>.yml : app/db/auth/visual. `db` = dict(host, user, password, name, socket)."""
    def q(v): return '"' + str(v).replace('"', '\\"') + '"'
    L = [f"# Projet de portage « {project['name']} » (généré par le module portage du hub)",
         "app:", f"  name: {project['slug']}", f"  kind: {project.get('kind') or 'fatfree'}", f"  source: {q(source_dir)}",
         f"  entry: {project.get('entry') or 'index.php'}", f"  charset: {project.get('charset') or 'latin1'}", f"  env_prefix: {env_prefix(project['slug'])}",
         "db:", f"  name: {db['name']}", f"  user: {db.get('user') or 'root'}", f"  password: {q(db.get('password') or '')}"]
    if db.get("socket"): L.append(f"  socket: {q(db['socket'])}")
    else: L.append(f"  host: {db.get('host') or 'localhost'}")
    L.append(f"  table_prefix: {q(project.get('table_prefix') or '')}")
    a = project.get("auth") or {}
    L += ["auth:", f"  test_login: {q(a.get('test_login') or '')}", f"  test_password: {q(a.get('test_password') or '')}"]
    if a.get("users_table"):
        L.append("  users: {table: %s, id: %s, login: %s, password: %s, name: %s, type: %s, admin_type: %s, domains: %s}" % (
            a["users_table"], a.get("id_col") or "id", a.get("login_col") or "login", a.get("password_col") or "password",
            a.get("name_col") or "name", a.get("type_col") or "type", a.get("admin_type") or "Admin", a.get("domains_col") or "null"))
    if not a.get("domains_table"): L.append("  domains: null")
    else: L.append("  domains: {table: %s, id: %s, label: %s}" % (a["domains_table"], a.get("domains_id_col") or "id", a.get("domains_label_col") or "label"))
    L += ["visual:", "  widths: [1400, 900]", "  screens: {}"]
    return "\n".join(L) + "\n"

def read_decisions(text):
    """PORT_SPEC.md -> liste de {unit, file, reads, writes, inputs, mail, redirects, decision} (tableau des unités seulement)."""
    rows, in_units = [], False
    for line in text.splitlines():
        if line.startswith("## "): in_units = False
        if line.startswith("| unité"): in_units = True; continue
        m = ROW_RE.match(line)
        if not in_units or not m: continue
        cells = [c.strip() for c in m.group(2).split("|")]
        if len(cells) < 7: cells += [""] * (7 - len(cells))
        rows.append(dict(unit=m.group(1), file=cells[0], reads=cells[1], writes=cells[2], inputs=cells[3], mail=cells[4], redirects=cells[5], decision=cells[6]))
    return rows

def write_decisions(text, decisions):
    """Réécrit la colonne décision des unités citées (dict unité -> décision) ; les autres lignes restent intactes."""
    out = []
    for line in text.splitlines():
        m = ROW_RE.match(line)
        if m and m.group(1) in decisions and not line.startswith("| unité"):
            cells = [c.strip() for c in m.group(2).split("|")]
            if len(cells) < 7: cells += [""] * (7 - len(cells))
            cells[6] = decisions[m.group(1)]
            line = "| `%s` | %s |" % (m.group(1), " | ".join(cells[:7]))
        out.append(line)
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")

def detect_kind(source_dir):
    """fatfree si un index.php route avec $f3->route/F3::route ou un [routes] dans un .ini ; monolith si un switch($mode) ; (kind, entry)."""
    src = pathlib.Path(source_dir)
    entry = None
    for cand in ("index.php", "optick.php", "main.php"):
        if (src / cand).exists(): entry = cand; break
    phps = sorted(src.rglob("*.php"))[:400]
    for f in phps:
        try: t = f.read_text(encoding="latin-1", errors="replace")
        except OSError: continue
        if re.search(r"\$f3->(route|map)\s*\(|F3::route\s*\(", t): return "fatfree", entry or str(f.relative_to(src))
    for ini in src.rglob("*.ini"):
        if re.search(r"^\[routes\]", ini.read_text(encoding="latin-1", errors="replace"), re.M): return "fatfree", entry or "index.php"
    best = None
    for f in phps:
        t = f.read_text(encoding="latin-1", errors="replace")
        n = len(re.findall(r"^\s*case\s+['\"]\w+['\"]\s*:", t, re.M))
        if re.search(r"^\s*switch\s*\(\$\w+\)", t, re.M) and n > (best[1] if best else 3): best = (str(f.relative_to(src)), n)
    if best: return "monolith", best[0]
    return "fatfree" if entry else "", entry or "index.php"
