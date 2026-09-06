// Client OIDC "tickets-portal" — déjà défini dans
// keycloak/realm-template.json depuis le début (Authorization Code +
// PKCE S256). Seul le code applicatif manquait — voir hub/src/authConfig.js
// pour le premier front à avoir fait ce câblage, repris ici à l'identique.
const KEYCLOAK_URL = import.meta.env.VITE_KEYCLOAK_URL || "http://localhost:6180";
const KEYCLOAK_REALM = import.meta.env.VITE_KEYCLOAK_REALM || "supervision-si";

export const oidcConfig = {
  authority: `${KEYCLOAK_URL}/realms/${KEYCLOAK_REALM}`,
  client_id: "tickets-portal",
  // window.location.origin ne contient JAMAIS de chemin (juste
  // schéma+hôte+port) -- ce portail vit sous /tickets/ (entrée unique
  // par chemin, voir tls-proxy/README.md), donc origin seul omettrait
  // ce préfixe entièrement, jamais compatible avec le motif
  // "https://host:port/tickets/*" autorisé côté Keycloak. Bug réel
  // rencontré sur le hub avec ce même oubli (voir hub/src/authConfig.js)
  // -- corrigé ici avant même de le tester séparément sur ce portail.
  redirect_uri: `${window.location.origin}/tickets/`,
  post_logout_redirect_uri: `${window.location.origin}/tickets/`,
  response_type: "code",
  scope: "openid profile email",
  // Nettoie l'URL après retour de Keycloak (retire ?code=...&state=...)
  // -- sans ça, un rechargement renverrait le même code déjà consommé.
  onSigninCallback: () => {
    window.history.replaceState({}, document.title, window.location.pathname);
  },
};
