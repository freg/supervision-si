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
- `POST /scan/self` — SBOM du dépôt par syft puis même chaîne ; **en arrière-plan** (#693) : `202 {id}` puis `GET /jobs/<id>`
  (`?wait=1` = synchrone). Données des modules exclues (`VULN_SELF_SCAN_EXCLUDES`).
- `POST /feeds/refresh` (arrière-plan, idem), `GET /feeds`, `GET /epss/<cve>`, `GET /jobs`
- `GET /diag` — état de l'installation (#693) : syft/osv-scanner présents, stockage inscriptible, dépôt monté,
  flux chargés, sortie Internet vers api.osv.dev / EPSS / KEV / Dependency-Track ; `?network=0` sans sonde externe.
  Aussi : bouton « État de l'installation » de la tuile, ouvert d'office en cas d'échec.

## Dépannage (#693)

```
./scripts/run.sh up -d --build vuln-api
./scripts/run.sh logs --tail 40 vuln-api
GATEWAY_REALM_ANSWER=marquer ./gateway/scripts/run.sh up -d --force-recreate tls-proxy
./scripts/run.sh exec vuln-api python -c "import app,json;print(json.dumps(app.diag(),indent=1,ensure_ascii=False))"
```

Sans sortie Internet vers api.osv.dev : `OSV_SCANNER_ARGS=--offline-vulnerabilities --download-offline-databases`
(base OSV téléchargée une fois puis locale ; nécessite quand même l'accès au téléchargement).
- `GET /summary`, `GET /assets`, `PATCH /assets/<nom>` (`exposed`, `kind`, `notes`), `GET /findings?asset=&priority=P1,P2&kev=1`

## À la main sur un hôte (avant la tranche agent)

```
syft scan dir:/ -o cyclonedx-json > hote.cdx.json
curl -k -X POST --data-binary @hote.cdx.json "https://<hub>/api/vuln/sbom?asset=hote&kind=host&exposed=0"
```

Dependency-Track (lourd : ~4 Go de RAM) : profil compose `vuln-dt`, à poser plutôt sur un autre nœud que la VM du hub.
