# Agent relais des parcours (livraison #441)

`python3 relay.py --central https://VM:6443/api/retro --token <RETRO_RELAY_TOKEN> [--ca ca.crt | --insecure] [--port 6320]`
ou `--config relay.json` (`{"central_url", "token", "ca_file", "insecure", "port", "queue_path"}`).
Python 3 seul. Écoute en local (127.0.0.1) pour l'extension ; file SQLite
`~/.retro-relay/queue.db` ; lots envoyés toutes les 2 s, rejoués après une
coupure. `python3 -m unittest test_relay` (faux central, panne et rejeu).
