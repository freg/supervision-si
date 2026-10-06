# vuln — vulnérabilités du SI (livraison #688)

Quatre orientations, une chaîne :

| Brique | Rôle ici |
|---|---|
| **syft** | inventaire logiciel (SBOM CycloneDX) d'un hôte, d'une image, d'un dépôt — sur l'hôte (agent, tranche 2) ou ici (`POST /scan/self` : le dépôt supervision-si monté en lecture seule) |
| **osv-scanner** | correspondance des composants avec la base OSV (avis GHSA, PYSEC, Debian, Alpine, Go, npm…) |
| **EPSS** (FIRST) | probabilité d'exploitation à 30 jours, rechargée chaque jour (`EPSS_URL`) |
| **KEV** (CISA) | vulnérabilités exploitées activement, rechargées chaque jour (`KEV_URLS`, miroir GitHub en secours) |
| **Dependency-Track** | (option, `DT_URL` + `DT_API_KEY`) dépôt de référence : historique, politiques, licences, VEX — chaque SBOM y est déposé (`PUT /api/v1/bom`, projet créé au besoin) |

Priorité : **P1** exploitée activement (KEV), ou EPSS ≥ 0,5 sur un actif exposé ; **P2** EPSS ≥ 0,1 (centile ≥ 0,95)
ou critique (CVSS ≥ 9) exposée ; **P3** CVSS ≥ 7 ou EPSS ≥ 0,01 ; **P4** le reste. Chaque rechargement des flux
re-priorise tout : une CVE qui entre au catalogue KEV remonte d'elle-même en P1.

## API (`/api/vuln/`)

- `POST /sbom?asset=<nom>&kind=host|image|app|repo|device&exposed=0|1` — SBOM CycloneDX JSON (corps ou `file`)
- `POST /scan/self` — SBOM du dépôt par syft puis même chaîne
- `POST /feeds/refresh`, `GET /feeds`, `GET /epss/<cve>`
- `GET /summary`, `GET /assets`, `PATCH /assets/<nom>` (`exposed`, `kind`, `notes`), `GET /findings?asset=&priority=P1,P2&kev=1`

## À la main sur un hôte (avant la tranche agent)

```
syft scan dir:/ -o cyclonedx-json > hote.cdx.json
curl -k -X POST --data-binary @hote.cdx.json "https://<hub>/api/vuln/sbom?asset=hote&kind=host&exposed=0"
```

Dependency-Track (lourd : ~4 Go de RAM) : profil compose `vuln-dt`, à poser plutôt sur un autre nœud que la VM du hub.
