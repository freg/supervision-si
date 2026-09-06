// Client OIDC "vault-admin-portal" (livraison #293) -- ajouté à
// keycloak/realm-template.json (Authorization Code + PKCE S256, même
// mécanique que vault-portal). Rien de plus à créer côté Keycloak
// une fois ce realm importé.
//
// Contrairement aux autres portails de ce projet : sert AUSSI de
// source de vérité pour "actor" (jusqu'ici un champ texte libre --
// voir vault/README.md, livraison #291) -- le login Keycloak
// VÉRIFIÉ remplace maintenant la saisie manuelle pour l'appel à
// POST /users/<login>/roles, la seule route protégée par rights-api.
// L'authentification Keycloak identifie QUI se connecte -- elle ne
// donne PAS accès aux secrets eux-mêmes, qui restent protégés par le
// chiffrement de bout en bout (mot de passe maître, jamais transmis
// ici ni nulle part) -- même séparation que vault-portal.
//
// PAS de chemin (contrairement à vault-portal qui vit sous /vault/)
// -- ce portail tourne sur un PORT DIRECT dédié
// (VAULT_ADMIN_PORTAL_LAN_PORT), jamais routé par tls-proxy (voir
// docker-compose.yml et vault/README.md).
const KEYCLOAK_URL = import.meta.env.VITE_KEYCLOAK_URL || "http://localhost:6180";
const KEYCLOAK_REALM = import.meta.env.VITE_KEYCLOAK_REALM || "supervision-si";

export const oidcConfig = {
  authority: `${KEYCLOAK_URL}/realms/${KEYCLOAK_REALM}`,
  client_id: "vault-admin-portal",
  // Voir hub/src/authConfig.js pour l'explication complète du "/"
  // final (bug réel rencontré ailleurs dans ce projet : redirect_uri
  // invalide sans lui).
  redirect_uri: `${window.location.origin}/`,
  post_logout_redirect_uri: `${window.location.origin}/`,
  response_type: "code",
  scope: "openid profile email",
  onSigninCallback: () => {
    window.history.replaceState({}, document.title, window.location.pathname);
  },
};
