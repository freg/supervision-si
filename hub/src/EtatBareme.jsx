// #882 : barème des estimations de l'état des lieux, façon planning poker. Un poids en POINTS par type d'action (échelle
// ½, 1, 2, 3, 5, 8, 13…), un coefficient par catégorie de système (physique, virtuel, conteneur, SGBD), des types
// AUTOMATISABLES (après la première fois, facteur de répétition), la vélocité (heures par point) et la marge.
// Le total se recalcule en direct sur l'état actuel (nombre d'occurrences de chaque type) : on voit où part le temps.
import { useEffect, useMemo, useRef, useState } from "react";
import { fetchEtatBareme, saveEtatBareme } from "./siAgentClient.js";

const n = (x) => (Math.round(x * 10) / 10).toLocaleString("fr-FR");

export default function EtatBareme({ siAgentApiBase, onClose, onSaved }) {
  const [d, setD] = useState(null);
  const [b, setB] = useState(null);
  const [msg, setMsg] = useState("");
  const fermer = useRef(onClose);
  fermer.current = onClose;
  useEffect(() => {   // une seule lecture à l'ouverture : un rafraîchissement de la page ne doit pas effacer les modifications
    fetchEtatBareme(siAgentApiBase).then((x) => { setD(x); setB(x?.bareme ? JSON.parse(JSON.stringify(x.bareme)) : null); }).catch((e) => setMsg(e.message));
  }, [siAgentApiBase]);
  useEffect(() => {
    const k = (e) => { if (e.key === "Escape") fermer.current(); };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, []);
  // aperçu en direct : la quantité de chaque type (catégories et répétitions comprises) est celle du dernier calcul serveur,
  // pondérée par le rapport points modifiés / points enregistrés
  const apercu = useMemo(() => {
    if (!d || !b) return null;
    let pts = 0;
    for (const t of d.types) {
      const ref = d.bareme.points[t.type] || 0;
      pts += ref ? t.total_points * ((b.points[t.type] || 0) / ref) : (b.points[t.type] || 0) * t.quantite;
    }
    const cr = d.categories.reduce((acc, c) => acc + c.points, 0);
    const cn = d.categories.reduce((acc, c) => acc + c.points * ((b.categories[c.categorie] || 1) / (c.coef || 1)), 0);
    if (cr > 0) pts *= cn / cr;
    const h = pts * Number(b.heures_par_point || 1);
    return { pts, h, hm: h * Number(b.marge || 1), j: (h * Number(b.marge || 1)) / 7 };
  }, [d, b]);
  if (!b) return <div className="edl-fiche-fond" onClick={onClose}><div className="edl-fiche">{msg || "lecture du barème…"}</div></div>;
  const enregistrer = async (defaut) => {
    setMsg("calcul…");
    const x = await saveEtatBareme(siAgentApiBase, defaut ? { defaut: true } : b);
    if (x?.error) { setMsg(x.error); return; }
    setD(x); setB(JSON.parse(JSON.stringify(x.bareme))); setMsg("enregistré : Excel, page d'audit et planning suivent ce barème"); onSaved?.();
  };
  const num = (k, props) => <input type="number" value={b[k]} onChange={(e) => setB({ ...b, [k]: e.target.value })} style={{ width: 70 }} {...props} />;
  return (
    <div className="edl-fiche-fond" onClick={onClose}>
      <div className="edl-fiche" style={{ width: "min(1100px, 100%)" }} role="dialog" aria-label="barème des estimations" onClick={(e) => e.stopPropagation()}>
        <header>
          <div><h3 style={{ margin: 0 }}>Barème des estimations (pesage façon planning poker)</h3>
            <span className="infra-muted">heures = points × heures par point × coefficient de catégorie × marge ; types automatisables : facteur de répétition après la 1re fois</span></div>
          <button type="button" className="secondary" onClick={onClose} title="fermer (Échap)">✕</button>
        </header>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 14, alignItems: "center", margin: "8px 0" }}>
          <label>heures par point (vélocité) {num("heures_par_point", { min: 0.1, max: 16, step: 0.25 })}</label>
          <label>marge × {num("marge", { min: 1, max: 10, step: 0.5 })}</label>
          <label title="au-delà de cet écart de versions, on reconstruit sur un système neuf">reconstruction au-delà de {num("seuil_reconstruction", { min: 1, max: 20, step: 1 })} versions</label>
          <label title="part d'un logiciel mis à jour en même temps que le système">logiciel avec le système × {num("logiciel_avec_os", { min: 0, max: 1, step: 0.1 })}</label>
          <label title="coût d'une action automatisable après la première fois (script déjà prêt)">répétition automatisée × {num("facteur_repetition", { min: 0, max: 1, step: 0.1 })}</label>
        </div>
        {apercu && <div className="np-tone neutral" style={{ margin: "6px 0" }}>
          Aperçu sur l'état actuel : <b>{n(apercu.pts)} points</b> → {n(apercu.h)} h sans marge → <b>{n(apercu.hm)} h avec marge, soit {n(apercu.j)} jours</b>
          {d && <span className="infra-muted"> (enregistré : {n(d.total.jours_marge)} jours)</span>}</div>}
        <h4 style={{ margin: "10px 0 4px" }}>Catégories de systèmes</h4>
        <table className="infra-table"><thead><tr><th>Catégorie</th><th>Coefficient</th><th>Systèmes concernés</th><th>Points (enregistré)</th></tr></thead>
          <tbody>{d.categories.map((c) => <tr key={c.categorie}><td>{c.libelle}</td>
            <td><input type="number" min="0.1" max="10" step="0.1" value={b.categories[c.categorie]} onChange={(e) => setB({ ...b, categories: { ...b.categories, [c.categorie]: e.target.value } })} style={{ width: 64 }} />
              {Number(b.categories[c.categorie]) !== c.defaut && <span className="infra-muted"> (défaut {c.defaut})</span>}</td>
            <td>{c.systemes}</td><td>{n(c.points)}</td></tr>)}</tbody></table>
        <h4 style={{ margin: "10px 0 4px" }}>Types d'action</h4>
        <div style={{ maxHeight: "48vh", overflow: "auto" }}>
          <table className="infra-table"><thead><tr><th>Type d'action</th><th>Points</th><th title="première fois plein tarif, ensuite × facteur de répétition">Automatisable</th><th>Occurrences</th><th>Points (enregistré)</th><th>Heures avec marge</th></tr></thead>
            <tbody>{d.types.map((t) => (
              <tr key={t.type} style={t.occurrences ? undefined : { opacity: 0.6 }}>
                <td>{t.libelle}</td>
                <td><select value={String(b.points[t.type])} onChange={(e) => setB({ ...b, points: { ...b.points, [t.type]: Number(e.target.value) } })}>
                  {[...new Set([...d.echelle, Number(b.points[t.type])])].sort((x, y) => x - y).map((v) => <option key={v} value={String(v)}>{v === 0.5 ? "½" : v}</option>)}</select>
                  {Number(b.points[t.type]) !== t.defaut && <span className="infra-muted"> (défaut {t.defaut === 0.5 ? "½" : t.defaut})</span>}</td>
                <td><input type="checkbox" checked={!!b.automatisable[t.type]} onChange={(e) => setB({ ...b, automatisable: { ...b.automatisable, [t.type]: e.target.checked } })} /></td>
                <td>{t.occurrences || "—"}</td><td>{t.total_points ? n(t.total_points) : "—"}</td><td>{t.heures_marge ? n(t.heures_marge) : "—"}</td>
              </tr>))}</tbody></table>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 10 }}>
          <button type="button" onClick={() => enregistrer(false)}>Enregistrer et recalculer</button>
          <button type="button" className="secondary" onClick={() => enregistrer(true)}>Revenir au barème par défaut</button>
          <span className="infra-muted">{msg}</span>
        </div>
      </div>
    </div>
  );
}
