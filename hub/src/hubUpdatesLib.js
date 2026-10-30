// Mises à jour du hub en pied de page (#762) : dernières livraisons (hubUpdates.json, généré depuis le CHANGELOG par
// scripts/gen-hub-updates.py) et, pour chacune, des boutons vers les écrans nouveaux ou modifiés.
import { SINCE, THEMES } from "./hubThemes.js";

// Écrans MODIFIÉS par une livraison (les tuiles NOUVELLES viennent de SINCE) : à compléter à chaque livraison visible.
// (#788 : rappel -- à chaque livraison visible, ajouter son entrée ici ET relancer scripts/gen-hub-updates.py)
// (#790 : `params` = paramètres d'écran posés avant l'ouverture, ex. { tab: "sms" } -> l'onglet précis)
export const UPDATE_LINKS = {
  941: [{ view: "si-agent", params: { section: "sauvegardes" }, hint: "fiche agent › Sauvegardes : bouton « { } Inventaire JSON » -- clés, chemins, exports (mots de passe, favoris, historique), relevé, sans aucune valeur" }],
  940: [{ view: "sauvegardes", params: { onglet: "nas" }, hint: "NAS QNAP : connexions et accès, journaux, aide des outils, gestion à distance (essai en lecture, actions déclarées en intervention)" }],
  939: [{ view: "sauvegardes", params: { onglet: "backuppc" }, hint: "thématique Sauvegardes à l'accueil ; BackupPC : hôtes, échecs à traiter, lancer / arrêter (intervention) ; NAS QNAP : snapshots, Time Machine, RAID par SSH" }],
  938: [{ view: "postes-windows", hint: "Diagnostic › Propositions et conseils : éléments nommés (quel disque, quelle carte, quelle mise à jour) et procédures avec commandes copiables" }],
  937: [{ view: "sauvegardes", hint: "tuile Sauvegardes : postes (conf + PBS), PBS, copies host/VM, BackupPC, NAS -- vue d'ensemble en lecture seule" }],
  936: [{ view: "si-agent", params: { section: "sauvegardes" }, hint: "fiche agent : onglet Sauvegardes ; boutons rouges Poste Windows, Sauvegarde données / image, Boot USB urgence" }],
  906: [{ view: "sockets", hint: "tuile Sockets : netstat -laputen des hôtes agentés (écoute et établies, processus, PID, utilisateur), à la demande avec historique" }],
  903: [{ view: "messages", hint: "tuile Messages : blog interne du hub (un mot pour tous ou pour soi, permanent ou à durée de vie, copiable)" }],
  902: [{ view: "si-agent", hint: "fiche d'un agent Windows : bloc de diagnostic « l'agent est installé mais rien ne remonte » à copier" }],
  900: [{ view: "si-agent", hint: "Windows : le fichier .cmd d'installation se suffit à lui-même (télécharge et vérifie l'agent)" }],
  899: [{ view: "si-agent", hint: "accueil sans connexion : « Nouvel agent » (installation ouverte agent par agent, fiche › Installation) et « Accès sécurisé »" }],
  897: [{ view: "si-agent", hint: "Agents › Installation : étape Windows « téléchargement, vérification et décompression » (PowerShell)" }],
  896: [{ view: "postes-windows", hint: "tuile Postes Windows : réinstallation (partages, abonnements, logiciels, messagerie) et diagnostic de panne ; tests de charge à la demande" }],
  895: [{ view: "vpn", hint: "onglet VPN : pairs et sessions WireGuard reconstitués des journaux du routeur (échecs, pertes de contact, adresses d'origine)" }],
  894: [{ view: "vpn", hint: "onglet VPN : journal WireGuard reçu en syslog (routeur MikroTik) ; réception syslog conservée 90 jours" }],
  892: [{ view: "vpn", hint: "onglet VPN : un serveur WireGuard illisible (routeur injoignable…) s'affiche avec son erreur" }],
  891: [{ view: "si-agent", params: { tab: "updates" }, hint: "Agents › Mises à jour : bouton « Tout mettre à jour »" }],
  889: [{ view: "vpn", hint: "onglet VPN : WireGuard d'un routeur MikroTik par l'API RouterOS (compte en lecture seule)" }],
  888: [{ view: "vpn", hint: "onglet VPN : opérateur d'origine (Starlink, 4G…) et stabilité par utilisateur (sessions courtes, reconnexions)" }],
  885: [{ view: "vpn", hint: "onglet VPN : sessions SoftEther (r2d2) par hub, utilisateur, protocole, poste, volumes ; échecs d'authentification" }],
  884: [{ view: "vpn", hint: "onglet VPN : pairs WireGuard et historique des connexions reconstitué (lecture seule)" }],
  883: [{ view: "nas", hint: "tuile NAS : volumes, disques (âge, SMART), RAID, applications, alertes -- SNMP en lecture seule" }],
  882: [{ view: "migration", params: { page: "etat" }, hint: "« ⚖ Barème des estimations » : points par type d'action, catégories (physique, virtuel, conteneur, SGBD), automatisable, vélocité, marge" }],
  881: [{ view: "migration", params: { page: "etat" }, hint: "Excel des décideurs et page d'audit de nouveau disponibles" }],
  880: [{ view: "si-agent", hint: "bouton « ⚙ OS » : ping, processus (htop), réseau (ntop), journal depuis l'hôte, une VM ou un CT (agents en 0.6.7)" }],
  879: [{ view: "migration", params: { page: "etat" }, hint: "copies, clones, préparations et tests rattachés à leur système, listés en fin ; « Rattachement » dans la fiche" }],
  878: [{ view: "migration", params: { page: "etat" }, hint: "temps estimé par action (marge ×3), planning en Gantt par regroupements de dépendances ; Excel et page d'audit" }],
  877: [{ view: "migration", params: { page: "etat" }, hint: "état des lieux compact (2 lignes), fiche au clic ; barres de défilement épaisses dans tout le hub" }],
  876: [{ view: "si-agent", hint: "Flotte : hôtes relevés à distance (nms, optick3) sous leur agent relais" }],
  874: [{ view: "aujourdhui", hint: "un rechargement revient sur la page consultée, son onglet et sa position" }],
  873: [{ view: "migration", params: { page: "etat" }, hint: "audit réseau : appareils découverts, services et versions vus du réseau ; feuille « Audit réseau » de l'Excel" },
        { view: "si-agent", params: { tab: "catalogue" }, hint: "sonde lan-audit (à lancer sur l'agent de super : --targets, --exclude)" }],
  872: [{ view: "nebula", params: { tab: "historique" }, hint: "historique des clients : relève horaire, relever maintenant, filtres, tri, périodes de présence" }],
  871: [{ view: "aujourdhui", hint: "pied de page : un seul rechargement par livraison, sinon la commande de reconstruction" }],
  870: [{ view: "migration", params: { page: "etat" }, hint: "état des lieux : affichage rapide (index des dernières mesures par sonde)" }],
  869: [{ view: "si-agent", params: { tab: "events" }, hint: "fin des « database is locked » : purge et historique des VM par petits lots" }],
  868: [{ view: "si-agent", hint: "bouton « ping » à côté des IP (Agents, Proxmox, onduleurs, postes, infra, latence, état des lieux, équipements)" }],
  867: [{ view: "si-agent", hint: "installeur des hôtes anciens Debian 4 / 5 : si-agent/agent/ancien/install-ancien.sh (pas de lien : opération manuelle)" }],
  866: [{ view: "migration", params: { page: "etat" }, hint: "serveurs anciens : ports écoutés, adresses et services corrigés" }],
  865: [{ view: "migration", params: { page: "etat" }, hint: "serveurs très anciens relevés à distance : système, paquets, ports, services" }],
  864: [{ view: "si-agent", hint: "installation sur un hôte ancien (Debian 9 / Python 3.5) : commandes complètes" }],
  863: [{ view: "migration", params: { page: "etat" }, hint: "pour les décideurs : où, quand, combien -- serveurs concernés, phases, volumes, durées, coupures" }],
  862: [{ view: "migration", params: { page: "etat" }, hint: "Excel décideurs et audit : chantiers en cours et décisions à prendre" }],
  861: [{ view: "migration", params: { page: "etat" }, hint: "état des lieux : serveurs et postes hors Proxmox, serveurs utilisés mais non suivis" }],
  860: [{ view: "migration", params: { page: "etat" }, hint: "audit obsolescence et support pour les décideurs : page à imprimer, calendrier des fins de support" }],
  859: [{ view: "migration", params: { page: "etat" }, hint: "état des lieux : les VM arrêtées sont lues hors ligne (système, paquets, services)" }],
  858: [{ view: "migration", params: { page: "etat" }, hint: "état des lieux : déclarer à la main un système illisible (VM sans agent invité, Windows), compteur de non identifiés" }],
  857: [{ view: "migration", params: { page: "etat" }, hint: "état des lieux des systèmes : versions, fin de support, mises à jour, services, usage, dépendances ; Excel pour les décideurs" }],
  856: [{ view: "migration", params: { page: "copies" }, hint: "toutes les copies de chaque CT / VM et leur distance à la source (0 = identique), volume, survie à la perte du nœud" }, { view: "migration", params: { page: "risques" }, hint: "risque permanent par CT / VM : sauvegarde, réplication, accès aux services, support, nœud" }],
  855: [{ view: "nebula", params: { tab: "pilotage" }, hint: "pilotage du campus : mesures et outils d'action, boucles de rétroaction à chaud, scénarios, bancs de test avec clients simulés" }],
  854: [{ view: "iapark", params: { tab: "modeles", onglet: "genealogie" }, hint: "généalogie des modèles depuis le Transformer : filiations, dates, auteurs, liens, mode d'emploi ; relevé quotidien Hugging Face" }],
  853: [{ view: "notifications", params: { tab: "pauses" }, hint: "pauses planifiées : fermeture de site, travaux, coupure ; bilan à la reprise" }],
  852: [{ view: "nebula", params: { tab: "vlan" }, hint: "anomalies : préparer l'action (impact, chien de garde, retour arrière), journal ; recherche sur tout en tête de tuile" }],
  851: [{ view: "nebula", params: { tab: "charge" }, hint: "charge par borne, SSID, VLAN, commutateur" }, { view: "nebula", params: { tab: "vlan" }, hint: "synoptique : rouge = panne qui compte, névralgiques, pastilles chiffrées" }],
  850: [{ view: "nebula", params: { tab: "veille" }, hint: "réglages de la veille pré-remplis : VLAN de Nebula, postes des fiches du campus" }],
  847: [{ view: "nebula", params: { tab: "veille" }, hint: "veille du réseau du campus : équipements, VLAN, DHCP, Internet, postes ; créneaux d'usage mixte" }],
  840: [{ view: "mailbox", hint: "agents si-mailbox : requêtes et automates IA dans la session ; discret par défaut" }],
  839: [{ view: "emulation", hint: "bouton Écran par le bastion (porte des écrans de l'hôte)" }, { view: "navigateur", hint: "usage « écrans d'émulation » dans le registre" }],
  838: [{ view: "emulation", hint: "lancement d'une machine complète : plus d'échec à tort, écran lancé ; émulateurs indépendants de l'agent" }],
  837: [{ view: "orchestration", params: { tab: "commandes" }, hint: "pied de page : commandes en cours avec lien, bandeau « terminé — voir »" }],
  836: [{ view: "orchestration", params: { tab: "vms" }, hint: "VM à la demande : clone d'un modèle, durée de vie, nettoyage automatique" }],
  835: [{ view: "emulation", hint: "écran (noVNC), SSH, adb ; exporter une image Raspberry installable ; installer une APK" }],
  834: [{ view: "orchestration", params: { tab: "deployer" }, hint: "catalogue d'images : sélection, recherche Docker Hub, étiquettes et architectures" }],
  833: [{ view: "orchestration", hint: "boutons « en cours… » et bascule vers le résultat ; Nomad démarre" }, { view: "emulation", hint: "boutons « en cours… »" }],
  832: [{ view: "orchestration", hint: "VM Proxmox et conteneurs k3s / Nomad : déployer, placement, quotas, durée de vie" }],
  831: [{ view: "emulation", hint: "émulateurs Raspberry Pi (3B, Zero W, Zero 2 W) et Android, déploiement de l'agent" }],
  830: [{ view: "aujourdhui", hint: "pied de page permanent : livraison, mise à jour en cours, travaux d'IA ; ↻ recharge sans cache" }],
  829: [{ view: "aujourdhui", hint: "Priorités : « ✓ » / « ✎ » sur chaque élément ; le jeu est dans Parc IA › Apprentissage" }],
  828: [{ view: "iapark", params: { tab: "apprentissage" }, hint: "Apprentissage : jeu du décideur (vos décisions de veille), entraînements, évaluation" }],
  827: [{ view: "iapark", params: { tab: "skills" }, hint: "Skills : consignes des Priorités (préparation, décideur, explication), versions, essai" }],
  826: [{ view: "banc", hint: "tuile Banc d'installation : Modèles de VM › Fabriquer (Debian, Ubuntu, Rocky), Pool et passages" }],
  825: [{ view: "si-agent", params: { tab: "banc" }, hint: "Banc d'installation : « Configurer le pool » (nœud, plage de vmid, modèles, commandes) puis « Lancer »" }],
  824: [{ view: "si-agent", params: { tab: "updates" }, hint: "agent 0.5.97 : mise à jour automatique Windows réparée ; MSI à construire (pas de lien : opération manuelle, si-agent/agent/windows/msi/README.md)" }],
  823: [{ view: "iapark", params: { tab: "modeles", onglet: "mes" }, hint: "Usages : cocher préparation / décideur / explication sur les modèles de l'hôte PRIORITES_LLM_HOTE" }],
  822: [{ view: "si-agent", params: { tab: "updates" }, hint: "Mises à jour › Diffusions en cascade (« Nouvelle diffusion » propose l'exemple pve-preflight)" }],
  821: [{ view: "iapark", hint: "onglet « Veille des modèles » : alertes, veille, historique, usages, bancs, réglages" }],
  820: [{ view: "veille", hint: "« ✕ » sur un article (article, source, sujet, thème, mots-clés) ; onglet « Rejets » pour repêcher" }],
  819: [{ view: "si-agent", hint: "vue locale (lecture seule) sur le poste : http://127.0.0.1:8090/ une fois ouverte par agent.json ou le central -- pas de lien : opération manuelle (voir README-DEPLOIEMENT, « Vue locale »)" }],
  818: [{ view: "veille", hint: "onglet « IA : sorties » (modèles, API, outils) ; Priorités : en haut de la page d'accueil" }],
  817: [{ view: "migration", params: { page: "prep" }, hint: "liens « activer la sonde » vers la fiche de l'agent (ou « pas de lien : opération manuelle »)" }],
  815: [{ view: "migration", params: { page: "prep" }, hint: "Préparer la réinstallation d'un nœud : quorum, invités transférés, sauvegardes, PRA par CT / VM" }],
  814: [{ view: "veille", hint: "Nouvelle tuile : alertes, news (IA, générales, France / Europe, règlements), impacts sur notre SI, filtres et extraction, diffusion" }],
  747: [{ view: "nebula", hint: "Rapports › Occupation" }],
  748: [{ view: "pve-ops", hint: "Migration › méthode directe" }],
  750: [{ view: "pve-ops", hint: "Migration › Rapatriement distant → local" }],
  751: [{ view: "pve-ops", hint: "Migration › directe sur le LAN" }],
  752: [{ view: "mailserver", hint: "Incidents, File d'attente, Échecs, Listes, Réglages" }],
  754: [{ front: "assistant", hint: "Évaluation et Journal" }, { view: "iapark", hint: "Tests" }],
  755: [{ view: "si-agent", hint: "Mises à jour" }],
  758: [{ view: "nebula", hint: "Rapports › Occupation › Anticipation" }],
  759: [{ view: "nebula", hint: "Rapports › Occupation › Anticipation" }],
  760: [{ view: "cortex", hint: "incidents « cause Wi-Fi probable »" }],
  799: [{ view: "navigateur", hint: "Navigateur des hôtes : apprendre un parcours, le rejouer avec le coffre, demande en langage courant" }],
  811: [{ view: "datarf", hint: "État du réseau de sondes : Activité / RF / Wi-Fi / LAN en couleur, action à faire, liens données et configuration" }],
  807: [{ view: "datarf", hint: "Configuration radio d'une sonde : rôles des interfaces, SSID testés (clés du coffre), envoi depuis le hub" }],
  806: [{ view: "datarf", hint: "Nouvelle tuile : spectre et écoute Wi-Fi des sondes, croisement par canal, bornes, constats" }],
  803: [{ view: "htop", hint: "Constat swap seulement si le swap est réellement actif" }],
  802: [{ view: "htop", hint: "htop des CT : relais local du Proxmox, émetteurs installés dans les CT en une commande" }],
  801: [{ view: "si-agent", hint: "Sondes wifi-monitor (Alfa en écoute passive) et rf-spectrum (HackRF) : fiche de l'agent › Sondes" }],
  800: [{ view: "htop", hint: "Nouvelle tuile : htop en direct de chaque VM, CT et Proxmox (relais UDP), constats, capacité d'un nœud" }],
  798: [{ view: "navigateur", hint: "Nouvelle tuile : navigateur visible sur l'hôte d'un agent (écran web, automate, parcours)" }],
  797: [{ view: "journal", hint: "Journal des chantiers : plus d'erreur 500 (base bloquée par le contrôle DNS)" }, { view: "edge", hint: "Contrôle DNS des proxys d'entrée sans bloquer la base" }],
  796: [{ view: "urgence", hint: "Écran Urgence : état 24 h, accès rapides, contacts, alertes poussées sur le téléphone" }, { view: "notifications", hint: "Alertes poussées : appareils abonnés (notify-api /push)" }],
  795: [{ view: "journal", hint: "Nouvelle tuile : journal des chantiers, import / export Excel, suggestions du hub" }],
  794: [{ view: "si-agent", hint: "hub-watch : SMS d'alerte par l'API du TRB140" }],
  793: [{ view: "si-agent", hint: "Sonde hub-watch (garde du hub depuis un autre hôte, alerte hors hub)" }],
  792: [{ view: "si-agent", hint: "Sondes remote-status (veille du NMS) et sms-gateway (passerelle 4G) : constats critiques" }],
  791: [{ view: "notifications", params: { tab: "sms" }, hint: "boutons d'accès direct au relais SMS et au TRB140" }],
  790: [{ view: "notifications", params: { tab: "sms" }, hint: "les boutons de mise à jour ouvrent l'onglet concerné (ici 📱 SMS)" }, { view: "migration", params: { onglet: "MX" }, hint: "onglet MX" }],
  789: [{ view: "notifications", params: { tab: "sms" }, hint: "La recherche « sms » trouve la tuile ; onglet 📱 SMS" }],
  787: [{ view: "notifications", params: { tab: "sms" }, hint: "Onglet 📱 SMS : envoi, journal, relance ; API interne /sms distincte du client externe" }],
  784: [{ view: "migration", params: { onglet: "MX" }, hint: "Onglets du plan (dont « MX ») ; étapes à la main avec commande et machine" }],
  783: [{ view: "services", hint: "Tour › cascade sans dépassement de délai (reconstruction par lots)" }],
  782: [{ view: "fleetviews", hint: "Colonne GPU" }, { view: "iapark", hint: "Cartes graphiques des hôtes" }],
  781: [{ view: "migration", hint: "Étape manuelle devenue automatique : plus bloquée après réimport" }],
  780: [{ view: "migration", hint: "Envoi ZFS des CT convertis en modèle (basevol)" }],
  778: [{ view: "migration", hint: "Tous les boutons : occupés pendant l'envoi, second clic bloqué, bandeau « fait » / « échec »" }],
  777: [{ view: "guest-usage", hint: "Fiche d'un CT / VM : SSH, sudo, fichiers modifiés, courriels, connexions établies, journaux récents ; mois : SSH, fichiers, courriels" }],
  776: [{ view: "edge", hint: "Nouvelle tuile : couple de proxys d'entrée, bascule vers un autre serveur interne, contrôle DNS et alerte « DNS à configurer »" }],
  775: [{ view: "latency", hint: "Nouvelle tuile : latence de toutes les IP publiques, points de mesure (agent, compte + sudo, rebond), erreurs avec solution" }],
  774: [{ view: "migration", hint: "Nouvelle tuile : plan de migration pas à pas, Démarrer / Pause / Étape suivante / Auto, erreurs avec bouton Solution" }],
  773: [{ view: "infra", hint: "Transferts › Destinations des transferts : copié, avancement, débit, fin estimée" }],
  772: [{ view: "services", hint: "Tour › Services › Hôte du hub : fichiers (inodes), « plein dans ~ », minimum 24 h, fichiers effacés encore ouverts" }],
  771: [{ view: "guest-usage", hint: "Colonnes 13 mois, Inactif réel, Décision ; liste décideurs (CSV) ; fiche ⚙ : décision et suivi de migration" }],
  770: [{ view: "mailserver", hint: "Onglet Contrôles : tests fabriqués (spam, virus) et indicateurs" }],
  769: [{ view: "guest-usage", hint: "Nouvel écran : activité de chaque CT / VM et fiche de paramétrage" }, { view: "proxmox", hint: "Lien vers l'activité de la VM" }],
  768: [{ view: "repatriation", hint: "Liens vers le journal dans les erreurs" }, { view: "si-agent", hint: "Événements filtrés par lien" }],
  766: [{ view: "infra", hint: "Transferts › Tâches Proxmox en cours" }],
  765: [{ view: "repatriation", hint: "Restes sur le nœud local" }],
  764: [{ view: "repatriation", hint: "Inventaire distant" }],
  763: [{ view: "repatriation", hint: "État des données" }, { view: "infra", hint: "État des données" }, { view: "fleetviews", hint: "État des données" }, { view: "iapark", hint: "État des données" }],
};

/** Libellé d'une vue ou d'un front d'après les thèmes du hub. */
export function entryLabel(target, themes = THEMES) {
  for (const t of themes) for (const e of t.entries || []) {
    if ((target.view && e.view === target.view) || (target.front && e.front === target.front)) return e.label;
  }
  return target.view || target.front;
}

/** Livraisons à afficher, chacune avec ses liens : nouvelles tuiles (SINCE) puis écrans modifiés (UPDATE_LINKS),
 *  sans doublon ; `available(view)` / `frontUrl(front)` décident si le bouton est actif. */
export function updatesWithLinks(items, { since = SINCE, links = UPDATE_LINKS, themes = THEMES } = {}) {
  const byDelivery = {};
  for (const [key, n] of Object.entries(since)) {
    if (key.includes(":")) continue;
    (byDelivery[n] = byDelivery[n] || []).push({ view: key, isNew: true });
  }
  return (items || []).map((u) => {
    const out = [];
    for (let n = u.from || u.n; n <= u.n; n += 1) out.push(...(byDelivery[n] || []), ...(links[n] || []));
    const seen = new Set();
    const uniq = out.filter((l) => { const k = (l.view || "") + "|" + (l.front || "") + "|" + JSON.stringify(l.params || {}); if (seen.has(k)) return false; seen.add(k); return true; });
    return { ...u, links: uniq.map((l) => ({ ...l, label: entryLabel(l, themes) })) };
  });
}

export const shortDate = (d) => (d ? `${d.slice(8, 10)}/${d.slice(5, 7)}` : "");
