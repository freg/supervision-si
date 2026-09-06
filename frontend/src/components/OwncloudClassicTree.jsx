// Vue arbre "classique" (liste indentée, verticale) -- alternative à
// OwncloudRadialTree pour le MÊME arbre/état de sélection/filtre :
// même interface de props (tree, selectedId, onSelectNode,
// relevantIds), volontairement, pour permuter librement entre les
// deux sans rien changer côté OwncloudApp.jsx. Pas de repli/dépliage
// LOCAL séparé -- montre tout ce qui est chargé, exactement comme le
// radial (cohérence en changeant de vue).

function OwncloudClassicNode({ node, depth, selectedId, onSelectNode, relevantIds }) {
  const isSelected = node.id === selectedId;
  const dimmed = relevantIds ? !relevantIds.has(node.id) : false;
  const isDir = node.raw?.isDir;
  const unloaded = node.hasUnloadedChildren;

  let rowClass = "owncloud-classic-row";
  if (isSelected) rowClass += " owncloud-classic-row-selected";
  if (dimmed) rowClass += " owncloud-radial-dim"; // même classe que le radial, même comportement visuel

  return (
    <>
      <div
        className={rowClass}
        style={{ paddingLeft: `${depth * 18 + 8}px` }}
        onClick={() => onSelectNode(node)}
        title={unloaded ? "Cliquer pour déplier" : undefined}
      >
        <span className="owncloud-classic-icon">{isDir ? (unloaded ? "📁" : "📂") : "📄"}</span>
        <span className="owncloud-classic-name">{node.name || "(racine)"}</span>
        {unloaded && <span className="owncloud-classic-unloaded-marker">•</span>}
      </div>
      {(node.children || []).map((child) => (
        <OwncloudClassicNode
          key={child.id}
          node={child}
          depth={depth + 1}
          selectedId={selectedId}
          onSelectNode={onSelectNode}
          relevantIds={relevantIds}
        />
      ))}
    </>
  );
}

export default function OwncloudClassicTree({ tree, selectedId, onSelectNode, relevantIds = null }) {
  if (!tree) {
    return <p className="owncloud-empty">Sélectionnez une racine à gauche pour afficher son arbre.</p>;
  }

  return (
    <div className="owncloud-classic-wrapper">
      <OwncloudClassicNode
        node={tree}
        depth={0}
        selectedId={selectedId}
        onSelectNode={onSelectNode}
        relevantIds={relevantIds}
      />
    </div>
  );
}
