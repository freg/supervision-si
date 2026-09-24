// Accueil en ARBRE (livraison #603) -- alternative aux tuiles : le contenu du
// menu déroulant (vue métier #599 ou disposition #516, même source, le menu
// reste), présenté comme une vue JSON dépliable : ▸ / ▾ par branche, feuilles
// cliquables, nombre d'éléments, « aussi sous … », filtre début de mot,
// tout déplier / replier. Sélecteur Tuiles ⇄ Arbre en tête de l'accueil.
import { useMemo, useState } from "react";

const LS_KEY = "hub.home.tree.open";

function loadOpen() { try { return new Set(JSON.parse(localStorage.getItem(LS_KEY) || "[]")); } catch { return new Set(); } }
function saveOpen(set) { try { localStorage.setItem(LS_KEY, JSON.stringify([...set])); } catch { /* ignoré */ } }

/** Nœud générique : { id, label, icon?, description?, count?, children: [nœuds], leaves: [{ id, label, kind, also? }] }. */
export default function HomeTree({ roots, query, onQuery, onOpenLeaf, leafActive, mode, onMode, emptyText }) {
  const [open, setOpen] = useState(loadOpen);
  const [allOpen, setAllOpen] = useState(null);  // null = état par nœud ; true / false = forcé
  const toggle = (id) => { setAllOpen(null); const s = new Set(open); if (s.has(id)) s.delete(id); else s.add(id); setOpen(s); saveOpen(s); };
  const isOpen = (id, depth) => (query ? true : allOpen != null ? allOpen : open.size ? open.has(id) : depth === 0);
  const total = useMemo(() => roots.reduce((n, r) => n + (r.count || 0), 0), [roots]);
  const renderLeaf = (l, depth) => (
    <div key={`${depth}:${l.id}`} className={`hub-home-tree-leaf${leafActive && leafActive(l) ? " active" : ""}`} style={{ paddingLeft: 14 + depth * 18 }}>
      <span className="hub-home-tree-bullet">·</span>
      <button type="button" className="hub-home-tree-link" onClick={() => onOpenLeaf(l)} title={l.also && l.also.length ? `aussi sous : ${l.also.join(" ; ")}` : l.description || ""}>
        {l.label}{l.kind === "link" && !l.embeddable ? " ↗" : ""}
      </button>
      {l.also && l.also.length > 0 && <span className="muted hub-home-tree-also">aussi sous {l.also.length === 1 ? l.also[0] : `${l.also.length} autres branches`}</span>}
    </div>
  );
  const renderNode = (n, depth) => {
    const o = isOpen(n.id, depth);
    const size = (n.leaves || []).length + (n.children || []).length;
    return (
      <div key={n.id} className="hub-home-tree-node">
        <div className="hub-home-tree-row" style={{ paddingLeft: depth * 18 }} onClick={() => toggle(n.id)} role="button" tabIndex={0} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(n.id); } }}>
          <span className="hub-home-tree-caret">{o ? "▾" : "▸"}</span>
          <span className={`hub-home-tree-label${depth === 0 ? " root" : ""}`}>{n.icon ? `${n.icon} ` : ""}{n.label}</span>
          <span className="muted hub-home-tree-count">{n.count != null ? `${n.count} outil${n.count > 1 ? "s" : ""}` : `${size}`}</span>
          {depth === 0 && n.description && <span className="muted hub-home-tree-desc">— {n.description}</span>}
          {!o && size > 0 && <span className="muted hub-home-tree-preview">{[...(n.children || []).map((c) => c.label), ...(n.leaves || []).map((l) => l.label)].slice(0, 6).join(", ")}{size > 6 ? "…" : ""}</span>}
        </div>
        {o && (
          <div className="hub-home-tree-children">
            {(n.leaves || []).map((l) => renderLeaf(l, depth + 1))}
            {(n.children || []).map((c) => renderNode(c, depth + 1))}
          </div>
        )}
      </div>
    );
  };
  return (
    <div className="hub-home-tree">
      <div className="hub-home-tree-bar">
        <div className="hub-home-switch" role="group" aria-label="mode d'accueil">
          <button type="button" className={mode === "tiles" ? "active" : ""} onClick={() => onMode("tiles")} title="accueil en tuiles">▦ Tuiles</button>
          <button type="button" className={mode === "tree" ? "active" : ""} onClick={() => onMode("tree")} title="accueil en arbre dépliable">⌥ Arbre</button>
        </div>
        <input type="search" placeholder="filtrer (début de mot)" value={query} onChange={(e) => onQuery(e.target.value)} />
        <button type="button" className="secondary" onClick={() => setAllOpen(true)}>tout déplier</button>
        <button type="button" className="secondary" onClick={() => setAllOpen(false)}>tout replier</button>
        <span className="muted">{total} outil{total > 1 ? "s" : ""} · {roots.length} racine{roots.length > 1 ? "s" : ""}</span>
      </div>
      <div className="hub-home-tree-body">
        {roots.map((r) => renderNode(r, 0))}
        {!roots.length && <p className="muted">{emptyText || "rien à afficher"}</p>}
      </div>
    </div>
  );
}
