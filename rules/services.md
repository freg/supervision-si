# Règles services — état des services et dépendances (espace Simple, Cortex)

Types prévus (pas encore émis par un module, sert d'abord à l'assistant) :
`service_down`, `service_slow`, `certificate_expiring`, `dns_mismatch`.

## R-SVC-01 · Un service est en panne et d'autres en dépendent
- Quand : service_down
- Gravité : haute
- Action : Vérifier d'abord la dépendance la plus basse (réseau, puis DNS, puis authentification) avant le service lui-même ; prévenir les personnes des services impactés en une phrase (« X est en panne, donc Y ne marche pas »).
- Applicable : non
- Pourquoi : Une panne en cascade se répare par la racine ; réparer une feuille ne sert à rien tant que la racine est à terre.

## R-SVC-02 · Un certificat expire bientôt
- Quand : certificate_expiring
- Gravité : moyenne
- Action : Renouveler le certificat avant l'échéance et vérifier la chaîne depuis un poste externe.
- Applicable : non
- Pourquoi : Un certificat expiré bloque les navigateurs et les agents ; le renouvellement est sans risque s'il est fait avant.
