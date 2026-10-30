// #944 : rendu commun d'une liste de conseils (diagnostic poste, NAS…) : niveau, constat, éléments nommés, procédure
// dépliable avec commandes copiables, mini bouton texte copiable, export de toutes les commandes.
import { useState } from "react";
import BoutonDetail from "./FenetreTexte.jsx";
import { texteConseil, scriptConseils } from "./conseilsDiagnostic.js";

function Commande({ texte }) {
  const [ok, setOk] = useState(false);
  const copier = () => { try { navigator.clipboard?.writeText(texte); setOk(true); setTimeout(() => setOk(false), 1200); } catch { /* presse-papiers indisponible */ } };
  return <code className="cd-cmd" title="cliquer pour copier" onClick={copier} style={{ cursor: "pointer" }}>{texte}{ok ? " ✔" : ""}</code>;
}

export default function ConseilsListe({ liste, titre = "Propositions et conseils", note, nomExport = "conseils" }) {
  const [ouverts, setOuverts] = useState({});
  const [tout, setTout] = useState(false);
  const b = { critique: 0, alerte: 0, info: 0 };
  for (const c of liste || []) b[c.niveau] = (b[c.niveau] || 0) + 1;
  if (!liste?.length) return <div className="np-tone good" style={{ margin: "8px 0" }}>{titre} : rien à signaler. ✔</div>;
  const script = scriptConseils(liste);
  return (
    <div className="infra-card" style={{ margin: "8px 0" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
        <h4 style={{ margin: 0 }}>{titre}</h4>
        {b.critique > 0 && <span className="np-tone bad">{b.critique} critique(s)</span>}
        {b.alerte > 0 && <span className="np-tone warn">{b.alerte} à surveiller</span>}
        {b.info > 0 && <span className="np-tone neutral">{b.info} info</span>}
        <span style={{ flex: 1 }} />
        <button type="button" className="secondary" onClick={() => setTout(!tout)}>{tout ? "Replier les procédures" : "Déplier les procédures"}</button>
        <BoutonDetail titre="Toutes les étapes et commandes" urgence="info" libelle="⌘" texte={script} />
      </div>
      <ol style={{ margin: "6px 0", paddingLeft: 20 }}>
        {liste.map((c, i) => {
          const ouvert = tout || ouverts[c.code];
          return (
            <li key={c.code + i} style={{ marginBottom: 8 }}>
              <b className={`np-tone ${c.niveau === "critique" ? "bad" : c.niveau === "alerte" ? "warn" : "neutral"}`}>{c.titre}</b>
              <BoutonDetail titre={c.titre} urgence={c.niveau === "critique" ? "critique" : c.niveau === "alerte" ? "alerte" : "info"} texte={texteConseil(c)} />
              <div className="infra-muted" style={{ fontSize: 13 }}>{c.constat}</div>
              {c.elements?.length > 0 && <ul className="cd-elements" style={{ margin: "2px 0", paddingLeft: 16, fontSize: 13 }}>{c.elements.map((e, j) => <li key={j}>{e}</li>)}</ul>}
              <div style={{ fontSize: 13 }}>→ {c.action}
                {c.etapes?.length > 0 && <button type="button" className="secondary cd-plier" style={{ marginLeft: 8, padding: "0 6px", fontSize: 12 }} onClick={() => setOuverts({ ...ouverts, [c.code]: !ouverts[c.code] })}>{ouvert ? "− procédure" : `+ procédure (${c.etapes.length})`}</button>}
              </div>
              {ouvert && c.etapes?.length > 0 && <ol className="cd-etapes" style={{ margin: "4px 0 0", paddingLeft: 18, fontSize: 13 }}>{c.etapes.map((e, j) => <li key={j}>{e.texte}{e.commande && <div><Commande texte={e.commande} /></div>}</li>)}</ol>}
            </li>);
        })}
      </ol>
      {note && <div className="infra-muted" style={{ fontSize: 11 }}>{note}</div>}
    </div>
  );
}
