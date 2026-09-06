import { useEffect, useState } from "react";
import { useAuth } from "react-oidc-context";
import {
  unlockWithPassword, usurpMaitrePrincipal, decryptArchivedRecoveryKey,
  fetchCollectionsForUser, previewResetImpact, resetAccount, reassignAccessAfterReset,
  checkAccountExists, bootstrapMasterKeyEscrow, MAITRE_PRINCIPAL_LOGIN, grantEscrowAccess,
} from "./vaultOps.js";
import { createAccountThemeStore } from "./preferences.js";

// Une seule instance pour toute la durée de vie de l'appli -- même
// motif que les autres fronts (voir hub/src/App.jsx). Synchronisation
// croisée avec les 3 autres fronts (famille localStorage) ne
// fonctionne PAS ici -- origine différente (port 6120) -- seule la
// persistance par compte (prefs-api) traverse cette limite.
const PREFS_API_BASE_URL = import.meta.env.VITE_PREFS_API_BASE_URL || "";
const themeStore = createAccountThemeStore({ apiBase: PREFS_API_BASE_URL });

const HUB_URL = import.meta.env.VITE_HUB_URL || "";
const VAULT_PORTAL_URL = import.meta.env.VITE_VAULT_PORTAL_URL || "";

// Jamais de chiffrement pour la partie "rôles" (métadonnées
// booléennes uniquement) -- mais la partie "débloquer un compte"
// utilise désormais la MÊME cryptographie que le coffre principal
// (voir vaultOps.js, usurpMaitrePrincipal/decryptArchivedRecoveryKey) :
// le mot de passe saisi ci-dessous ne quitte JAMAIS le navigateur, il
// sert uniquement à dériver localement la clé qui déchiffre la clé
// privée déjà enveloppée -- exactement comme sur l'écran de
// déverrouillage du coffre lui-même.
const ADMIN_API_BASE = import.meta.env.VITE_VAULT_ADMIN_API_BASE_URL || "";

const ROLE_FIELDS = [
  { key: "is_read_only", label: "Lecture seule", hint: "Ne peut jamais créer/modifier/supprimer — uniquement consulter." },
  { key: "is_recovery_controller", label: "Contrôle des récupérations", hint: "Marqueur informatif pour l'instant -- voir note sous le tableau." },
  { key: "is_system_master", label: "Accès permanent (maître_système)", hint: "Co-destinataire systématique de chaque collection — peut tout déchiffrer, à tout moment." },
];

async function adminApiGet(path) {
  const res = await fetch(`${ADMIN_API_BASE}${path}`);
  const body = await res.json().catch(() => ({}));
  return { ok: res.ok, status: res.status, data: body };
}
async function adminApiPost(path, body) {
  const res = await fetch(`${ADMIN_API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  return { ok: res.ok, status: res.status, data };
}

export default function App() {
  // Livraison #293 -- Keycloak AJOUTÉ comme porte d'entrée
  // supplémentaire, jamais un remplacement du déverrouillage par
  // mot de passe ci-dessous (qui reste la SEULE façon de dériver la
  // clé privée pour "débloquer un compte" -- ne change rien à ça).
  // Sert UNIQUEMENT à connaître les groupes Keycloak de la personne,
  // pour rights-api (#291) -- Keycloak identifie QUI se connecte,
  // pas ce qu'elle peut déchiffrer.
  const auth = useAuth();

  // Connexion UNIQUE -- sert à la fois d'identité journalisée (voir
  // require_lan_and_actor côté vault-admin-api) ET, si la personne
  // est membre de maitre_clefs, de clé pour déverrouiller la section
  // "débloquer un compte". Plus de champ "nom" séparé (source de
  // confusion signalée : taper un nom ne filtrait rien, ne servait
  // qu'à la journalisation sans que ce soit clair).
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [loggingIn, setLoggingIn] = useState(false);
  const [loginError, setLoginError] = useState(null);
  const [myPrivateKey, setMyPrivateKey] = useState(null); // non-null une fois connecté
  const [theme, setThemeState] = useState(themeStore.get() || "dark");

  // null = jamais tenté, "denied" = tenté et refusé (pas membre
  // maitre_clefs), "ok" = clé utilisable pour déchiffrer.
  const [masterKey, setMasterKey] = useState(null);
  const [masterKeyStatus, setMasterKeyStatus] = useState(null); // null | "denied" | "ok"
  const [masterKeyDeniedReason, setMasterKeyDeniedReason] = useState(null);
  // Distingue "personne n'a jamais initialisé le séquestre" (à
  // amorcer, voir bootstrapMasterKeyEscrow) de "il existe, vous n'y
  // avez juste pas accès" (à demander à quelqu'un qui l'a) -- bug réel
  // trouvé en testant : ces deux cas produisaient le même message
  // d'erreur trompeur, laissant croire à tort à un problème de groupe
  // Keycloak alors que le séquestre n'existait tout simplement pas.
  const [escrowExists, setEscrowExists] = useState(null); // null (pas encore su) | true | false
  const [bootstrapPassword, setBootstrapPassword] = useState("");
  const [bootstrapBusy, setBootstrapBusy] = useState(false);
  const [bootstrapError, setBootstrapError] = useState(null);
  const [bootstrapDone, setBootstrapDone] = useState(false);
  // Octroi de l'accès au séquestre à un autre compte -- demandé
  // explicitement : rendre triviale l'extension de cet accès à
  // d'autres admins de confiance, directement depuis ce portail.
  const [grantEscrowTarget, setGrantEscrowTarget] = useState("");
  const [grantEscrowBusy, setGrantEscrowBusy] = useState(false);
  const [grantEscrowError, setGrantEscrowError] = useState(null);
  const [grantEscrowDone, setGrantEscrowDone] = useState(null); // login du dernier compte accordé avec succès

  const [archiveEntries, setArchiveEntries] = useState([]); // [{login, archived_at}]
  const [archiveLoading, setArchiveLoading] = useState(false);
  const [revealedKeys, setRevealedKeys] = useState({}); // login -> clé en clair
  const [revealBusy, setRevealBusy] = useState(null);
  const [revealError, setRevealError] = useState(null);
  const [copiedLogin, setCopiedLogin] = useState(null);

  const [users, setUsers] = useState([]);
  const [usersLoading, setUsersLoading] = useState(false);
  const [roleFilter, setRoleFilter] = useState("");
  const [savingKey, setSavingKey] = useState(null);
  const [savedFlash, setSavedFlash] = useState(null);
  const [roleError, setRoleError] = useState(null);

  // Réinitialiser un compte (sans perdre les collections) -- voir
  // vaultOps.js, resetAccount/previewResetImpact/reassignAccessAfterReset.
  const [resetTargetLogin, setResetTargetLogin] = useState("");
  const [resetPreview, setResetPreview] = useState(null); // null | [{id, name, reassignable}]
  const [resetPreviewLoading, setResetPreviewLoading] = useState(false);
  const [resetPreviewError, setResetPreviewError] = useState(null);
  const [resetBusy, setResetBusy] = useState(false);
  const [resetDone, setResetDone] = useState(null); // {login, hadAccessTo} une fois réinitialisé
  const [reassignAccountReady, setReassignAccountReady] = useState(null); // null | true | false
  const [reassignCheckBusy, setReassignCheckBusy] = useState(false);
  const [reassignBusy, setReassignBusy] = useState(false);
  const [reassignResult, setReassignResult] = useState(null);

  useEffect(() => themeStore.onChange(setThemeState), []);
  const toggleTheme = () => themeStore.set(theme === "dark" ? "light" : "dark", login.trim() || undefined);

  async function handleBootstrapEscrow() {
    if (!bootstrapPassword) return;
    setBootstrapBusy(true);
    setBootstrapError(null);
    const res = await bootstrapMasterKeyEscrow(bootstrapPassword, login.trim());
    setBootstrapPassword(""); // jamais gardé en mémoire au-delà du nécessaire
    setBootstrapBusy(false);
    if (!res.ok) {
      setBootstrapError(res.error);
      return;
    }
    setBootstrapDone(true);
    setEscrowExists(true);
    // L'accès a déjà été accordé DANS bootstrapMasterKeyEscrow (voir
    // vaultOps.js, alsoGrantToLogin) -- l'usurpation doit donc réussir
    // immédiatement, sans étape séparée.
    const usurpation = await usurpMaitrePrincipal(login.trim(), myPrivateKey);
    if (usurpation.ok) {
      setMasterKey(usurpation.privateKey);
      setMasterKeyStatus("ok");
      loadArchiveList();
    }
  }

  async function handleGrantEscrowAccess() {
    const target = grantEscrowTarget.trim();
    if (!target) return;
    setGrantEscrowBusy(true);
    setGrantEscrowError(null);
    setGrantEscrowDone(null);
    const res = await grantEscrowAccess(target, login.trim(), myPrivateKey);
    setGrantEscrowBusy(false);
    if (res.ok) {
      setGrantEscrowDone(target);
      setGrantEscrowTarget("");
    } else {
      setGrantEscrowError(res.error);
    }
  }

  async function handleLogin() {
    if (!login.trim() || !password) return;
    setLoggingIn(true);
    setLoginError(null);
    const res = await unlockWithPassword(login.trim(), password);
    setPassword(""); // jamais gardé en mémoire au-delà de ce qui est strictement nécessaire
    if (!res.ok) {
      setLoggingIn(false);
      setLoginError(res.error);
      return;
    }
    setMyPrivateKey(res.privateKey);
    themeStore.load(login.trim()); // amorce le thème depuis prefs-api si rien de local pour ce navigateur

    // Tentative d'usurpation -- échoue silencieusement (juste
    // masterKeyStatus="denied") si l'accès à la collection de séquestre
    // n'a pas encore été accordé, jamais bloquant pour la suite (la
    // gestion des rôles reste disponible). Message d'erreur RÉEL
    // conservé (voir usurpMaitrePrincipal) -- jamais un texte
    // générique qui parlerait à tort du groupe Keycloak (bug réel
    // signalé : ce mécanisme ne vérifie QUE l'accès cryptographique à
    // la collection, jamais le groupe -- les deux sont indépendants).
    const usurpation = await usurpMaitrePrincipal(login.trim(), res.privateKey);
    if (usurpation.ok) {
      setMasterKey(usurpation.privateKey);
      setMasterKeyStatus("ok");
      loadArchiveList();
    } else {
      setMasterKeyStatus("denied");
      setMasterKeyDeniedReason(usurpation.error);
      // Distingue "jamais amorcé" de "existe mais pas accès" -- voir
      // /escrow-status (vault-admin-api), une question volontairement
      // publique (juste un booléen).
      const statusRes = await adminApiGet(`/escrow-status?actor=${encodeURIComponent(login.trim())}`);
      if (statusRes.ok) setEscrowExists(statusRes.data.exists);
    }

    loadUsers(login.trim());
    setLoggingIn(false);
  }

  async function loadArchiveList() {
    setArchiveLoading(true);
    const res = await adminApiGet(`/recovery-archive?actor=${encodeURIComponent(login.trim())}`);
    setArchiveLoading(false);
    if (res.ok) setArchiveEntries(res.data);
  }

  async function handleRevealKey(targetLogin) {
    setRevealBusy(targetLogin);
    setRevealError(null);
    const res = await adminApiGet(`/recovery-archive/${encodeURIComponent(targetLogin)}?actor=${encodeURIComponent(login.trim())}`);
    if (!res.ok) {
      setRevealBusy(null);
      setRevealError(res.data.error || "récupération impossible");
      return;
    }
    try {
      const plainKey = await decryptArchivedRecoveryKey(res.data.wrapped_recovery_key_for_master, masterKey);
      setRevealedKeys((prev) => ({ ...prev, [targetLogin]: plainKey }));
    } catch {
      setRevealError(`déchiffrement impossible pour ${targetLogin} — donnée corrompue ou clé maître_principal invalide`);
    }
    setRevealBusy(null);
  }

  async function handleCopyKey(targetLogin) {
    try {
      await navigator.clipboard.writeText(revealedKeys[targetLogin]);
      setCopiedLogin(targetLogin);
      setTimeout(() => setCopiedLogin((v) => (v === targetLogin ? null : v)), 1500);
    } catch {
      // Sélection manuelle du texte affiché reste toujours possible
      // si le presse-papiers est refusé par le navigateur.
    }
  }

  async function handlePreviewReset() {
    if (!resetTargetLogin.trim()) return;
    setResetPreviewLoading(true);
    setResetPreviewError(null);
    setResetPreview(null);
    setResetDone(null);
    setReassignResult(null);
    setReassignAccountReady(null);
    const target = resetTargetLogin.trim();
    const exists = await checkAccountExists(target);
    if (!exists) {
      setResetPreviewLoading(false);
      setResetPreviewError(`aucun compte coffre pour "${target}"`);
      return;
    }
    const [targetCollections, myCollections] = await Promise.all([
      fetchCollectionsForUser(target),
      fetchCollectionsForUser(login),
    ]);
    setResetPreview(previewResetImpact(targetCollections, myCollections));
    setResetPreviewLoading(false);
  }

  async function handleConfirmReset() {
    setResetBusy(true);
    const res = await resetAccount(resetTargetLogin.trim());
    setResetBusy(false);
    if (res.ok) {
      setResetDone({ login: resetTargetLogin.trim(), hadAccessTo: res.hadAccessTo });
      setResetPreview(null);
    }
  }

  async function handleCheckAccountRecreated() {
    setReassignCheckBusy(true);
    const exists = await checkAccountExists(resetDone.login);
    setReassignAccountReady(exists);
    setReassignCheckBusy(false);
  }

  async function handleReassign() {
    setReassignBusy(true);
    const collectionIds = resetDone.hadAccessTo.map((c) => c.id);
    const res = await reassignAccessAfterReset(collectionIds, resetDone.login, login, myPrivateKey);
    setReassignResult(res);
    setReassignBusy(false);
  }

  async function loadUsers(actorLogin) {
    setUsersLoading(true);
    const res = await adminApiGet(`/users?actor=${encodeURIComponent(actorLogin)}`);
    setUsersLoading(false);
    if (res.ok) setUsers(res.data);
  }

  async function toggleRole(targetLogin, roleKey, currentValue) {
    const flashKey = `${targetLogin}:${roleKey}`;
    setSavingKey(flashKey);
    setRoleError(null);
    const res = await adminApiPost(`/users/${encodeURIComponent(targetLogin)}/roles?actor=${encodeURIComponent(login.trim())}`, {
      [roleKey]: !currentValue,
      // Livraison #293 -- groupes Keycloak VÉRIFIÉS (pas le login
      // vault ci-dessus, qui n'a aucune notion de groupe), pour la
      // vérification rights-api côté vault-admin-api (#291).
      groups: auth.user?.profile?.groups || [],
    });
    if (res.ok) {
      setUsers((prev) => prev.map((u) => (u.login === targetLogin ? { ...u, [roleKey]: !currentValue ? 1 : 0 } : u)));
      setSavedFlash(flashKey);
      setTimeout(() => setSavedFlash((v) => (v === flashKey ? null : v)), 1500);
    } else {
      setRoleError(res.data.error || `erreur ${res.status}`);
    }
    setSavingKey(null);
  }

  const archivedLogins = new Set(archiveEntries.map((e) => e.login));
  const filteredUsers = roleFilter.trim()
    ? users.filter((u) => u.login.toLowerCase().includes(roleFilter.trim().toLowerCase()))
    : users;

  // Livraison #293 -- porte Keycloak, APRÈS tous les hooks
  // (respecte les règles de hooks React -- jamais un retour
  // anticipé avant qu'ils aient tous été appelés), AVANT le garde
  // de déverrouillage existant ci-dessous.
  if (auth.isLoading) {
    return (
      <div className="admin-app admin-center">
        <p className="admin-muted">Connexion en cours…</p>
      </div>
    );
  }
  if (!auth.isAuthenticated) {
    return (
      <div className="admin-app admin-center">
        <div className="admin-card">
          <h1>🔐 Coffre-fort — administration des rôles</h1>
          <p className="admin-muted">Connexion via l'annuaire de l'entreprise (Keycloak / LDAP).</p>
          <button className="primary" onClick={() => auth.signinRedirect()}>Se connecter</button>
        </div>
      </div>
    );
  }

  if (!myPrivateKey) {
    return (
      <div className="admin-app">
        <header className="admin-header">
          <div className="admin-header-top">
            {(HUB_URL || VAULT_PORTAL_URL) && (
              <nav className="admin-nav">
                {HUB_URL && <a href={HUB_URL} target="_blank" rel="noreferrer">🏠 Hub</a>}
                {VAULT_PORTAL_URL && <a href={VAULT_PORTAL_URL} target="_blank" rel="noreferrer">🔐 Coffre-fort</a>}
                {HUB_URL && <a href={`${HUB_URL}?view=settings`} target="_blank" rel="noreferrer">⚙️ Paramètres</a>}
              </nav>
            )}
            <button
              className="admin-theme-toggle"
              onClick={toggleTheme}
              title={theme === "dark" ? "Passer au thème clair" : "Passer au thème sombre"}
            >
              {theme === "dark" ? "☀️" : "🌙"}
            </button>
          </div>
          <h1>🔐 Coffre-fort — Administration</h1>
          <p className="admin-muted">
            Connectez-vous avec votre propre compte coffre. Réservé au réseau local — chaque
            action est journalisée sous ce login.
          </p>
        </header>
        <div className="admin-panel">
          <div className="admin-form-row">
            <input
              placeholder="Votre login"
              value={login}
              onChange={(e) => setLogin(e.target.value)}
            />
            <input
              type="password"
              placeholder="Votre mot de passe"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleLogin()}
            />
            <button className="primary" onClick={handleLogin} disabled={!login.trim() || !password || loggingIn}>
              {loggingIn ? "…" : "Se connecter"}
            </button>
          </div>
          {loginError && <p className="admin-error">{loginError}</p>}
        </div>
      </div>
    );
  }

  return (
    <div className="admin-app">
      <header className="admin-header">
        <div className="admin-header-top">
          {(HUB_URL || VAULT_PORTAL_URL) && (
            <nav className="admin-nav">
              {HUB_URL && <a href={HUB_URL} target="_blank" rel="noreferrer">🏠 Hub</a>}
              {VAULT_PORTAL_URL && <a href={VAULT_PORTAL_URL} target="_blank" rel="noreferrer">🔐 Coffre-fort</a>}
              {HUB_URL && <a href={`${HUB_URL}?view=settings`} target="_blank" rel="noreferrer">⚙️ Paramètres</a>}
            </nav>
          )}
          <button
            className="admin-theme-toggle"
            onClick={toggleTheme}
            title={theme === "dark" ? "Passer au thème clair" : "Passer au thème sombre"}
          >
            {theme === "dark" ? "☀️" : "🌙"}
          </button>
        </div>
        <h1>🔐 Coffre-fort — Administration</h1>
        <p className="admin-muted">Connecté en tant que <strong>{login}</strong>.</p>
      </header>

      <div className="admin-panel">
        <h2>🔓 Débloquer un compte</h2>
        <p className="admin-muted">
          Pour une personne ayant perdu son mot de passe ET sa propre copie de la clé de
          récupération. Révèle la copie ARCHIVÉE (déposée à la création du compte, chiffrée
          pour maître_principal) — la personne l'utilise ensuite elle-même via l'écran de
          déverrouillage du coffre, sans que rien ne soit jamais touché à ses collections.
        </p>
        {masterKeyStatus === "denied" && escrowExists === false && !bootstrapDone && (
          <div className="admin-bootstrap">
            <p className="admin-error">
              Le séquestre maître_clefs n'a encore jamais été initialisé sur cette installation
              — personne n'y a accès pour l'instant, y compris vous. Si vous connaissez le mot
              de passe du compte coffre <code>{MAITRE_PRINCIPAL_LOGIN}</code>, vous pouvez
              l'amorcer maintenant. Vous recevrez alors l'accès immédiatement.
            </p>
            <div className="admin-form-row">
              <input
                type="password"
                placeholder={`Mot de passe de ${MAITRE_PRINCIPAL_LOGIN}`}
                value={bootstrapPassword}
                onChange={(e) => setBootstrapPassword(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleBootstrapEscrow()}
              />
              <button className="primary" onClick={handleBootstrapEscrow} disabled={!bootstrapPassword || bootstrapBusy}>
                {bootstrapBusy ? "…" : "🔑 Initialiser le séquestre"}
              </button>
            </div>
            {bootstrapError && <p className="admin-error">{bootstrapError}</p>}
          </div>
        )}
        {masterKeyStatus === "denied" && escrowExists !== false && (
          <p className="admin-error">
            {masterKeyDeniedReason || "accès refusé"} — la gestion des rôles ci-dessous reste
            accessible. Si vous pensez devoir avoir cet accès, demandez à quelqu'un qui l'a déjà
            de vous l'accorder (indépendant du groupe Keycloak <code>maitre_clefs</code> —
            l'appartenance au groupe ne suffit pas, l'accès à la collection de séquestre doit
            être accordé explicitement par quelqu'un qui la détient déjà).
          </p>
        )}
        {masterKeyStatus === "ok" && (
          <>
            {archiveLoading && <p className="admin-muted">Chargement…</p>}
            {!archiveLoading && archiveEntries.length === 0 && (
              <p className="admin-muted">Aucune clé de récupération archivée pour l'instant.</p>
            )}
            {revealError && <p className="admin-error">{revealError}</p>}
            <table className="admin-table">
              <tbody>
                {archiveEntries.map((entry) => (
                  <tr key={entry.login}>
                    <td className="admin-login-cell">{entry.login}</td>
                    <td>
                      {revealedKeys[entry.login] ? (
                        <div className="admin-revealed-key">
                          <code>{revealedKeys[entry.login]}</code>
                          <button className="secondary" onClick={() => handleCopyKey(entry.login)}>
                            {copiedLogin === entry.login ? "✓ Copié" : "📋 Copier"}
                          </button>
                        </div>
                      ) : (
                        <button
                          className="secondary"
                          onClick={() => handleRevealKey(entry.login)}
                          disabled={revealBusy === entry.login}
                        >
                          {revealBusy === entry.login ? "…" : "🔑 Afficher la clé de récupération"}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            <div className="admin-bootstrap">
              <p className="admin-muted">
                Vous avez accès au séquestre — vous pouvez étendre cet accès à un autre compte
                de confiance, directement ici, sans passer par l'onglet Collections du coffre
                normal. Reste un octroi cryptographique normal, jamais un raccourci qui
                contournerait le chiffrement.
              </p>
              <div className="admin-form-row">
                <input
                  placeholder="Login à qui accorder l'accès"
                  value={grantEscrowTarget}
                  onChange={(e) => setGrantEscrowTarget(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleGrantEscrowAccess()}
                />
                <button className="primary" onClick={handleGrantEscrowAccess} disabled={!grantEscrowTarget.trim() || grantEscrowBusy}>
                  {grantEscrowBusy ? "…" : "🔑 Accorder l'accès au séquestre"}
                </button>
              </div>
              {grantEscrowError && <p className="admin-error">{grantEscrowError}</p>}
              {grantEscrowDone && <p className="admin-muted">✓ Accès accordé à <strong>{grantEscrowDone}</strong>.</p>}
            </div>
          </>
        )}
      </div>

      <div className="admin-panel">
        <h2>🔄 Réinitialiser un compte</h2>
        <p className="admin-muted">
          Pour un compte réellement bloqué (rien à révéler ci-dessus non plus). Supprime le
          compte pour permettre sa recréation -- les collections auxquelles il avait accès ne
          sont JAMAIS touchées, mais il faudra ensuite lui réattribuer l'accès manuellement
          (uniquement possible pour les collections auxquelles VOUS avez vous-même accès).
        </p>
        <div className="admin-form-row">
          <input
            placeholder="Login à réinitialiser"
            value={resetTargetLogin}
            onChange={(e) => setResetTargetLogin(e.target.value)}
          />
          <button className="secondary" onClick={handlePreviewReset} disabled={!resetTargetLogin.trim() || resetPreviewLoading}>
            {resetPreviewLoading ? "…" : "👁️ Aperçu avant réinitialisation"}
          </button>
        </div>
        {resetPreviewError && <p className="admin-error">{resetPreviewError}</p>}

        {resetPreview && (
          <>
            {resetPreview.length === 0 && (
              <p className="admin-muted">Ce compte n'a accès à aucune collection -- réinitialisation sans risque.</p>
            )}
            {resetPreview.length > 0 && (
              <ul className="admin-reset-preview-list">
                {resetPreview.map((c) => (
                  <li key={c.id} className={c.reassignable ? "admin-reassignable" : "admin-orphan"}>
                    {c.reassignable ? "✓" : "⚠️"} {c.name}
                    {!c.reassignable && " — vous n'y avez pas accès, sera PERDUE si personne d'autre n'y a accès"}
                  </li>
                ))}
              </ul>
            )}
            {resetPreview.some((c) => !c.reassignable) && (
              <p className="admin-error">
                Au moins une collection deviendra définitivement inaccessible si vous continuez
                (propriété du chiffrement de bout en bout, pas une limite de cet outil).
              </p>
            )}
            <button className="primary" onClick={handleConfirmReset} disabled={resetBusy}>
              {resetBusy ? "…" : "🔄 Confirmer la réinitialisation"}
            </button>
          </>
        )}

        {resetDone && (
          <div className="admin-reset-done">
            <p className="admin-muted">
              Compte <strong>{resetDone.login}</strong> réinitialisé. Demandez-lui de recréer
              son compte coffre (écran normal de première connexion), puis revenez ici.
            </p>
            {reassignAccountReady !== true && (
              <button className="secondary" onClick={handleCheckAccountRecreated} disabled={reassignCheckBusy}>
                {reassignCheckBusy ? "…" : "🔄 Vérifier si le compte a été recréé"}
              </button>
            )}
            {reassignAccountReady === false && (
              <p className="admin-muted">Pas encore recréé -- réessayez dans un instant.</p>
            )}
            {reassignAccountReady === true && !reassignResult && (
              <button className="primary" onClick={handleReassign} disabled={reassignBusy}>
                {reassignBusy ? "…" : `🔗 Réattribuer l'accès (${resetDone.hadAccessTo.length} collection${resetDone.hadAccessTo.length > 1 ? "s" : ""})`}
              </button>
            )}
            {reassignResult && (
              <p className="admin-muted">
                {reassignResult.granted} accordé{reassignResult.granted > 1 ? "s" : ""}, {reassignResult.failed} échec{reassignResult.failed > 1 ? "s" : ""}.
                {reassignResult.errors.length > 0 && <> ({reassignResult.errors.join(", ")})</>}
              </p>
            )}
          </div>
        )}
      </div>

      <div className="admin-panel">
        <h2>Rôles des comptes</h2>
        <input
          className="admin-filter-input"
          placeholder="🔍 Filtrer par login…"
          value={roleFilter}
          onChange={(e) => setRoleFilter(e.target.value)}
        />
        {usersLoading && <p className="admin-muted">Chargement…</p>}
        {roleError && <p className="admin-error">{roleError}</p>}
        {!usersLoading && filteredUsers.length > 0 && (
          <table className="admin-table">
            <thead>
              <tr>
                <th>Compte</th>
                {ROLE_FIELDS.map((f) => (
                  <th key={f.key} title={f.hint}>{f.label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filteredUsers.map((u) => (
                <tr key={u.login}>
                  <td className="admin-login-cell">
                    {u.login}
                    {archivedLogins.has(u.login) && (
                      <span className="admin-archived-badge" title="Une clé de récupération est archivée pour ce compte">🔑</span>
                    )}
                  </td>
                  {ROLE_FIELDS.map((f) => {
                    const flashKey = `${u.login}:${f.key}`;
                    return (
                      <td key={f.key} className="admin-role-cell">
                        <input
                          type="checkbox"
                          checked={!!u[f.key]}
                          disabled={savingKey === flashKey}
                          onChange={() => toggleRole(u.login, f.key, u[f.key])}
                        />
                        {savedFlash === flashKey && <span className="admin-saved-flash">✓</span>}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <p className="admin-muted admin-hint">
          "Contrôle des récupérations" reste pour l'instant un simple marqueur informatif — la
          capacité réelle de révéler une clé archivée dépend d'appartenir au groupe Keycloak
          <code>maitre_clefs</code> (voir la section "🔑" ci-dessus, badge à côté du login des
          comptes concernés), pas de cette case à cocher.
        </p>
      </div>
    </div>
  );
}
