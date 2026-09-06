"""
Extraction de structures de données CANDIDATES depuis des vues
d'écran HTML (livraison #245, backlog item 30 -- "Rétro-ingénierie",
extension demandée explicitement : "importer du php et des vues
d'écran en html puis d'en déduire une partie des structures de
données"). Complète `php_sql_scanner.py` (relations déduites des
JOINTURES SQL) -- ici, les CHAMPS d'une entité sont déduits de ce
que l'écran affiche ou soumet, trois signaux distincts :

1. **Champs de formulaire** (`name="..."` sur input/select/textarea,
   à l'intérieur d'un `<form>`) -- le signal le plus fiable, un
   formulaire de saisie correspond quasi toujours DIRECTEMENT aux
   colonnes d'une table dans une vieille application PHP sans forte
   couche d'abstraction.
2. **Accès aux champs dans le moteur de gabarits Fat-Free natif**
   (`{{@item.champ}}` ou `{{@item['champ']}}`, notamment à
   l'intérieur d'une boucle `<repeat>` -- confirmé par la
   documentation officielle F3 : "item contains the array of data
   retrieved from the database table... accessed using the column
   name as the array key").
3. **Accès aux champs en PHP brut affiché directement**
   (`<?= $row['champ'] ?>` ou `<?php echo $row->champ; ?>`) -- les
   applications Fat-Free plus anciennes utilisent souvent des vues
   PHP classiques (classe `View`) plutôt que le moteur de gabarits
   natif -- la personne a signalé explicitement que le code varie
   "selon les époques de l'évolution".

**Approche VOLONTAIREMENT PAR EXPRESSION RÉGULIÈRE**, même
philosophie que `php_sql_scanner.py` -- CANDIDATS à valider
humainement, jamais une certitude. Restreint aux motifs D'AFFICHAGE
(echo/`<?=`) plutôt que tout accès PHP à un tableau/objet -- un
tableau PHP sert à mille choses (config, session...) qui n'ont rien
à voir avec une structure de données métier ; se limiter à ce qui
est RÉELLEMENT AFFICHÉ À L'ÉCRAN garde le signal propre, quitte à
manquer des champs jamais affichés nulle part (limite acceptée,
jamais un faux positif au prix d'un vrai manqué).
"""
import re

# Bloc <form ...>...</form> complet, action capturée séparément.
_FORM_BLOCK_PATTERN = re.compile(r"<form\b([^>]*)>(.*?)</form>", re.IGNORECASE | re.DOTALL)
_FORM_ACTION_PATTERN = re.compile(r'action\s*=\s*["\']([^"\']*)["\']', re.IGNORECASE)

# name="..." sur input/select/textarea -- accepte aussi bien
# name="champ" que name="entite[champ]" (motif de soumission
# structurée courant en PHP ancien style).
_FIELD_NAME_PATTERN = re.compile(
    r'<(?:input|select|textarea)\b[^>]*\bname\s*=\s*["\']([^"\']+)["\']',
    re.IGNORECASE,
)
_ARRAY_STYLE_NAME_PATTERN = re.compile(r"^(\w+)\[(\w+)\]$")

# {{@item.champ}} ou {{@item['champ']}} ou {{@item["champ"]}} --
# espaces autour de @ et du contenu TOUJOURS optionnels (confirmé :
# la syntaxe F3 documentée est {{@name}}, sans espace obligatoire).
_F3_TEMPLATE_FIELD_PATTERN = re.compile(
    r"\{\{\s*@(\w+)(?:\.(\w+)|\[\s*['\"](\w+)['\"]\s*\])\s*\}\}"
)

# <?= $var['champ'] ?> / <?= $var->champ ?> / <?php echo $var['champ']; ?>
# -- restreint au contexte ECHO/court-tag (voir docstring du module :
# uniquement ce qui est réellement AFFICHÉ, jamais tout accès PHP).
_PHP_ECHO_FIELD_PATTERN = re.compile(
    r"<\?(?:php\s+)?(?:=|echo)\s+\$(\w+)(?:\[\s*['\"](\w+)['\"]\s*\]|->(\w+))",
    re.IGNORECASE,
)


def extract_form_fields(html_text, filename=None):
    """Renvoie une liste de {form_action, fields: [...], source_file}
    -- un élément par bloc `<form>` trouvé. `fields` : noms bruts
    (le split `entite[champ]` -> `champ` n'est PAS fait ici, laissé
    visible tel quel -- la personne verra immédiatement le préfixe
    d'origine, utile pour repérer LE groupe logique du formulaire)."""
    results = []
    for match in _FORM_BLOCK_PATTERN.finditer(html_text):
        attrs, body = match.group(1), match.group(2)
        action_match = _FORM_ACTION_PATTERN.search(attrs)
        fields = _FIELD_NAME_PATTERN.findall(body)
        if not fields:
            continue  # un <form> sans aucun champ nommé n'apporte rien
        results.append({
            "form_action": action_match.group(1) if action_match else None,
            "fields": fields,
            "source_file": filename,
        })
    return results


def extract_template_field_access(html_text):
    """Renvoie {variable_racine: {champ1, champ2, ...}} -- regroupe
    TOUS les accès aux champs d'une même variable (ex. `@item`)
    trouvés dans le texte, tous motifs confondus (gabarit F3 natif +
    PHP brut affiché). Une variable accédée SANS jamais de champ
    précis (juste `{{@nom}}` seul) n'apparaît PAS ici -- rien à en
    tirer comme structure."""
    grouped = {}

    def _add(root, field):
        if not field:
            return
        grouped.setdefault(root, set()).add(field)

    for match in _F3_TEMPLATE_FIELD_PATTERN.finditer(html_text):
        root, dot_field, bracket_field = match.groups()
        _add(root, dot_field or bracket_field)

    for match in _PHP_ECHO_FIELD_PATTERN.finditer(html_text):
        root, bracket_field, arrow_field = match.groups()
        _add(root, bracket_field or arrow_field)

    return grouped


def scan_view_source(text, filename=None):
    """Point d'entrée principal, même motif que
    `php_sql_scanner.scan_php_source` -- appelé sur CHAQUE fichier
    `.php`/`.html`/`.htm`/`.phtml` d'une archive (une vue Fat-Free
    peut être écrite dans n'importe laquelle de ces extensions selon
    l'époque). Renvoie {"forms": [...], "template_fields": {racine:
    [champs triés]}}."""
    forms = extract_form_fields(text, filename=filename)
    template_fields_raw = extract_template_field_access(text)
    template_fields = {root: sorted(fields) for root, fields in template_fields_raw.items()}
    return {"forms": forms, "template_fields": template_fields}


def merge_template_field_results(results):
    """Fusionne plusieurs résultats de `scan_view_source` (un par
    fichier) en UN SEUL regroupement {variable_racine: [champs]} --
    la MÊME variable (ex. `@client`) apparaît généralement dans
    PLUSIEURS écrans (liste, fiche, formulaire d'édition...), chacun
    n'en révélant qu'une partie ; fusionner donne la structure la
    plus complète possible à partir de l'ensemble des vues."""
    merged = {}
    for result in results:
        for root, fields in result.get("template_fields", {}).items():
            merged.setdefault(root, set()).update(fields)
    return {root: sorted(fields) for root, fields in merged.items()}
