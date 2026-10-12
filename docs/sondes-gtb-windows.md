# Sondes GTB/GTC sur poste Windows (livraison #739)

Cible : poste Windows 10 Pro 22H2 qui fait tourner un superviseur GTB ancien (ex. Neutrino GLT 9.x), pour trouver
pourquoi il perd ses automates ou ses remontées. Deux sondes de l'agent, livrées **désactivées**, privilégiées (compte SYSTEM).

| Sonde | Ce qu'elle voit | Outils (rien à installer) |
|---|---|---|
| `gtb-netwatch` | tentatives de connexion du poste vers les automates et inverses : acceptées, refusées (RST), sans réponse, injoignables (ICMP + routeur), coupées ; UDP BACnet/KNX/SNMP sans réponse ; automates qui n'arrivent pas à joindre le poste | `pktmon` (Windows 10 2004+), `Get-NetTCPConnection` ; sinon tcpdump/dumpcap |
| `app-logwatch` | processus et services de l'application, fichiers qu'ils tiennent ouverts (« lsof »), journaux récents, erreurs réseau (Winsock 10060/10061/10065/10054) et IP:port citées, plantages du journal d'événements | API Windows (ctypes), PowerShell ; `handle.exe` de Sysinternals s'il est posé à côté |

## Mise en route sur le poste

1. Agent installé comme d'habitude (`si-agent\agent\windows\install.cmd`), exclusion antivirus si besoin.
2. Hub → Agents → le poste → Sondes : activer `app-logwatch` puis `gtb-netwatch`.
3. Régler les arguments si besoin :
   - `gtb-netwatch` : `--targets 192.0.2.0/24` (réseau des automates : capture plus légère), `--process neutrino`,
     `--seconds 120`, `--keep C:\ProgramData\si-agent\captures` (garde la capture pour Wireshark) ;
   - `app-logwatch` : `--match neutrino,kieback`, `--paths D:\GLT\Log` si les journaux sont ailleurs.

Essai à la main (invite administrateur, depuis le dossier de l'agent) :

```
python\python.exe plugins\app-logwatch\app_logwatch.py --match neutrino,kieback --minutes 120
python\python.exe plugins\gtb-netwatch\gtb_netwatch.py --seconds 60 --process neutrino
```

## Lire les constats

- `tcp-no-answer` : l'automate ne répond pas (éteint, pare-feu, mauvaise route). `tcp-refused` : il répond « port fermé »
  (service de l'automate arrêté ou mauvais port configuré). `unreachable` : un routeur dit qu'il ne sait pas y aller.
- `inbound-refused` / `inbound-dropped` : un automate essaie de joindre le poste (alarmes) et le poste n'écoute pas, ou
  le pare-feu Windows jette.
- `udp-no-answer` sur 47808 : équipement BACnet absent ou BBMD non relayé entre réseaux.
- `log-network` : à croiser avec `gtb-netwatch` (mêmes IP:port). `service-stopped`, `app-crash` : côté logiciel.

## Limites

- `pktmon` : une seule capture à la fois sur le poste ; la sonde retire les filtres pktmon existants.
- Handles : énumération bornée à 60 s ; certains processus protégés ne se laissent pas lire.
- Seuls les en-têtes (128 octets) sont capturés, et le fichier est supprimé après analyse (sauf `--keep`).
