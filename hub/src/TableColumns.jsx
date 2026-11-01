// En-tête de tableau configurable (livraison #698) : poignée de largeur au bord
// droit de chaque colonne (glisser ; double-clic = largeur automatique), menu
// « Colonnes » pour masquer / réafficher, réglages mémorisés (tableLayout.js).
//
//   const cols = [{ id: "agent", label: "Agent", fixed: true }, { id: "site", label: "Site" }, …];
//   const t = useTableColumns("agents", cols);
//   <table style={t.tableStyle}><TableColumnsHead t={t} /><tbody>…{t.show("site") && <td>…</td>}…</tbody></table>
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { normalizeLayout, visibleColumns, toggleHidden, setWidth, resetWidth, readLocal, loadAccount, saveLayout, isDefault,
  autoKeys, rawLayout, autoToggle, autoCss, clampWidth } from "./tableLayout.js";

export function useTableColumns(tableId, columns) {
  const [layout, setLayout] = useState(() => normalizeLayout(readLocal(tableId), columns));
  const touched = useRef(false);
  useEffect(() => {
    let alive = true;
    loadAccount(tableId).then((acc) => {
      if (alive && acc && !touched.current && !readLocal(tableId)) setLayout(normalizeLayout(acc, columns));
    });
    return () => { alive = false; };
    /* eslint-disable-next-line react-hooks/exhaustive-deps */
  }, [tableId]);
  const update = (next) => { touched.current = true; setLayout(next); saveLayout(tableId, next); };
  const visible = visibleColumns(columns, layout);
  const sized = Object.keys(layout.widths).length > 0;
  return {
    columns, layout, visible,
    show: (id) => !layout.hidden.includes(id),
    toggle: (id) => update(toggleHidden(layout, columns, id)),
    resize: (id, w, save = true) => (save ? update(setWidth(layout, id, w)) : setLayout(setWidth(layout, id, w))),
    autoWidth: (id) => update(resetWidth(layout, id)),
    reset: () => update({ widths: {}, hidden: [] }),
    isDefault: isDefault(layout),
    tableStyle: sized ? { tableLayout: "fixed", width: "max-content", minWidth: "100%" } : undefined,
  };
}

function ResizeHandle({ t, id, thRef }) {
  const onDown = (e) => {
    e.preventDefault(); e.stopPropagation();
    const startX = e.clientX, start = thRef.current?.getBoundingClientRect().width || 120;
    let last = start;
    const move = (ev) => { last = start + ev.clientX - startX; t.resize(id, last, false); };
    const up = () => { window.removeEventListener("mousemove", move); window.removeEventListener("mouseup", up); t.resize(id, last, true); };
    window.addEventListener("mousemove", move); window.addEventListener("mouseup", up);
  };
  return <span role="separator" aria-label="largeur de la colonne" title="Glisser pour élargir · double-clic : largeur automatique"
    onMouseDown={onDown} onDoubleClick={(e) => { e.stopPropagation(); t.autoWidth(id); }} onClick={(e) => e.stopPropagation()}
    style={{ position: "absolute", top: 0, right: -3, width: 7, height: "100%", cursor: "col-resize", zIndex: 2 }} />;
}

function HeadCell({ t, c, children }) {
  const ref = useRef(null);
  return (
    <th ref={ref} className={c.className} title={c.title} style={{ position: "relative", overflow: "hidden", textOverflow: "ellipsis" }}>
      {children ?? c.label}{!c.noResize && <ResizeHandle t={t} id={c.id} thRef={ref} />}
    </th>
  );
}

/** Menu « Colonnes » : cases à cocher + réinitialisation. */
export function ColumnsMenu({ t }) {
  const [open, setOpen] = useState(false);
  const box = useRef(null);
  useEffect(() => {
    if (!open) return undefined;
    const close = (e) => { if (box.current && !box.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);
  return (
    <span ref={box} style={{ position: "relative", display: "inline-block" }} onClick={(e) => e.stopPropagation()}>
      <button type="button" className="secondary" title="Colonnes affichées et largeurs" onClick={() => setOpen(!open)}>
        ⚙ Colonnes{t.layout.hidden.length ? ` (${t.layout.hidden.length} masquée${t.layout.hidden.length > 1 ? "s" : ""})` : ""}
      </button>
      {open && (
        <div className="hub-card" style={{ position: "absolute", right: 0, top: "100%", zIndex: 20, padding: 8, minWidth: 220, textAlign: "left", fontWeight: "normal" }}>
          {t.columns.filter((c) => c.label).map((c) => (
            <label key={c.id} style={{ display: "block", whiteSpace: "nowrap", opacity: c.fixed ? 0.6 : 1 }}>
              <input type="checkbox" checked={t.show(c.id)} disabled={c.fixed} onChange={() => t.toggle(c.id)} /> {c.label}
            </label>
          ))}
          <button type="button" className="secondary" style={{ marginTop: 6 }} disabled={t.isDefault} onClick={() => t.reset()}>Réinitialiser</button>
          <div className="muted" style={{ fontSize: 11, marginTop: 4 }}>Largeur : glisser le bord droit d'un en-tête.<br />Réglages mémorisés pour votre compte.</div>
        </div>
      )}
    </span>
  );
}

/** <colgroup> + <thead> ; `render` (facultatif) remplace le contenu d'un en-tête : (col) => noeud. */
export function TableColumnsHead({ t, render }) {
  return (
    <>
      <colgroup>{t.visible.map((c) => <col key={c.id} style={t.layout.widths[c.id] ? { width: t.layout.widths[c.id] } : undefined} />)}</colgroup>
      <thead><tr>{t.visible.map((c) => <HeadCell key={c.id} t={t} c={c}>{render?.(c)}</HeadCell>)}</tr></thead>
    </>
  );
}

// ------------------------------------------------------------------ #707 : n'importe quel tableau existant

/** Enveloppe un <table> (en-tête sur une seule ligne <thead>) : poignée de largeur sur chaque en-tête (glisser ;
 *  double-clic = largeur automatique), bouton « ⚙ » au survol pour masquer / réafficher, réglages mémorisés comme
 *  #698 (clé `table.auto.<id>`). Colonnes reconnues par leur libellé : l'ordre ou l'ajout de colonnes ne mélange rien.
 *  Sans <thead> d'une ligne, le tableau est rendu tel quel. */
export function AutoColumns({ id, children }) {
  const tableId = `auto.${id}`;
  const scope = `ac-${String(id).replace(/[^A-Za-z0-9_-]/g, "-")}`;
  const ref = useRef(null);
  const [keys, setKeys] = useState([]);
  const [layout, setLayout] = useState(() => rawLayout(readLocal(tableId)));
  const layoutRef = useRef(layout);
  layoutRef.current = layout;
  const touched = useRef(false);
  useEffect(() => {
    let alive = true;
    loadAccount(tableId).then((acc) => { if (alive && acc && !touched.current && !readLocal(tableId)) setLayout(rawLayout(acc)); });
    return () => { alive = false; };
    /* eslint-disable-next-line react-hooks/exhaustive-deps */
  }, [tableId]);
  const update = (next, save = true) => { touched.current = true; layoutRef.current = next; setLayout(next); if (save) saveLayout(tableId, next); };

  useLayoutEffect(() => {
    const table = ref.current && [...ref.current.children].find((n) => n.tagName === "TABLE");
    const rows = table?.tHead?.rows;
    if (!rows || rows.length !== 1) { if (keys.length) setKeys([]); return; }
    const ths = [...rows[0].cells];
    const k = autoKeys(ths.map((th) => th.dataset.col || th.textContent));
    if (k.join("\u0001") !== keys.join("\u0001")) setKeys(k);
    ths.forEach((th, i) => {
      if (th.colSpan > 1) return;
      let h = [...th.children].find((n) => n.classList?.contains("ac-handle"));
      if (!h) {
        h = document.createElement("span");
        h.className = "ac-handle";
        h.title = "Glisser pour élargir · double-clic : largeur automatique";
        h.addEventListener("click", (e) => e.stopPropagation());
        h.addEventListener("dblclick", (e) => {
          e.stopPropagation();
          const w = { ...layoutRef.current.widths }; delete w[e.currentTarget.dataset.key];
          update({ ...layoutRef.current, widths: w });
        });
        h.addEventListener("mousedown", (e) => {
          e.preventDefault(); e.stopPropagation();
          const key = e.currentTarget.dataset.key;
          const startX = e.clientX, start = e.currentTarget.parentElement.getBoundingClientRect().width;
          let last = start;
          const move = (ev) => { last = clampWidth(start + ev.clientX - startX); update({ ...layoutRef.current, widths: { ...layoutRef.current.widths, [key]: last } }, false); };
          const up = () => { window.removeEventListener("mousemove", move); window.removeEventListener("mouseup", up); update({ ...layoutRef.current }); };
          window.addEventListener("mousemove", move); window.addEventListener("mouseup", up);
        });
        th.appendChild(h);
      }
      h.dataset.key = k[i];
    });
  });

  const named = keys.filter(Boolean);
  return (
    <div ref={ref} className={`ac-wrap ${scope}`}>
      {keys.length > 0 && <style>{autoCss(scope, keys, layout)}</style>}
      {named.length > 1 && <AutoMenu keys={named} layout={layout} onToggle={(k) => update(autoToggle(layout, keys, k))} onReset={() => update({ widths: {}, hidden: [] })} />}
      {children}
    </div>
  );
}

function AutoMenu({ keys, layout, onToggle, onReset }) {
  const [open, setOpen] = useState(false);
  const box = useRef(null);
  useEffect(() => {
    if (!open) return undefined;
    const close = (e) => { if (box.current && !box.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);
  const n = layout.hidden.filter((k) => keys.includes(k)).length;
  return (
    <span ref={box} className={`ac-menu${open || n ? " ac-menu-on" : ""}`}>
      <button type="button" className="secondary" title="Colonnes affichées et largeurs" onClick={() => setOpen(!open)}>⚙{n ? ` ${n} masquée${n > 1 ? "s" : ""}` : ""}</button>
      {open && (
        <div className="hub-card ac-menu-panel">
          {keys.map((k) => <label key={k}><input type="checkbox" checked={!layout.hidden.includes(k)} onChange={() => onToggle(k)} /> {k}</label>)}
          <button type="button" className="secondary" style={{ marginTop: 6 }} disabled={!layout.hidden.length && !Object.keys(layout.widths).length} onClick={onReset}>Réinitialiser</button>
          <div className="muted" style={{ fontSize: 11, marginTop: 4 }}>Largeur : glisser le bord droit d'un en-tête.<br />Réglages mémorisés pour votre compte.</div>
        </div>
      )}
    </span>
  );
}
