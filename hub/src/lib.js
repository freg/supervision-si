// Logique pure du hub — testable via Node, sans dépendance à
// import.meta.env ni au DOM.

// Groupes Keycloak (realm supervision-si) -> rôle applicatif
// équivalent (mêmes clés que ROLE_LABELS ci-dessous, et que
// tickets/portal/src/lib.js — ne pas laisser diverger). PIVOT fait
// après un bug Keycloak documenté de longue date (KEYCLOAK-3469) :
// les rôles realm HÉRITÉS d'un groupe ne remontent pas toujours de
// façon fiable dans realm_access.roles du jeton, contrairement à ceux
// assignés directement à l'utilisateur — alors que l'appartenance aux
// groupes elle-même (claim "groups", mapper dédié) s'est révélée
// fiable en conditions réelles (rôles absents malgré des groupes
// visiblement corrects). Toute la logique de visibilité de ce fichier
// s'appuie donc sur les GROUPES, jamais sur les rôles calculés par
// Keycloak.
export const GROUP_TO_ROLE = {
  administrateurs: "admin",
  demandeurs: "demandeur",
  techniciens: "technicien",
  direction: "politique",
  supervision: "supervision",
  service: "service",
  maitre_clefs: "maitre_clefs",
  // Groupe dédié au fork ProjeQtOr (livraison #476) -- la tuile reste
  // visible de TOUS (décision de la personne) ; ce mapping existe pour
  // les filtrages FUTURS (droits fins dans ProjeQtOr, liens externes
  // restreints...), aucune tuile ne s'en sert encore.
  projeqtor: "projeqtor",
};

/** Convertit une liste de groupes Keycloak bruts en rôles applicatifs
 * connus (ignore tout groupe non mappé, jamais d'exception sur une
 * entrée absente/malformée). */
export function groupsToRoles(groups) {
  if (!Array.isArray(groups)) return [];
  return groups.map((g) => GROUP_TO_ROLE[g]).filter(Boolean);
}

/** true si `value` figure dans le tableau (générique, utilisé aussi
 * bien pour des rôles dérivés que des groupes bruts — jamais
 * d'exception sur une entrée absente/malformée). */
export function hasValue(list, value) {
  return Array.isArray(list) && list.includes(value);
}

/** true si la personne est administrateur (groupe Keycloak
 * "administrateurs") -- pour gater la section "Général" de la page
 * de paramètres (admin uniquement sur le paramétrage global par
 * application, demandé explicitement). */
export function isAdmin(groups) {
  return hasValue(groups, "administrateurs");
}

/** true si la personne est technicien (groupe Keycloak "techniciens")
 * -- pour n'afficher les préférences personnelles du rappel
 * d'activité qu'aux personnes concernées. */
export function isTechnicien(groups) {
  return hasValue(groups, "techniciens");
}


// Liste des fronts du projet — un seul endroit à modifier pour en
// ajouter un futur (une seule carte par FRONT séparé et déployé
// indépendamment, jamais un lien par onglet interne : les modules
// internes de Supervision SI — IPAM, Zenoss, Fusion... — sont TOUS
// dans le même front "Supervision SI", pas des fronts séparés).
//
// Visibilité par groupe Keycloak, décidée avec la personne :
// - Supervision SI  : groupe "supervision" (indépendant des 4 rôles
//   du portail tickets — quelqu'un peut avoir accès à l'un sans
//   l'autre).
// - Portail tickets : tout le monde (aucune condition).
// - Administration Keycloak : groupe "administrateurs" OU "techniciens".
// - DBA (administration multi-SGBD) : groupe "administrateurs"
//   SEULEMENT — pas "techniciens", contrairement à Keycloak. Décision
//   volontairement plus stricte : cet outil stocke des identifiants de
//   connexion à des bases EXTERNES au projet (l'écosystème DBA plus
//   large de la personne) et permet du SQL libre, DELETE/DROP compris
//   — une sensibilité différente d'une console Keycloak en lecture
//   seule pour la plupart des usages techniciens.
// - Coffre-fort (codes/secrets) : groupe "service" — dédié, distinct
//   de "techniciens" volontairement (décidé avec la personne) : tous
//   les techniciens n'ont pas forcément besoin des codes d'accès
//   physiques. Chiffrement de bout en bout côté coffre lui-même (le
//   serveur ne voit jamais rien en clair) — cette carte ne contrôle
//   que la VISIBILITÉ du lien depuis le hub, pas l'accès réel aux
//   secrets, qui reste de toute façon impossible sans le mot de passe
//   maître de la personne, jamais connu ici.
//
// keycloakConsoleUrl/groups : carte "Administration Keycloak"
// conditionnelle, pointe vers la console SCOPÉE au realm
// supervision-si (/auth/admin/supervision-si/console/), pas la
// console master : avoir un rôle applicatif dans supervision-si ne
// donne PAS automatiquement de droits Keycloak au niveau plateforme
// (realm master) — voir hub/README.md pour ce que ça implique
// concrètement (la carte est un lien, pas une garantie d'accès tant
// que des droits de gestion de realm n'ont pas été accordés séparément
// dans Keycloak).
export function buildFrontsList({
  frontendUrl, portalUrl, keycloakConsoleUrl, dbaUrl, vaultUrl, vaultAdminUrl, ldapAdminUrl, projeqtorUrl,
  groups, externalLinks,
}) {
  const roles = groupsToRoles(groups);
  const fronts = [];
  if (frontendUrl && hasValue(roles, "supervision")) {
    fronts.push({
      id: "supervision",
      name: "Supervision SI",
      description: "Carte, arbres radiaux, IPAM, Zenoss, Fusion IP/MAC, géomatique…",
      url: frontendUrl,
      embeddable: true,
    });
  }
  if (portalUrl) {
    fronts.push({
      id: "tickets",
      name: "Portail tickets",
      description: "Demandes, suivi, priorités, statistiques — selon votre profil",
      url: portalUrl,
      embeddable: true,
    });
  }
  if (keycloakConsoleUrl && (hasValue(roles, "admin") || hasValue(roles, "technicien"))) {
    fronts.push({
      id: "keycloak-admin",
      name: "Administration Keycloak",
      description: "Utilisateurs, rôles, groupes, fédération LDAP — realm supervision-si",
      url: keycloakConsoleUrl,
      // Keycloak refuse lui-même d'être intégré en iframe (protection
      // de sécurité native, X-Frame-Options) -- reste un lien classique,
      // jamais un onglet de la coquille.
      embeddable: false,
    });
  }
  if (dbaUrl && hasValue(roles, "admin")) {
    fronts.push({
      id: "dba",
      name: "DBA",
      description: "Administration multi-SGBD (PostgreSQL, MySQL, SQLite) — connexions, navigation, SQL libre",
      url: dbaUrl,
      embeddable: true,
    });
  }
  if (vaultUrl && hasValue(roles, "service")) {
    fronts.push({
      id: "vault",
      name: "Coffre-fort",
      description: "Codes d'accès, équipements sécurisés — chiffré de bout en bout",
      url: vaultUrl,
      embeddable: true,
    });
  }
  if (vaultAdminUrl && (hasValue(roles, "admin") || hasValue(roles, "maitre_clefs"))) {
    fronts.push({
      id: "vault-admin",
      name: "Administration du coffre-fort",
      description: "Rôles : lecture seule, contrôle des récupérations, accès permanent (maître_système)",
      url: vaultAdminUrl,
      // Origine DIFFÉRENTE (port LAN direct, jamais routé par
      // tls-proxy -- voir docker-compose.yml) -- jamais un onglet
      // intégré, une vraie navigation reste nécessaire.
      embeddable: false,
    });
  }
  if (ldapAdminUrl && hasValue(roles, "admin")) {
    fronts.push({
      id: "ldap-admin",
      name: "Administration OpenLDAP",
      description: "Utilisateurs, réinitialisation de mots de passe, sauvegardes versionnées",
      url: ldapAdminUrl,
      embeddable: true,
    });
  }
  // ProjeQtOr (fork, livraison #476) -- visible de TOUT LE MONDE,
  // comme le portail tickets (décision explicite de la personne :
  // "visibilité à tous, il y aura une page publique"). Aucune
  // condition de rôle ici ; le groupe Keycloak "projeqtor" existe pour
  // des filtrages futurs. L'accès RÉEL reste protégé par l'écran de
  // connexion de ProjeQtOr lui-même (LDAP du hub ou comptes propres).
  if (projeqtorUrl) {
    fronts.push({
      id: "projeqtor",
      name: "ProjeQtOr",
      description: "Gestion de projets — fork maison, ergonomie en cours de refonte",
      url: projeqtorUrl,
      embeddable: true,
    });
  }
  // Liens externes gérés par les administrateurs -- backlog, livraison
  // #121. `allowed_roles` VIDE (ou absent) = visible de tout le monde,
  // même défaut que les entrées internes ci-dessus qui n'ont pas de
  // condition de rôle (ex. portail tickets). Filtrage CÔTÉ CLIENT
  // uniquement -- même posture de confiance que le reste du hub
  // (aucune vérification de rôle ne se fait jamais côté serveur, voir
  // prefs-api/app.py). Jamais une exception sur une entrée malformée
  // (URL manquante, allowed_roles pas un tableau) -- simplement omise.
  for (const link of externalLinks || []) {
    if (!link || !link.url) continue;
    const allowedRoles = Array.isArray(link.allowed_roles) ? link.allowed_roles : [];
    if (allowedRoles.length > 0 && !allowedRoles.some((r) => hasValue(roles, r))) continue;
    fronts.push({
      id: `external-${link.id}`,
      name: link.name,
      description: link.description || "",
      url: link.url,
      embeddable: !!link.embeddable,
      external: true,
    });
  }
  return fronts;
}

// Libellés lisibles pour les rôles applicatifs (dérivés des groupes,
// voir GROUP_TO_ROLE ci-dessus). Mêmes clés que tickets/portal/src/lib.js.
export const ROLE_LABELS = {
  admin: "Administrateur",
  demandeur: "Demandeur",
  technicien: "Technicien",
  politique: "Direction",
  supervision: "Supervision",
  service: "Service",
  maitre_clefs: "Maître des clés",
  projeqtor: "ProjeQtOr",
};

/** groups : tableau brut de groupes Keycloak (claim "groups") --
 * traduit en libellés lisibles via GROUP_TO_ROLE/ROLE_LABELS. Ne lève
 * jamais sur une entrée absente/malformée. */
export function formatUserRoles(groups) {
  return groupsToRoles(groups).map((r) => ROLE_LABELS[r]);
}
