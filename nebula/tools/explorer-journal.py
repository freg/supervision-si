#!/usr/bin/env python3
"""Exploration en LECTURE SEULE de ce que l'OpenAPI Nebula donne sur les flux, le filtrage et les incidents d'une passerelle.

À lancer DANS le conteneur nebula-api (la clé d'API y est déjà) :
  cd ~/SRC/data2/tickets/supervision-si && docker exec -i -e SITE=numeria $(docker ps -qf name=nebula-api) python3 - < nebula/tools/explorer-journal.py > ~/nebula-journal-$(date +%H%M).txt

SITE : morceau du nom du site Nebula. MOTS : mots recherchés dans les journaux (défaut idruide,google,gvt1,play).
Corps de gw/event-logs non documenté : plusieurs variantes sont essayées, les messages d'erreur de l'API servent d'indice.
Aucune écriture vers Nebula (GET et POST de consultation uniquement), aucune clé dans la sortie.
"""
import collections, json, os, re, sys, time
sys.path.insert(0, "/app")
import nebula_client as nb

SITE = os.environ.get("SITE", "numeria").lower()
MOTS = [m for m in os.environ.get("MOTS", "idruide,google,gvt1,play").lower().split(",") if m]
c = nb.NebulaClient(os.environ["NEBULA_API_KEY"], base_url=os.environ.get("NEBULA_BASE_URL") or None)


def montrer(titre, f):
    print("\n==== %s" % titre)
    try:
        r = f()
    except Exception as e:  # noqa: BLE001 -- l'erreur est l'information
        print("ERREUR : %s" % str(e)[:600]); return None
    txt = json.dumps(r, ensure_ascii=False, default=str)
    print("taille %d ; début :\n%s" % (len(txt), txt[:2500]))
    return r


def liste(r):
    if isinstance(r, list):
        return r
    if isinstance(r, dict):
        for k in ("data", "logs", "events", "items", "result"):
            if isinstance(r.get(k), list):
                return r[k]
    return []


for org in c.list_organizations():
    oid = org.get("orgId") or org.get("id")
    for s in c.list_sites(oid):
        nom = str(s.get("siteName") or s.get("name") or "")
        if SITE not in nom.lower():
            continue
        sid = s.get("siteId") or s.get("id")
        print("######## site %s" % nom)
        devs = c.devices_for_site(oid, sid)
        print("appareils (type, modèle) : %s" % sorted({(str(d.get("type")), str(d.get("model"))) for d in devs}))
        gws = [d for d in devs if str(d.get("type") or "").upper() in ("GW", "GWH", "FIREWALL", "GATEWAY", "USG")]
        for g in gws:
            did = g.get("devId")
            montrer("état passerelle %s" % g.get("model"), lambda: c.gw_system_status(sid, did))
            montrer("usage passerelle 1d", lambda: c.gw_traffic_usage(sid, did, "1d"))
        corps = [{"period": "1d"}, {"period": "2h"}, {"period": "1d", "category": "security"},
                 {"period": "1d", "type": "content_filter"}, {"period": "1d", "type": "app_patrol"},
                 {"period": "1d", "type": "ips"}, {"period": "1d", "keyword": "idruide"}]
        tous = []
        for b in corps:
            r = montrer("gw/event-logs %s" % json.dumps(b), lambda b=b: c._post("/v1/nebula/%s/gw/event-logs" % sid, b, "journal"))
            tous += liste(r)
        # synthèse : catégories, et « moments » par heure pour les mots cherchés
        cat = collections.Counter(str(e.get("category") or e.get("type") or "?") for e in tous if isinstance(e, dict))
        print("\n==== catégories vues : %s" % cat.most_common(30))
        heures = collections.Counter()
        for e in tous:
            t = json.dumps(e, ensure_ascii=False).lower()
            for m in MOTS:
                if m in t:
                    ts = e.get("timestamp") or e.get("time") or e.get("ts") or 0
                    try:
                        ts = float(ts) / (1000 if float(ts) > 1e11 else 1)
                        h = time.strftime("%Y-%m-%d %Hh", time.localtime(ts))
                    except (TypeError, ValueError):
                        h = str(ts)[:13]
                    heures[(m, h)] += 1
        print("==== moments (mot, heure) : %s" % sorted(heures.items()))
        montrer("clients du site 1d (5 premiers)", lambda: c.get_site_clients(sid, period="1d")[:5])
