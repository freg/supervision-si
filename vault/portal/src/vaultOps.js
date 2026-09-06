/**
 * Orchestration du coffre — enchaîne les primitives cryptographiques
 * (./vaultCrypto.js, copié comme theme.css/preferences.js au moment
 * du build) et les appels réseau (./api.js), séparé des composants
 * React pour rester testable indépendamment de l'interface.
 *
 * Aucune fonction ici ne renvoie ni ne journalise jamais un secret en
 * clair au-delà de ce que l'appelant a explicitement demandé de
 * déchiffrer -- et jamais vers le réseau, dans un sens ou dans
 * l'autre.
 */

import {
  generateSalt, deriveMasterKey,
  generateUserKeyPair, exportPublicKey, importPublicKey,
  wrapPrivateKey, unwrapPrivateKey,
  generateRecoveryKey, importRecoveryKey,
  generateCollectionKey, wrapCollectionKeyForUser, unwrapCollectionKeyForUser,
  encryptWithCollectionKey, decryptWithCollectionKey,
} from "./vaultCrypto.js";
import { getJson, postJson, putJson, deleteJson } from "./api.js";

// Login RÉSERVÉ du compte "maître_principal" (voir vault/README.md,
// section maitre_clefs) -- décidé avec la personne : archive
// centralisée des clés de récupération individuelles, déchiffrable
// uniquement par les membres du groupe Keycloak "maitre_clefs", qui
// "usurpent" cette identité via le mécanisme de partage de collection
// déjà existant plutôt qu'un mot de passe commun à mémoriser.
export const MAITRE_PRINCIPAL_LOGIN = "maitre_principal";
// Nom RÉSERVÉ de la collection de séquestre -- une collection comme
// une autre pour le backend, rien de spécial côté stockage.
const MASTER_KEY_ESCROW_COLLECTION_NAME = "🔑 Clé maître (accès secours maitre_clefs)";

// Dupliqué à l'identique de vaultCrypto.js (fonctions privées là-bas)
// plutôt que d'élargir la surface exportée d'un module déjà testé --
// utilitaire trivial, le risque de divergence est négligeable face au
// risque de toucher un fichier crypto stable pour un besoin
// périphérique.
function bytesToBase64(bytes) {
  let binary = "";
  for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
  return btoa(binary);
}
function base64ToBytes(base64) {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

/**
 * Crée un nouveau compte coffre pour `login` — génère tout le matériel
 * cryptographique nécessaire, envoie au serveur uniquement ce qui est
 * déjà chiffré, et renvoie la clé privée déjà déverrouillée (prête à
 * l'usage immédiat) ainsi que la clé de RÉCUPÉRATION EN CLAIR — champ
 * de sortie le plus sensible de toute cette fonction, à n'afficher
 * qu'UNE SEULE FOIS à la personne (voir README du coffre), jamais
 * journalisée, jamais renvoyée au serveur sous cette forme.
 */
export async function createVaultAccount(login, password) {
  const salt = generateSalt();
  const masterKey = await deriveMasterKey(password, salt);
  const keyPair = await generateUserKeyPair();
  const publicKeyB64 = await exportPublicKey(keyPair.publicKey);
  const wrappedByPassword = await wrapPrivateKey(keyPair.privateKey, masterKey);

  const recoveryKey = generateRecoveryKey();
  const recoveryAesKey = await importRecoveryKey(recoveryKey);
  const wrappedByRecovery = await wrapPrivateKey(keyPair.privateKey, recoveryAesKey);

  const res = await postJson("/users", {
    login,
    salt,
    public_key: publicKeyB64,
    wrapped_private_key_iv: wrappedByPassword.iv,
    wrapped_private_key_ciphertext: wrappedByPassword.ciphertext,
    wrapped_private_key_recovery_iv: wrappedByRecovery.iv,
    wrapped_private_key_recovery_ciphertext: wrappedByRecovery.ciphertext,
  });
  if (!res.ok) {
    return { ok: false, error: res.data.error || "création impossible" };
  }

  // Archivage automatique pour maitre_clefs -- SILENCIEUX si aucun
  // maître_principal n'existe encore (rien à archiver, pas une
  // erreur : ce mécanisme est optionnel, seulement actif une fois
  // qu'un administrateur a mis en place ce compte réservé). Jamais
  // bloquant pour la création du compte elle-même : un échec ici ne
  // doit jamais empêcher la personne d'utiliser son coffre.
  await archiveRecoveryKeyForMaster(login, recoveryKey).catch(() => {});

  return { ok: true, privateKey: keyPair.privateKey, recoveryKey };
}

/**
 * Dépose la clé de récupération de `login` dans l'archive, chiffrée
 * avec la clé PUBLIQUE du compte maître_principal. Chiffrement RSA-OAEP
 * DIRECT sur les octets bruts (crypto.subtle.encrypt), PAS via
 * wrapCollectionKeyForUser/wrapKey -- cette dernière voie exigerait
 * que la clé de récupération importée soit "extractable", ce qui
 * aurait forcé une modification d'importRecoveryKey() dans
 * vaultCrypto.js (déjà testé, 30 tests) pour un besoin qui ne la
 * justifie pas : on a ici directement la chaîne base64 en clair sous
 * la main, pas besoin de repasser par un objet CryptoKey intermédiaire
 * juste pour la rechiffrer. N'échoue jamais bruyamment si aucun
 * maître_principal n'existe -- ce mécanisme reste entièrement
 * optionnel.
 */
export async function archiveRecoveryKeyForMaster(login, recoveryKeyBase64) {
  const masterRes = await getJson(`/users/${MAITRE_PRINCIPAL_LOGIN}`);
  if (!masterRes.ok) return { ok: true, skipped: true }; // pas de maître_principal configuré -- rien à archiver
  const masterPublicKey = await importPublicKey(masterRes.data.public_key);
  const recoveryKeyBytes = base64ToBytes(recoveryKeyBase64);
  const encrypted = await crypto.subtle.encrypt({ name: "RSA-OAEP" }, masterPublicKey, recoveryKeyBytes);
  const wrapped = bytesToBase64(new Uint8Array(encrypted));
  const res = await postJson("/recovery-archive", { login, wrapped_recovery_key_for_master: wrapped });
  return res.ok ? { ok: true } : { ok: false, error: res.data.error };
}

/**
 * Met en séquestre la clé privée du compte maître_principal — à
 * appeler UNE FOIS, juste après avoir créé ce compte réservé. La clé
 * privée exportée devient le "secret" d'une collection dédiée,
 * chiffrée par le mécanisme habituel (createSecret) -- aucun
 * enveloppement supplémentaire nécessaire, la clé de la collection
 * suffit déjà. Donner accès à un membre de maitre_clefs ensuite est
 * ensuite un simple grantAccess(), le mécanisme déjà existant, rien
 * de nouveau à construire pour ça.
 */
export async function createMasterKeyEscrow(maitrePrincipalPrivateKey, maitrePrincipalPublicKeyB64) {
  const coll = await createCollection(
    MASTER_KEY_ESCROW_COLLECTION_NAME,
    MAITRE_PRINCIPAL_LOGIN,
    maitrePrincipalPublicKeyB64
  );
  if (!coll.ok) return coll;

  const rawPrivateKey = await crypto.subtle.exportKey("pkcs8", maitrePrincipalPrivateKey);
  const exported = bytesToBase64(new Uint8Array(rawPrivateKey));
  const secretRes = await createSecret(
    coll.id,
    "clé privée du maître_principal",
    exported,
    coll.collectionKey,
    MAITRE_PRINCIPAL_LOGIN
  );
  if (!secretRes.ok) return secretRes;
  return { ok: true, collectionId: coll.id };
}

/**
 * Amorçage en un seul appel -- pour l'interface d'initialisation
 * (portail admin) : prend le mot de passe de maître_principal
 * directement (jamais via usurpation, circulaire tant que le
 * séquestre n'existe pas), récupère sa clé publique, puis crée le
 * séquestre. Combine unlockWithPassword + GET /users/<login> +
 * createMasterKeyEscrow pour que l'appelant n'ait qu'un mot de passe
 * à fournir.
 *
 * `alsoGrantToLogin` (optionnel) -- octroie IMMÉDIATEMENT l'accès à
 * ce compte une fois le séquestre créé. Correction après relecture :
 * sans ça, la personne qui vient de fournir le mot de passe de
 * maître_principal pour amorcer n'aurait PAS automatiquement accès
 * elle-même (seul "maitre_principal" l'a, auto-octroyé à sa propre
 * création) -- elle aurait dû refaire une étape séparée pour
 * s'accorder l'accès qu'elle vient de rendre possible. Échec de cet
 * octroi complémentaire n'invalide jamais l'amorçage lui-même (déjà
 * réussi à ce stade) -- renvoie quand même {ok:true}.
 */
export async function bootstrapMasterKeyEscrow(password, alsoGrantToLogin) {
  const unlockRes = await unlockWithPassword(MAITRE_PRINCIPAL_LOGIN, password);
  if (!unlockRes.ok) return unlockRes;
  const userRes = await getJson(`/users/${encodeURIComponent(MAITRE_PRINCIPAL_LOGIN)}`);
  if (!userRes.ok) return { ok: false, error: "compte maître_principal introuvable" };
  const escrowRes = await createMasterKeyEscrow(unlockRes.privateKey, userRes.data.public_key);
  if (!escrowRes.ok || !alsoGrantToLogin) return escrowRes;

  try {
    const collectionsRes = await getJson(`/collections?user=${encodeURIComponent(MAITRE_PRINCIPAL_LOGIN)}`);
    const escrowCollection = collectionsRes.ok
      ? collectionsRes.data.find((c) => c.id === escrowRes.collectionId)
      : null;
    if (escrowCollection) {
      const escrowKey = await unlockCollectionKey(escrowCollection.wrapped_key, unlockRes.privateKey);
      await grantAccess(escrowRes.collectionId, alsoGrantToLogin, escrowKey, MAITRE_PRINCIPAL_LOGIN);
    }
  } catch {
    // Amorçage déjà réussi (escrowRes.ok) -- un échec ICI signifie
    // juste que l'octroi immédiat n'a pas eu lieu, pas que le
    // séquestre lui-même est en mauvais état. La personne pourra
    // toujours se faire accorder l'accès séparément ensuite.
  }
  return escrowRes;
}

/**
 * Accorde l'accès au séquestre maître_clefs à un autre compte --
 * pour un compte qui a DÉJÀ cet accès lui-même (via `myPrivateKey`,
 * déjà déverrouillé). Réutilise grantAccess() tel quel sur la
 * collection de séquestre, jamais de logique dupliquée. Demandé
 * explicitement : rendre triviale l'extension de cet accès à
 * d'autres admins de confiance, directement depuis le portail admin
 * -- sans devoir passer par l'onglet Collections du coffre normal.
 *
 * Ne CONTOURNE jamais la protection cryptographique -- exige
 * toujours que l'appelant ait réellement l'accès (myPrivateKey doit
 * déchiffrer la clé de la collection), ça reste un octroi normal,
 * juste rendu plus accessible.
 */
export async function grantEscrowAccess(targetLogin, myLogin, myPrivateKey) {
  const collectionsRes = await getJson(`/collections?user=${encodeURIComponent(myLogin)}`);
  if (!collectionsRes.ok) return { ok: false, error: "impossible de lister vos collections" };
  const escrow = collectionsRes.data.find((c) => c.name === MASTER_KEY_ESCROW_COLLECTION_NAME);
  if (!escrow) return { ok: false, error: "vous n'avez pas accès au séquestre vous-même" };
  let escrowKey;
  try {
    escrowKey = await unlockCollectionKey(escrow.wrapped_key, myPrivateKey);
  } catch {
    return { ok: false, error: "déchiffrement de votre propre accès impossible" };
  }
  return grantAccess(escrow.id, targetLogin, escrowKey, myLogin);
}

/**
 * Pour un membre de maitre_clefs déjà déverrouillé (SA PROPRE clé
 * privée, jamais celle du maître_principal) : retrouve et déchiffre
 * la clé privée séquestrée du maître_principal — "usurpe" son
 * identité pour la durée de cet usage, sans jamais avoir eu besoin de
 * connaître son mot de passe maître. Échoue proprement si la
 * personne n'a pas (ou plus) accès à la collection de séquestre --
 * exactement le même mécanisme de révocation que pour une collection
 * normale.
 */
export async function usurpMaitrePrincipal(login, myPrivateKey) {
  const collectionsRes = await getJson(`/collections?user=${encodeURIComponent(login)}`);
  if (!collectionsRes.ok) return { ok: false, error: "impossible de lister les collections" };
  const escrow = collectionsRes.data.find((c) => c.name === MASTER_KEY_ESCROW_COLLECTION_NAME);
  if (!escrow) {
    return { ok: false, error: "aucun accès à la collection de séquestre — quelqu'un ayant déjà cet accès doit vous l'accorder explicitement (indépendant du groupe Keycloak maitre_clefs)" };
  }

  let escrowCollectionKey;
  try {
    escrowCollectionKey = await unlockCollectionKey(escrow.wrapped_key, myPrivateKey);
  } catch {
    return { ok: false, error: "impossible de déverrouiller la collection de séquestre" };
  }

  const secretsRes = await getJson(`/collections/${escrow.id}/secrets`);
  if (!secretsRes.ok || secretsRes.data.length === 0) {
    return { ok: false, error: "collection de séquestre vide — le maître_principal n'a peut-être pas encore été configuré" };
  }
  const { value } = await decryptSecret(secretsRes.data[0], escrowCollectionKey);
  const rawPrivateKey = base64ToBytes(value);
  const maitrePrincipalPrivateKey = await crypto.subtle.importKey(
    "pkcs8",
    rawPrivateKey,
    { name: "RSA-OAEP", hash: "SHA-256" },
    true,
    ["unwrapKey", "decrypt"] // les deux : unwrapKey (déballer une clé de collection) ET decrypt (déchiffrer une clé de récupération archivée), deux usages Web Crypto distincts
  );
  return { ok: true, privateKey: maitrePrincipalPrivateKey };
}

/** Existe-t-il déjà un compte coffre pour ce login -- détermine si le
 * premier écran doit proposer "créer" ou "déverrouiller". */
export async function checkAccountExists(login) {
  const res = await getJson(`/users/${encodeURIComponent(login)}`);
  return res.ok;
}

/** Déverrouille avec le mot de passe maître — {ok:false, error} si
 * incorrect ou si le compte n'existe pas (jamais une exception non
 * gérée remontée à l'appelant), {ok:true, privateKey} sinon. */
export async function unlockWithPassword(login, password) {
  const res = await getJson(`/users/${encodeURIComponent(login)}`);
  if (!res.ok) {
    return { ok: false, error: res.status === 404 ? "aucun compte coffre pour cet utilisateur" : (res.data.error || "erreur serveur") };
  }
  const user = res.data;
  try {
    const masterKey = await deriveMasterKey(password, user.salt);
    const privateKey = await unwrapPrivateKey(
      { iv: user.wrapped_private_key_iv, ciphertext: user.wrapped_private_key_ciphertext },
      masterKey
    );
    return { ok: true, privateKey };
  } catch {
    // Mauvais mot de passe -- échec attendu d'AES-GCM (étiquette
    // d'authentification), jamais une exception à laisser remonter.
    return { ok: false, error: "mot de passe incorrect" };
  }
}

/** Même chose mais avec la clé de récupération -- cas du mot de passe
 * oublié. */
export async function unlockWithRecoveryKey(login, recoveryKeyBase64) {
  const res = await getJson(`/users/${encodeURIComponent(login)}`);
  if (!res.ok) {
    return { ok: false, error: res.status === 404 ? "aucun compte coffre pour cet utilisateur" : (res.data.error || "erreur serveur") };
  }
  const user = res.data;
  try {
    const recoveryAesKey = await importRecoveryKey(recoveryKeyBase64);
    const privateKey = await unwrapPrivateKey(
      { iv: user.wrapped_private_key_recovery_iv, ciphertext: user.wrapped_private_key_recovery_ciphertext },
      recoveryAesKey
    );
    return { ok: true, privateKey };
  } catch {
    return { ok: false, error: "clé de récupération incorrecte" };
  }
}

/** Change le mot de passe maître — la clé privée RSA elle-même NE
 * CHANGE JAMAIS (voir vault/api/app.py, rotate-password), seule son
 * enveloppe est reconstruite : tous les accès déjà accordés à des
 * collections restent valides sans aucune action supplémentaire.
 * Nécessite la clé privée DÉJÀ déverrouillée (mot de passe actuel ou
 * clé de récupération, peu importe lequel a servi à y arriver). */
export async function changePassword(login, newPassword, privateKey) {
  const salt = generateSalt();
  const masterKey = await deriveMasterKey(newPassword, salt);
  const wrapped = await wrapPrivateKey(privateKey, masterKey);
  const res = await postJson(`/users/${encodeURIComponent(login)}/rotate-password`, {
    salt,
    wrapped_private_key_iv: wrapped.iv,
    wrapped_private_key_ciphertext: wrapped.ciphertext,
  });
  return res.ok ? { ok: true } : { ok: false, error: res.data.error || "échec du changement" };
}

/**
 * Déchiffre une clé de récupération archivée — nécessite la clé
 * privée du maître_principal (obtenue via usurpMaitrePrincipal()).
 * Symétrique de archiveRecoveryKeyForMaster (RSA-OAEP direct sur les
 * octets, pas wrapKey), redonne le format base64 attendu par
 * unlockWithRecoveryKey().
 */
export async function decryptArchivedRecoveryKey(wrappedRecoveryKeyBase64, maitrePrincipalPrivateKey) {
  const encryptedBytes = base64ToBytes(wrappedRecoveryKeyBase64);
  const decrypted = await crypto.subtle.decrypt({ name: "RSA-OAEP" }, maitrePrincipalPrivateKey, encryptedBytes);
  return bytesToBase64(new Uint8Array(decrypted));
}

/** Crée une nouvelle collection — s'auto-accorde l'accès dans la
 * MÊME requête (voir vault/api/app.py : atomique, jamais de fenêtre
 * où la collection existerait sans que personne n'y ait accès). */
export async function createCollection(name, ownLogin, ownPublicKeyBase64) {
  const collectionKey = await generateCollectionKey();
  const ownPublicKey = await importPublicKey(ownPublicKeyBase64);
  const selfWrappedKey = await wrapCollectionKeyForUser(collectionKey, ownPublicKey);
  const res = await postJson("/collections", { name, created_by: ownLogin, self_wrapped_key: selfWrappedKey });
  if (!res.ok) return { ok: false, error: res.data.error || "création impossible" };
  const collectionId = res.data.id;

  // Escrow systématique -- CHAQUE collection enveloppe aussi sa clé
  // pour tout compte maître_système (accès permanent, décidé avec la
  // personne), pas seulement les collections publiques. Jamais
  // bloquant : un échec ici ne doit jamais empêcher la création de la
  // collection elle-même, juste laisser le maître_système sans accès
  // à CELLE-là en particulier (rattrapable manuellement ensuite).
  const systemMasters = await fetchUsersByRole("system_master");
  for (const master of systemMasters) {
    if (master.login === ownLogin) continue; // déjà enveloppée ci-dessus, jamais deux fois pour la même personne
    try {
      await grantAccess(collectionId, master.login, collectionKey, ownLogin);
    } catch {
      // volontairement silencieux, voir commentaire ci-dessus
    }
  }

  return { ok: true, id: collectionId, collectionKey };
}

/** Comptes ayant une capacité donnée (voir vault-api, GET /users --
 * paramètre role) -- utilisé pour l'escrow systématique ci-dessus.
 * Jamais les blobs chiffrés de qui que ce soit, uniquement login +
 * clé publique, déjà public par construction. */
export async function fetchUsersByRole(role) {
  const res = await getJson(`/users?role=${encodeURIComponent(role)}`);
  return res.ok ? res.data : [];
}

/** Liste les collections d'une personne (id, nom, wrapped_key) --
 * utilisé pour l'aperçu avant réinitialisation (voir
 * previewResetImpact) et ailleurs où une simple liste suffit, sans
 * déchiffrement. */
export async function fetchCollectionsForUser(login) {
  const res = await getJson(`/collections?user=${encodeURIComponent(login)}`);
  return res.ok ? res.data : [];
}

/**
 * Calcule, pour chaque collection d'une personne à réinitialiser,
 * si VOUS (l'appelant, via vos propres collections déjà chargées)
 * pourrez la lui réattribuer après coup -- pure logique, jamais
 * d'appel réseau ici (les deux listes sont déjà récupérées par
 * l'appelant). Sert d'AVERTISSEMENT avant confirmation : une
 * collection non réassignable par vous deviendra définitivement
 * perdue pour la personne si personne d'autre n'y a accès non plus
 * (propriété du chiffrement de bout en bout, pas un manque de cet
 * outil).
 */
export function previewResetImpact(targetCollections, myCollections) {
  const myIds = new Set(myCollections.map((c) => c.id));
  return (targetCollections || []).map((c) => ({ id: c.id, name: c.name, reassignable: myIds.has(c.id) }));
}

/**
 * Réinitialise un compte -- pour quelqu'un ayant perdu mot de passe
 * ET clé de récupération (voir vault-api, DELETE /users/<login>).
 * Renvoie la liste des collections auxquelles la personne avait
 * accès -- jamais perdues, juste besoin d'être RÉATTRIBUÉES ensuite
 * (voir reassignAccessAfterReset ci-dessous) par quelqu'un qui y a
 * encore accès, une fois que la personne a recréé son compte.
 */
export async function resetAccount(login) {
  const res = await deleteJson(`/users/${encodeURIComponent(login)}`);
  return res.ok
    ? { ok: true, hadAccessTo: res.data.had_access_to }
    : { ok: false, error: res.data.error || "réinitialisation impossible" };
}

/**
 * Réattribue l'accès à un compte NOUVELLEMENT recréé (après
 * resetAccount) -- appelée par quelqu'un qui a DÉJÀ accès aux
 * collections concernées (typiquement le maître_système, ou un autre
 * membre). Réutilise grantAccess() tel quel pour chaque collection --
 * un compte "réinitialisé" redevient un simple nouveau membre, rien
 * de spécial à cette étape. Continue sur les collections suivantes
 * même si l'une d'elles échoue (accès déjà révoqué entre-temps,
 * collection elle-même supprimée...) -- jamais tout ou rien.
 */
export async function reassignAccessAfterReset(collectionIds, newLogin, myLogin, myPrivateKey) {
  let granted = 0, failed = 0;
  const errors = [];
  for (const collectionId of collectionIds) {
    const collectionsRes = await getJson(`/collections?user=${encodeURIComponent(myLogin)}`);
    const collection = collectionsRes.ok ? collectionsRes.data.find((c) => c.id === collectionId) : null;
    if (!collection) {
      failed++;
      errors.push(`${collectionId} : vous n'y avez plus accès`);
      continue;
    }
    let collectionKey;
    try {
      collectionKey = await unlockCollectionKey(collection.wrapped_key, myPrivateKey);
    } catch {
      failed++;
      errors.push(`${collectionId} : déverrouillage impossible`);
      continue;
    }
    const res = await grantAccess(collectionId, newLogin, collectionKey, myLogin);
    if (res.ok) granted++; else { failed++; errors.push(`${collection.name} : ${res.error}`); }
  }
  return { ok: true, granted, failed, errors };
}

/**
 * Rattrapage -- accorde l'accès maître_système aux collections
 * EXISTANTES qui n'en ont pas encore (créées avant qu'un compte
 * is_system_master existe, voir vault/README.md : l'escrow
 * automatique de createCollection ne s'applique qu'aux NOUVELLES
 * collections, jamais rétroactivement). Ne peut être fait QUE par
 * quelqu'un ayant DÉJÀ accès à la collection concernée -- le
 * maître_système, par définition, n'a justement pas encore cet
 * accès pour celles-ci, ne peut donc jamais se l'accorder lui-même.
 *
 * Parcourt TOUTES les collections de `login`, accorde l'accès à
 * TOUT compte is_system_master qui ne l'a pas encore. Jamais
 * bloquant sur une collection en particulier -- un échec isolé
 * (accès déjà en cours d'octroi ailleurs, etc.) n'empêche jamais le
 * reste du rattrapage.
 */
export async function backfillSystemMasterAccess(login, privateKey) {
  const collectionsRes = await getJson(`/collections?user=${encodeURIComponent(login)}`);
  if (!collectionsRes.ok) return { ok: false, error: collectionsRes.data.error || "impossible de lister les collections" };

  const systemMasters = await fetchUsersByRole("system_master");
  if (systemMasters.length === 0) return { ok: true, granted: 0, skipped: 0, failed: 0 };

  let granted = 0, skipped = 0, failed = 0;

  for (const collection of collectionsRes.data) {
    const accessRes = await getJson(`/collections/${collection.id}/access`);
    const existingLogins = new Set(accessRes.ok ? accessRes.data.map((a) => a.login) : []);

    const missingMasters = systemMasters.filter((m) => !existingLogins.has(m.login));
    if (missingMasters.length === 0) {
      skipped++;
      continue;
    }

    let collectionKey;
    try {
      collectionKey = await unlockCollectionKey(collection.wrapped_key, privateKey);
    } catch {
      failed += missingMasters.length; // collection illisible avec CETTE clé -- jamais bloquant pour les autres
      continue;
    }

    for (const master of missingMasters) {
      const res = await grantAccess(collection.id, master.login, collectionKey, login);
      if (res.ok) granted++; else failed++;
    }
  }

  return { ok: true, granted, skipped, failed };
}

/** Accorde l'accès à une collection à quelqu'un d'autre — récupère sa
 * clé PUBLIQUE (jamais rien de secret nécessaire de son côté pour
 * cette étape), enveloppe la clé de collection à son intention. */
export async function grantAccess(collectionId, targetLogin, collectionKey, grantedByLogin) {
  const userRes = await getJson(`/users/${encodeURIComponent(targetLogin)}`);
  if (!userRes.ok) {
    return { ok: false, error: "utilisateur introuvable (n'a peut-être pas encore de compte coffre)" };
  }
  const targetPublicKey = await importPublicKey(userRes.data.public_key);
  const wrappedKey = await wrapCollectionKeyForUser(collectionKey, targetPublicKey);
  const res = await postJson(`/collections/${collectionId}/access`, {
    login: targetLogin,
    wrapped_key: wrappedKey,
    granted_by: grantedByLogin,
  });
  return res.ok ? { ok: true } : { ok: false, error: res.data.error || "échec de l'octroi" };
}

/** Déballe la clé d'une collection listée (voir GET /collections,
 * champ wrapped_key) — à appeler à l'ouverture d'une collection, pas
 * systématiquement pour toutes celles listées. */
export async function unlockCollectionKey(wrappedKeyBase64, privateKey) {
  return unwrapCollectionKeyForUser(wrappedKeyBase64, privateKey);
}

/** Chiffre et envoie un nouveau secret dans une collection déjà
 * déverrouillée (collectionKey en clair, en mémoire uniquement).
 * `localisation` ET `keyword` : EN CLAIR tous les deux (voir schéma
 * vault-api) -- `keyword` d'abord envisagé chiffré, revu après retour
 * explicite : chiffré aurait empêché la navigation par mot-clé à
 * travers TOUTES les collections (voir fetchAllKeywords plus bas),
 * contraire à l'objectif même du champ (retrouver un code en urgence,
 * y compris avant d'avoir accès à la collection concernée). Le
 * libellé et la valeur, eux, restent chiffrés comme toujours. */
export async function createSecret(collectionId, label, value, collectionKey, createdBy, { localisation, keyword, templateId, reason } = {}) {
  const encLabel = await encryptWithCollectionKey(label, collectionKey);
  const encValue = await encryptWithCollectionKey(value, collectionKey);
  const body = {
    encrypted_label_iv: encLabel.iv,
    encrypted_label_ciphertext: encLabel.ciphertext,
    encrypted_value_iv: encValue.iv,
    encrypted_value_ciphertext: encValue.ciphertext,
    created_by: createdBy,
  };
  if (localisation) body.localisation = localisation;
  if (reason) body.reason = reason;
  if (keyword && keyword.trim()) body.keyword = keyword.trim();
  if (templateId) body.template_id = templateId;
  const res = await postJson(`/collections/${collectionId}/secrets`, body);
  return res.ok ? { ok: true, id: res.data.id } : { ok: false, error: res.data.error || "création impossible" };
}

/**
 * Modifie un secret déjà existant -- label/valeur RECHIFFRÉS si
 * fournis (jamais transmis en clair, jamais partiels : soit un champ
 * change en entier, soit il n'est pas touché) ; localisation/keyword
 * transmis EN CLAIR (voir createSecret ci-dessus pour le
 * raisonnement sur keyword). `changedBy` OBLIGATOIRE (journalisé
 * côté serveur, voir secret_history) ; `reason` fortement recommandé
 * mais pas imposé ici (le formulaire côté écran peut choisir de
 * l'exiger).
 */
export async function updateSecretWithHistory(secretId, collectionKey, changedBy, { label, value, keyword, localisation, templateId, reason } = {}) {
  const body = { changed_by: changedBy };
  if (reason) body.reason = reason;
  if (label !== undefined) {
    const enc = await encryptWithCollectionKey(label, collectionKey);
    body.encrypted_label_iv = enc.iv;
    body.encrypted_label_ciphertext = enc.ciphertext;
  }
  if (value !== undefined) {
    const enc = await encryptWithCollectionKey(value, collectionKey);
    body.encrypted_value_iv = enc.iv;
    body.encrypted_value_ciphertext = enc.ciphertext;
  }
  if (keyword !== undefined) body.keyword = keyword;
  if (localisation !== undefined) body.localisation = localisation;
  if (templateId !== undefined) body.template_id = templateId;

  const res = await putJson(`/secrets/${secretId}`, body);
  return res.ok ? { ok: true } : { ok: false, error: res.data.error || "modification impossible" };
}

/** Historique qui/quand/motif d'un secret -- jamais le contenu
 * avant/après (voir vault-api, table secret_history). */
export async function fetchSecretHistory(secretId) {
  const res = await getJson(`/secrets/${secretId}/history`);
  return res.ok ? res.data : [];
}

/** Archive un secret -- remplace la SUPPRESSION véritable (voir
 * vault-api, DELETE /secrets/<id> devenu un archivage). `reason`
 * fortement recommandé mais pas imposé ici (le formulaire côté écran
 * peut choisir de l'exiger, comme pour une modification). */
export async function archiveSecret(secretId, archivedBy, reason) {
  const res = await deleteJson(`/secrets/${secretId}`, { archived_by: archivedBy, reason });
  return res.ok ? { ok: true } : { ok: false, error: res.data.error || "archivage impossible" };
}

/** Annule un archivage -- réservé au PROPRIÉTAIRE (created_by) côté
 * serveur (vérification logique, pas une garantie -- voir
 * vault-api) : renvoie une erreur 403 explicite si quelqu'un d'autre
 * essaie, à afficher tel quel côté interface. */
export async function restoreSecret(secretId, restoredBy, reason) {
  const res = await postJson(`/secrets/${secretId}/restore`, { restored_by: restoredBy, reason });
  return res.ok ? { ok: true } : { ok: false, error: res.data.error || "restauration impossible" };
}

/** Liste les secrets ARCHIVÉS d'une collection -- visible à quiconque
 * a accès (demandé explicitement : "archivage pour TOUS les
 * utilisateurs"), seule la RESTAURATION est réservée au propriétaire. */
export async function fetchArchivedSecrets(collectionId) {
  const res = await getJson(`/collections/${collectionId}/secrets?archived=true`);
  return res.ok ? res.data : [];
}

/** Versions PASSÉES d'un secret, déchiffrées -- pour l'écran de
 * retour en arrière. Contrairement à l'historique (jamais le
 * contenu), chaque version porte un instantané chiffré complet (voir
 * vault-api, table secret_versions) : déchiffré ici avec la clé de
 * collection, comme un secret normal. Une version individuellement
 * corrompue/illisible n'empêche jamais les autres de s'afficher
 * (même philosophie que loadAllDecryptedSecretLabels). */
export async function fetchSecretVersions(secretId, collectionKey) {
  const res = await getJson(`/secrets/${secretId}/versions`);
  if (!res.ok) return [];
  const versions = [];
  for (const v of res.data) {
    try {
      const { label, value } = await decryptSecret(v, collectionKey);
      versions.push({
        id: v.id, label, value, keyword: v.keyword, localisation: v.localisation,
        changedBy: v.changed_by, changedAt: v.changed_at, reason: v.reason,
      });
    } catch {
      versions.push({
        id: v.id, label: "(déchiffrement impossible)", value: "",
        changedBy: v.changed_by, changedAt: v.changed_at, reason: v.reason,
      });
    }
  }
  return versions;
}

/** Retour en arrière -- réservé au PROPRIÉTAIRE côté serveur (même
 * vérification logique que restoreSecret ci-dessus). La restauration
 * elle-même reste annulable (voir vault-api, capture l'état remplacé
 * avant d'appliquer la version choisie). */
export async function restoreSecretVersion(secretId, versionId, restoredBy, reason) {
  const res = await postJson(`/secrets/${secretId}/versions/${versionId}/restore`, { restored_by: restoredBy, reason });
  return res.ok ? { ok: true } : { ok: false, error: res.data.error || "retour en arrière impossible" };
}

/** Journal À TRAVERS TOUT LE COFFRE -- pour le tableau de bord du
 * maître_système (voir vault-api, GET /history). Jamais de libellé
 * ici (secret_id seul, jamais décrypté côté serveur) -- à
 * l'appelant de croiser avec une liste de secrets déjà déchiffrés
 * (voir loadAllDecryptedSecretLabels) pour afficher quelque chose de
 * lisible. */
export async function fetchGlobalHistory() {
  const res = await getJson("/history");
  return res.ok ? res.data : [];
}

/** Ajoute une observation -- CHIFFRÉE avec la clé de la collection du
 * secret concerné, comme le libellé/les champs (voir vault/README.md,
 * "tout est chiffré" -- demande explicite). Jamais de modification/
 * suppression individuelle en V1 (liste d'annotations accumulées, pas
 * un contenu qu'on retouche, voir vault-api). */
export async function addSecretObservation(secretId, text, collectionKey, author) {
  const enc = await encryptWithCollectionKey(text, collectionKey);
  const res = await postJson(`/secrets/${secretId}/observations`, {
    encrypted_text_iv: enc.iv,
    encrypted_text_ciphertext: enc.ciphertext,
    author,
  });
  return res.ok ? { ok: true, id: res.data.id } : { ok: false, error: res.data.error || "ajout impossible" };
}

/** Récupère et déchiffre la liste des observations d'un secret --
 * ordre chronologique croissant (déjà trié côté serveur, voir
 * vault-api). Une observation individuellement corrompue/illisible
 * n'empêche jamais les autres de s'afficher (même philosophie que
 * loadAllDecryptedSecretLabels). */
export async function fetchSecretObservations(secretId, collectionKey) {
  const res = await getJson(`/secrets/${secretId}/observations`);
  if (!res.ok) return [];
  const observations = [];
  for (const o of res.data) {
    try {
      const text = await decryptWithCollectionKey(
        { iv: o.encrypted_text_iv, ciphertext: o.encrypted_text_ciphertext },
        collectionKey
      );
      observations.push({ id: o.id, text, author: o.author, createdAt: o.created_at });
    } catch {
      observations.push({ id: o.id, text: "(déchiffrement impossible)", author: o.author, createdAt: o.created_at });
    }
  }
  return observations;
}

/** Résumé agrégé (nombre + date la plus récente) des observations
 * pour un ENSEMBLE de secrets -- demandé explicitement (page
 * "Observations", tableau trié/filtré sur tous les secrets
 * accessibles). Jamais de déchiffrement ici (juste des métadonnées
 * en clair côté serveur -- nombre, horodatage), bien plus léger
 * qu'un fetchSecretObservations par secret. Échec réseau -- objet
 * vide, jamais une exception qui casserait tout l'écran. */
export async function fetchObservationsSummary(secretIds) {
  if (!secretIds || secretIds.length === 0) return {};
  const res = await postJson("/secrets/observations-summary", { ids: secretIds });
  return res.ok ? res.data : {};
}

/** Navigation par mot-clé, À TRAVERS TOUTES les collections -- peu
 * importe si la personne a accès à chacune (voir vault-api,
 * GET /keywords) : le but est d'aider à retrouver EN URGENCE dans
 * quelle collection chercher, avant même d'avoir la clé pour la
 * déchiffrer. Expose keyword + nom de collection, jamais le libellé
 * exact ni la valeur (toujours hors de portée sans le bon accès). */
export async function fetchAllKeywords() {
  const res = await getJson("/keywords");
  return res.ok ? res.data : [];
}

/** Modèles de fiche -- nom + liste de libellés de champs, jamais
 * chiffrés (pure structure, voir vault-api). GLOBAUX par défaut
 * (visibles de tout le monde) -- depuis backlog coffre-fort #2,
 * peuvent aussi être scopés à une collection précise. Sans
 * `collectionId`, comportement INCHANGÉ (tous les modèles). Avec,
 * ajoute les modèles propres à CETTE collection à la liste des
 * globaux (jamais ceux d'une autre collection, voir vault-api). */
export async function fetchTemplates(collectionId) {
  const res = await getJson(collectionId ? `/templates?collection_id=${encodeURIComponent(collectionId)}` : "/templates");
  return res.ok ? res.data : [];
}

/** `collectionId` optionnel (absent = modèle GLOBAL, comportement
 * historique inchangé) -- scope ce nouveau modèle à une collection
 * précise si fourni. `requiredLabels` optionnel -- INDICATIF
 * seulement (jamais bloquant à l'enregistrement d'un secret, décidé
 * explicitement avec la personne), filtré côté serveur pour rester un
 * sous-ensemble cohérent de fieldLabels. */
export async function createTemplate(name, fieldLabels, createdBy, { collectionId, requiredLabels } = {}) {
  const body = { name, field_labels: fieldLabels, created_by: createdBy };
  if (collectionId) body.collection_id = collectionId;
  if (requiredLabels && requiredLabels.length > 0) body.required_labels = requiredLabels;
  const res = await postJson("/templates", body);
  return res.ok ? { ok: true, id: res.data.id } : { ok: false, error: res.data.error || "création impossible" };
}

export async function deleteTemplate(templateId) {
  const res = await deleteJson(`/templates/${templateId}`);
  return res.ok ? { ok: true } : { ok: false, error: res.data.error || "suppression impossible" };
}

/** Déchiffre un secret déjà récupéré (voir GET .../secrets) avec la
 * clé de sa collection déjà déverrouillée. `keyword` est déjà en
 * clair (voir schéma) -- transmis tel quel, jamais déchiffré ici. */
export async function decryptSecret(secret, collectionKey) {
  const label = await decryptWithCollectionKey(
    { iv: secret.encrypted_label_iv, ciphertext: secret.encrypted_label_ciphertext },
    collectionKey
  );
  const value = await decryptWithCollectionKey(
    { iv: secret.encrypted_value_iv, ciphertext: secret.encrypted_value_ciphertext },
    collectionKey
  );
  return { label, value, keyword: secret.keyword || "" };
}

/** Déchiffre UNIQUEMENT la valeur -- pour l'écran de recherche
 * (voir loadAllDecryptedSecretLabels ci-dessous), où le libellé est
 * déjà déchiffré et connu (secret.label), inutile de le redéchiffrer
 * une deuxième fois via decryptSecret (qui exige aussi les champs
 * encrypted_label_*, absents des objets transformés par cette
 * fonction). */
export async function decryptSecretValueOnly(secret, collectionKey) {
  return decryptWithCollectionKey(
    { iv: secret.encrypted_value_iv, ciphertext: secret.encrypted_value_ciphertext },
    collectionKey
  );
}

/**
 * Charge et déchiffre TOUS les libellés accessibles, À TRAVERS toutes
 * les collections -- nécessaire pour l'écran de recherche par
 * localisation (vault/README.md), pas organisé par collection comme
 * le reste de l'interface. Préserve localisation/access_count/
 * last_accessed_at (déjà en clair, voir schéma vault-api) et une
 * référence à la collection d'origine + sa clé déjà déverrouillée
 * (pour révéler la VALEUR à la demande ensuite, sans redéverrouiller).
 *
 * Une collection dont la clé échoue à se déverrouiller, ou un secret
 * individuel corrompu, sont IGNORÉS plutôt que de faire échouer tout
 * le chargement -- `failedCollections` reste honnête sur ce qui
 * manque plutôt que de le cacher silencieusement.
 */
export async function loadAllDecryptedSecretLabels(login, privateKey) {
  const collectionsRes = await getJson(`/collections?user=${encodeURIComponent(login)}`);
  if (!collectionsRes.ok) {
    return { ok: false, error: collectionsRes.data.error || "impossible de charger les collections" };
  }

  const secrets = [];
  const failedCollections = [];

  for (const collection of collectionsRes.data) {
    let collectionKey;
    try {
      collectionKey = await unlockCollectionKey(collection.wrapped_key, privateKey);
    } catch {
      failedCollections.push(collection.name);
      continue;
    }
    const secretsRes = await getJson(`/collections/${collection.id}/secrets`);
    if (!secretsRes.ok) {
      failedCollections.push(collection.name);
      continue;
    }
    for (const secret of secretsRes.data) {
      try {
        const { label } = await decryptSecret(secret, collectionKey);
        secrets.push({
          id: secret.id,
          label,
          // Champs chiffrés bruts CONSERVÉS -- bug réel corrigé ici :
          // sans eux, révéler la VALEUR plus tard (voir
          // revealSecretValue dans VaultSearchScreen.jsx) échouait
          // systématiquement avec "Déchiffrement impossible", faute
          // de matière première à déchiffrer. Le libellé, lui, est
          // déjà déchiffré ci-dessus (nécessaire pour la liste/tri/
          // recherche sans re-déchiffrer à chaque rendu).
          encrypted_value_iv: secret.encrypted_value_iv,
          encrypted_value_ciphertext: secret.encrypted_value_ciphertext,
          localisation: secret.localisation,
          templateId: secret.template_id,
          access_count: secret.access_count,
          last_accessed_at: secret.last_accessed_at,
          collectionId: collection.id,
          collectionName: collection.name,
          collectionKey,
        });
      } catch {
        // Un secret individuel corrompu ne doit jamais faire échouer
        // tout le reste -- simplement absent du résultat.
      }
    }
  }

  return { ok: true, secrets, failedCollections };
}

/** Signale qu'un secret a été RÉVÉLÉ (valeur consultée, pas juste son
 * libellé listé) -- voir vault/api/app.py, POST .../record-access.
 * Jamais bloquant : un échec ici (réseau, etc.) ne doit jamais
 * empêcher la personne de voir le code qu'elle vient de déchiffrer,
 * juste le compteur d'usage qui restera légèrement en retard. */
export async function recordSecretAccess(secretId) {
  try {
    await postJson(`/secrets/${secretId}/record-access`, {});
  } catch {
    // volontairement silencieux, voir commentaire ci-dessus
  }
}
