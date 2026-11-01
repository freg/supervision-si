# -*- coding: utf-8 -*-
"""Liste SSID -> VLAN -> sous-réseau d'un site Nebula, pour le test d'atteignabilité SSID x VLAN
(tools/ssid-vlan-check.sh). À exécuter DANS le conteneur nebula-api (clé API déjà dans son environnement) :

  cd ~/SRC/data2/tickets/supervision-si && (umask 077; ./scripts/run.sh exec -T nebula-api python - "SITE-ALPHA" < nebula/tools/ssid_vlan_list.py | sed -n "/^#site/,$p" > ~/ssids-site.txt)   # run.sh écrit aussi sur la sortie standard

Sortie, une ligne par SSID actif : SSID;clé;vlan;sous_reseau;passerelle  -- la clé WPA vient de l'OpenAPI (champ wpaKey) :
fichier à garder en 600, jamais dans le dépôt. Puis une ligne « #vlans;vid=sous_reseau,… » : tous les VLAN routés par
la passerelle (cibles du test). Argument : nom (ou début de nom) du site, insensible à la casse."""
import ipaddress
import os
import sys

import nebula_client
import vlanmap

want = (sys.argv[1] if len(sys.argv) > 1 else "").lower()
c = nebula_client.NebulaClient(os.environ.get("NEBULA_API_KEY", "").strip(), (os.environ.get("NEBULA_BASE_URL") or "").strip() or None)  # comme app.py
site = None
for org in c.list_organizations() or []:
    for s in c.list_sites(org["orgId"]) or []:
        if not want or str(s.get("name", "")).lower().startswith(want) or want in str(s.get("name", "")).lower():
            site = (org["orgId"], s["siteId"], s.get("name") or s.get("siteName"))
            break
    if site:
        break
if not site:
    sys.exit("site introuvable : %s" % want)
org_id, site_id, name = site
devs = c.devices_for_site(org_id, site_id)
gw = next((d["devId"] for d in devs if str(d.get("type") or "").upper() in ("GW", "GWH", "FIREWALL", "GATEWAY", "USG")), None)
nets = vlanmap.gateway_networks(c.gw_interface_settings(site_id, gw)) if gw else {}


def first_host(cidr):
    try:
        return str(next(ipaddress.ip_network(cidr, strict=False).hosts()))
    except (ValueError, StopIteration, TypeError):
        return ""


print("#site;%s" % (name or site_id))
for w in c.ap_wlan_settings(site_id) or []:
    if not isinstance(w, dict) or not w.get("enabled", True):
        continue
    vid = w.get("vlan") if isinstance(w.get("vlan"), int) else 1
    sub = (nets.get(vid) or {}).get("subnet") or ""
    print("%s;%s;%s;%s;%s" % (w.get("name") or w.get("ssid") or "?", w.get("wpaKey") or "", vid, sub, first_host(sub)))
print("#vlans;" + ",".join("%s=%s" % (v, n["subnet"]) for v, n in sorted(nets.items()) if n.get("subnet")))
