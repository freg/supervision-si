# -*- coding: utf-8 -*-
"""Transport SSH pour RouterOS (livraison #587) -- « le hub doit être
transparent » : rien à activer sur le routeur (l'accès SSH existe déjà),
ni API REST (v7 seulement, service www-ssl), ni API binaire. Même surface
que RouterOSClient (get / patch / post_action) pour que la tuile ne change
pas, plus les règles NAT (nat_*).

Mécanique : une commande non interactive par appel (`ssh user+ct@routeur
"<commande>"`, `+ct` = sans couleurs ni pagination). Les objets sont lus par
le langage de script RouterOS -- `:put [/ip firewall nat get $i]` imprime
« .id=*1;chain=dstnat;… » (v6 comme v7) -- parsé par `parse_kv_list`.
Paramiko est importé à la demande : tests avec un exécuteur simulé.
"""
import logging
import re

log = logging.getLogger("mikrotik.ssh")


class RouterOSError(Exception):
    pass


# Ressources « objet unique » (`get` sans identifiant) ; le reste est une liste.
SINGLE = {"system/identity", "system/resource", "system/routerboard", "system/clock", "system/note", "ip/dns", "ip/settings"}
SAFE_VALUE_RE = re.compile(r"^[A-Za-z0-9 _.:/,\-+*@()\[\]#%=!]*$")
SAFE_WORD_RE = re.compile(r"^[A-Za-z0-9_.\-*:]+$")


def menu_path(path):
    """« ip/firewall/nat » -> « /ip firewall nat » (chemin REST -> menu CLI)."""
    parts = [p for p in str(path or "").strip("/").split("/") if p]
    if not all(re.match(r"^[a-z0-9-]+$", p) for p in parts):
        raise RouterOSError("chemin RouterOS invalide : %r" % path)
    return "/" + " ".join(parts)


def quote(value):
    v = str(value)
    if not SAFE_VALUE_RE.match(v):
        raise RouterOSError("valeur refusée (caractères interdits) : %r" % v)
    return '"%s"' % v


def to_cli(k, v):
    """Champ REST -> argument CLI : booléens « true/false » -> yes/no."""
    if isinstance(v, bool):
        v = "yes" if v else "no"
    elif str(v).lower() in ("true", "false"):
        v = "yes" if str(v).lower() == "true" else "no"
    if not re.match(r"^[a-z0-9.-]+$", k):
        raise RouterOSError("nom de champ invalide : %r" % k)
    return "%s=%s" % (k, quote(v))


def parse_kv_list(text):
    """Sortie de `:put [/x get $i]` (une ligne par objet, « k=v;k=v ») ->
    liste de dicts. Un « ; » dans une valeur (commentaire) est recollé au
    champ précédent ; les indicateurs `.id`, `disabled`… restent des chaînes
    comme en REST."""
    out = []
    for line in (text or "").replace("\r", "").split("\n"):
        line = line.strip()
        if not line or "=" not in line:
            continue
        rec, cur = {}, None
        for tok in line.split(";"):
            m = re.match(r"^(\.?[a-z][a-z0-9.-]*)=(.*)$", tok, re.S)
            if m:
                cur = m.group(1)
                rec[cur] = m.group(2)
            elif cur is not None:
                rec[cur] += ";" + tok
        if rec:
            out.append(rec)
    return out


def parse_print_single(text):
    """Sortie de `/x print` d'un objet unique : « clé: valeur » par ligne."""
    out = {}
    for line in (text or "").replace("\r", "").split("\n"):
        m = re.match(r"^\s*([a-z][a-z0-9.-]*):\s*(.*)$", line)
        if m:
            out[m.group(1)] = m.group(2).strip()
    return out


ERROR_RE = re.compile(r"(?m)^(syntax error|bad command name|expected end of command|input does not match|failure:|invalid value|no such item|ambiguous|not enough permissions|expected command name|missing value|bad argument)", re.I)


class RouterOSSsh(object):
    def __init__(self, host, port, user, password, timeout=12, runner=None):
        self.host, self.port, self.user, self.password, self.timeout = host, int(port or 22), user, password, timeout
        self._runner = runner  # tests : fonction (commande) -> (sortie, code)
        self._client = None

    # -- exécution ------------------------------------------------------------
    def _connect(self):
        if self._client is not None:
            return self._client
        import paramiko  # différé
        cli = paramiko.SSHClient()
        cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # empreinte non épinglée : patte interne (cf. README)
        user = self.user if "+" in self.user else self.user + "+ct"   # +c sans couleurs, +t « dumb terminal »
        try:
            cli.connect(self.host, port=self.port, username=user, password=self.password, timeout=self.timeout,
                        allow_agent=False, look_for_keys=False, banner_timeout=self.timeout)
        except Exception as exc:  # noqa: BLE001 -- paramiko lève plusieurs classes
            name = exc.__class__.__name__
            if "Authentication" in name:
                raise RouterOSError("authentification SSH refusée (accès du coffre à corriger dans la tuile Accès d'équipements ?)")
            raise RouterOSError("routeur injoignable en SSH %s:%d (%s)" % (self.host, self.port, name))
        self._client = cli
        return cli

    def run(self, command, stdin_text=None):
        """Exécute une commande RouterOS ; -> texte. Erreur RouterOS -> RouterOSError."""
        if self._runner is not None:
            out, code = self._runner(command)
        else:
            cli = self._connect()
            try:
                stdin, stdout, stderr = cli.exec_command(command, timeout=self.timeout)
                if stdin_text:
                    stdin.write(stdin_text)
                    stdin.flush()
                out = stdout.read().decode("utf-8", "replace") + stderr.read().decode("utf-8", "replace")
                code = stdout.channel.recv_exit_status()
            except Exception as exc:  # noqa: BLE001
                raise RouterOSError("commande SSH interrompue (%s)" % exc.__class__.__name__)
        out = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", out or "")
        if ERROR_RE.search(out) or code not in (0, None):
            raise RouterOSError("RouterOS : %s" % (out.strip().splitlines() or ["erreur (code %s)" % code])[0][:200])
        return out

    def close(self):
        if self._client is not None:
            try:
                self._client.close()
            except Exception:  # noqa: BLE001
                pass
            self._client = None

    # -- même surface que le client REST ------------------------------------------
    def get(self, path):
        menu = menu_path(path)
        if path.strip("/") in SINGLE:
            try:
                rows = parse_kv_list(self.run(":put [%s get]" % menu))
                if rows:
                    return rows[0]
            except RouterOSError:
                pass
            return parse_print_single(self.run("%s print" % menu))
        return parse_kv_list(self.run(":foreach i in=[%s find] do={:put [%s get $i]}" % (menu, menu)))

    def patch(self, path, fields):
        menu, _, ident = path.strip("/").rpartition("/")
        if not SAFE_WORD_RE.match(ident or ""):
            raise RouterOSError("identifiant invalide : %r" % ident)
        args = " ".join(to_cli(k, v) for k, v in (fields or {}).items())
        self.run("%s set %s %s" % (menu_path(menu), ident, args))
        return {}

    def post_action(self, path, args):
        menu = menu_path(path)
        if path.strip("/") == "system/reboot":
            self.run("/system reboot", stdin_text="y\n")
            return {}
        params = " ".join(to_cli(k, v) for k, v in (args or {}).items())
        out = self.run("%s %s" % (menu, params))
        return [{"output": l} for l in out.replace("\r", "").split("\n") if l.strip()]

    # -- règles NAT ---------------------------------------------------------------
    def nat_list(self):
        return self.get("ip/firewall/nat")

    def nat_add(self, fields):
        args = " ".join(to_cli(k, v) for k, v in fields.items())
        out = self.run("/ip firewall nat add %s" % args)
        return {"id": out.strip().splitlines()[0].strip() if out.strip() else None}

    def nat_set(self, ident, fields):
        return self.patch("ip/firewall/nat/%s" % ident, fields)

    def nat_remove(self, ident):
        if not SAFE_WORD_RE.match(ident or ""):
            raise RouterOSError("identifiant invalide")
        self.run("/ip firewall nat remove %s" % ident)
        return {}

    def nat_move(self, ident, before):
        if not (SAFE_WORD_RE.match(ident or "") and SAFE_WORD_RE.match(before or "")):
            raise RouterOSError("identifiant invalide")
        self.run("/ip firewall nat move %s destination=%s" % (ident, before))
        return {}


# -- commandes libres en lecture seule ---------------------------------------------
READ_ONLY_RE = re.compile(r"^(/[a-z0-9 /-]*?)\s*(print|export|monitor-traffic|get)(\s+[a-z0-9 =,.:\"/*_@<>!-]*)?$", re.I)
FORBIDDEN_RE = re.compile(r"\b(set|add|remove|enable|disable|reboot|reset|shutdown|upgrade|install|import|run|move|unset|password|/tool fetch|/system script)\b|[;{}\[\]$]", re.I)


def read_only_command(cmd):
    """Vrai si la commande ne peut rien modifier (print / export / get / monitor)."""
    c = " ".join(str(cmd or "").strip().split())
    return bool(READ_ONLY_RE.match(c)) and not FORBIDDEN_RE.search(c)
