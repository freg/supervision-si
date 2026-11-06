// #974 : calendrier des relèves de l'historique des clients (une diode par heure). noir : pas de relève ; rouge : erreur ;
// bleu : rien de nouveau ; vert : nouvelles informations (correspondance avec le registre, MAC, IP, nom, fabricant,
// équipement de raccordement). Clic sur une diode : détail des relèves de l'heure. API : /client-history/calendar, /poll/<id>.
import { useCallback, useEffect, useMemo, useState } from "react";
import BoutonDetail from "./FenetreTexte.jsx";
import { ETATS, NOUVEAUTES, grilleReleves, bilan, texteNouveautes } from "./relevesLib.js";

const fmt = (s) => (s ? new Date(s * 1000).toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "—");
const ligne = (cat, x) => ({
  macs: () => `${x.mac}  ${x.nom || ""}  ${x.ip || ""}  ${x.fabricant || ""}`,
  ips: () => `${x.mac}  ${x.nom || ""}  ${x.ancienne} → ${x.nouvelle}`,
  noms: () => `${x.mac}  « ${x.ancien} » → « ${x.nouveau} »`,
  fabricants: () => `${x.fabricant}  (${x.mac} ${x.nom || ""})`,
  raccordements: () => `${x.equipement}  (${x.mac} ${x.nom || ""})`,
  correspondances: () => `${x.nom}  ${x.mac}  ${x.ip || ""}`,
}[cat] || (() => JSON.stringify(x)))();

export default function NebulaRelevesCalendrier({ nebulaApiBase, siteId, version = 0 }) {
  const [jours, setJours] = useState(14);
  const [d, setD] = useState(null);
  const [err, setErr] = useState(null);
  const [sel, setSel] = useState(null);       // {jour, h, details: [...] | null}

  const charger = useCallback(() => {
    const p = new URLSearchParams({ jours });
    if (siteId) p.set("site", siteId);
    fetch(`${nebulaApiBase}/client-history/calendar?${p}`, { credentials: "include" })
      .then(async (r) => { const j = await r.json(); if (!r.ok) throw new Error(j.error || r.status); setD(j); setErr(null); })
      .catch((e) => setErr(String(e.message || e)));
  }, [nebulaApiBase, siteId, jours]);
  useEffect(() => { charger(); const t = setInterval(charger, 120000); return () => clearInterval(t); }, [charger, version]);

  const grille = useMemo(() => grilleReleves(d?.releves, { jours }), [d, jours]);
  const b = bilan(grille);

  const ouvrir = async (jour, c) => {
    if (sel && sel.jour === jour.jour && sel.h === c.h) { setSel(null); return; }
    setSel({ jour: jour.jour, libelle: jour.libelle, h: c.h, c, details: null });
    if (!c.ids.length) return;
    const details = await Promise.all(c.ids.map((id) => fetch(`${nebulaApiBase}/client-history/poll/${id}`, { credentials: "include" }).then((r) => r.json()).catch(() => null)));
    setSel((s) => (s && s.jour === jour.jour && s.h === c.h ? { ...s, details: details.filter(Boolean) } : s));
  };

  const diode = (c, taille = 11) => ({
    width: taille, height: taille, borderRadius: "50%", display: "inline-block", boxSizing: "border-box",
    background: c.futur ? "transparent" : ETATS[c.etat].couleur, border: `1px solid ${c.futur ? "var(--border)" : c.etat === "noir" ? "var(--border)" : ETATS[c.etat].couleur}`,
    opacity: c.futur ? 0.3 : 1,
  });

  return (
    <div className="hub-card" style={{ padding: 8 }}>
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center", marginBottom: 6 }}>
        <strong>📅 Relèves</strong>
        <select value={jours} onChange={(e) => setJours(Number(e.target.value))} aria-label="période">
          {[7, 14, 31, 62, 92].map((n) => <option key={n} value={n}>{n} jours</option>)}
        </select>
        {Object.entries(ETATS).map(([k, e]) => <span key={k} style={{ whiteSpace: "nowrap" }}><span style={diode({ etat: k })} /> {e.libelle} ({b[k]})</span>)}
        <span className="muted">
          {d?.premiere ? `relèves depuis le ${fmt(d.premiere)}` : "aucune relève enregistrée"}{d?.interval_s ? ` · toutes les ${Math.round(d.interval_s / 60)} min` : ""}
        </span>
        {err && <span className="error">calendrier : {err}</span>}
      </div>
      <div style={{ overflowX: "auto" }}>
        <table style={{ borderCollapse: "collapse", fontSize: 11 }}>
          <thead><tr><th />{Array.from({ length: 24 }, (_, h) => <th key={h} style={{ fontWeight: 400, padding: "0 2px", color: "var(--muted)" }}>{h % 3 === 0 ? `${h}h` : ""}</th>)}</tr></thead>
          <tbody>
            {grille.map((j) => (
              <tr key={j.jour}>
                <td style={{ paddingRight: 6, whiteSpace: "nowrap", color: "var(--muted)" }}>{j.libelle}</td>
                {j.cases.map((c) => (
                  <td key={c.h} style={{ padding: "1px 2px", textAlign: "center" }}>
                    <button type="button" onClick={() => ouvrir(j, c)} disabled={c.futur}
                      title={`${j.libelle} ${c.h} h : ${c.futur ? "à venir" : ETATS[c.etat].libelle}${c.clients != null ? ` · ${c.clients} client(s)` : ""}${texteNouveautes(c.n) ? ` · ${texteNouveautes(c.n)}` : ""}`}
                      style={{ all: "unset", cursor: c.futur ? "default" : "pointer", lineHeight: 0, outline: sel && sel.jour === j.jour && sel.h === c.h ? "2px solid var(--text)" : "none", borderRadius: "50%" }}>
                      <span style={diode(c)} />
                    </button>
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {sel && (
        <div style={{ marginTop: 6, borderTop: "1px solid var(--border)", paddingTop: 6 }}>
          <strong>{sel.libelle}, {sel.h} h – {sel.h + 1} h</strong> : {ETATS[sel.c.etat].libelle}
          {!sel.c.ids.length && <span className="muted"> — aucune relève enregistrée dans cette heure (service arrêté, relève bloquée ou antérieure à la mise en place)</span>}
          {sel.c.ids.length > 0 && !sel.details && <span className="muted"> — ⏳ chargement…</span>}
          {(sel.details || []).map((x) => {
            const nv = x.nouveautes || {};
            const texte = NOUVEAUTES.filter(([k]) => (nv[k] || []).length).map(([k, l]) => `${(nv.n || {})[k]} ${l}${(nv.n || {})[k] > nv[k].length ? ` (${nv[k].length} premières)` : ""} :\n${nv[k].map((y) => "  " + ligne(k, y)).join("\n")}`).join("\n\n");
            return (
              <div key={x.id} style={{ marginTop: 4 }}>
                <span style={diode({ etat: x.etat })} /> {fmt(x.at)} · {x.trigger} · {x.clients != null ? `${x.clients} client(s)` : "rien d'enregistré"} · {Math.round((x.duration_ms || 0) / 100) / 10} s
                {nv.rattrapage_24h && <span className="muted"> · rattrapage des 24 h gardées par Nebula</span>}
                {texteNouveautes(nv.n) && <> · <strong>{texteNouveautes(nv.n)}</strong> <BoutonDetail texte={texte} titre={`Nouveautés de la relève du ${fmt(x.at)}`} urgence="info" libelle="détail" /></>}
                {x.error && <> · <span style={{ color: "var(--danger)" }}>erreur</span> <BoutonDetail texte={x.error} titre={`Erreur de la relève du ${fmt(x.at)}`} urgence="alerte" libelle="⚠" /></>}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
