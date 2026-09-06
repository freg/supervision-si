"""
Parsing et diff LDIF (RFC 2849) -- fondation du front de gestion
OpenLDAP, testable intégralement sans dépendance externe (ni
bibliothèque LDAP, ni serveur réel, aucun des deux disponibles dans
cet environnement de développement -- voir ldap_client.py pour la
partie qui, elle, ne peut être que partiellement vérifiée ici).

Choix assumé après clarification avec la personne : le format de
sauvegarde est du LDIF STANDARD (RFC 2849), produit et réinjectable
avec les outils habituels (`ldapsearch`/`ldapmodify`/`ldapadd`)
DEPUIS UN SHELL, indépendamment de cette interface -- jamais un
format maison. L'historique "façon git" (diffs entre versions) est
construit PAR-DESSUS ce format standard, pas à sa place.

Représentation interne d'un LDIF parsé : dict ordonné
{dn: {attribut: [valeurs...]}} -- une liste de valeurs même pour un
attribut mono-valué, jamais une distinction spéciale à gérer côté
appelant.
"""

import base64
from collections import OrderedDict


def parse_ldif(text):
    """Parse un texte LDIF en {dn: {attribut: [valeurs]}} (ordonné,
    préserve l'ordre d'apparition des entrées -- utile pour un diff
    lisible). Gère :
    - les commentaires (lignes commençant par '#'), ignorés ;
    - les attributs multi-valués (même nom d'attribut répété) ;
    - les valeurs encodées en base64 ('attr:: valeur', double
      deux-points) -- décodées, mais REPRÉSENTÉES avec un préfixe
      '(base64) ' plutôt que les octets bruts : un diff sur du
      binaire brut (ex. jpegPhoto) n'apporte rien de lisible, jamais
      une tentative de décoder comme du texte ce qui ne l'est pas ;
    - le repliement de ligne LDIF (une ligne continuant la
      précédente commence par UNE espace) ;
    - les lignes vides comme séparateurs d'entrées.
    Une entrée sans 'dn:' valide en tête est ignorée silencieusement
    plutôt que de faire échouer tout le parsing -- un LDIF réel peut
    contenir des blocs de commentaires ou du bruit en tête de
    fichier."""
    entries = OrderedDict()
    current_dn = None
    current_attrs = None
    raw_lines = text.replace("\r\n", "\n").split("\n")

    # Première passe : dé-repliement des lignes continuées.
    logical_lines = []
    for line in raw_lines:
        if line.startswith(" ") and logical_lines:
            logical_lines[-1] += line[1:]
        else:
            logical_lines.append(line)

    def flush():
        nonlocal current_dn, current_attrs
        if current_dn is not None and current_attrs is not None:
            entries[current_dn] = current_attrs
        current_dn = None
        current_attrs = None

    for line in logical_lines:
        if line.startswith("#"):
            continue
        if line.strip() == "":
            flush()
            continue

        if line.startswith("dn::"):
            # dn lui-même encodé en base64 -- rare mais valide RFC 2849.
            try:
                current_dn = base64.b64decode(line[4:].strip()).decode("utf-8", errors="replace")
            except Exception:
                continue
            current_attrs = OrderedDict()
            continue
        if line.startswith("dn:"):
            current_dn = line[3:].strip()
            current_attrs = OrderedDict()
            continue

        if current_attrs is None:
            continue  # ligne orpheline avant tout 'dn:' -- ignorée

        if "::" in line:
            attr, _, raw_value = line.partition("::")
            attr = attr.strip()
            try:
                decoded = base64.b64decode(raw_value.strip())
                try:
                    value = "(base64) " + decoded.decode("utf-8")
                except UnicodeDecodeError:
                    value = f"(base64, {len(decoded)} octets binaires)"
            except Exception:
                value = "(base64 invalide)"
        elif ":" in line:
            attr, _, value = line.partition(":")
            attr = attr.strip()
            value = value.strip()
        else:
            continue  # ligne mal formée -- ignorée plutôt que de faire échouer tout le parsing

        current_attrs.setdefault(attr, []).append(value)

    flush()
    return entries


def write_ldif(entries):
    """Sérialise {dn: {attribut: [valeurs]}} en texte LDIF standard --
    inverse de parse_ldif pour ce qui est représentable en texte
    (les valeurs déjà décodées depuis du base64 texte restent en
    clair ; celles marquées binaires ne sont PAS ré-encodées, cette
    fonction sert à la lecture humaine et aux sauvegardes, jamais à
    reconstruire un LDIF bit-à-bit identique à l'original)."""
    lines = []
    for dn, attrs in entries.items():
        lines.append(f"dn: {dn}")
        for attr, values in attrs.items():
            for value in values:
                lines.append(f"{attr}: {value}")
        lines.append("")  # ligne vide = séparateur d'entrées
    return "\n".join(lines)


def diff_ldif(old_entries, new_entries):
    """Diff "façon git" entre deux instantanés déjà parsés -- demandé
    explicitement. Renvoie {added: [dn...], removed: [dn...],
    modified: [{dn, attr_changes: {attr: {old: [...], new: [...]}}}]}
    -- jamais une liste plate indifférenciée, pour permettre un
    affichage groupé côté interface (entrées ajoutées/supprimées vs
    entrées juste modifiées, avec le détail attribut par attribut
    pour ces dernières)."""
    old_dns = set(old_entries.keys())
    new_dns = set(new_entries.keys())

    added = sorted(new_dns - old_dns)
    removed = sorted(old_dns - new_dns)

    modified = []
    for dn in sorted(old_dns & new_dns):
        old_attrs = old_entries[dn]
        new_attrs = new_entries[dn]
        attr_changes = {}
        all_attr_names = set(old_attrs.keys()) | set(new_attrs.keys())
        for attr in sorted(all_attr_names):
            old_values = old_attrs.get(attr, [])
            new_values = new_attrs.get(attr, [])
            if sorted(old_values) != sorted(new_values):
                attr_changes[attr] = {"old": old_values, "new": new_values}
        if attr_changes:
            modified.append({"dn": dn, "attr_changes": attr_changes})

    return {"added": added, "removed": removed, "modified": modified}
