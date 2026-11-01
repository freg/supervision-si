# -*- coding: utf-8 -*-
"""Création de comptes et affectation aux groupes (livraison LDAP).

Logique PURE, testable sans serveur : construction des DN, des fragments
LDIF (add compte, add/del membre de groupe), allocation d'un uidNumber libre
(max+1) et choix de l'attribut d'appartenance selon la classe du groupe.

Schéma repris de l'existant (compte de service du groupe exemple) : objectClass top +
posixAccount + inetOrgPerson ; cn = « prénom nom » ; displayName ; sn ;
givenName/mail optionnels ; uidNumber alloué ; gidNumber (défaut 65534) ;
homeDirectory /home/<uid> ; loginShell (défaut /bin/false) ; userPassword en
clair, HACHÉ PAR LE SERVEUR (ppolicy/olcPasswordHash). Les écritures partent
en LDIF via ldap_client.apply_ldif (ldapmodify) et l'erreur ldapmodify est
remontée telle quelle -- jamais avalée.
"""
import base64
import re

DEFAULT_OBJECT_CLASSES = ("top", "posixAccount", "inetOrgPerson")
UID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")


def valid_uid(uid):
    return bool(UID_RE.match((uid or "").strip()))


def _needs_b64(value):
    """RFC 2849 : valeur à encoder en base64 (:: ) si caractère de tête risqué,
    espace final, ou octet non imprimable / non-ASCII."""
    if value == "":
        return False
    if value[0] in (" ", ":", "<"):
        return True
    if value[-1] == " ":
        return True
    for ch in value:
        o = ord(ch)
        if o == 0 or o == 10 or o == 13 or o > 127:
            return True
    return False


def ldif_attr(name, value):
    """Une ligne d'attribut LDIF, base64 si nécessaire (accents, etc.)."""
    value = "" if value is None else str(value)
    if _needs_b64(value):
        enc = base64.b64encode(value.encode("utf-8")).decode("ascii")
        return "%s:: %s" % (name, enc)
    return "%s: %s" % (name, value)


def account_dn(uid, kind, accounts_dn, external_dn):
    """DN d'un compte selon le type : interne sous ou=accounts, externe sous
    ou=external,ou=accounts."""
    uid = (uid or "").strip()
    if kind == "externe":
        parent = external_dn
    elif kind == "interne":
        parent = accounts_dn
    else:
        raise ValueError("type de compte inconnu : %r (attendu 'interne' ou 'externe')" % kind)
    if not parent:
        raise ValueError("conteneur de comptes non configuré pour le type %r" % kind)
    return "uid=%s,%s" % (uid, parent)


def next_uid_number(uidnumber_text, floor=1000):
    """Plus grand uidNumber trouvé + 1, à partir de la sortie ldapsearch (lignes
    « uidNumber: N »). Renvoie None si aucun trouvé au-dessus du plancher --
    l'appelant refuse alors plutôt que de créer un compte à un numéro douteux."""
    maxi = 0
    for line in (uidnumber_text or "").splitlines():
        s = line.strip()
        if s.lower().startswith("uidnumber:"):
            frag = s.split(":", 1)[1].strip()
            try:
                n = int(frag)
            except ValueError:
                continue
            if n > maxi:
                maxi = n
    if maxi < floor:
        return None
    return maxi + 1


def build_add_account_ldif(dn, uid, sn, uid_number, gid_number,
                           given_name=None, mail=None, password=None,
                           login_shell="/bin/false", description=None,
                           object_classes=DEFAULT_OBJECT_CLASSES, home_directory=None):
    """Fragment LDIF « changetype: add » d'un compte. cn/displayName = « prénom
    nom » (ou nom seul si pas de prénom). home = /home/<uid> par défaut."""
    uid = uid.strip()
    sn = (sn or "").strip()
    given = (given_name or "").strip()
    cn = ("%s %s" % (given, sn)).strip() if given else sn
    home = home_directory or ("/home/%s" % uid)
    lines = ["dn: %s" % dn, "changetype: add"]
    for oc in object_classes:
        lines.append("objectClass: %s" % oc)
    lines.append(ldif_attr("uid", uid))
    lines.append(ldif_attr("cn", cn))
    lines.append(ldif_attr("displayName", cn))
    lines.append(ldif_attr("sn", sn))
    if given:
        lines.append(ldif_attr("givenName", given))
    if mail:
        lines.append(ldif_attr("mail", mail))
    lines.append(ldif_attr("uidNumber", str(uid_number)))
    lines.append(ldif_attr("gidNumber", str(gid_number)))
    lines.append(ldif_attr("homeDirectory", home))
    lines.append(ldif_attr("loginShell", login_shell))
    if password:
        lines.append(ldif_attr("userPassword", password))
    if description:
        lines.append(ldif_attr("description", description))
    return "\n".join(lines) + "\n"


def group_member_attr(object_classes):
    """Attribut d'appartenance selon la classe du groupe -- None si inconnu
    (l'appelant refuse alors explicitement, pas de supposition silencieuse)."""
    ocs = {str(o).lower() for o in (object_classes or [])}
    if "groupofnames" in ocs:
        return "member"
    if "groupofuniquenames" in ocs:
        return "uniqueMember"
    if "posixgroup" in ocs:
        return "memberUid"
    return None


def group_member_value(attr, user_dn, uid):
    """Valeur à écrire : le DN complet pour member/uniqueMember, l'uid pour
    memberUid (posixGroup)."""
    if attr == "memberUid":
        return uid
    return user_dn


def build_group_member_ldif(group_dn, attr, value, add=True):
    """Fragment LDIF modify add/delete d'un membre de groupe."""
    op = "add" if add else "delete"
    return "dn: %s\nchangetype: modify\n%s: %s\n%s\n" % (group_dn, op, attr, ldif_attr(attr, value))
