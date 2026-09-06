"""
Application d'un interpréteur à un message (livraison #191) --
transforme un message IMAP en bloc de données JSON structuré, selon
les champs définis (voir interpreters_store.py).

**Motifs bornés par un délai d'attente, via un VRAI PROCESSUS
séparé** -- un motif regex fourni par une PERSONNE (jamais du code
de confiance) appliqué à un CONTENU EXTERNE (le corps d'un email,
jamais de confiance non plus) peut, en combinaison, causer un retour
arrière catastrophique ("catastrophic backtracking") -- un motif
d'apparence anodine peut bloquer l'exécution pendant un temps
arbitrairement long selon le texte en face.

**PIÈGE RÉEL rencontré en testant** : un premier essai avec un THREAD
séparé (même motif que `ssh-tunnels/api/mount_process.measure_latency`,
#182) s'est révélé COMPLÈTEMENT INEFFICACE ici -- contrairement à un
appel système (`os.stat()`, qui LIBÈRE le GIL pendant l'attente), le
moteur `re` en C NE LIBÈRE JAMAIS le GIL pendant son propre calcul de
retour arrière -- AUCUN AUTRE THREAD, pas même celui qui vérifie le
délai d'attente sur le `Future`, ne peut s'exécuter tant que l'appel
`re.search()` n'est pas revenu -- mesuré RÉELLEMENT : 86 secondes
d'attente malgré un délai demandé de 1 seconde, sur un motif
catastrophique volontairement construit pour le test. Un THREAD ne
peut structurellement PAS protéger contre ce cas précis -- seul un
VRAI PROCESSUS séparé peut être interrompu de force (`terminate()`,
au niveau du système d'exploitation, indépendant de ce que Python
fait en interne) -- corrigé avec `multiprocessing.Process`.
"""
import multiprocessing
import re


def _regex_worker(pattern, text, result_queue):
    """Exécuté dans le PROCESSUS SÉPARÉ -- jamais d'accès direct au
    reste de l'application depuis ici, seulement le motif/texte reçus
    en argument et la file pour renvoyer le résultat."""
    try:
        m = re.search(pattern, text or "", re.DOTALL)
        if m is None:
            result_queue.put((None, None))
        else:
            result_queue.put((m.group(1) if m.groups() else m.group(0), None))
    except re.error as exc:
        result_queue.put((None, f"motif invalide : {exc}"))


def _apply_pattern_with_timeout(pattern, text, timeout=2):
    """Renvoie (valeur, erreur) -- voir docstring du module pour le
    raisonnement complet sur le choix d'un processus plutôt qu'un
    thread. `terminate()` (SIGTERM) puis `kill()` (SIGKILL) en filet
    de sécurité si le processus ignore le premier signal -- même
    escalade que `ssh-tunnels/api/mount_process.stop_mount_process`
    (#180), un processus qui refuse de mourir proprement ne doit
    jamais bloquer indéfiniment l'appelant non plus."""
    result_queue = multiprocessing.Queue()
    process = multiprocessing.Process(target=_regex_worker, args=(pattern, text, result_queue))
    process.start()
    process.join(timeout=timeout)

    if process.is_alive():
        process.terminate()
        process.join(timeout=1)
        if process.is_alive():
            process.kill()
            process.join()
        return None, f"délai d'extraction dépassé ({timeout}s) -- motif potentiellement trop coûteux"

    try:
        return result_queue.get_nowait()
    except Exception:  # noqa: BLE001 -- file vide (processus mort sans avoir rien renvoyé, cas limite)
        return None, "extraction échouée (processus terminé sans résultat)"


def find_matching_interpreter(interpreters, message):
    """Renvoie le PREMIER interpréteur ACTIVÉ dont les critères
    correspondent au message (`match_subject`/`match_from`,
    recherche PARTIELLE insensible à la casse -- même esprit que les
    filtres IMAP du volet 2, #189), ou None si aucun ne correspond.
    Un interpréteur SANS critère (les deux `None`) correspond à
    TOUT message -- utile comme "interpréteur par défaut", mais
    place-le EN DERNIER dans la liste pour ne pas masquer les autres
    (jamais réordonné ici, l'ordre de la liste fournie fait foi)."""
    subject = (message.get("subject") or "").lower()
    sender = (message.get("from") or "").lower()
    for interp in interpreters:
        if not interp["enabled"]:
            continue
        if interp.get("match_subject") and interp["match_subject"].lower() not in subject:
            continue
        if interp.get("match_from") and interp["match_from"].lower() not in sender:
            continue
        return interp
    return None


def apply_interpreter(interpreter, message):
    """Renvoie (result, errors) -- `result` : dict {nom_champ:
    valeur_ou_None}, TOUJOURS une clé par champ défini même en cas
    d'échec (valeur None) -- jamais un dict partiel qui masquerait
    silencieusement un champ manquant. `errors` : liste de messages,
    un par champ en échec (délai dépassé, motif invalide)."""
    result = {}
    errors = []
    for field in interpreter["fields"]:
        source_text = message.get("subject", "") if field["source"] == "subject" else (
            message.get("body_text") or message.get("body_html") or ""
        )
        value, error = _apply_pattern_with_timeout(field["pattern"], source_text)
        result[field["name"]] = value
        if error:
            errors.append(f"champ '{field['name']}' : {error}")
    return result, errors
