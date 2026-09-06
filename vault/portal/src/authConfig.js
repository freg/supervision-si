// Client OIDC "vault-portal" — déjà défini dans
// keycloak/realm-template.json (Authorization Code + PKCE S256, même
// mécanique que hub/tickets-portal). Rien à créer côté Keycloak.
//
// L'authentification Keycloak identifie QUI se connecte (login) --
// elle ne donne PAS accès aux secrets eux-mêmes, qui restent protégés
// par le chiffrement de bout en bout (mot de passe maître, jamais
// transmis ici ni nulle part). Keycloak = "qui êtes-vous", le coffre
// = "qu'avez-vous le droit de déchiffrer" -- deux choses séparées,
// volontairement.
const KEYCLOAK_URL = import.meta.env.VITE_KEYCLOAK_URL || "http://localhost:6180";
const KEYCLOAK_REALM = import.meta.env.VITE_KEYCLOAK_REALM || "supervision-si";

export const oidcConfig = {
  authority: `${KEYCLOAK_URL}/realms/${KEYCLOAK_REALM}`,
  client_id: "vault-portal",
  // Voir hub/src/authConfig.js pour l'explication complète du "/"
  // final (bug réel rencontré : redirect_uri invalide sans lui).
  redirect_uri: `${window.location.origin}/vault/`,
  post_logout_redirect_uri: `${window.location.origin}/vault/`,
  response_type: "code",
  scope: "openid profile email",
  onSigninCallback: () => {
    window.history.replaceState({}, document.title, window.location.pathname);
  },
};
