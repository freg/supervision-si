#!/bin/bash
# test-flux.sh - verifie depuis le reseau local les flux sortants exiges par un editeur (Google Android Enterprise, Idruide...).
# LECTURE SEULE : resolution DNS, connexion TCP, poignee de main TLS (emetteur du certificat = detection d'inspection SSL),
# requete NTP pour UDP/123. Aucune modification du poste ni du pare-feu.
#   bash test-flux.sh                      # liste Google integree
#   bash test-flux.sh -f idruide.txt       # + une liste supplementaire (format : groupe;hote;proto;ports)
#   IFACE=enp1s0 bash test-flux.sh         # forcer l'interface de sortie (tester depuis un autre VLAN du mini-PC)
#   bash test-flux.sh -g                   # sans la liste Google (seulement -f)
# Sorties : /tmp/flux-<hote>-<date>.txt (lisible) et .csv (pour le hub / un tableur).
# Envoi au hub (#962, tuile « Flux éditeurs ») : HUB=https://<hub>/api/nebula SITE=<id site> SOURCE="mini-PC" bash test-flux.sh
#   -l google,idruide : listes tenues dans le hub (au lieu de la liste integree) ; reglages memorises dans ~/.test-flux.env
#   supervision continue (cron) : 17 * * * * HOME=/home/freg bash /home/freg/test-flux.sh -q >/dev/null 2>&1
# Ports : 443  |  5228-5230  |  5235,5236     Proto : tcp | udp      Lignes commencant par # ignorees.
set -u
CONF="$HOME/.test-flux.env"; [ -f "$CONF" ] && . "$CONF"
GOOGLE=1; EXTRA=(); LISTES="${LISTES:-}"; QUIET=0
while [ $# -gt 0 ]; do case "$1" in -f) EXTRA+=("$2"); shift 2;; -g) GOOGLE=0; shift;; -l) LISTES="$2"; shift 2;; -q) QUIET=1; shift;; *) echo "option inconnue : $1"; exit 2;; esac; done
HUB="${HUB:-}"; SITE="${SITE:-}"; SOURCE="${SOURCE:-$(hostname)}"
[ -n "$HUB" ] && printf 'HUB=%q\nSITE=%q\nSOURCE=%q\nLISTES=%q\nIFACE=%q\n' "$HUB" "$SITE" "$SOURCE" "$LISTES" "${IFACE:-}" > "$CONF"
T=$(date +%Y%m%d-%H%M); OUT="/tmp/flux-$(hostname)-$T"; TO=5
IF="${IFACE:-}"; CURLIF=(); [ -n "$IF" ] && CURLIF=(--interface "$IF")

google_list() { cat <<'EOF'
# Source : support.google.com/work/android/answer/10513641 (releve du 03/11/2026). Les jokers (*.x) sont testes sur un hote representatif.
google-appareils;play.google.com;tcp;443,5228-5230
google-appareils;android.com;tcp;443
google-appareils;www.google-analytics.com;tcp;443
google-appareils;lh3.googleusercontent.com;tcp;443
google-appareils;www.gstatic.com;tcp;443,5228-5230
google-appareils;redirector.gvt1.com;tcp;443,5228-5230
google-appareils;lh3.ggpht.com;tcp;443
google-appareils;dl.google.com;tcp;443
google-appareils;dl-ssl.google.com;tcp;443
google-appareils;android.apis.google.com;tcp;443,5228-5230
google-appareils;beacons.gvt2.com;tcp;443
google-appareils;beacons.gvt3.com;tcp;443
google-appareils;www.googleapis.com;tcp;443
google-appareils;m.google.com;tcp;443
google-appareils;accounts.google.com;tcp;443
google-appareils;accounts.google.fr;tcp;443
google-appareils;gcm-http.googleapis.com;tcp;443,5228-5230
google-appareils;android.googleapis.com;tcp;443,5228-5230
google-appareils;fcm.googleapis.com;tcp;443,5228-5230
google-appareils;fcm-xmpp.googleapis.com;tcp;443,5228-5230,5235,5236
google-appareils;gcm-xmpp.googleapis.com;tcp;443,5228-5230,5235,5236
google-appareils;firebaseinstallations.googleapis.com;tcp;443,5228-5230
google-appareils;firebaselogging.googleapis.com;tcp;443
google-appareils;pki.google.com;tcp;443
google-appareils;clients1.google.com;tcp;443
google-appareils;clients2.google.com;tcp;443
google-appareils;clients3.google.com;tcp;443
google-appareils;clients4.google.com;tcp;443
google-appareils;clients5.google.com;tcp;443
google-appareils;clients6.google.com;tcp;443
google-appareils;chromiumdash.appspot.com;tcp;443
google-appareils;connectivitycheck.android.com;tcp;443
google-appareils;connectivitycheck.gstatic.com;tcp;443
google-appareils;www.google.com;tcp;443
google-appareils;ota.googlezip.net;tcp;443
google-appareils;ota-cache1.googlezip.net;tcp;443
google-appareils;ota-cache3.googlezip.net;tcp;443
google-appareils;mtalk.google.com;tcp;443,5228-5230
google-appareils;mtalk4.google.com;tcp;443,5228-5230
google-appareils;alt1-mtalk.google.com;tcp;443,5228-5230
google-appareils;alt8-mtalk.google.com;tcp;443,5228-5230
google-appareils;device-provisioning.googleapis.com;tcp;443,5228-5230
google-appareils;time.google.com;udp;123
google-appareils;android-safebrowsing.google.com;tcp;443
google-appareils;safebrowsing.google.com;tcp;443
google-console;androidmanagement.googleapis.com;tcp;443
google-console;fonts.googleapis.com;tcp;443
google-console;accounts.youtube.com;tcp;443
google-console;crl.pki.goog;tcp;443
google-console;ocsp.pki.goog;tcp;443
google-console;apis.google.com;tcp;443
google-console;ajax.googleapis.com;tcp;443
google-console;payments.google.com;tcp;443
google-console;google.com;tcp;443
google-console;ogs.google.com;tcp;443
google-console;notifications.google.com;tcp;443
google-console;enterprise.google.com;tcp;443
EOF
}

ports() { local p out=(); IFS=',' read -ra L <<< "$1"; for p in "${L[@]}"; do
  if [[ "$p" == *-* ]]; then for ((i=${p%-*}; i<=${p#*-}; i++)); do out+=("$i"); done; else out+=("$p"); fi; done; echo "${out[@]}"; }
SRC=""; [ -n "$IF" ] && SRC=$(ip -4 -o addr show dev "$IF" scope global | awk '{print $4}' | cut -d/ -f1 | head -1)
tcp_ok() { python3 - "$1" "$2" "$SRC" "$TO" <<'PY' 2>/dev/null
import socket, sys
h, p, src, to = sys.argv[1], int(sys.argv[2]), sys.argv[3], float(sys.argv[4])
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.settimeout(to)
if src: s.bind((src, 0))
s.connect((h, p)); s.close()
PY
}
tls_emetteur() { echo | timeout 8 openssl s_client ${SRC:+-bind "$SRC:0"} -connect "$1:443" -servername "$1" 2>/dev/null | openssl x509 -noout -issuer 2>/dev/null | sed 's/^issuer= *//; s/.*O *= *\([^,]*\).*/\1/'; }
ntp_ok() { python3 - "$1" "$SRC" <<'PY' 2>/dev/null
import socket, sys
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.settimeout(5)
if sys.argv[2]: s.bind((sys.argv[2], 0))
s.sendto(b'\x1b' + 47 * b'\0', (sys.argv[1], 123)); d, _ = s.recvfrom(48); print("ok" if len(d) >= 48 else "ko")
PY
}

{ if [ -n "$HUB" ] && [ -n "$LISTES" ]; then for l in ${LISTES//,/ }; do curl -sf -m 15 "$HUB/flux/listes/$l.txt" || echo "# liste $l introuvable sur le hub" >&2; done
  elif [ "$GOOGLE" = 1 ]; then google_list; fi; for f in "${EXTRA[@]}"; do cat "$f"; done; } | grep -v '^\s*#' | grep -v '^\s*$' > "$OUT.liste"
echo "groupe;hote;ip;proto;port;resultat;detail" > "$OUT.csv"
{
echo "=== Test des flux sortants - $(hostname) - $(date '+%d/%m/%Y %H:%M') ==="
echo "Sortie : ${IF:-route par defaut} ($(ip -4 -o addr show ${IF:+dev "$IF"} scope global 2>/dev/null | awk '{print $2" "$4}' | head -3 | tr '\n' ' '))"
echo "Passerelle : $(ip route show default | awk '{print $3" via "$5}' | head -1) ; DNS : $(awk '/^nameserver/{print $2}' /etc/resolv.conf | tr '\n' ' ')"
IPPUB=$(curl -s -m 5 "${CURLIF[@]}" https://ifconfig.me 2>/dev/null); echo "IP publique vue de l'exterieur : ${IPPUB:-?}"
[ -n "${https_proxy:-}${HTTPS_PROXY:-}" ] && echo "ATTENTION : proxy defini dans l'environnement (${https_proxy:-$HTTPS_PROXY}) - Google exige un acces direct"
echo
nok=0; nko=0; ninsp=0
while IFS=';' read -r grp hote proto pl; do
  ip=$(getent ahostsv4 "$hote" | awk 'NR==1{print $1}')
  if [ -z "$ip" ]; then printf '%-8s %-40s %-5s %-11s %s\n' "KO" "$hote" "$proto" "$pl" "nom non resolu (DNS)"; echo "$grp;$hote;;$proto;$pl;KO;DNS" >> "$OUT.csv"; nko=$((nko+1)); continue; fi
  for p in $(ports "$pl"); do
    if [ "$proto" = udp ]; then
      if [ "$p" = 123 ]; then r=$(ntp_ok "$hote"); [ "$r" = ok ] && st=OK det="reponse NTP" || { st=KO; det="pas de reponse NTP (UDP/123 filtre ?)"; }
      else st="?"; det="UDP sans reponse attendue : non verifiable d'ici"; fi
    else
      if tcp_ok "$ip" "$p"; then st=OK; det="connexion TCP"; else st=KO; det="connexion refusee ou filtree"; fi
    fi
    if [ "$st" = OK ] && [ "$p" = 443 ]; then
      em=$(tls_emetteur "$hote")
      if [ -n "$em" ] && [[ "$grp" == google* ]] && ! echo "$em" | grep -qiE 'google|GTS|GlobalSign'; then st=INSPECTE; det="certificat emis par « $em » : inspection SSL (Google demande de l'exclure)"; ninsp=$((ninsp+1))
      else det="TLS ok${em:+, emetteur $em}"; fi
    fi
    [ "$st" = OK ] && nok=$((nok+1)); [ "$st" = KO ] && nko=$((nko+1))
    printf '%-8s %-40s %-5s %-11s %s\n' "$st" "$hote" "$proto" "$p" "$det"
    echo "$grp;$hote;$ip;$proto;$p;$st;$det" >> "$OUT.csv"
  done
done < "$OUT.liste"
echo
# Un port refuse par un hote mais accepte par un autre n'est pas filtre par le pare-feu : l'hote ne le sert pas (ex. 5228 sur
# play.google.com alors que mtalk.google.com l'accepte). Reclassement « NS » (non servi par cet hote).
ouverts=$(awk -F';' 'NR>1 && $6=="OK" {print $4"/"$5}' "$OUT.csv" | sort -u)
nns=0; tmp=$(mktemp)
awk -F';' -v OFS=';' -v ouv="$ouverts" 'BEGIN{n=split(ouv,a,"\n"); for(i=1;i<=n;i++) o[a[i]]=1}
  NR>1 && $6=="KO" && $7 !~ /DNS/ && (($4"/"$5) in o) {$6="NS"; $7="port ouvert vers d autres hotes : non servi par celui-ci (pas un blocage)"} {print}' "$OUT.csv" > "$tmp" && cat "$tmp" > "$OUT.csv"; rm -f "$tmp"
nns=$(awk -F';' 'NR>1 && $6=="NS"' "$OUT.csv" | wc -l); nko=$((nko - nns))
[ "$nns" -gt 0 ] && echo "$nns KO reclasses NS (port non servi par cet hote, ouvert vers d'autres) : voir le CSV."
awk -F';' 'NR>1 && $6=="KO"' "$OUT.csv" | awk -F';' '{print "  KO reel : "$2" "$4"/"$5" - "$7}'
echo "Bilan : $nok OK, $nko KO reel(s), $nns NS, $ninsp inspecte(s) SSL. Detail tableur : $OUT.csv"
echo "Rappel : ce test vaut pour le VLAN du mini-PC ; les tablettes sur un autre VLAN / SSID peuvent avoir d'autres regles (IFACE=<sous-interface du VLAN>)."
} > >(if [ "$QUIET" = 1 ]; then cat > "$OUT.txt"; else tee "$OUT.txt"; fi)
wait $! 2>/dev/null
rm -f "$OUT.liste"
if [ -n "$HUB" ] && [ -n "$SITE" ]; then
  IPSRC=$(ip -4 -o addr show ${IFACE:+dev "$IFACE"} scope global 2>/dev/null | awk '{print $4}' | cut -d/ -f1 | head -1)
  [ -z "${IFACE:-}" ] && IPSRC=$(ip -4 route get 8.8.8.8 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src") print $(i+1)}')
  python3 - "$OUT.csv" "$SOURCE" "${IFACE:-}" "$IPSRC" "${IPPUB:-}" > "$OUT.json" <<'PY'
import csv, json, sys
f, src, iface, ipsrc, ippub = sys.argv[1:6]
rows = list(csv.DictReader(open(f, encoding="utf-8"), delimiter=";"))
print(json.dumps({"source": src, "iface": iface, "ip_source": ipsrc, "ip_publique": ippub,
  "resultats": [{"groupe": r["groupe"], "hote": r["hote"], "ip": r["ip"], "proto": r["proto"], "port": r["port"], "statut": r["resultat"], "detail": r["detail"]} for r in rows]}))
PY
  rep=$(curl -s -m 30 -w '\n%{http_code}' -X POST "$HUB/sites/$SITE/flux/resultats" -H 'Content-Type: application/json' --data-binary @"$OUT.json")
  code=$(echo "$rep" | tail -1); corps=$(echo "$rep" | sed '$d')
  if [ "$code" = 200 ]; then echo "Envoye au hub ($SITE) : $(echo "$corps" | python3 -c 'import json,sys; d=json.load(sys.stdin); a=d["alertes"]; print("passage #%s, %s alerte(s) ouverte(s), %s nouvelle(s), %s retablie(s)" % (d["passage"], a["ouvertes"], a["nouvelles"], a["retablies"]))')"
  else echo "Envoi au hub impossible (HTTP $code) : $(echo "$corps" | head -c 200)"; fi
fi
