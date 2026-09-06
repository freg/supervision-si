"""
Extraction du schéma FONCTIONNEL de l'application -- écrans, actions,
routes -- depuis les déclarations de routage Fat-Free (livraison
#248, backlog item 30 -- "Rétro-ingénierie", second volet demandé à
l'origine : "proposer un schéma fonctionnel de l'interface").
Complète `php_sql_scanner.py` (relations de données) et
`html_view_scanner.py` (structures de champs) -- ici, ce n'est plus
la DONNÉE qui est déduite mais l'ORGANISATION de l'application
elle-même : quels écrans/actions existent, quel contrôleur les gère,
quels paramètres d'URL ils acceptent.

**Syntaxe F3 VÉRIFIÉE via la documentation officielle avant de
coder** (jamais devinée) : `$f3->route('GET /chemin', handler)` --
le handler est soit une CLOSURE inline (function...), soit une
chaîne `'Classe->methode'` (instance) ou `'Classe::methode'`
(statique). Plusieurs méthodes HTTP séparées par `|`
(`'GET|POST /chemin'`). Alias optionnel (`'GET @nom: /chemin'`).
Jetons de paramètre d'URL préfixés par `@` dans le CHEMIN lui-même
(`/client/@id`) -- à ne pas confondre avec l'alias de route, qui
utilise la MÊME syntaxe `@` mais À UN ENDROIT DIFFÉRENT du motif
(entre la méthode et le chemin, jamais dans le chemin). Ancien style
statique `F3::route(...)` (versions plus anciennes de F3) également
couvert -- la personne a signalé que son code varie "selon les
époques".

**Approche VOLONTAIREMENT PAR EXPRESSION RÉGULIÈRE**, même
philosophie que les deux autres scanners de ce module -- une
CLOSURE inline n'est PAS entièrement extraite (corps de fonction
potentiellement complexe, multi-lignes, avec des parenthèses/
accolades imbriquées -- fragile à capturer fidèlement par regex) ;
seule sa PRÉSENCE est signalée (`handler_type: "closure"`), la
personne retrouve le détail directement dans le fichier via le
numéro de ligne fourni.
"""
import re

# $f3->route('...', ...) ou F3::route('...', ...) -- capture le
# motif de route (groupe 1) et, SI le second argument est une chaîne
# littérale simple juste après (pas une closure), le handler
# (groupe 2, None sinon -- traité comme une closure inline).
_ROUTE_CALL_PATTERN = re.compile(
    r"(?:\$\w+\s*->\s*route|F3::route)\s*\(\s*['\"]([^'\"]+)['\"]\s*,\s*(?:['\"]([^'\"]+)['\"])?",
)

# Alias de route -- "GET @nom: /chemin" -- l'alias apparaît ENTRE les
# méthodes et le chemin, précédé d'un @ et suivi de ":". Distinct des
# jetons @param dans le CHEMIN lui-même (voir _URL_TOKEN_PATTERN).
_ALIAS_PATTERN = re.compile(r"^([\w|]+)\s+@(\w+):\s*(.+)$")

# Jeton de paramètre dynamique DANS le chemin -- "/client/@id" -> "id".
_URL_TOKEN_PATTERN = re.compile(r"@(\w+)")


def parse_route_pattern(pattern):
    """Décompose le PREMIER argument de `route()` -- ex.
    "GET|POST /client/@id" -- en {"methods": [...], "path": str,
    "alias": str|None, "url_tokens": [...]}."""
    alias_match = _ALIAS_PATTERN.match(pattern)
    if alias_match:
        methods_str, alias, path = alias_match.groups()
    else:
        parts = pattern.split(None, 1)
        methods_str = parts[0] if parts else ""
        path = parts[1] if len(parts) > 1 else ""
        alias = None
    methods = [m for m in methods_str.split("|") if m]
    url_tokens = _URL_TOKEN_PATTERN.findall(path)
    return {"methods": methods, "path": path.strip(), "alias": alias, "url_tokens": url_tokens}


def _split_handler(handler_str):
    """'Controller\\Admin->login' -> ("Controller\\Admin", "login",
    "instance") ; 'Controller\\Auth::login' -> (..., "static"). None
    partout si le format n'est reconnu ni comme instance ni comme
    statique (ex. un simple nom de fonction globale, sans classe)."""
    if "->" in handler_str:
        cls, method = handler_str.split("->", 1)
        return cls, method, "instance"
    if "::" in handler_str:
        cls, method = handler_str.split("::", 1)
        return cls, method, "static"
    return None, handler_str, "function"


def extract_routes(php_text, filename=None):
    """Renvoie une liste de routes CANDIDATES -- une par appel
    `route()` trouvé. Chaque route : {methods, path, alias,
    url_tokens, handler_type ("instance"|"static"|"function"|
    "closure"), controller_class, controller_method, source_file,
    source_line}."""
    routes = []
    for line_number, line in enumerate(php_text.splitlines(), start=1):
        for match in _ROUTE_CALL_PATTERN.finditer(line):
            raw_pattern, handler_str = match.groups()
            parsed = parse_route_pattern(raw_pattern)
            if handler_str:
                cls, method, handler_type = _split_handler(handler_str)
            else:
                cls, method, handler_type = None, None, "closure"
            routes.append({
                **parsed,
                "handler_type": handler_type,
                "controller_class": cls,
                "controller_method": method,
                "source_file": filename,
                "source_line": line_number,
            })
    return routes


def group_routes_by_controller(routes):
    """Regroupe les routes par contrôleur (`controller_class`) --
    donne directement la vue "quels écrans/actions gère CE
    contrôleur", le cœur du schéma fonctionnel demandé. Les routes
    SANS contrôleur identifiable (closures inline, fonctions
    globales) sont regroupées sous la clé `None` -- toujours visibles,
    jamais perdues silencieusement."""
    grouped = {}
    for route in routes:
        key = route["controller_class"]
        grouped.setdefault(key, []).append(route)
    return grouped
