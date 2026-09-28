# si-agent sur un hôte à Python trop ancien (Python autonome)

L'agent `si-agent` requiert **Python ≥ 3.7** (f-strings 3.6, `subprocess.run(capture_output=, text=)` et `ThreadingHTTPServer` 3.7). Sur un hôte ancien — **Debian 9 / Proxmox VE 5 = Python 3.5** — il ne peut pas tourner tel quel, et `install.sh` **refuse désormais proprement** (au lieu d'installer un service qui boucle en crash au démarrage).

L'agent n'a **aucune dépendance tierce** (stdlib pure, `sqlite3` inclus dans le Python autonome). Il suffit donc d'un **interpréteur récent autonome** — aucun changement du Python système, aucun risque pour l'hôte — puis de lancer `install.sh --python <chemin>`.

## Option A — via `uv` (le plus simple)

```
curl -LsSf https://astral.sh/uv/install.sh | sh
~/.local/bin/uv python install 3.11
PYAGENT="$(~/.local/bin/uv python find 3.11)"
"$PYAGENT" --version                      # doit afficher 3.11.x
```

## Option B — archive python-build-standalone (sans uv)

Récupérer sur `https://github.com/astral-sh/python-build-standalone/releases/latest` l'asset `cpython-3.11.*-x86_64-unknown-linux-gnu-install_only.tar.gz`, puis :

```
mkdir -p /opt/pyagent && tar -xzf cpython-3.11.*.tar.gz -C /opt/pyagent
PYAGENT=/opt/pyagent/python/bin/python3
"$PYAGENT" --version
```

## Installer l'agent avec cet interpréteur

Mêmes options que d'habitude (enrôlement par jeton ou `--agent/--secret/--central`), en ajoutant `--python` :

```
# enrôlement par jeton, plugin proxmox laissé éteint :
SI_AGENT_ENROLL_TOKEN='<jeton>' SI_AGENT_CENTRAL='https://<central>/api/si-agent' SI_AGENT_SITE='ovh' \
  sudo ./install.sh --python "$PYAGENT" --no-detect
```

`install.sh` vérifie que `--python` est bien ≥ 3.7, écrit l'`ExecStart` du service systemd sur cet interpréteur, et démarre. Le reste (enrôlement, vérif CA) utilise le `python3` système pour de simples requêtes HTTP — volontairement compatibles 3.5, donc sans souci sur l'hôte ancien.

## Vérifier

```
systemctl status si-agent
PYTHONPATH=/opt/si-agent "$PYAGENT" -m si_agent.agent --status
```

À terme, mieux vaut **migrer/décommissionner** ces hôtes EOL que maintenir un runtime greffé ; ce montage est un pont, pas une cible.
