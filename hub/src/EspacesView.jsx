// Onglet « Espaces disques / données » (livraison #986) : pour chaque machine suivie (agents hôtes, NAS), matériel
// (disques physiques, RAM, baies), volumes (taille, occupé, libre, tendance, saturation estimée), RAID, possibilités
// d'extension et niveaux d'alerte -- regroupés par rôle, LAN ou hébergeur (classement deviné, corrigeable ici).
// API : si-agent-api /espaces, /espaces/classement, /espaces/seuils. Logique : espacesLib.js. Lecture seule sur les machines.
import { useCallback, useEffect, useMemo, useState } from "react";
import { hubLink } from "./hubLinks.js";
import BoutonDetail from "./FenetreTexte.jsx";
import { CRITERES, NIVEAUX, taille, saturationTexte, penteTexte, filtrer, grouper, valeurs } from "./espacesLib.js";

const lireMemo = (k, d) => { try { return localStorage.getItem(k) || d; } catch { return d; } };
const ecrireMemo = (k, v) => { try { localStorage.setItem(k, v); } catch { /* stockage indisponible */ } };

function Barre({ pct, niveau }) {
  return <span style={{ display: "inline-block", width: 90, height: 8, borderRadius: 4, background: "var(--border)", verticalAlign: "middle", marginRight: 6 }}>
    <span style={{ display: "block", width: `${Math.min(100, pct || 0)}%`, height: "100%", borderRadius: 4, background: NIVEAUX[niveau] || "var(--muted)" }} /></span>;
}

function Classement({ m, suggestions, onSave }) {
  const [v, setV] = useState(m.classement || {});
  const [busy, setBusy] = useState(null);
  useEffect(() => { setV(m.classement || {}); }, [m.classement]);
  const save = async (k) => {
    if ((v[k] || "") === (m.classement?.[k] || "")) return;
    setBusy(k);
    await onSave(m.id, { [k]: v[k] || "" });
    setBusy(null);
  };
  return (
    <span style={{ display: "inline-flex", gap: 4, flexWrap: "wrap" }}>
      {CRITERES.map(([k, l]) => (
        <span key={k}>
          <input list={`esp-${k}`} value={v[k] || ""} title={`${l} (Entrée ou sortie du champ pour enregistrer)`} style={{ width: 110, fontSize: 12 }}
            onChange={(e) => setV({ ...v, [k]: e.target.value })} onBlur={() => save(k)} onKeyDown={(e) => { if (e.key === "Enter") e.target.blur(); }} />
          {busy === k && <span className="muted" style={{ fontSize: 11 }}> ⏳</span>}
          <datalist id={`esp-${k}`}>{(suggestions[k] || []).map((x) => <option key={x} value={x} />)}</datalist>
        </span>
      ))}
    </span>
  );
}

export default function EspacesView({ onBack, siAgentApiBase }) {
  const [d, setD] = useState(null);
  const [err, setErr] = useState(null);
  const [critere, setCritere] = useState(() => lireMemo("hub.espaces.critere", "role"));
  const [niveau, setNiveau] = useState("tous");
  const [q, setQ] = useState("");
  const [ouvert, setOuvert] = useState({});
  const [seuilsOuverts, setSeuilsOuverts] = useState(false);
  const [seuils, setSeuils] = useState(null);
  const [busy, setBusy] = useState(null);

  const charger = useCallback(async () => {
    setBusy("charger");
    try {
      const r = await fetch(`${siAgentApiBase}/espaces`);
      const j = await r.json();
      if (!r.ok) throw new Error(j.error || r.status);
      setD(j); setSeuils(j.seuils); setErr(null);
    } catch (e) { setErr(e.message); }
    finally { setBusy(null); }
  }, [siAgentApiBase]);
  useEffect(() => { charger(); }, [charger]);
  useEffect(() => { ecrireMemo("hub.espaces.critere", critere); }, [critere]);

  const machines = useMemo(() => filtrer(d?.machines, { niveau, q }), [d, niveau, q]);
  const groupes = useMemo(() => grouper(machines, critere), [machines, critere]);
  const suggestions = useMemo(() => Object.fromEntries(CRITERES.map(([k]) => [k, valeurs(d?.machines, k)])), [d]);

  const enregistrerClassement = async (id, champs) => {
    try {
      const r = await fetch(`${siAgentApiBase}/espaces/classement`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ id, ...champs }) });
      if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || r.status);
      await charger();
    } catch (e) { setErr(`classement : ${e.message}`); }
  };
  const enregistrerSeuils = async () => {
    setBusy("seuils");
    try {
      const r = await fetch(`${siAgentApiBase}/espaces/seuils`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(seuils) });
      const j = await r.json();
      if (!r.ok) throw new Error(j.error || r.status);
      setSeuilsOuverts(false); await charger();
    } catch (e) { setErr(`seuils : ${e.message}`); }
    finally { setBusy(null); }
  };

  const nb = (n) => (d?.machines || []).filter((m) => m.niveau === n).length;
  return (
    <section className="view">
      <header className="view-header" style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <button type="button" className="secondary" onClick={onBack}>◀ Retour</button>
        <h1 style={{ margin: 0 }}>💽 Espaces disques / données</h1>
        <label>Regrouper par <select value={critere} onChange={(e) => setCritere(e.target.value)}>{CRITERES.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>
        <select value={niveau} onChange={(e) => setNiveau(e.target.value)} aria-label="niveau"><option value="tous">toutes les machines</option><option value="a-surveiller">à surveiller seulement</option></select>
        <input placeholder="rechercher (nom, rôle, modèle de disque…)" value={q} onChange={(e) => setQ(e.target.value)} style={{ minWidth: 220 }} />
        <button type="button" className="secondary" onClick={() => setSeuilsOuverts(!seuilsOuverts)}>⚙ Seuils</button>
        <button type="button" className="secondary" onClick={charger} disabled={!!busy}>{busy === "charger" ? "⏳" : "↻"}</button>
        {d && <span className="muted">{d.machines.length} machine(s) · <span style={{ color: NIVEAUX.critique }}>{nb("critique")} critique(s)</span> · <span style={{ color: NIVEAUX.attention }}>{nb("attention")} à surveiller</span></span>}
      </header>
      {err && <p className="error">{err}</p>}
      {seuilsOuverts && seuils && (
        <div className="panel" style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center", marginBottom: 8 }}>
          {[["attention", "attention à (%)"], ["critique", "critique à (%)"], ["jours_attention", "attention si plein dans (j)"], ["jours_critique", "critique si plein dans (j)"]].map(([k, l]) => (
            <label key={k}>{l} <input type="number" value={seuils[k]} onChange={(e) => setSeuils({ ...seuils, [k]: Number(e.target.value) })} style={{ width: 70 }} /></label>))}
          <button type="button" onClick={enregistrerSeuils} disabled={!!busy}>{busy === "seuils" ? "⏳ enregistrement…" : "Enregistrer"}</button>
          <span className="muted" style={{ fontSize: 12 }}>La saturation est estimée d'après la pente des 30 derniers jours (un relevé par jour).</span>
        </div>
      )}
      {!d && !err && <p className="muted">⏳ chargement…</p>}
      {groupes.map((g) => (
        <section key={g.valeur} className="hub-card" style={{ margin: "8px 0", padding: 10 }}>
          <h3 style={{ margin: "0 0 6px" }}>{g.valeur} <span className="muted" style={{ fontSize: 13, fontWeight: 400 }}>
            · {g.machines.length} machine(s) · {taille(g.occupe)} occupés sur {taille(g.taille)}
            {g.critique ? <span style={{ color: NIVEAUX.critique }}> · {g.critique} critique(s)</span> : null}{g.attention ? <span style={{ color: NIVEAUX.attention }}> · {g.attention} à surveiller</span> : null}</span></h3>
          <table className="table"><thead><tr><th>Machine</th><th>Matériel</th><th>Volumes</th><th>Extension</th><th>Classement (rôle · LAN · hébergeur)</th></tr></thead><tbody>
            {g.machines.map((m) => {
              const pire = [...m.volumes].sort((a, b) => (b.pct || 0) - (a.pct || 0))[0];
              const ouv = !!ouvert[m.id];
              const lien = m.type === "nas" ? hubLink("sauvegardes", {}) : hubLink("si-agent", { agent: m.id, section: "disks" });
              return [
                <tr key={m.id} style={{ cursor: "pointer" }} onClick={() => setOuvert({ ...ouvert, [m.id]: !ouv })}>
                  <td style={{ whiteSpace: "nowrap" }}><span style={{ color: NIVEAUX[m.niveau] }}>●</span> <strong>{m.nom}</strong> <span className="muted" style={{ fontSize: 11 }}>{m.type === "nas" ? "NAS" : "agent"}</span> {ouv ? "▴" : "▾"}
                    {m.alertes?.length > 0 && <span onClick={(e) => e.stopPropagation()}> <BoutonDetail texte={m.alertes.join("\n")} titre={`Alertes : ${m.nom}`} urgence={m.niveau === "critique" ? "alerte" : "info"} libelle={`⚠ ${m.alertes.length}`} /></span>}</td>
                  <td style={{ fontSize: 12 }}>{m.materiel?.modele || ""}{m.materiel?.ram ? ` · RAM ${taille(m.materiel.ram)}` : ""}<br /><span className="muted">{(m.materiel?.disques || []).length} disque(s){m.materiel?.baies ? ` / ${m.materiel.baies} baies` : ""}{(m.materiel?.disques || []).length ? ` : ${[...new Set(m.materiel.disques.map((x) => taille(x.taille)))].join(", ")}` : ""}</span></td>
                  <td style={{ whiteSpace: "nowrap", fontSize: 12 }}>{pire ? <><Barre pct={pire.pct} niveau={pire.niveau} />{pire.pct ?? "?"} % {pire.nom}</> : <span className="muted">aucun volume relevé</span>}{m.volumes.length > 1 ? <span className="muted"> +{m.volumes.length - 1}</span> : null}
                    <br /><span className="muted">{taille(m.occupe)} / {taille(m.taille)}{pire?.saturation_jours != null ? ` · ${saturationTexte(pire.saturation_jours)}` : ""}</span></td>
                  <td style={{ fontSize: 12, maxWidth: 360 }}>{m.extension?.length ? m.extension[0] : <span className="muted">—</span>}{m.extension?.length > 1 ? <span className="muted"> (+{m.extension.length - 1})</span> : null}</td>
                  <td onClick={(e) => e.stopPropagation()}><Classement m={m} suggestions={suggestions} onSave={enregistrerClassement} /></td>
                </tr>,
                ouv && (
                  <tr key={m.id + "-d"}><td colSpan={5} style={{ background: "var(--bg)" }}>
                    <div style={{ display: "flex", gap: 24, flexWrap: "wrap" }}>
                      <div><h4 style={{ margin: "4px 0" }}>Volumes</h4>
                        <table className="table" style={{ fontSize: 12 }}><thead><tr><th>Volume</th><th>Taille</th><th>Occupé</th><th>Libre</th><th>%</th><th>Tendance (30 j)</th><th>Saturation</th></tr></thead><tbody>
                          {m.volumes.map((v) => <tr key={v.nom}><td>{v.nom}{v.fs ? <span className="muted"> {v.fs}</span> : null}</td><td>{taille(v.taille)}</td><td>{taille(v.occupe)}</td><td>{taille(v.libre)}</td>
                            <td style={{ whiteSpace: "nowrap" }}><Barre pct={v.pct} niveau={v.niveau} />{v.pct ?? "?"} %</td><td>{v.pente_jour == null ? <span className="muted">pas assez de relevés</span> : penteTexte(v.pente_jour)}</td>
                            <td style={{ color: NIVEAUX[v.niveau] }}>{saturationTexte(v.saturation_jours)}</td></tr>)}
                        </tbody></table></div>
                      <div><h4 style={{ margin: "4px 0" }}>Disques physiques</h4>
                        {(m.materiel?.disques || []).length ? <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12 }}>{m.materiel.disques.map((x, i) => <li key={i}>{x.nom} · {x.modele || "?"} · {taille(x.taille)}{x.rotatif === false ? " · SSD" : ""}{x.etat ? ` · ${x.etat}` : ""}{x.temperature ? ` · ${x.temperature}` : ""}</li>)}</ul> : <p className="muted">non relevés</p>}
                        {(m.raid || []).length > 0 && <><h4 style={{ margin: "8px 0 4px" }}>RAID</h4><ul style={{ margin: 0, paddingLeft: 18, fontSize: 12 }}>{m.raid.map((r, i) => <li key={i}>{r.array || r.dev || r.nom} · {r.level || r.niveau} · {(r.devices || r.disques || []).length} disque(s) · {r.state || r.etat || ""}</li>)}</ul></>}</div>
                      <div style={{ maxWidth: 480 }}><h4 style={{ margin: "4px 0" }}>Possibilités d'extension</h4>
                        {m.extension?.length ? <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12 }}>{m.extension.map((x, i) => <li key={i}>{x}</li>)}</ul> : <p className="muted" style={{ fontSize: 12 }}>rien de détecté (pas de baie libre connue, pas de disque inutilisé, pas d'espace libre en LVM / ZFS)</p>}
                        <p style={{ fontSize: 12 }}><a href={lien}>{m.type === "nas" ? "NAS dans Sauvegardes (RAID, instantanés, journaux)" : "fiche de l'agent › Disques et stockage"} →</a></p></div>
                    </div>
                  </td></tr>
                ),
              ];
            })}
          </tbody></table>
        </section>
      ))}
      {d && !groupes.length && <p className="muted">aucune machine {niveau === "a-surveiller" ? "à surveiller" : "avec ces filtres"}</p>}
    </section>
  );
}
