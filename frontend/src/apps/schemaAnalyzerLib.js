// Outil "Analyse schéma SQL" — parseur + moteur d'inférence de
// relations, entièrement pur (aucune dépendance réseau/DOM), pensé
// pour du texte de dump mysqldump réaliste (celui de tous les modules
// bases de ce projet : IPAM, Optick, TTS-GU, Zenoss, Cacti, OwnCloud)
// plutôt qu'un parseur SQL généraliste.
//
// Deux couches de relations, jamais mélangées dans le résultat :
//   - EXPLICITES : vraies contraintes FOREIGN KEY déclarées dans le
//     dump (rares dans ce projet — la plupart des tables MyISAM ne
//     les supportent pas, mais IPAM et OwnCloud, en InnoDB, en ont).
//   - DEVINÉES : inférées depuis le nom des colonnes, jamais depuis
//     leur contenu — <table>_id, <table>Id, id_<table> (les trois
//     conventions vraiment rencontrées dans les dumps de ce projet :
//     phpipam en camelCase, optick/tts-gu en préfixe id_).

// ------------------------------------------------------------------
// 1. Découpage du dump en blocs CREATE TABLE
// ------------------------------------------------------------------

/**
 * Repère chaque `CREATE TABLE \`nom\` ( ... ) options;` et renvoie le
 * nom de table + le corps brut (tout ce qui est entre les parenthèses
 * EXTÉRIEURES) + les options de fin (ENGINE=...). Suit la profondeur
 * de parenthèses pour trouver la fermeture correcte — un type comme
 * `decimal(10,2)` ne doit jamais être confondu avec la fin de la
 * définition de table.
 */
export function splitCreateTableBlocks(sql) {
  const blocks = [];
  const re = /CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?`([^`]+)`\s*\(/gi;
  let m;
  while ((m = re.exec(sql)) !== null) {
    const tableName = m[1];
    const bodyStart = re.lastIndex; // juste après la parenthèse ouvrante
    let depth = 1;
    let i = bodyStart;
    while (i < sql.length && depth > 0) {
      const ch = sql[i];
      if (ch === "(") depth++;
      else if (ch === ")") depth--;
      i++;
    }
    if (depth !== 0) continue; // dump tronqué/malformé pour cette table — ignorée proprement
    const body = sql.slice(bodyStart, i - 1);
    const afterParen = sql.slice(i, sql.indexOf(";", i) === -1 ? sql.length : sql.indexOf(";", i));
    blocks.push({ tableName, body, tableOptions: afterParen.trim() });
    re.lastIndex = i;
  }
  return blocks;
}

/**
 * Découpe le corps d'une table en "champs" top-level — sur les
 * virgules, mais UNIQUEMENT celles à la profondeur 0 (jamais celles
 * imbriquées dans un type comme `decimal(10,2)` ou une liste de
 * colonnes `(\`a\`, \`b\`)`).
 */
export function splitTopLevelFields(body) {
  const fields = [];
  let depth = 0;
  let current = "";
  for (const ch of body) {
    if (ch === "(") depth++;
    if (ch === ")") depth--;
    if (ch === "," && depth === 0) {
      fields.push(current.trim());
      current = "";
    } else {
      current += ch;
    }
  }
  if (current.trim()) fields.push(current.trim());
  return fields.filter(Boolean);
}

// ------------------------------------------------------------------
// 2. Classification d'un champ top-level
// ------------------------------------------------------------------

function parseQuotedList(str) {
  // "`a`, `b`" -> ["a", "b"]
  return [...str.matchAll(/`([^`]+)`/g)].map((m) => m[1]);
}

/**
 * Classifie et parse un champ top-level en colonne, clé primaire,
 * index ou contrainte de clé étrangère. Renvoie `null` pour un champ
 * non reconnu plutôt que de planter — un dump réel contient des
 * variantes qu'on n'a pas forcément anticipées, mieux vaut ignorer
 * proprement une ligne isolée que de faire échouer toute la table.
 */
export function parseField(field) {
  const trimmed = field.trim();

  if (/^PRIMARY\s+KEY/i.test(trimmed)) {
    const cols = parseQuotedList(trimmed);
    return { kind: "primaryKey", columns: cols };
  }

  if (/^CONSTRAINT\s+`[^`]+`\s+FOREIGN\s+KEY/i.test(trimmed)) {
    const m = trimmed.match(
      /FOREIGN\s+KEY\s*\(`([^`]+)`\)\s*REFERENCES\s*`([^`]+)`\s*\(`([^`]+)`\)/i
    );
    if (!m) return null;
    return { kind: "foreignKey", column: m[1], refTable: m[2], refColumn: m[3] };
  }

  if (/^(UNIQUE\s+)?KEY\s+`[^`]+`\s*\(/i.test(trimmed)) {
    const cols = parseQuotedList(trimmed.replace(/^(UNIQUE\s+)?KEY\s+`[^`]+`/i, ""));
    return { kind: "index", columns: cols, unique: /^UNIQUE/i.test(trimmed) };
  }

  // Définition de colonne : `nom` type ...
  const colMatch = trimmed.match(/^`([^`]+)`\s+([a-zA-Z][\w]*(?:\([^)]*\))?)/);
  if (colMatch) {
    const name = colMatch[1];
    const type = colMatch[2];
    const nullable = !/NOT\s+NULL/i.test(trimmed);
    const autoIncrement = /AUTO_INCREMENT/i.test(trimmed);
    return { kind: "column", name, type, nullable, autoIncrement };
  }

  return null; // champ non reconnu (KEY sans nom, syntaxe inattendue...) — ignoré proprement
}

// ------------------------------------------------------------------
// 3. Assemblage : dump complet -> schéma structuré
// ------------------------------------------------------------------

/**
 * Parse un dump mysqldump complet en un objet { tables } exploitable.
 * Chaque table : { name, columns, primaryKey, foreignKeys }.
 * columns[].isPrimaryKey est calculé après coup (une colonne peut être
 * listée dans PRIMARY KEY sans porter elle-même AUTO_INCREMENT, cas
 * des clés composites).
 */
export function parseSchema(sql) {
  const blocks = splitCreateTableBlocks(sql);
  const tables = blocks.map(({ tableName, body }) => {
    const fields = splitTopLevelFields(body).map(parseField).filter(Boolean);

    const columns = fields.filter((f) => f.kind === "column");
    const primaryKeyField = fields.find((f) => f.kind === "primaryKey");
    const primaryKey = primaryKeyField ? primaryKeyField.columns : [];
    const foreignKeys = fields
      .filter((f) => f.kind === "foreignKey")
      .map((f) => ({ column: f.column, refTable: f.refTable, refColumn: f.refColumn }));

    const pkSet = new Set(primaryKey);
    return {
      name: tableName,
      columns: columns.map((c) => ({
        name: c.name,
        type: c.type,
        nullable: c.nullable,
        autoIncrement: c.autoIncrement,
        isPrimaryKey: pkSet.has(c.name),
      })),
      primaryKey,
      foreignKeys,
    };
  });

  return { tables };
}

// ------------------------------------------------------------------
// 4. Inférence des relations devinées (noms de colonnes)
// ------------------------------------------------------------------

/** table -> singulier naïf (categories -> category, subnets -> subnet,
 * status -> status inchangé si déjà singulier au sens naïf). Volontai-
 * rement simple (une règle -ies/-y, une règle -s) : suffisant pour les
 * schémas anglais rencontrés ici, jamais présenté comme infaillible. */
/** Mots anglais courants se terminant par un "s" qui n'est PAS un
 * pluriel — sans cette liste, la règle générale tronquerait à tort
 * "status" (une vraie table de Zenoss) en "statu". Liste courte et
 * assumée non exhaustive : un dictionnaire de pluriels irréguliers
 * complet dépasserait largement l'objectif d'un outil qui "devine". */
const SINGULAR_S_EXCEPTIONS = new Set([
  "status", "bus", "gas", "series", "species", "campus", "virus", "corpus", "atlas", "canvas",
]);

export function naiveSingularize(name) {
  const lower = name.toLowerCase();
  if (SINGULAR_S_EXCEPTIONS.has(lower)) return lower;
  if (lower.endsWith("ies") && lower.length > 4) return lower.slice(0, -3) + "y";
  if (lower.endsWith("ses") && lower.length > 4) return lower.slice(0, -2);
  if (lower.endsWith("s") && !lower.endsWith("ss") && lower.length > 2) return lower.slice(0, -1);
  return lower;
}

/** Découpe une colonne camelCase/snake_case en "mots" minuscules —
 * "masterSubnetId" -> ["master","subnet","id"], "id_category" ->
 * ["id","category"], "parent_ticket_id" -> ["parent","ticket","id"]. */
function splitWords(name) {
  return name
    .replace(/([a-z0-9])([A-Z])/g, "$1_$2")
    .split(/[_\s]+/)
    .filter(Boolean)
    .map((w) => w.toLowerCase());
}

/**
 * Détecte le préfixe commun aux noms de table de CE dump précis (ex.
 * "tts_" pour optick/tts-gu, "oc_" pour OwnCloud) — un préfixe
 * partagé par au moins la moitié des tables, jamais deviné à
 * l'aveugle sur un seul nom. Retourne "" si aucun préfixe net ne se
 * dégage (rien à retirer, ce n'est pas un défaut).
 */
export function detectCommonPrefix(tableNames) {
  if (tableNames.length < 2) return "";
  const candidates = {};
  for (const name of tableNames) {
    const m = name.match(/^([a-zA-Z]+_)/);
    if (m) candidates[m[1]] = (candidates[m[1]] || 0) + 1;
  }
  let best = "";
  let bestCount = 0;
  for (const [prefix, count] of Object.entries(candidates)) {
    if (count > bestCount) {
      best = prefix;
      bestCount = count;
    }
  }
  return bestCount >= tableNames.length / 2 ? best : "";
}

/**
 * Construit, pour chaque table, l'ensemble des "clés de
 * correspondance" utilisées pour reconnaître une colonne qui la
 * désigne : le nom tel quel, son singulier naïf, et la même chose
 * sans le préfixe commun du dump si un préfixe a été détecté.
 */
export function buildTableMatchIndex(tableNames) {
  const prefix = detectCommonPrefix(tableNames);
  const index = new Map(); // matchKey -> Set(tableName)
  const add = (key, tableName) => {
    if (!key) return;
    if (!index.has(key)) index.set(key, new Set());
    index.get(key).add(tableName);
  };
  for (const name of tableNames) {
    const lower = name.toLowerCase();
    const stripped = prefix && lower.startsWith(prefix) ? lower.slice(prefix.length) : lower;
    for (const key of new Set([lower, naiveSingularize(lower), stripped, naiveSingularize(stripped)])) {
      add(key, name);
    }
  }
  return index;
}

/**
 * Tente d'extraire, pour une colonne donnée, les "mots" du nom de
 * table visé selon les 3 conventions rencontrées dans ce projet :
 * suffixe snake_case (`subnet_id`), suffixe camelCase (`subnetId`),
 * préfixe snake_case (`id_category`). Renvoie un TABLEAU de mots (pas
 * une chaîne collée) : "masterSubnetId" -> ["master","subnet"] — le
 * dernier mot est le "nom tête" du composé (le plus significatif,
 * convention anglaise modificateur+tête), testé en priorité pour
 * reconnaître une auto-référence qualifiée comme `masterSubnetId` ou
 * `parentCategoryId`. Renvoie null si la colonne ne ressemble à
 * aucune des trois conventions (ex. `editDate`, `description`).
 */
export function extractReferenceStem(columnName) {
  if (/^id$/i.test(columnName)) return null; // la clé primaire elle-même, jamais une référence

  const words = splitWords(columnName);
  if (words.length < 2) return null;

  if (words[words.length - 1] === "id") {
    return words.slice(0, -1);
  }
  if (words[0] === "id") {
    return words.slice(1);
  }
  return null;
}

/**
 * Moteur d'inférence complet : pour chaque colonne de chaque table
 * (hors clé primaire et hors colonnes déjà couvertes par une FK
 * EXPLICITE), tente de deviner une table cible.
 *
 * Confiance :
 *   - "high"   : correspondance exacte (nom de table ou son singulier)
 *   - "medium" : correspondance après retrait du préfixe commun du dump
 *   - "low"    : jamais renvoyée ici (réservé à une évolution future
 *     type correspondance floue/sous-chaîne — volontairement absente
 *     pour l'instant, un faux positif "deviné" avec trop de confiance
 *     est pire qu'une relation manquée).
 *
 * Une colonne pouvant correspondre à PLUSIEURS tables (ambiguïté
 * réelle, ex. deux tables au même nom singulier) renvoie une entrée
 * par table candidate plutôt que d'en choisir une arbitrairement.
 */
export function inferGuessedEdges(schema) {
  const tableNames = schema.tables.map((t) => t.name);
  const matchIndex = buildTableMatchIndex(tableNames);
  const prefix = detectCommonPrefix(tableNames);
  const edges = [];

  for (const table of schema.tables) {
    const explicitColumns = new Set(table.foreignKeys.map((fk) => fk.column));
    for (const col of table.columns) {
      if (col.isPrimaryKey) continue;
      if (explicitColumns.has(col.name)) continue; // déjà une relation EXPLICITE, ne pas la redeviner en double

      const stemWords = extractReferenceStem(col.name);
      if (!stemWords) continue;

      const joinedStem = stemWords.join("");
      const singularJoined = naiveSingularize(joinedStem);
      const lastWord = stemWords[stemWords.length - 1];
      const singularLastWord = naiveSingularize(lastWord);
      const strippedJoined = prefix && joinedStem.startsWith(prefix) ? joinedStem.slice(prefix.length) : joinedStem;

      // Haute confiance : le nom complet du composé (collé) correspond
      // exactement à une table (ou à son singulier) — le cas simple
      // "subnetId", "id_category", sans mot modificateur superflu.
      const highMatches = new Set([
        ...(matchIndex.get(joinedStem) || []),
        ...(matchIndex.get(singularJoined) || []),
      ]);
      if (highMatches.size > 0) {
        for (const target of highMatches) {
          edges.push({
            fromTable: table.name, fromColumn: col.name, toTable: target,
            confidence: "high", selfReference: target === table.name,
          });
        }
        continue;
      }

      // Confiance moyenne : soit après retrait du préfixe commun du
      // dump, soit via le dernier mot du composé (le "nom tête" —
      // convention anglaise modificateur+tête, ex. "master" + "Subnet"
      // dans masterSubnetId) — attrape les auto-références qualifiées
      // que la correspondance exacte du bloc entier collé rate
      // toujours ("mastersubnet" ne matche ni "subnet" ni "subnets").
      const mediumMatches = new Set([
        ...(matchIndex.get(strippedJoined) || []),
        ...(stemWords.length > 1 ? matchIndex.get(lastWord) || [] : []),
        ...(stemWords.length > 1 ? matchIndex.get(singularLastWord) || [] : []),
      ]);
      for (const target of mediumMatches) {
        edges.push({
          fromTable: table.name, fromColumn: col.name, toTable: target,
          confidence: "medium", selfReference: target === table.name,
        });
      }
    }
  }
  return edges;
}

/** Relations explicites, mises à plat depuis schema.tables[].foreignKeys
 * (une seule fonction pour homogénéiser la forme avec inferGuessedEdges,
 * plutôt que deux formes différentes selon la source). */
export function explicitEdges(schema) {
  const edges = [];
  for (const table of schema.tables) {
    for (const fk of table.foreignKeys) {
      edges.push({
        fromTable: table.name, fromColumn: fk.column, toTable: fk.refTable,
        toColumn: fk.refColumn, selfReference: fk.refTable === table.name,
      });
    }
  }
  return edges;
}

/** Point d'entrée unique : dump texte -> schéma + les deux couches de
 * relations, jamais mélangées. */
export function analyzeSchema(sql) {
  const schema = parseSchema(sql);
  return {
    schema,
    explicitEdges: explicitEdges(schema),
    guessedEdges: inferGuessedEdges(schema),
  };
}
