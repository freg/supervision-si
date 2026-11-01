// Disposition du hub (livraison #516) : l'arborescence menus / tuiles /
// outils / options éditée en glisser-déposer, racine « hub ». Glisser une
// feuille du catalogue (droite) dans l'arbre (gauche) l'y AJOUTE (jamais
// retirée du catalogue : la même feuille peut être placée autant de fois
// qu'on veut) ; glisser un nœud de l'arbre le DÉPLACE (Alt enfoncé :
// le duplique). Un nœud lâché sur le haut d'une ligne se place avant
// elle, sur le corps d'un groupe : dedans, en dernier.
//
// Enregistrement : pour soi (préférences) ou, pour un administrateur,
// pour tout le monde (arbre du site). « Revenir au défaut » retire
// l'arbre personnel. Le JSON est visible et éditable en bas pour ceux qui
// préfèrent le texte (export / import). Logique pure : hubTree.js.
import { useEffect, useMemo, useState } from "react";
import {
  ROOT_ID, cloneNode, countRefs, defaultTree, exportTree, findNode, group, importTree,
  insertNode, moveNode, ref, removeNode, updateNode,
} from "./hubTree.js";

const KIND_LABEL = { view: "Vues", "view-front": "Vues", link: "Fronts externes", action: "Actions du hub", auto: "Automatique" };

export default function HubTreeView({ tree, siteTree, themes, catalog, isAdmin, onSave, onReset, onBack, login }) {
  const [draft, setDraft] = useState(() => tree);
  const [selected, setSelected] = useState(ROOT_ID);
  const [filter, setFilter] = useState("");
  const [json, setJson] = useState("");
  const [showJson, setShowJson] = useState(false);
  const [status, setStatus] = useState("");
  const [dragOver, setDragOver] = useState(null); // { id, where: "before" | "into" }
  const [editing, setEditing] = useState(null); // id du groupe en renommage
  const [dirty, setDirty] = useState(false);

  useEffect(() => { setDraft(tree); setDirty(false); }, [tree]);
  useEffect(() => { if (showJson) setJson(exportTree(draft)); }, [draft, showJson]);

  const change = (t) => { if (t !== draft) { setDraft(t); setDirty(true); } };
  const leaves = useMemo(() => {
    const f = filter.trim().toLowerCase();
    const all = [...catalog.values()];
    return f ? all.filter((l) => l.label.toLowerCase().includes(f) || l.id.includes(f)) : all;
  }, [catalog, filter]);

  // --- glisser-déposer (HTML5 natif, aucune dépendance)
  const payload = (e) => { try { return JSON.parse(e.dataTransfer.getData("text/plain") || "null"); } catch { return null; } };
  const onDragStartNode = (e, id) => { e.dataTransfer.setData("text/plain", JSON.stringify({ kind: "node", id })); e.dataTransfer.effectAllowed = "copyMove"; e.stopPropagation(); };
  const onDragStartLeaf = (e, key) => { e.dataTransfer.setData("text/plain", JSON.stringify({ kind: "leaf", ref: key })); e.dataTransfer.effectAllowed = "copy"; };
  const whereOf = (e, node) => {
    const r = e.currentTarget.getBoundingClientRect();
    const y = (e.clientY - r.top) / Math.max(1, r.height);
    if (node.type === "group") return y < 0.3 ? "before" : "into";
    return y < 0.5 ? "before" : "after";
  };
  const onDragOverNode = (e, node) => { e.preventDefault(); e.stopPropagation(); setDragOver({ id: node.id, where: whereOf(e, node) }); };
  const onDropNode = (e, node) => {
    e.preventDefault(); e.stopPropagation();
    setDragOver(null);
    const p = payload(e);
    if (!p) return;
    const where = whereOf(e, node);
    let parentId, index;
    if (where === "into") { parentId = node.id; index = null; } else {
      const f = findNode(draft, node.id);
      if (!f || !f.parent) return;
      parentId = f.parent.id; index = f.index + (where === "after" ? 1 : 0);
    }
    if (p.kind === "leaf") change(insertNode(draft, parentId, ref(p.ref), index));
    else if (p.kind === "node") {
      if (e.altKey) { const f = findNode(draft, p.id); if (f) change(insertNode(draft, parentId, cloneNode(f.node), index)); }
      else change(moveNode(draft, p.id, parentId, index));
    }
  };

  const addLeaf = (key) => {
    const f = findNode(draft, selected);
    const parentId = f && f.node.type === "group" ? selected : ROOT_ID;
    change(insertNode(draft, parentId, ref(key)));
  };
  const addGroup = (parentId) => {
    const g = group("Nouveau groupe", []);
    change(insertNode(draft, parentId, g));
    setSelected(g.id); setEditing(g.id);
  };
  const duplicate = (id) => { const f = findNode(draft, id); if (f && f.parent) change(insertNode(draft, f.parent.id, cloneNode(f.node), f.index + 1)); };

  const save = async (scope) => {
    setStatus("enregistrement…");
    const r = await onSave(draft, scope);
    setStatus(r?.ok ? (scope === "site" ? "arbre du site enregistré (tout le monde)" : "disposition enregistrée (pour vous)") : `échec : ${r?.error || "?"}`);
    if (r?.ok) setDirty(false);
  };
  const reset = async (scope) => {
    if (!window.confirm(scope === "site" ? "Retirer l'arbre du site ? Les personnes sans disposition personnelle reverront l'accueil par défaut." : "Revenir à la disposition par défaut (ou celle du site) ?")) return;
    setStatus("…");
    const r = await onReset(scope);
    setStatus(r?.ok ? "remis à zéro" : `échec : ${r?.error || "?"}`);
  };
  const applyJson = () => {
    const t = importTree(json);
    if (!t) { setStatus("JSON invalide : rien appliqué"); return; }
    change(t); setStatus("JSON appliqué (non enregistré)");
  };

  const renderNode = (node, depth) => {
    const isRoot = node.id === ROOT_ID;
    const leaf = node.type === "ref" ? catalog.get(node.ref) : null;
    const over = dragOver && dragOver.id === node.id ? dragOver.where : null;
    const cls = ["hub-tree-row", node.type, selected === node.id ? "selected" : "", over ? `drop-${over}` : "", node.type === "ref" && !leaf && node.ref !== "auto:external-links" ? "unavailable" : ""].join(" ");
    return (
      <li key={node.id} className="hub-tree-item">
        <div
          className={cls}
          style={{ paddingLeft: 8 + depth * 18 }}
          draggable={!isRoot}
          onDragStart={(e) => onDragStartNode(e, node.id)}
          onDragOver={(e) => onDragOverNode(e, node)}
          onDragLeave={() => setDragOver((d) => (d && d.id === node.id ? null : d))}
          onDrop={(e) => onDropNode(e, node)}
          onClick={() => setSelected(node.id)}
        >
          <span className="hub-tree-handle" title={isRoot ? "racine" : "glisser pour déplacer (Alt : dupliquer)"}>{isRoot ? "⌂" : "⋮⋮"}</span>
          {node.type === "group" ? (
            editing === node.id ? (
              <input
                autoFocus
                className="hub-tree-edit"
                defaultValue={node.label}
                onBlur={(e) => { change(updateNode(draft, node.id, { label: e.target.value.trim() || node.label })); setEditing(null); }}
                onKeyDown={(e) => { if (e.key === "Enter") e.currentTarget.blur(); if (e.key === "Escape") setEditing(null); }}
              />
            ) : (
              <strong className="hub-tree-label" onDoubleClick={() => !isRoot && setEditing(node.id)}>{node.icon} {node.label} <span className="muted">({(node.children || []).length})</span></strong>
            )
          ) : (
            <span className="hub-tree-label">
              {leaf ? leaf.label : node.ref === "auto:external-links" ? "Liens externes (automatique)" : `${node.ref} (indisponible pour vous — gardé pour les autres)`}
              {leaf && leaf.kind === "link" ? " ↗" : ""}
              <span className="muted"> · {node.ref}</span>
            </span>
          )}
          <span className="hub-tree-actions">
            {node.type === "group" && <button type="button" className="secondary" title="Nouveau sous-groupe" onClick={(e) => { e.stopPropagation(); addGroup(node.id); }}>＋ groupe</button>}
            {node.type === "group" && !isRoot && <button type="button" className="secondary" title="Icône (emoji)" onClick={(e) => { e.stopPropagation(); const v = window.prompt("Icône (un emoji, vide pour aucune)", node.icon || ""); if (v !== null) change(updateNode(draft, node.id, { icon: v.trim() })); }}>icône</button>}
            {node.type === "group" && !isRoot && <button type="button" className="secondary" title="Renommer" onClick={(e) => { e.stopPropagation(); setEditing(node.id); }}>✎</button>}
            {!isRoot && <button type="button" className="secondary" title="Dupliquer (même parent)" onClick={(e) => { e.stopPropagation(); duplicate(node.id); }}>⧉</button>}
            {!isRoot && <button type="button" className="secondary danger" title="Retirer" onClick={(e) => { e.stopPropagation(); change(removeNode(draft, node.id)); if (selected === node.id) setSelected(ROOT_ID); }}>✕</button>}
          </span>
        </div>
        {node.type === "group" && node.children.length > 0 && (
          <ul className="hub-tree-children">{node.children.map((c) => renderNode(c, depth + 1))}</ul>
        )}
      </li>
    );
  };

  const groupsOf = (kind) => leaves.filter((l) => (KIND_LABEL[l.kind] || l.kind) === kind);
  const kinds = [...new Set(leaves.map((l) => KIND_LABEL[l.kind] || l.kind))];

  return (
    <div className="hub-tree-view">
      <div className="hub-theme-bar">
        <button type="button" className="secondary" onClick={onBack}>◀ Retour</button>
        <strong className="hub-theme-title">🧭 Disposition du hub</strong>
        <span className="muted">{dirty ? "modifications non enregistrées" : "à jour"}{status ? ` · ${status}` : ""}</span>
      </div>
      <p className="muted hub-tree-help">
        Glissez une feuille du catalogue dans l'arbre pour l'y ajouter (autant de fois que voulu, dans autant de groupes) ; glissez un nœud de l'arbre pour le déplacer, avec Alt pour le dupliquer.
        Le haut d'une ligne = « avant », le corps d'un groupe = « dedans ». Les groupes sous la racine sont les menus de l'en-tête et les super-tuiles de l'accueil ; les feuilles sous la racine, des boutons et des tuiles seules ; les sous-groupes, des sections de menu.
        Double-clic sur un groupe pour le renommer.
      </p>
      <div className="hub-tree-columns">
        <div className="hub-tree-pane">
          <div className="hub-tree-toolbar">
            <button type="button" onClick={() => save("me")} disabled={!dirty && !!tree}>Enregistrer pour moi</button>
            {isAdmin && <button type="button" onClick={() => save("site")} title="Devient la disposition de toute personne sans disposition personnelle">Enregistrer pour tout le monde</button>}
            <button type="button" className="secondary" onClick={() => { change(defaultTree(themes)); setStatus("disposition par défaut chargée (non enregistrée)"); }}>Charger le défaut</button>
            {siteTree && <button type="button" className="secondary" onClick={() => { change(siteTree); setStatus("arbre du site chargé (non enregistré)"); }}>Charger l'arbre du site</button>}
            <button type="button" className="secondary" onClick={() => reset("me")}>Revenir au défaut (moi)</button>
            {isAdmin && siteTree && <button type="button" className="secondary danger" onClick={() => reset("site")}>Retirer l'arbre du site</button>}
            <button type="button" className="secondary" onClick={() => setShowJson((v) => !v)}>{showJson ? "Masquer le JSON" : "JSON"}</button>
          </div>
          <ul className="hub-tree">{renderNode(draft.root, 0)}</ul>
          {showJson && (
            <div className="hub-tree-json">
              <textarea value={json} onChange={(e) => setJson(e.target.value)} spellCheck={false} rows={18} />
              <div className="hub-tree-toolbar">
                <button type="button" onClick={applyJson}>Appliquer le JSON</button>
                <button type="button" className="secondary" onClick={() => { navigator.clipboard?.writeText(json).then(() => setStatus("JSON copié"), () => setStatus("copie impossible")); }}>Copier</button>
              </div>
            </div>
          )}
        </div>
        <div className="hub-tree-pane hub-tree-catalog">
          <div className="hub-tree-toolbar">
            <strong>Catalogue</strong>
            <input type="search" placeholder="filtrer…" value={filter} onChange={(e) => setFilter(e.target.value)} />
            <span className="muted">{leaves.length} feuille{leaves.length > 1 ? "s" : ""} · ajout dans : {findNode(draft, selected)?.node?.label || "Hub"}</span>
          </div>
          {kinds.map((k) => (
            <div key={k} className="hub-tree-catalog-section">
              <h4>{k}</h4>
              <ul>
                {groupsOf(k).map((l) => {
                  const n = countRefs(draft, l.id);
                  return (
                    <li key={l.id} className="hub-tree-leaf" draggable onDragStart={(e) => onDragStartLeaf(e, l.id)} title={l.description || l.id}>
                      <span className="hub-tree-handle">⋮⋮</span>
                      <span className="hub-tree-label">{l.label}{l.kind === "link" ? " ↗" : ""} <span className="muted">· {l.id}{n ? ` · ×${n}` : ""}</span></span>
                      <button type="button" className="secondary" title="Ajouter dans le groupe sélectionné" onClick={() => addLeaf(l.id)}>＋</button>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </div>
      </div>
      <p className="muted hub-tree-help">Connecté : {login}. Une feuille absente du catalogue (URL non configurée, rôle) reste dans l'arbre mais n'est jamais affichée : la disposition du site peut donc contenir plus que ce que chacun voit.</p>
    </div>
  );
}
