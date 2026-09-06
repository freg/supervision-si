"""
Application d'UNE règle de tri (livraison #190) -- orchestre
imap_wrapper (jamais réimplémenté ici) : liste les messages du
dossier surveillé correspondant aux critères de la règle, puis
exécute ses actions.

**Ordre des actions, jamais interchangeable** : étiquette/marquage lu
D'ABORD, déplacement EN DERNIER -- un message DÉPLACÉ change d'UID
(nouveau message dans le dossier de destination, l'original supprimé
via EXPUNGE, voir imap_wrapper.move_message) -- toute action
ultérieure sur l'ANCIEN uid échouerait ("message introuvable").

**Erreur PAR MESSAGE, jamais bloquante pour les autres** -- un
message qui échoue (permissions, dossier de destination absent...)
est consigné dans `errors`, les messages SUIVANTS de la même règle
sont quand même traités. Jamais un "tout ou rien" sur un lot.
"""
import imap_wrapper


def apply_rule(conn, rule, limit=200):
    """Renvoie {matched, moved, labeled, marked_seen, errors: [...]}.
    `limit` -- plafond dur sur le nombre de messages traités en UN
    appel (même raisonnement que /messages, jamais un traitement
    massif incontrôlé en une seule fois)."""
    messages, _total = imap_wrapper.list_messages(
        conn, rule["watch_folder"], limit=limit,
        subject_filter=rule.get("match_subject") or None,
        from_filter=rule.get("match_from") or None,
        unseen_only=bool(rule.get("match_unseen_only")),
    )
    summary = {"matched": len(messages), "moved": 0, "labeled": 0, "marked_seen": 0, "errors": []}

    for msg in messages:
        uid = msg["uid"]
        try:
            if rule.get("action_add_label"):
                imap_wrapper.add_label(conn, rule["watch_folder"], uid, rule["action_add_label"])
                summary["labeled"] += 1
            if rule.get("action_mark_seen"):
                imap_wrapper.mark_seen(conn, rule["watch_folder"], uid)
                summary["marked_seen"] += 1
            if rule.get("action_move_to"):
                imap_wrapper.move_message(conn, rule["watch_folder"], uid, rule["action_move_to"])
                summary["moved"] += 1
        except imap_wrapper.ImapError as exc:
            summary["errors"].append(f"message {uid} : {exc}")

    return summary
