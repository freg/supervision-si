"""
Moteur d'orchestration des analyseurs -- livraison #307. Sépare le
CALCUL (chaque `analyze()` d'analyzers/*.py, pur, sans effet de
bord) de l'ENREGISTREMENT (ce module, seul point qui écrit en base)
-- un analyseur reste testable isolément sans jamais toucher au
stockage (voir les tests de chaque module dans analyzers/).
"""
import logging

from analyzers import ANALYZERS

_log = logging.getLogger("netprobe_analyzer_engine")


def run_analyzer(db_path, analyzer_name):
    """Exécute UN analyseur nommé, enregistre ses constats, renvoie
    le nombre de constats enregistrés. Renvoie None si le nom est
    inconnu -- l'appelant décide du code HTTP, jamais une exception
    ici pour un simple nom invalide."""
    import store  # import tardif -- évite un cycle si analyzers/*.py importent aussi store au niveau module

    analyzer = ANALYZERS.get(analyzer_name)
    if analyzer is None:
        return None
    try:
        findings = analyzer.analyze(db_path)
    except Exception as exc:  # noqa: BLE001 -- un analyseur en échec ne doit JAMAIS bloquer les autres
        _log.debug("run_analyzer : %s a échoué -- %s", analyzer_name, exc)
        return 0
    for finding in findings:
        store.record_analysis_result(
            db_path, analyzer_name, finding["severity"], finding["message"],
            target_id=finding.get("target_id"),
        )
    return len(findings)


def run_all_analyzers(db_path):
    """Exécute TOUS les analyseurs enregistrés -- un échec de l'un
    n'empêche jamais les autres de tourner (voir run_analyzer).
    Renvoie {nom: nombre_de_constats}."""
    results = {}
    for name in ANALYZERS:
        results[name] = run_analyzer(db_path, name)
    return results
