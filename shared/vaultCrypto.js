/**
 * Cœur cryptographique du coffre-fort de codes/secrets — chiffrement
 * DE BOUT EN BOUT : le serveur ne voit et ne stocke jamais rien en
 * clair, aucune clé capable de déchiffrer quoi que ce soit ne lui est
 * jamais transmise. Décision prise avec la personne après avoir
 * explicitement pesé la complexité contre la sensibilité du sujet
 * (codes d'accès physiques, futur coffre de mots de passe).
 *
 * RÈGLE ABSOLUE : aucun algorithme fait maison. Uniquement l'API Web
 * Crypto standard (`crypto.subtle`), la même que celle des vrais
 * gestionnaires de secrets audités (Bitwarden et consorts) —
 * implémentée nativement par le navigateur ET par Node.js (≥ 19,
 * `globalThis.crypto`), ce qui permet de tester ce fichier avec
 * exactement le même code que celui qui tournera réellement en
 * production, sans mock ni simulation. Copié (comme shared/theme.css)
 * dans le front du coffre au moment du build.
 *
 * SCHÉMA DE CHIFFREMENT HYBRIDE — le problème que ça résout : plusieurs
 * personnes, chacune avec son propre mot de passe maître JAMAIS transmis
 * au serveur, doivent pouvoir accéder à des SOUS-ENSEMBLES différents de
 * secrets (accès fin par site/équipement/groupe, décidé avec la
 * personne) sans que le serveur détienne jamais de quoi déchiffrer quoi
 * que ce soit.
 *
 *   1. Chaque UTILISATEUR a sa propre paire de clés RSA-OAEP.
 *      - La clé PRIVÉE est chiffrée avec une clé dérivée de SON mot de
 *        passe maître (PBKDF2) avant d'être envoyée au serveur pour
 *        stockage -- le serveur ne peut jamais la déchiffrer.
 *      - La clé PUBLIQUE est stockée en clair (c'est son rôle).
 *   2. Chaque COLLECTION (site, équipement, groupe...) a sa propre clé
 *      symétrique AES-256, générée aléatoirement.
 *   3. Donner accès à un utilisateur = chiffrer ("envelopper") la clé
 *      de la collection avec SA clé publique RSA -- une petite entrée
 *      par (collection, utilisateur), jamais besoin de rechiffrer les
 *      secrets eux-mêmes pour accorder un accès.
 *   4. Chaque SECRET est chiffré avec la clé AES de sa collection.
 *
 * Le mot de passe maître ne quitte JAMAIS cette machine, encore moins
 * le navigateur -- il ne sert qu'à dériver localement la clé qui
 * déchiffre la clé privée RSA de la personne.
 *
 * DÉTECTION DE MOT DE PASSE INCORRECT "GRATUITE" : AES-GCM inclut une
 * étiquette d'authentification -- déchiffrer avec la mauvaise clé
 * (donc le mauvais mot de passe) fait ÉCHOUER crypto.subtle.decrypt()
 * avec une exception, jamais un déchiffrement silencieux vers des
 * données corrompues. Aucune vérification de mot de passe séparée à
 * implémenter (et surtout PAS à ajouter : un second chemin de
 * vérification, plus faible, serait une régression de sécurité).
 *
 * RÉCUPÉRATION EN CAS DE MOT DE PASSE OUBLIÉ : une clé de récupération
 * (voir plus bas, generateRecoveryKey) enveloppe une DEUXIÈME copie
 * indépendante de la clé privée -- affichée une seule fois à la
 * création du compte, à conserver en lieu sûr par la personne (jamais
 * stockée nulle part sous une forme exploitable). Sans mot de passe
 * NI clé de récupération, le coffre est définitivement irrécupérable,
 * par personne -- propriété voulue du chiffrement de bout en bout,
 * pas un défaut.
 */

// --- Utilitaires d'encodage --------------------------------------
// btoa/atob et TextEncoder/TextDecoder sont des API de plateforme
// standard, disponibles nativement en navigateur ET en Node ≥ 16 --
// aucune dépendance externe, aucune branche selon l'environnement.

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

// --- Sel et dérivation de clé maître -------------------------------

/** Sel aléatoire, unique par utilisateur -- PAS secret (stocké en
 * clair aux côtés du compte), sert uniquement à empêcher des tables
 * arc-en-ciel précalculées entre plusieurs comptes. */
export function generateSalt() {
  return bytesToBase64(crypto.getRandomValues(new Uint8Array(16)));
}

// 600 000 itérations : recommandation OWASP actuelle pour PBKDF2-SHA256
// (pas un nombre arbitraire) -- ralentit délibérément une attaque par
// force brute hors ligne sur un mot de passe maître volé, au prix d'un
// délai d'environ une seconde au déverrouillage, jugé acceptable ici.
const PBKDF2_ITERATIONS = 600000;

/** Dérive une clé AES-256 à partir du mot de passe maître -- ne quitte
 * jamais la mémoire de cette session sous forme exportée (extractable:
 * false), sert uniquement à déchiffrer/chiffrer la clé privée RSA de
 * la personne. */
export async function deriveMasterKey(password, saltBase64, iterations = PBKDF2_ITERATIONS) {
  const salt = base64ToBytes(saltBase64);
  const passwordKey = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(password),
    "PBKDF2",
    false,
    ["deriveKey"]
  );
  return crypto.subtle.deriveKey(
    { name: "PBKDF2", salt, iterations, hash: "SHA-256" },
    passwordKey,
    { name: "AES-GCM", length: 256 },
    false,
    ["encrypt", "decrypt"]
  );
}

// --- Paire de clés utilisateur (RSA-OAEP) --------------------------

/** Nouvelle paire de clés RSA-OAEP pour un utilisateur -- générée une
 * seule fois, à la création du compte. */
export async function generateUserKeyPair() {
  return crypto.subtle.generateKey(
    { name: "RSA-OAEP", modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: "SHA-256" },
    true,
    ["wrapKey", "unwrapKey"]
  );
}

/** Exporte la clé publique en base64 (format SPKI) -- destinée à être
 * envoyée au serveur EN CLAIR, c'est son rôle d'être publique. */
export async function exportPublicKey(publicKey) {
  const raw = await crypto.subtle.exportKey("spki", publicKey);
  return bytesToBase64(new Uint8Array(raw));
}

export async function importPublicKey(base64) {
  const bytes = base64ToBytes(base64);
  // ["wrapKey", "encrypt"] -- deux usages Web Crypto DISTINCTS pour une
  // opération cryptographiquement similaire (l'API les sépare
  // explicitement, une clé autorisée pour l'un ne peut pas servir pour
  // l'autre sans y être aussi autorisée). Élargi pour couvrir les deux :
  // wrapKey (partage d'une clé de collection, usage d'origine) ET
  // encrypt (chiffrement direct de petites données, ex. archivage
  // d'une clé de récupération pour maître_clefs). Aucune perte de
  // sécurité : cette clé est PUBLIQUE par définition, l'élargissement
  // de ses usages autorisés n'expose rien de nouveau.
  return crypto.subtle.importKey("spki", bytes, { name: "RSA-OAEP", hash: "SHA-256" }, true, ["wrapKey", "encrypt"]);
}

/**
 * Chiffre la clé PRIVÉE RSA avec une clé d'enveloppement AES-GCM
 * QUELCONQUE avant envoi au serveur -- générique volontairement : sert
 * aussi bien pour la clé dérivée du mot de passe maître (usage
 * courant) que pour la clé de récupération (voir plus bas) -- deux
 * enveloppes indépendantes de la MÊME clé privée, stockées côte à
 * côte côté serveur, chacune utilisable seule pour la déverrouiller.
 * Le serveur ne peut déchiffrer NI L'UNE NI L'AUTRE sans le mot de
 * passe ou la clé de récupération correspondante.
 */
export async function wrapPrivateKey(privateKey, wrappingKey) {
  const exported = await crypto.subtle.exportKey("pkcs8", privateKey);
  const iv = crypto.getRandomValues(new Uint8Array(12)); // taille standard recommandée pour AES-GCM
  const ciphertext = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, wrappingKey, exported);
  return { iv: bytesToBase64(iv), ciphertext: bytesToBase64(new Uint8Array(ciphertext)) };
}

/**
 * Déchiffre la clé privée RSA avec une clé d'enveloppement AES-GCM
 * (mot de passe maître OU clé de récupération, indifféremment) --
 * ÉCHOUE (lève une exception) si la clé fournie ne correspond pas,
 * grâce à l'étiquette d'authentification d'AES-GCM. C'est la seule et
 * unique vérification de mot de passe/clé de récupération de tout le
 * système -- volontairement, voir la note en tête de fichier.
 */
export async function unwrapPrivateKey(wrappedBlob, wrappingKey) {
  const iv = base64ToBytes(wrappedBlob.iv);
  const ciphertext = base64ToBytes(wrappedBlob.ciphertext);
  const decrypted = await crypto.subtle.decrypt({ name: "AES-GCM", iv }, wrappingKey, ciphertext);
  return crypto.subtle.importKey(
    "pkcs8",
    decrypted,
    { name: "RSA-OAEP", hash: "SHA-256" },
    true,
    ["unwrapKey"]
  );
}

// --- Clé de récupération --------------------------------------------
//
// Contrepartie assumée du chiffrement de bout en bout : sans copie de
// secours, un mot de passe maître oublié rend le coffre DÉFINITIVEMENT
// irrécupérable, par personne, pas même par un administrateur -- c'est
// une propriété voulue du chiffrement de bout en bout, pas un défaut.
// La clé de récupération est une DEUXIÈME façon de déverrouiller la
// même clé privée, à côté du mot de passe -- affichée UNE SEULE FOIS
// à la création du compte, à imprimer/conserver en lieu sûr par la
// personne. Jamais stockée nulle part sous une forme exploitable.

/** 256 bits d'entropie aléatoire, formatés en base64 pour
 * impression/recopie manuelle. */
export function generateRecoveryKey() {
  const bytes = crypto.getRandomValues(new Uint8Array(32));
  return bytesToBase64(bytes);
}

/** Reconstruit la clé AES-256 utilisable à partir de la chaîne de
 * récupération -- déjà suffisamment aléatoire (générée par
 * generateRecoveryKey, jamais un mot de passe humain) pour être
 * utilisée directement comme clé, sans passer par PBKDF2 (qui n'a de
 * sens que pour étirer un secret à faible entropie comme un mot de
 * passe mémorisé). */
export async function importRecoveryKey(recoveryKeyBase64) {
  const bytes = base64ToBytes(recoveryKeyBase64);
  return crypto.subtle.importKey("raw", bytes, { name: "AES-GCM" }, false, ["encrypt", "decrypt"]);
}

// --- Clé de collection (site / équipement / groupe) ----------------

/** Nouvelle clé symétrique AES-256 pour une collection -- générée une
 * seule fois à la création de la collection. */
export async function generateCollectionKey() {
  return crypto.subtle.generateKey({ name: "AES-GCM", length: 256 }, true, ["encrypt", "decrypt"]);
}

/** "Enveloppe" la clé de collection avec la clé publique RSA d'un
 * utilisateur -- c'est CETTE opération, répétée une fois par
 * utilisateur autorisé, qui matérialise l'accès fin : accorder l'accès
 * à quelqu'un de plus ne nécessite qu'une nouvelle enveloppe, jamais
 * de rechiffrer les secrets eux-mêmes. */
export async function wrapCollectionKeyForUser(collectionKey, userPublicKey) {
  const wrapped = await crypto.subtle.wrapKey("raw", collectionKey, userPublicKey, { name: "RSA-OAEP" });
  return bytesToBase64(new Uint8Array(wrapped));
}

/** Déballe la clé de collection avec la clé privée RSA de
 * l'utilisateur (déjà déchiffrée via son mot de passe maître) --
 * ÉCHOUE si cette personne n'a jamais reçu d'enveloppe pour cette
 * collection (rien à déballer) ou si la clé privée fournie ne
 * correspond pas à celle utilisée pour l'enveloppement. */
export async function unwrapCollectionKeyForUser(wrappedBase64, userPrivateKey) {
  const wrapped = base64ToBytes(wrappedBase64);
  return crypto.subtle.unwrapKey(
    "raw",
    wrapped,
    userPrivateKey,
    { name: "RSA-OAEP" },
    { name: "AES-GCM", length: 256 },
    true,
    ["encrypt", "decrypt"]
  );
}

// --- Secrets individuels --------------------------------------------

/** Chiffre une valeur (code, mot de passe...) avec la clé de sa
 * collection. `plaintext` : chaîne quelconque -- le secret lui-même,
 * mais aussi potentiellement son libellé si on choisit de le chiffrer
 * aussi (décision prise : oui, voir README du coffre — même un
 * libellé de secret peut être sensible, ex. l'emplacement d'une porte
 * sécurisée). */
export async function encryptWithCollectionKey(plaintext, collectionKey) {
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const encoded = new TextEncoder().encode(plaintext);
  const ciphertext = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, collectionKey, encoded);
  return { iv: bytesToBase64(iv), ciphertext: bytesToBase64(new Uint8Array(ciphertext)) };
}

/** Déchiffre une valeur avec la clé de collection -- ÉCHOUE si la clé
 * ne correspond pas (mauvaise collection) ou si le contenu a été
 * altéré (étiquette d'authentification AES-GCM), jamais un
 * déchiffrement silencieux corrompu. */
export async function decryptWithCollectionKey(blob, collectionKey) {
  const iv = base64ToBytes(blob.iv);
  const ciphertext = base64ToBytes(blob.ciphertext);
  const decrypted = await crypto.subtle.decrypt({ name: "AES-GCM", iv }, collectionKey, ciphertext);
  return new TextDecoder().decode(decrypted);
}
