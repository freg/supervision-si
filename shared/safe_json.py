"""
Livraison #287, demandé explicitement -- "rend systématiquement les
erreurs plus explicites, ça doit être le comportement général des
remontées d'erreur". Généralisé depuis le correctif réel #286
(glpi/api/glpi_client.py) : un appel HTTP qui renvoie un code 2xx
mais un corps NON-JSON (page HTML d'un proxy, panne intermédiaire,
mauvaise URL...) plante avec une JSONDecodeError/ValueError brute et
inexploitable dès que le code appelant fait `resp.json()` sans
filet -- même après avoir déjà vérifié le code HTTP.

Utilitaire PARTAGÉ (plutôt que dupliqué dans chaque `app.py`, comme
fait initialement pour glpi_client.py/mayan_client.py/nebula_client.py/
schema_client.py/google_oauth.py, qui gardent leur propre variante
locale liée à leur classe d'erreur spécifique -- ceci couvre les
appels INTERNES restants, service à service, où une RuntimeError
générique suffit, l'appelant l'attrapant déjà via un `except Exception`
ou similaire côté route Flask)."""


def safe_json(resp, context):
    """Renvoie `resp.json()`, ou lève une RuntimeError avec un aperçu
    du VRAI corps de réponse (tronqué à 300 caractères) si le corps
    n'est pas du JSON valide -- jamais un traceback Python brut."""
    try:
        return resp.json()
    except ValueError:
        snippet = (resp.text or "").strip()[:300]
        raise RuntimeError(f"{context} : réponse HTTP {resp.status_code} inattendue (pas du JSON valide) -- début de la réponse : {snippet!r}")
