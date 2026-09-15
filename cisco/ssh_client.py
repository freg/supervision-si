# -*- coding: utf-8 -*-
"""Session SSH interactive vers un équipement Cisco (IOS / NX-OS) --
livraison #508. paramiko en canal « shell » (les vieux IOS 12.x
n'acceptent pas toujours exec_command), invite détectée par expression
régulière, pagination désactivée (`terminal length 0`), passage en mode
enable si besoin, mode configuration pour les restaurations et gestes
d'urgence. Jamais de mot de passe dans les traces ni les erreurs.

Import de paramiko différé : les tests utilisent un faux transport.
"""
import re
import socket
import time

PROMPT_RE = re.compile(r"(?m)^[\w.\-()/:@]+[>#]\s*$")
MORE_RE = re.compile(r"--More--")
ERROR_RE = re.compile(r"^(% |ERROR:|Invalid input|Ambiguous command|Incomplete command|Command rejected|% Invalid)", re.M)


class CiscoError(Exception):
    pass


class CiscoSession:
    def __init__(self, host, username, password, port=22, timeout=10, enable_password=None, transport=None):
        self.host, self.port, self.timeout = host, int(port), timeout
        self._user, self._password, self._enable = username, password, enable_password or password
        self._chan = transport  # objet avec send()/recv(n)/recv_ready()/close() -- faux en test
        self._client = None
        self.platform = "ios"

    # --- connexion ---------------------------------------------------------
    def open(self):
        if self._chan is None:
            try:
                import paramiko
            except ImportError:
                raise CiscoError("paramiko absent")
            self._client = paramiko.SSHClient()
            self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            try:
                # algorithmes anciens tolérés (IOS 12.x : ssh-rsa, dh-group1) -- paramiko
                # les négocie de lui-même ; `look_for_keys=False` pour ne jamais tenter
                # une clé du conteneur.
                self._client.connect(self.host, port=self.port, username=self._user, password=self._password,
                                     timeout=self.timeout, allow_agent=False, look_for_keys=False, banner_timeout=self.timeout + 5)
                self._chan = self._client.invoke_shell(width=511, height=1000)
                self._chan.settimeout(self.timeout)
            except (socket.error, OSError, EOFError) as exc:
                raise CiscoError("connexion SSH impossible vers %s:%s (%s)" % (self.host, self.port, exc.__class__.__name__))
            except Exception as exc:  # noqa: BLE001 -- paramiko.AuthenticationException, SSHException…
                name = exc.__class__.__name__
                raise CiscoError("SSH %s : %s" % (self.host, "authentification refusée" if "Authentication" in name else name))
        # un retour chariot d'abord : la bannière et l'invite arrivent alors
        # dans tous les cas (équipement réel ou canal simulé)
        self.enable()
        self.run("terminal length 0")
        self.run("terminal width 511")
        return self

    def close(self):
        try:
            if self._chan:
                self._chan.close()
            if self._client:
                self._client.close()
        except Exception:  # noqa: BLE001
            pass

    def __enter__(self):
        return self.open()

    def __exit__(self, *exc):
        self.close()

    # --- bas niveau ----------------------------------------------------------
    def _read_until(self, pattern, timeout=None):
        deadline = time.monotonic() + (timeout or self.timeout)
        buf = ""
        while time.monotonic() < deadline:
            if self._chan.recv_ready():
                buf += self._chan.recv(65535).decode("utf-8", errors="replace")
                if MORE_RE.search(buf):
                    self._chan.send(" ")
                    buf = MORE_RE.sub("", buf)
                if pattern.search(buf):
                    return buf
            else:
                time.sleep(0.05)
        raise CiscoError("pas d'invite après %ss sur %s" % (timeout or self.timeout, self.host))

    def _expect_prompt(self, timeout=None):
        out = self._read_until(PROMPT_RE, timeout)
        return out

    def run(self, command, timeout=None):
        """Envoie une commande, rend sa sortie (sans l'écho ni l'invite)."""
        self._chan.send(command + "\n")
        out = self._expect_prompt(timeout)
        lines = out.replace("\r", "").split("\n")
        # retire l'écho de la commande (première ligne) et l'invite (dernière)
        if lines and command.strip() in lines[0]:
            lines = lines[1:]
        if lines and PROMPT_RE.match(lines[-1] + "\n") or (lines and re.match(r"^[\w.\-()/:@]+[>#]\s*$", lines[-1])):
            lines = lines[:-1]
        return "\n".join(lines).strip("\n")

    def enable(self):
        self._chan.send("\n")
        out = self._expect_prompt()
        last = out.replace("\r", "").strip().split("\n")[-1]
        if last.endswith(">"):
            self._chan.send("enable\n")
            got = self._read_until(re.compile(r"(?i)password:|[#]\s*$"))
            if "assword" in got:
                self._chan.send(self._enable + "\n")
                self._expect_prompt()
            last = "#"
        if not last.endswith("#"):
            raise CiscoError("mode enable indisponible sur %s" % self.host)

    # --- haut niveau --------------------------------------------------------
    def show(self, command, timeout=None):
        if not re.match(r"^\s*show\b", command):
            raise CiscoError("seules les commandes show sont acceptées ici")
        out = self.run(command, timeout)
        if ERROR_RE.search(out):
            raise CiscoError("commande refusée par l'équipement : %s" % command)
        return out

    def configure(self, lines, timeout=None):
        """Mode configuration : envoie les lignes, rend les erreurs éventuelles
        ligne par ligne (jamais silencieux). Termine par `end`."""
        results = []
        self.run("configure terminal", timeout)
        try:
            for line in lines:
                if not line.strip() or line.strip().startswith("!"):
                    continue
                out = self.run(line, timeout)
                if ERROR_RE.search(out):
                    results.append({"line": line, "error": out.strip()[:300]})
        finally:
            self.run("end", timeout)
        return results

    def write_memory(self, timeout=None):
        self._chan.send("write memory\n")
        out = self._read_until(re.compile(r"(?i)\[OK\]|Copy complete|\[confirm\]|[#]\s*$"), (timeout or self.timeout) * 3)
        if "[confirm]" in out:
            self._chan.send("\n")
            out += self._expect_prompt((timeout or self.timeout) * 3)
        if ERROR_RE.search(out):
            raise CiscoError("write memory refusé")
        return out
