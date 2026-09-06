/**
 * Arbre JSON générique avec sélection en cascade.
 *
 * Modèle de sélection volontairement simple pour ce squelette (v1) :
 * `deselectedPaths` contient les chemins explicitement décochés. Un nœud
 * est considéré sélectionné si aucun chemin de `deselectedPaths` n'est un
 * préfixe du sien (donc décocher un parent "ferme le portail" pour tout
 * son sous-arbre). Pour recocher un enfant individuellement, il faut
 * d'abord recocher son parent — les cases des descendants d'un nœud
 * décoché sont donc désactivées (pas cliquables) plutôt que de permettre
 * une réactivation locale, pour éviter un état ambigu.
 */

function isPrefixOf(candidatePrefix, path) {
  if (candidatePrefix === path) return true;
  return path.startsWith(`${candidatePrefix}.`) || path.startsWith(`${candidatePrefix}[`);
}

export function isPathSelected(path, deselectedPaths) {
  for (const off of deselectedPaths) {
    if (isPrefixOf(off, path)) return false;
  }
  return true;
}

/**
 * Navigue dans la donnée brute pour retrouver la valeur à un chemin
 * donné (même convention que les chemins construits par l'arbre :
 * "$.features[0].properties.type").
 */
export function getValueAtPath(rootData, path) {
  if (path === "$") return rootData;
  const tokens = path.slice(1).match(/\.[^.[\]]+|\[\d+\]/g) || [];
  let current = rootData;
  for (const token of tokens) {
    if (current == null) return undefined;
    current = token.startsWith(".") ? current[token.slice(1)] : current[parseInt(token.slice(1, -1), 10)];
  }
  return current;
}

/**
 * Parcourt `value` (situé à `currentPath`) en direction de `targetPath`,
 * et ajoute à `deselectedSet` chaque branche croisée en chemin qui ne
 * mène PAS vers la cible — sans toucher à la cible elle-même ni à ses
 * propres descendants. C'est ce qui permet de réintégrer un nœud précis
 * sous un ancêtre éteint sans rallumer tout le reste de la branche.
 */
function pruneSiblingsTowardTarget(value, currentPath, targetPath, deselectedSet) {
  if (currentPath === targetPath) return;
  if (value === null || typeof value !== "object") return;

  const entries = Array.isArray(value)
    ? value.map((v, i) => [`${currentPath}[${i}]`, v])
    : Object.entries(value).map(([k, v]) => [`${currentPath}.${k}`, v]);

  for (const [childPath, childValue] of entries) {
    const leadsToTarget = childPath === targetPath || isPrefixOf(childPath, targetPath);
    if (leadsToTarget) {
      pruneSiblingsTowardTarget(childValue, childPath, targetPath, deselectedSet);
    } else {
      deselectedSet.add(childPath);
    }
  }
}

/**
 * Calcule le nouvel ensemble `deselectedPaths` pour réintégrer
 * précisément `targetPath` dans la sélection, même s'il se trouve sous
 * un ancêtre actuellement éteint — en préservant l'état des branches
 * voisines (elles restent éteintes) plutôt que de tout rallumer.
 */
export function computeReinclusion(deselectedPaths, rawRootData, targetPath) {
  const blockingAncestors = [...deselectedPaths].filter(
    (p) => p !== targetPath && isPrefixOf(p, targetPath)
  );

  const next = new Set(deselectedPaths);

  if (blockingAncestors.length === 0) {
    next.delete(targetPath);
    return next;
  }

  const outermost = blockingAncestors.reduce((a, b) => (a.length <= b.length ? a : b));
  next.delete(outermost);

  const valueAtOutermost = getValueAtPath(rawRootData, outermost);
  pruneSiblingsTowardTarget(valueAtOutermost, outermost, targetPath, next);

  return next;
}

/**
 * Sous-ensemble de `deselectedPaths` pertinent pour un aperçu temporaire
 * enraciné à `rootPath` : ignore l'état propre de `rootPath` et de ses
 * ancêtres (pour permettre de "rouvrir" une branche éteinte dans
 * l'aperçu), garde les exclusions propres aux descendants.
 */
export function localDeselectedFor(deselectedPaths, rootPath) {
  const local = new Set();
  for (const p of deselectedPaths) {
    if (p !== rootPath && isPrefixOf(rootPath, p)) {
      local.add(p);
    }
  }
  return local;
}

function hasBlockedAncestor(path, deselectedPaths) {
  for (const off of deselectedPaths) {
    if (off !== path && isPrefixOf(off, path)) return true;
  }
  return false;
}

function labelForKey(key) {
  return key === "$" ? "(racine)" : key;
}

function JsonTreeNode({ label, path, value, deselectedPaths, onToggle, depth }) {
  const selected = isPathSelected(path, deselectedPaths);
  const disabled = hasBlockedAncestor(path, deselectedPaths);
  const isContainer = value !== null && typeof value === "object";

  return (
    <div className="json-tree-node" style={{ marginLeft: depth * 14 }}>
      <label className={`json-tree-row ${disabled ? "disabled" : ""}`}>
        <input
          type="checkbox"
          checked={selected}
          disabled={disabled}
          onChange={() => onToggle(path, selected)}
        />
        <span className="json-tree-label">{labelForKey(label)}</span>
        {!isContainer && <span className="json-tree-value">{String(value)}</span>}
      </label>

      {isContainer && !Array.isArray(value) &&
        Object.entries(value).map(([key, childValue]) => (
          <JsonTreeNode
            key={key}
            label={key}
            path={`${path}.${key}`}
            value={childValue}
            deselectedPaths={deselectedPaths}
            onToggle={onToggle}
            depth={depth + 1}
          />
        ))}

      {isContainer && Array.isArray(value) &&
        value.map((childValue, index) => (
          <JsonTreeNode
            key={index}
            label={`[${index}]`}
            path={`${path}[${index}]`}
            value={childValue}
            deselectedPaths={deselectedPaths}
            onToggle={onToggle}
            depth={depth + 1}
          />
        ))}
    </div>
  );
}

export default function JsonTree({ data, deselectedPaths, onToggle, rootPath = "$", rootLabel = "$" }) {
  return (
    <JsonTreeNode
      label={rootLabel}
      path={rootPath}
      value={data}
      deselectedPaths={deselectedPaths}
      onToggle={onToggle}
      depth={0}
    />
  );
}
