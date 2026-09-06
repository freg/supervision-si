"""
Registre des règles de l'orchestrateur -- même motif que
netprobe/api/analyzers/__init__.py (ANALYZERS). Une entrée = un nom
de règle exposé via l'API (GET /rules, POST /run/<nom>) -> le module
qui l'implémente.
"""
from . import no_services, new_device, snmp_candidate

RULES = {
    "no_services": no_services,
    "new_device": new_device,
    "snmp_candidate": snmp_candidate,
}
