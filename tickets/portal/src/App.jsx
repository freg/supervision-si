import React, { useEffect, useState } from "react";
import { useAuth } from "react-oidc-context";
import { getJson, postJson } from "./api.js";
import { ROLE_LABELS, ROLE_ACCENTS, computeAccessibleRoles } from "./lib.js";
import { createAccountThemeStore } from "./preferences.js";
import versionInfo from "./VERSION.json";
import DemandeurView from "./views/DemandeurView.jsx";
import TechnicienView from "./views/TechnicienView.jsx";
import PolitiqueView from "./views/PolitiqueView.jsx";
import AdminView from "./views/AdminView.jsx";

const PREFS_API_BASE_URL = import.meta.env.VITE_PREFS_API_BASE_URL || "";
// Une seule instance pour toute la durée de vie de l'appli -- voir
// shared/preferences.js et hub/src/App.jsx (même mécanisme,
// dupliqué volontairement, pas de composant React partagé entre
// fronts dans ce projet).
const themeStore = createAccountThemeStore({ apiBase: PREFS_API_BASE_URL });

// Vue demandeur "pour le compte de" -- le personnel (technicien,
// admin, direction, supervision) qui reçoit un appel téléphonique
// choisit un demandeur, puis voit/utilise la vue demandeur normale
// pour cette personne. JAMAIS un vrai changement d'identité Keycloak
// (pas de nouvelle session, pas de token exchange) -- tout reste
// attribué au demandeur choisi (user_id), avec le personnel tracé
// comme auteur réel (acted_by_user_id) — voir tickets/README.md.
function ActingForDemandeurView({ actor }) {
  const [demandeurs, setDemandeurs] = useState([]);
  const [selectedId, setSelectedId] = useState("");

  useEffect(() => {
    getJson("/users").then((r) => {
      if (r.ok) setDemandeurs(r.data.filter((u) => u.role === "demandeur"));
    });
  }, []);

  const selected = demandeurs.find((d) => String(d.id) === selectedId);

  return (
    <div>
      <div className="panel acting-for-picker">
        <h2>✍️ Saisir pour le compte d'un demandeur</h2>
        <p className="muted">
          Utile pour un appel téléphonique : choisissez la personne pour qui
          vous saisissez — la demande apparaîtra chez elle, avec votre nom
          tracé comme auteur réel.
        </p>
        <select value={selectedId} onChange={(e) => setSelectedId(e.target.value)}>
          <option value="">— Choisir un demandeur —</option>
          {demandeurs.map((d) => (
            <option key={d.id} value={d.id}>{d.name || d.login}</option>
          ))}
        </select>
      </div>
      {selected && <DemandeurView me={selected} actedBy={actor} />}
    </div>
  );
}

// Écran de connexion — plus de saisie manuelle de login : l'identité
// vient de Keycloak/LDAP (client OIDC "tickets-portal", même mécanique
// que hub/, voir hub/README.md pour le détail du flux et les deux
// accrocs réels rencontrés en le mettant en place — realm jamais
// importé, crypto.subtle qui exige HTTPS/localhost).
function LoginScreen({ onLogin }) {
  return (
    <div className="login-wrap">
      <div className="panel">
        <h2>Portail tickets</h2>
        <p className="muted">Connexion via l'annuaire de l'entreprise (Keycloak / LDAP).</p>
        <button className="primary" onClick={onLogin}>🔐 Se connecter</button>
      </div>
    </div>
  );
}

// Le login LDAP authentifié par Keycloak est inconnu de la base
// tickets (jamais encore utilisé ce portail) — propose la création
// d'un compte demandeur, comme avant, mais désormais rattaché à une
// identité VÉRIFIÉE (LDAP), pas à un login tapé librement par
// n'importe qui.
function CreateAccountScreen({ ldapLogin, suggestedName, onCreated, onLogout }) {
  const [name, setName] = useState(suggestedName || "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const createAccount = async () => {
    if (busy) return;
    setBusy(true);
    setError(null);
    const res = await postJson("/users", {
      login: ldapLogin,
      name: name.trim() || ldapLogin,
      role: "demandeur",
    });
    if (!res.ok) {
      setBusy(false);
      setError(res.data.error || "création impossible");
      return;
    }
    const profile = await getJson(`/portal/profile?login=${encodeURIComponent(ldapLogin)}`);
    setBusy(false);
    if (profile.ok) onCreated(profile.data);
    else setError("compte créé mais profil illisible — réessayer");
  };

  return (
    <div className="login-wrap">
      <div className="panel">
        <h2>Portail tickets</h2>
        <p>
          Connecté en tant que <strong>{ldapLogin}</strong> (annuaire de
          l'entreprise), mais aucun compte tickets ne lui correspond encore.
          Créer un compte demandeur ?
        </p>
        <div className="form-grid">
          <div className="form-row">
            <label>Nom affiché</label>
            <input
              autoFocus
              placeholder="Prénom Nom (facultatif)"
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && createAccount()}
            />
          </div>
          <div className="form-actions">
            <button onClick={onLogout}>Se déconnecter</button>
            <button className="primary" onClick={createAccount} disabled={busy}>
              ➕ Créer mon compte demandeur
            </button>
          </div>
        </div>
        {error && <p className="error-text">{error}</p>}
        <p className="login-notice">
          Les rôles technicien, politique et administrateur sont attribués
          par un administrateur — jamais auto-attribuables depuis cet écran.
        </p>
      </div>
    </div>
  );
}

export default function App() {
  const auth = useAuth();
  const [profile, setProfile] = useState(null);
  const [profileState, setProfileState] = useState("idle"); // idle|loading|ok|unknown|error
  const [profileError, setProfileError] = useState(null);
  // Rôle actuellement affiché — distinct du rôle "réel" (profile.role,
  // la ligne users.role) : une personne membre de plusieurs groupes
  // Keycloak peut prévisualiser plusieurs vues sans changer d'identité
  // (me={profile} reste toujours la vraie identité pour les requêtes,
  // seul le CHOIX de vue affichée change).
  const [selectedRole, setSelectedRole] = useState(null);

  // Lien direct vers un ticket précis (livraison #170, demandé
  // explicitement -- lien depuis GedView.jsx, "Liaisons" d'un
  // document). Lu UNE SEULE FOIS au montage (useState avec fonction
  // d'initialisation, jamais re-lu à chaque rendu) -- ?ticket=<id>
  // dans l'URL. "En rôle technicien si possible, sinon lecture
  // seule" : ci-dessous, si la personne n'a PAS accès technicien,
  // repli sur sa propre vue (demandeur -- voit alors sa PROPRE liste
  // de tickets, jamais une fiche à laquelle elle n'a pas droit).
  const [linkedTicketId] = useState(() => {
    const params = new URLSearchParams(window.location.search);
    const raw = params.get("ticket");
    return raw && /^\d+$/.test(raw) ? raw : null;
  });

  const ldapLogin = auth.user?.profile?.preferred_username;
  const suggestedName = auth.user?.profile?.name;
  const [theme, setThemeState] = useState(themeStore.get() || "light");
  useEffect(() => {
    if (!ldapLogin) return;
    themeStore.load(ldapLogin);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ldapLogin]);
  useEffect(() => themeStore.onChange(setThemeState), []);
  const toggleTheme = () => themeStore.set(theme === "dark" ? "light" : "dark", ldapLogin);
  // Vérification SILENCIEUSE de session au montage — même correctif
  // que hub/src/App.jsx, même cause (bug réel rencontré : authentifié
  // sur ce portail via le cache, "Se connecter" quand même redemandé
  // en revenant du hub — chaque front ne regarde que son propre
  // stockage local, jamais s'il existe déjà une session Keycloak
  // valide ailleurs dans le même realm). Voir hub/src/App.jsx pour le
  // détail complet (iframe de même origine, entrée unique par chemin).
  const [silentCheckDone, setSilentCheckDone] = useState(false);

  useEffect(() => {
    if (auth.isLoading || auth.isAuthenticated || auth.activeNavigator || silentCheckDone) return;
    auth.signinSilent()
      .catch(() => {
        // Pas de session Keycloak valide ailleurs -- normal, l'écran
        // "Se connecter" s'affichera juste après.
      })
      .finally(() => setSilentCheckDone(true));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auth.isLoading, auth.isAuthenticated, auth.activeNavigator, silentCheckDone]);

  useEffect(() => {
    if (!auth.isAuthenticated || !ldapLogin) return;
    setProfileState("loading");
    getJson(`/portal/profile?login=${encodeURIComponent(ldapLogin)}`).then((res) => {
      if (res.ok) {
        setProfile(res.data);
        setSelectedRole(res.data.role);
        setProfileState("ok");
      } else if (res.status === 404) {
        setProfileState("unknown");
      } else {
        setProfileError(res.data.error || "API injoignable");
        setProfileState("error");
      }
    });
  }, [auth.isAuthenticated, ldapLogin]);

  if (auth.isLoading || (!auth.isAuthenticated && !silentCheckDone && !auth.error)) {
    return (
      <div className="login-wrap">
        <p className="muted">Connexion en cours…</p>
      </div>
    );
  }

  if (auth.error) {
    return (
      <div className="login-wrap">
        <div className="panel">
          <h2>⚠️ Erreur de connexion</h2>
          <p className="error-text">{auth.error.message}</p>
          <button className="primary" onClick={() => auth.signinRedirect()}>Réessayer</button>
        </div>
      </div>
    );
  }

  if (!auth.isAuthenticated) {
    return <LoginScreen onLogin={() => auth.signinRedirect()} />;
  }

  if (profileState === "unknown") {
    return (
      <CreateAccountScreen
        ldapLogin={ldapLogin}
        suggestedName={suggestedName}
        onCreated={(p) => { setProfile(p); setProfileState("ok"); }}
        onLogout={() => auth.signoutRedirect()}
      />
    );
  }

  if (profileState === "error") {
    return (
      <div className="login-wrap">
        <div className="panel">
          <h2>⚠️ Erreur</h2>
          <p className="error-text">{profileError}</p>
          <button onClick={() => auth.signoutRedirect()}>Se déconnecter</button>
        </div>
      </div>
    );
  }

  if (profileState !== "ok" || !profile) {
    return (
      <div className="login-wrap">
        <p className="muted">Chargement du profil…</p>
      </div>
    );
  }

  const accent = ROLE_ACCENTS[profile.role] || "#2980b9";
  const kcGroups = Array.isArray(auth.user?.profile?.groups) ? auth.user.profile.groups : [];
  const accessibleRoles = computeAccessibleRoles(profile.role, kcGroups);
  // Lien direct vers un ticket (livraison #170) -- FORCE le rôle
  // technicien si accessible (une fiche précise se consulte mieux
  // là, la file "toute entreprise" y donne accès quel que soit le
  // demandeur d'origine) -- prioritaire sur le rôle choisi
  // manuellement (selectedRole), jamais l'inverse : le lien doit
  // amener directement là où il pointe.
  const hasTechnicienAccess = accessibleRoles.includes("technicien");
  const activeRole = linkedTicketId && hasTechnicienAccess
    ? "technicien"
    : accessibleRoles.includes(selectedRole) ? selectedRole : profile.role;
  const isRealDemandeur = profile.role === "demandeur";
  const showLinkedTicketFallbackNotice = Boolean(linkedTicketId) && !hasTechnicienAccess;
  // "Se déconnecter" retiré pour le personnel (décidé avec la
  // personne — reste connecté toute la journée via SSO, pas de raison
  // courante de se déconnecter). Basé sur les GROUPES Keycloak, pas le
  // rôle local du portail : quelqu'un peut être "demandeur" localement
  // ET dans le groupe "supervision" (ex. un cadre qui soumet parfois
  // des demandes mais a aussi accès à Supervision SI) — la consigne
  // portait sur les groupes, pas sur le rôle portail.
  const STAFF_GROUPS = ["administrateurs", "techniciens", "direction", "supervision"];
  const isStaffGroup = kcGroups.some((g) => STAFF_GROUPS.includes(g));
  const showDisconnect = !isStaffGroup;

  let view = null;
  if (activeRole === "admin") view = <AdminView me={profile} />;
  else if (activeRole === "technicien") view = <TechnicienView me={profile} initialTicketId={linkedTicketId} />;
  else if (activeRole === "politique") view = <PolitiqueView me={profile} />;
  else if (isRealDemandeur) view = <DemandeurView me={profile} />;
  else view = <ActingForDemandeurView actor={profile} />;

  return (
    <div className="portal-root" style={{ "--accent": accent }}>
      <header className="portal-header">
        <a href="/" className="portal-hub-link" title="Retour au hub">🏠 Hub</a>
        <a href="/?view=settings" className="portal-hub-link" title="Paramètres (page dédiée dans le hub)">⚙️ Paramètres</a>
        <button
          className="portal-hub-link"
          onClick={toggleTheme}
          title={theme === "dark" ? "Passer au thème clair" : "Passer au thème sombre"}
        >
          {theme === "dark" ? "☀️" : "🌙"}
        </button>
        <div className="portal-brand">
          🎫 Portail tickets<small>Supervision SI</small>
        </div>
        {accessibleRoles.length > 1 && (
          <div className="role-switcher" title="Accès à plusieurs vues (plusieurs groupes Keycloak)">
            {accessibleRoles.map((r) => (
              <button
                key={r}
                className={r === activeRole ? "active" : ""}
                onClick={() => setSelectedRole(r)}
              >
                {ROLE_LABELS[r]}
              </button>
            ))}
          </div>
        )}
        <div className="spacer" />
        {kcGroups.length > 0 && (
          <span
            className="role-chip role-chip-groups"
            title={`Groupes Keycloak (realm supervision-si) : ${kcGroups.join(", ")}`}
          >
            🗂️ {kcGroups.join(", ")}
          </span>
        )}
        <span className="role-chip">
          👤 {profile.name || profile.login}
          <span className="role-name">{ROLE_LABELS[profile.role] || profile.role}</span>
        </span>
        {showDisconnect && (
          <button onClick={() => auth.signoutRedirect()}>Se déconnecter</button>
        )}
      </header>
      <main className="portal-main">
        {showLinkedTicketFallbackNotice && (
          <p className="hint" style={{ margin: "12px 16px" }}>
            ℹ️ Le lien pointait vers le ticket #{linkedTicketId}, mais vous n'avez pas
            accès à la vue technicien pour l'ouvrir directement -- voici votre propre
            liste de demandes à la place.
          </p>
        )}
        {view}
      </main>
      <div className="version-badge" title={`hash contenu : ${versionInfo.content_hash} · hash git : ${versionInfo.git_hash} · dernière vérification : ${versionInfo.last_checked_at}`}>
        #{versionInfo.delivery_number || "?"}
      </div>
    </div>
  );
}

