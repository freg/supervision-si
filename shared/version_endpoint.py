"""
Ajoute une route /version à une application Flask -- lit VERSION.json
(copié au build depuis shared/, généré par scripts/run.sh juste avant
chaque build, jamais une valeur maintenue à la main). Demandé après
une confusion réelle sur "est-ce que j'ai bien la dernière version
déployée ?". Basé sur un HASH du contenu réel des fichiers, pas un
horodatage brut (retour réel : un simple horodatage change à chaque
"--build" même sans rien changer, rendant le numéro inutile comme
indicateur de "est-ce vraiment une nouvelle version ?") -- le hash,
lui, reste identique tant que rien n'a changé.

Toujours une réponse, MÊME si VERSION.json est absent (service pas
encore couvert par ce mécanisme, ou premier lancement avant que
run.sh ait tourné) -- jamais une 500 pour ça, juste une valeur
explicite "inconnu".
"""
import json
import os


def register_version_route(app, service_name):
    from flask import jsonify

    @app.route("/version", methods=["GET"])
    def _version():
        version_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "VERSION.json")
        info = {"service": service_name, "content_hash": "inconnu (VERSION.json absent)", "git_hash": "inconnu", "last_checked_at": "inconnu"}
        try:
            with open(version_path, encoding="utf-8") as f:
                info.update(json.load(f))
            info["service"] = service_name  # jamais écrasé par le contenu du fichier partagé (même hash pour tous, mais le nom de service reste propre à CETTE API)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            pass
        return jsonify(info), 200
