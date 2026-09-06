"""
Client SNMP (livraison #212, backlog item 13 -- module SNMP). Utilise
`pysnmp` (fork `lextudio/pysnmp`, ACTIF -- l'original `etingof/pysnmp`
est à l'abandon depuis 2022, décès du mainteneur -- vérifié avant de
choisir cette dépendance, jamais la première trouvée par réflexe).

**⚠️ Portée VOLONTAIREMENT LIMITÉE, décisions prises pour pouvoir
avancer plutôt que d'attendre -- à corriger si elles ne conviennent
pas** (la demande d'origine listait 3 aspects explicitement "à
trancher ensemble") :
1. **SNMPv1/v2c (communauté) SEULEMENT** dans cette livraison --
   SNMPv3 (identifiants chiffrés, USM) ajoute une complexité
   d'authentification significative, volontairement reportée à une
   étape suivante une fois ce socle validé.
2. **Informations analysées** : groupe "System" standard (sysDescr,
   sysName, sysUpTime, sysContact, sysLocation -- SNMPv2-MIB) et
   table des interfaces (ifDescr, ifOperStatus, ifSpeed -- IF-MIB) --
   les deux MIB les plus universellement supportées, un point de
   départ raisonnable plutôt qu'une couverture MIB exhaustive.
3. **PAS de scan de ports/services** (1er volet de la demande
   d'origine) -- seulement l'accès SNMP lui-même (GET/WALK) une fois
   qu'on sait DÉJÀ qu'une cible répond au protocole -- la découverte
   de ce qui est ouvert sur une cible est un chantier à part, plus
   proche d'un scanner réseau général que d'un client SNMP.
4. **PAS de "déploiement automatisé"** -- terme de la demande
   d'origine resté ambigu (déployer QUOI, sur la cible elle-même ou
   une configuration locale ?) -- rien construit sur ce point,
   explicitement laissé de côté plutôt que deviné.

**⚠️ JAMAIS TESTÉ CONTRE UN VRAI ÉQUIPEMENT SNMP** -- `pysnmp`
n'est pas installable dans cet environnement de développement (réseau
restreint, comme `sshpass`/certains autres paquets rencontrés dans ce
projet). Code écrit à partir de la documentation OFFICIELLE
(docs.lextudio.com/pysnmp/v7.1, exemples vérifiés un par un avant
d'écrire ce module, jamais improvisés) -- la logique de conversion/
formatage ENVELOPPANT ces appels est testée (voir les tests
associés), mais PAS l'appel réseau réel lui-même. À vérifier en
priorité au premier usage réel.

**⚠️ VRAI BUG TROUVÉ AU PREMIER DÉPLOIEMENT RÉEL** (logs gunicorn
fournis par la personne) -- `ImportError: cannot import name
'ContextData' from 'pysnmp.hlapi.v1arch.asyncio'`. Confirmé par
recherche : `ContextData` n'existe QUE dans `v3arch` (SNMPv3, système
de contextes/moteurs) -- absent de `v1arch` (SNMPv1/v2c, ce module),
qui n'en a d'ailleurs jamais eu besoin dans les APPELS RÉELS
`get_cmd`/`bulk_cmd` de ce fichier (jamais passé en argument, malgré
l'affirmation ci-dessus d'exemples "vérifiés un par un" -- cet import
précis avait échappé à cette vérification). Corrigé : import retiré,
AUCUNE autre modification nécessaire (le code appelant était déjà
correct).
"""
import asyncio
import logging
import time

from pysnmp.hlapi.v1arch.asyncio import (
    CommunityData, ObjectIdentity, ObjectType,
    SnmpDispatcher, UdpTransportTarget, bulk_cmd, get_cmd, is_end_of_mib,
)

# Traces DEBUG (livraison #215) -- appels réseau SNMP, susceptibles
# de bloquer/échouer silencieusement (cible injoignable, communauté
# refusée, délai réseau). RÈGLE ABSOLUE, même que le reste de la
# chaîne chiffrement/authentification : la COMMUNAUTÉ (fonctionnellement
# un mot de passe) n'apparaît JAMAIS dans un message de log, à AUCUN
# niveau -- seule sa longueur peut être tracée si utile, jamais sa
# valeur.
_log = logging.getLogger("snmp_client")


class SnmpError(Exception):
    pass


SYSTEM_OIDS = [
    ("sysDescr", ObjectIdentity("SNMPv2-MIB", "sysDescr", 0)),
    ("sysUpTime", ObjectIdentity("SNMPv2-MIB", "sysUpTime", 0)),
    ("sysContact", ObjectIdentity("SNMPv2-MIB", "sysContact", 0)),
    ("sysName", ObjectIdentity("SNMPv2-MIB", "sysName", 0)),
    ("sysLocation", ObjectIdentity("SNMPv2-MIB", "sysLocation", 0)),
]

INTERFACE_COLUMNS = [
    ("ifDescr", ObjectIdentity("IF-MIB", "ifDescr")),
    ("ifOperStatus", ObjectIdentity("IF-MIB", "ifOperStatus")),
    ("ifSpeed", ObjectIdentity("IF-MIB", "ifSpeed")),
]

# Livraison #384, backlog item 49 reformulé -- "il s'agit d'analyser
# le trafic" (pas seulement le statut en ligne/hors ligne). Compteurs
# 64 bits (ifHCInOctets/ifHCOutOctets, RFC 2863/3273) -- PRÉFÉRÉS aux
# compteurs 32 bits ifInOctets/ifOutOctets historiques : un lien
# gigabit+ rebouclerait un compteur 32 bits en quelques secondes à
# pleine charge (2^32 octets ÷ débit), rendant toute mesure de débit
# par différence de deux relevés PEU FIABLE sans détection de
# rebouclage -- jamais un problème réel avec la variante 64 bits aux
# débits actuels.
TRAFFIC_COLUMNS = [
    ("ifDescr", ObjectIdentity("IF-MIB", "ifDescr")),
    ("ifHCInOctets", ObjectIdentity("IF-MIB", "ifHCInOctets")),
    ("ifHCOutOctets", ObjectIdentity("IF-MIB", "ifHCOutOctets")),
]

# RFC 2863 -- valeurs numériques RÉELLES d'ifOperStatus, jamais
# devinées (texte normatif de la RFC, pas une supposition).
IF_OPER_STATUS_LABELS = {
    1: "up", 2: "down", 3: "testing", 4: "unknown",
    5: "dormant", 6: "notPresent", 7: "lowerLayerDown",
}


def _run_async(coro, timeout):
    """Exécute une coroutine pysnmp de façon SYNCHRONE (ce module
    tourne dans des routes Flask synchrones, comme tout le reste de
    ce projet -- jamais introduit `async def` dans les routes
    elles-mêmes pour rester cohérent avec les ~25 autres services).
    `asyncio.run` crée sa PROPRE boucle d'événements à chaque appel --
    plus coûteux qu'une boucle partagée, mais chaque appel SNMP de ce
    module est occasionnel (déclenché par une action humaine dans le
    hub), jamais un flux à haut débit qui justifierait cette
    complexité."""
    try:
        return asyncio.run(asyncio.wait_for(coro, timeout=timeout))
    except asyncio.TimeoutError:
        _log.debug("_run_async : délai global dépassé (%ss) -- cible probablement injoignable", timeout)
        raise SnmpError(f"délai dépassé ({timeout}s) -- cible injoignable ou trop lente à répondre")


async def _get_system_info(host, community, port, timeout):
    _log.debug("_get_system_info : requête GET démarrée -- host=%s port=%s timeout=%ss (communauté : %d caractères, jamais sa valeur)",
               host, port, timeout, len(community))
    with SnmpDispatcher() as dispatcher:
        start = time.monotonic()
        error_indication, error_status, error_index, var_binds = await get_cmd(
            dispatcher,
            CommunityData(community, mpModel=1),  # mpModel=1 -- SNMPv2c (community, GETBULK dispo) -- mpModel=0 serait SNMPv1 strict
            await UdpTransportTarget.create((host, port), timeout=timeout),
            *[ObjectType(oid) for _, oid in SYSTEM_OIDS],
        )
        elapsed_ms = int((time.monotonic() - start) * 1000)
        if error_indication:
            _log.debug("_get_system_info : ÉCHEC réseau après %d ms -- %s", elapsed_ms, error_indication)
            raise SnmpError(str(error_indication))
        if error_status:
            _log.debug("_get_system_info : ÉCHEC SNMP après %d ms -- %s (index %s)", elapsed_ms, error_status.prettyPrint(), error_index)
            raise SnmpError(f"{error_status.prettyPrint()} (index {error_index})")
        result = {}
        for (label, _), var_bind in zip(SYSTEM_OIDS, var_binds):
            result[label] = var_bind[1].prettyPrint()
        _log.debug("_get_system_info : succès en %d ms (%d valeurs obtenues)", elapsed_ms, len(result))
        return result


def get_system_info(host, community, port=161, timeout=5):
    """GET synchrone des 5 valeurs du groupe "System" (SNMPv2-MIB) --
    lève SnmpError avec un message actionnable en cas d'échec (cible
    injoignable, communauté refusée, délai dépassé) -- jamais une
    exception `pysnmp` brute qui remonterait jusqu'à la route Flask."""
    return _run_async(_get_system_info(host, community, port, timeout), timeout + 2)


async def _walk_table(host, community, port, timeout, columns, label):
    """WALK BULK synchrone générique sur un jeu de colonnes IF-MIB
    donné -- factorisé (livraison #384) pour être partagé entre
    _walk_interfaces (statut/vitesse) et _walk_traffic_counters
    (compteurs 64 bits), plutôt que deux copies de la même boucle
    GETBULK. `label` sert uniquement aux messages de debug, pour
    distinguer les deux appelants dans les journaux."""
    _log.debug("_walk_table[%s] : démarré -- host=%s port=%s timeout=%ss (communauté : %d caractères, jamais sa valeur)",
               label, host, port, timeout, len(community))
    rows = []
    var_binds = [ObjectType(oid) for _, oid in columns]
    round_num = 0
    with SnmpDispatcher() as dispatcher:
        while True:
            round_num += 1
            start = time.monotonic()
            error_indication, error_status, error_index, var_bind_table = await bulk_cmd(
                dispatcher,
                CommunityData(community, mpModel=1),
                await UdpTransportTarget.create((host, port), timeout=timeout),
                0, 25,
                *var_binds,
            )
            elapsed_ms = int((time.monotonic() - start) * 1000)
            if error_indication:
                _log.debug("_walk_table[%s] : ÉCHEC réseau au tour %d (après %d ms) -- %s", label, round_num, elapsed_ms, error_indication)
                raise SnmpError(str(error_indication))
            if error_status:
                _log.debug("_walk_table[%s] : ÉCHEC SNMP au tour %d (après %d ms) -- %s (index %s)",
                           label, round_num, elapsed_ms, error_status.prettyPrint(), error_index)
                raise SnmpError(f"{error_status.prettyPrint()} (index {error_index})")
            row = {}
            for (col_label, _), var_bind in zip(columns, var_bind_table):
                row[col_label] = var_bind[1].prettyPrint()
            if row.get("ifDescr"):
                if "ifOperStatus" in row:
                    try:
                        row["ifOperStatus"] = IF_OPER_STATUS_LABELS.get(int(row["ifOperStatus"]), row["ifOperStatus"])
                    except (ValueError, TypeError):
                        pass  # valeur non numérique inattendue -- laissée telle quelle, jamais une exception ici
                rows.append(row)
            var_binds = var_bind_table
            if is_end_of_mib(var_binds):
                _log.debug("_walk_table[%s] : fin de MIB atteinte au tour %d -- %d ligne(s) au total", label, round_num, len(rows))
                break
    return rows


async def _walk_interfaces(host, community, port, timeout):
    return await _walk_table(host, community, port, timeout, INTERFACE_COLUMNS, "interfaces")


def walk_interfaces(host, community, port=161, timeout=5):
    """WALK synchrone de la table des interfaces (IF-MIB) -- une
    entrée PAR interface, `ifOperStatus` déjà traduit en texte
    (RFC 2863). Limite implicite : aucune borne sur le NOMBRE
    d'interfaces retournées -- acceptable pour un équipement réseau
    normal (quelques dizaines d'interfaces au plus), pourrait devenir
    un problème sur un équipement massivement empilé -- pas rencontré
    dans les usages attendus de ce module, jamais testé en pratique."""
    return _run_async(_walk_interfaces(host, community, port, timeout), timeout * 4)


async def _walk_traffic_counters(host, community, port, timeout):
    return await _walk_table(host, community, port, timeout, TRAFFIC_COLUMNS, "traffic")


async def _get_interface_traffic_rate(host, community, port, timeout, sample_interval):
    first = await _walk_traffic_counters(host, community, port, timeout)
    await asyncio.sleep(sample_interval)
    second = await _walk_traffic_counters(host, community, port, timeout)

    # Apparié par ifDescr -- suppose la liste d'interfaces STABLE
    # entre les deux relevés (quelques secondes d'écart), hypothèse
    # raisonnable pour un équipement réseau normal, jamais vérifiée
    # contre un cas où des interfaces apparaissent/disparaissent en
    # cours de mesure (VLAN dynamique, par exemple) -- une interface
    # absente d'un des deux relevés est simplement OMISE du résultat,
    # jamais une valeur inventée.
    first_by_descr = {row["ifDescr"]: row for row in first if row.get("ifDescr")}
    results = []
    for row in second:
        descr = row.get("ifDescr")
        if not descr or descr not in first_by_descr:
            continue
        prev = first_by_descr[descr]
        try:
            in_delta = int(row["ifHCInOctets"]) - int(prev["ifHCInOctets"])
            out_delta = int(row["ifHCOutOctets"]) - int(prev["ifHCOutOctets"])
        except (ValueError, TypeError, KeyError):
            continue  # valeur non numérique inattendue -- interface omise, jamais une exception ici
        # Rebouclage de compteur (redémarrage de l'équipement,
        # réinitialisation de compteur) -- delta NÉGATIF alors qu'un
        # compteur ne peut que croître -- interface omise plutôt
        # qu'un débit négatif absurde. Jamais rencontré en pratique
        # avec un compteur 64 bits sur l'échelle de temps d'un seul
        # sample_interval, mais vérifié quand même par prudence.
        if in_delta < 0 or out_delta < 0:
            continue
        results.append({
            "ifDescr": descr,
            "in_bytes_per_sec": round(in_delta / sample_interval, 1),
            "out_bytes_per_sec": round(out_delta / sample_interval, 1),
        })
    return results


def get_interface_traffic_rate(host, community, port=161, timeout=5, sample_interval=5):
    """Débit RÉEL par interface (octets/s, entrant et sortant) --
    calculé par DIFFÉRENCE entre deux relevés des compteurs 64 bits
    IF-MIB espacés de `sample_interval` secondes (défaut 5s :
    compromis entre précision -- un intervalle trop court amplifie le
    bruit d'arrondi -- et temps de réponse de cette route, qui reste
    UN appel HTTP synchrone bloquant pendant toute la durée du
    prélèvement). Livraison #384, backlog item 49 reformulé --
    "il s'agit d'analyser le trafic" : un simple compteur cumulatif
    brut (déjà exposé par walk_interfaces si besoin) répond mal à ce
    besoin, seul un DÉBIT (dérivée dans le temps) le fait vraiment."""
    return _run_async(
        _get_interface_traffic_rate(host, community, port, timeout, sample_interval),
        (timeout * 4 * 2) + sample_interval + 5,
    )
