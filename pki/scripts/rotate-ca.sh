#!/usr/bin/env bash
# Bascule ASSISTÉE de l'autorité de certification interne (livraison #496,
# BACKLOG item 3 voie b). Rien n'est jamais fait automatiquement par
# run.sh : chaque phase est une commande explicite, relançable, qui
# refuse d'avancer si l'état attendu n'est pas là.
#
#   rotate-ca.sh status    où en est la bascule (aucune écriture)
#   rotate-ca.sh prepare   1. CA neuve dans $PKI_DIR/next/ca + bundle ancienne+neuve
#                             -> distribuer le BUNDLE aux agents / postes / dockers
#                                PENDANT que le hub sert encore l'ancienne CA
#   rotate-ca.sh switch    2. ancienne CA archivée dans $PKI_DIR/ca-old-<date>/,
#                             CA neuve en place, certificat serveur réémis
#                             -> redémarrer la pile ; les consommateurs qui ont le
#                                bundle continuent sans coupure
#   rotate-ca.sh finish    3. bundle réduit à la CA neuve (fin de la période de
#                             transition) -> retirer l'ancienne CA des magasins
#
# Pourquoi un bundle : les agents (ssl.create_default_context(cafile=...)),
# le client si-proxy du Mac et la plupart des magasins acceptent un fichier
# PEM contenant PLUSIEURS autorités. Distribuer ancienne+neuve AVANT la
# bascule évite l'effet « TLS rompu jusqu'au remplacement du fichier »
# décrit dans l'analyse d'impact (BACKLOG item 3, cas 1). Les deux CA
# ont le même sujet mais des numéros de série différents (aléatoires
# depuis #495), donc aucune collision SEC_ERROR_REUSED_ISSUER_AND_SERIAL.
#
# Jamais : suppression d'une clé (l'ancienne ca.key reste dans
# ca-old-<date>/, à détruire à la main quand plus rien ne la référence),
# modification d'une CA existante, action sans la phase précédente.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$HERE/../.."

get_env() {
  local key="$1" default="$2"
  local value="${!key:-}"
  if [[ -z "$value" ]]; then
    value=$(grep -E "^${key}=" "$ROOT/.env" 2>/dev/null | tail -1 | cut -d= -f2- || true)
    value="${value%\"}"; value="${value#\"}"
    value="${value%\'}"; value="${value#\'}"
  fi
  echo "${value:-$default}"
}

PKI_DIR="$(get_env PKI_DIR "")"
if [[ -n "$PKI_DIR" ]]; then
  case "$PKI_DIR" in "~"*) echo "ERREUR : PKI_DIR='$PKI_DIR' commence par '~' -- chemin absolu requis" >&2; exit 1;; esac
  BASE="$PKI_DIR"
else
  BASE="$(cd "$HERE/.." && pwd)"
fi
CA_DIR="$BASE/ca"
NEXT_DIR="$BASE/next"
BUNDLE="$BASE/ca-bundle.crt"
STATE="$BASE/rotation.state"   # une ligne : prepared | switched (absent = pas de bascule en cours)

fp() { openssl x509 -in "$1" -noout -fingerprint -sha256 2>/dev/null | cut -d= -f2; }
serial() { openssl x509 -in "$1" -noout -serial 2>/dev/null | cut -d= -f2; }
phase() { [[ -f "$STATE" ]] && cat "$STATE" || echo "none"; }

consumers() {
  cat <<EOF
Consommateurs de la CA à mettre à jour ($1) :
  - agents hôtes (fichier central-ca.crt puis redémarrage du service) :
      Linux   : /etc/si-agent/central-ca.crt              -> systemctl restart si-agent
      macOS   : /usr/local/etc/si-agent/central-ca.crt    -> launchctl kickstart -k system/fr.exemple.si-agent
      Windows : %ProgramData%\\si-agent\\central-ca.crt    -> Restart-Service si-agent
    (ou réinstallation : install.sh / install-macos.sh --ca <fichier>, install.ps1 -Ca <fichier>)
  - client si-proxy du Mac : SI_PROXY_CA (~/.config/si-proxy/ca.crt) -> remplacer par <fichier>
  - postes / navigateurs du LAN : importer la CA NEUVE (pki/README.md, section distribution) ;
    Firefox a son propre magasin ; retirer l'ancienne SEULEMENT à la phase finish
  - dockers INDÉPENDANTS qui ont COPIÉ ca.crt dans leur trust store (cacerts Java,
    update-ca-certificates, image) : rejouer la copie avec <fichier>
  - conteneurs du hub (si-agent-api, si-proxy, si-proxy-admin-api) : volume /ca/ca.crt
    -> automatique au redémarrage de la pile après switch ; relais si-proxy :
    ./si-proxy/setup-certs.sh <hub> [--clients] après switch (certificats réémis)
EOF
}

cmd_status() {
  echo "PKI       : $BASE"
  echo "phase     : $(phase)"
  if [[ -f "$CA_DIR/ca.crt" ]]; then
    echo "CA en place : série $(serial "$CA_DIR/ca.crt")  sha256 $(fp "$CA_DIR/ca.crt")"
    "$HERE/generate-ca.sh" --check >/dev/null 2>&1 && echo "            conforme (#495)" || echo "            SANS keyUsage -> bascule justifiée"
  else
    echo "CA en place : absente"
  fi
  [[ -f "$NEXT_DIR/ca/ca.crt" ]] && echo "CA neuve    : série $(serial "$NEXT_DIR/ca/ca.crt")  sha256 $(fp "$NEXT_DIR/ca/ca.crt")  ($NEXT_DIR/ca)"
  if [[ -f "$BUNDLE" ]]; then
    echo "bundle      : $BUNDLE ($(grep -c 'BEGIN CERTIFICATE' "$BUNDLE") certificat(s))"
  fi
  ls -d "$BASE"/ca-old-* 2>/dev/null | sed 's/^/archive     : /' || true
}

cmd_prepare() {
  [[ -f "$CA_DIR/ca.crt" && -f "$CA_DIR/ca.key" ]] || { echo "pas de CA en place dans $CA_DIR : rien à basculer (generate-ca.sh)" >&2; exit 1; }
  [[ "$(phase)" == "none" ]] || { echo "bascule déjà en cours (phase $(phase)) -- 'status' pour voir, supprimer $STATE et $NEXT_DIR à la main pour recommencer" >&2; exit 1; }
  [[ -e "$NEXT_DIR/ca/ca.crt" ]] && { echo "$NEXT_DIR/ca existe déjà -- supprimer à la main pour recommencer" >&2; exit 1; }
  mkdir -p "$NEXT_DIR"; chmod 700 "$NEXT_DIR"
  echo "== 1/3 CA neuve (extensions #495) dans $NEXT_DIR/ca"
  PKI_DIR="$NEXT_DIR" "$HERE/generate-ca.sh"
  echo "== 2/3 bundle ancienne + neuve : $BUNDLE"
  cat "$CA_DIR/ca.crt" "$NEXT_DIR/ca/ca.crt" > "$BUNDLE"; chmod 644 "$BUNDLE"
  echo "prepared" > "$STATE"
  echo "== 3/3 à faire AVANT 'switch' (le hub sert toujours l'ancienne CA, rien n'est cassé) :"
  consumers "$BUNDLE"
  echo
  echo "empreinte de la CA neuve (à comparer lors de la distribution) : $(fp "$NEXT_DIR/ca/ca.crt")"
  echo "puis : $0 switch"
}

cmd_switch() {
  [[ "$(phase)" == "prepared" ]] || { echo "phase attendue : prepared (lancer 'prepare' d'abord) -- actuelle : $(phase)" >&2; exit 1; }
  [[ -f "$NEXT_DIR/ca/ca.crt" && -f "$NEXT_DIR/ca/ca.key" ]] || { echo "CA neuve absente de $NEXT_DIR/ca" >&2; exit 1; }
  if [[ "${1:-}" != "--yes" ]]; then
    echo "Cette phase remplace la CA servie par le hub. Tous les consommateurs SANS le bundle"
    echo "perdront la connexion TLS jusqu'à mise à jour de leur ca.crt. Confirmer : $0 switch --yes"
    exit 2
  fi
  local stamp; stamp="$(date +%Y%m%d-%H%M%S)"
  local OLD="$BASE/ca-old-$stamp"
  echo "== 1/4 ancienne CA archivée dans $OLD (clé conservée, mode 700)"
  mv "$CA_DIR" "$OLD"; chmod 700 "$OLD"
  echo "== 2/4 CA neuve en place"
  mv "$NEXT_DIR/ca" "$CA_DIR"; rmdir "$NEXT_DIR" 2>/dev/null || true
  echo "== 3/4 certificat serveur réémis par la CA neuve"
  "$HERE/generate-server-cert.sh"
  cat "$OLD/ca.crt" "$CA_DIR/ca.crt" > "$BUNDLE"; chmod 644 "$BUNDLE"
  echo "switched" > "$STATE"
  echo "== 4/4 à faire maintenant :"
  echo "  - redémarrer la pile (scripts/run-all.sh up -d) : volumes /ca/ca.crt et cert serveur pris en compte"
  echo "  - ./si-proxy/setup-certs.sh <hub> [--clients]  (relais et clients réémis par la CA neuve)"
  echo "  - vérifier un agent : sa file locale survit, 'central_in_use' revient à true dans la tuile"
  echo "  - quand TOUT le monde a la CA neuve : $0 finish"
  echo "retour arrière possible tant que 'finish' n'est pas lancé : mv $CA_DIR $NEXT_DIR-abandon && mv $OLD $CA_DIR && generate-server-cert.sh"
}

cmd_finish() {
  [[ "$(phase)" == "switched" ]] || { echo "phase attendue : switched -- actuelle : $(phase)" >&2; exit 1; }
  cp "$CA_DIR/ca.crt" "$BUNDLE"; chmod 644 "$BUNDLE"
  rm -f "$STATE"
  echo "bundle réduit à la CA neuve ($BUNDLE). Reste à faire, à la main :"
  echo "  - retirer l'ancienne CA des magasins des postes/navigateurs (même sujet, série différente)"
  echo "  - redistribuer $BUNDLE (CA neuve seule) aux agents qui avaient reçu le bundle de transition"
  echo "  - détruire l'ancienne clé quand plus rien ne la référence : rm -rf $BASE/ca-old-*  (jamais fait ici)"
  consumers "$CA_DIR/ca.crt"
}

case "${1:-}" in
  status)  cmd_status ;;
  prepare) cmd_prepare ;;
  switch)  cmd_switch "${2:-}" ;;
  finish)  cmd_finish ;;
  *) sed -n '2,25p' "$0" | sed 's/^# \{0,1\}//'; exit 2 ;;
esac
