# si-agent : installeur MSI (livraison #824, BACKLOG 133)

**État : écrit et vérifié statiquement, pas encore construit ni installé sur un vrai Windows** — premier passage prévu
sur une VM Windows du pool de test (BACKLOG 133).

## Construire (Windows x64)

```powershell
dotnet tool install --global wix
wix extension add -g WixToolset.Util.wixext
cd <archive ou dépôt>\si-agent\agent
powershell -NoProfile -ExecutionPolicy Bypass -File .\windows\msi\build-msi.ps1 [-PythonSha256 <empreinte>] [-SignCert <empreinte certificat>]
```

Résultat : `windows\msi\out\si-agent-<version>.msi` (agent + Python embarqué : aucun téléchargement à l'installation).

## Installer

```powershell
msiexec /i si-agent-0.5.97.msi /qn CENTRAL=https://<central>:6443/api/si-agent TOKEN=<jeton du site> CAFINGERPRINT=<sha256 de la CA> SITE=siege /l*v si-agent-msi.log
```

| Propriété | Rôle |
|---|---|
| `CENTRAL` | URL du central (obligatoire à la première installation) |
| `TOKEN` | jeton d'enrôlement du site (obligatoire ; masqué dans le journal MSI) |
| `CAFINGERPRINT` | empreinte SHA-256 de la CA du central ; absente : magasin Windows (`-SystemCa`, central à certificat public) |
| `SITE` | site de l'agent (défaut `default`) |
| `PLUGINS` | sondes à activer, séparées par des virgules |
| `KEEPDATA=1` | à la désinstallation : garder `C:\ProgramData\si-agent` (configuration, file locale, journal) |

GPO : affectation de logiciel avec une transformation (.mst) portant ces propriétés ; Intune : application « line-of-business »
avec la ligne `msiexec` ci-dessus.

## Mettre à jour, désinstaller

- Nouvelle version du MSI : mise à jour majeure, `install.ps1 -Upgrade` (agent.json et enrôlement conservés).
- La mise à jour automatique par le central (#522) continue de fonctionner sur un poste installé par MSI.
- `msiexec /x si-agent-0.5.97.msi /qn` (ou Paramètres > Applications) : tâche planifiée et programme retirés ;
  données retirées sauf `KEEPDATA=1`.

## Ce que fait le MSI

Il pose l'archive de l'agent (`payload\`) et le Python embarqué (`python\`) dans `C:\Program Files\si-agent`, puis lance
le même `windows\install.ps1` que l'installation manuelle (enrôlement par jeton, CA vérifiée par empreinte,
`agent.json` réservé à SYSTEM et aux administrateurs, tâche planifiée SYSTEM). Une seule logique d'installation à
maintenir.
