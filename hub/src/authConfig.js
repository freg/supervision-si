// Client OIDC "supervision-hub" — déjà défini dans
// keycloak/realm-template.json (Authorization Code + PKCE S256, comme
// tickets-portal et supervision-frontend). Rien à créer côté Keycloak,
// juste à s'y connecter.
//
// KEYCLOAK_URL et KEYCLOAK_REALM sont injectés via docker-compose
// (VITE_KEYCLOAK_URL/VITE_KEYCLOAK_REALM) — jamais codés en dur, pour
// que ce même code fonctionne sans modification quel que soit
// l'hôte/domaine réel de déploiement.
const KEYCLOAK_URL = import.meta.env.VITE_KEYCLOAK_URL || "http://localhost:6180";
const KEYCLOAK_REALM = import.meta.env.VITE_KEYCLOAK_REALM || "supervision-si";

export const oidcConfig = {
  authority: `${KEYCLOAK_URL}/realms/${KEYCLOAK_REALM}`,
  client_id: "supervision-hub",
  // window.location.origin ne contient JAMAIS de chemin (juste
  // schéma+hôte+port), même si la page est servie sous un préfixe —
  // pour le hub (base "/"), ça tombe juste MAIS sans le "/" final que
  // Keycloak exige pour matcher son motif de redirectUri autorisé
  // ("https://host:port/*" -- un "*" qui suit un "/", pas "port" seul).
  // Bug réel rencontré : "Paramètre invalide : redirect_uri" avec
  // juste window.location.origin. Voir tickets/portal/src/authConfig.js
  // pour l'équivalent sous /tickets/, où l'écart est plus large encore
  // (le chemin n'y est jamais inclus du tout par origin).
  redirect_uri: `${window.location.origin}/`,
  post_logout_redirect_uri: `${window.location.origin}/`,
  response_type: "code",
  scope: "openid profile email",
  // Nettoie l'URL (retire ?code=...&state=... ajoutés par Keycloak
  // après redirection) — sans ça, un rechargement de page renverrait
  // le même code d'autorisation déjà consommé et échouerait.
  onSigninCallback: () => {
    window.history.replaceState({}, document.title, window.location.pathname);
  },
};
