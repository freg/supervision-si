// #976 : calendrier d'activité localisé d'un terminal -- une case par heure, colorée par le lieu où il a passé le plus de
// temps (pièce du plan, sinon borne, sinon SSID) ; case vide = pas vu. Clic : sessions de l'heure (IP, borne, SSID, VLAN).
// Données : /sites/<site>/reperage/parc/terminal/<id> (historique des clients, relève horaire). Logique : relevesLib.js.
import { useEffect, useMemo, useState } from "react";
import { grilleActivite, nomLieu } from "./relevesLib.js";

const hh = (t) => new Date(t * 1000).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });

export default function CalendrierActivite({ base, eid, jours: joursInitial = 14, lieux: lieuxFournis = null }) {
  const [jours, setJours] = useState(joursInitial);
  const [rep, setRep] = useState(null);
  const [sel, setSel] = useState(null);
  useEffect(() => {
    if (lieuxFournis || !eid) return;
    setRep(null); setSel(null);
    fetch(`${base}/reperage/parc/terminal/${eid}?jours=${jours}`, { credentials: "include" })
      .then(async (r) => { const j = await r.json(); setRep(r.ok ? j : { erreur: j.error || r.status }); }).catch((e) => setRep({ erreur: e.message }));
  }, [base, eid, jours, lieuxFournis]);
  const lieux = lieuxFournis || rep?.lieux;
  const g = useMemo(() => grilleActivite(lieux, { jours }), [lieux, jours]);

  if (!lieuxFournis && !rep) return <p className="muted">⏳ activité…</p>;
  if (rep?.erreur) return <p className="muted">activité indisponible : {rep.erreur}</p>;
  if (!lieux?.length) return <p className="muted">jamais vu sur le réseau sur la période{rep?.message ? ` — ${rep.message}` : ""} (il faut une MAC sur la fiche et la relève horaire de l'historique des clients).</p>;
  return (
    <div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", fontSize: 12 }}>
        <select value={jours} onChange={(e) => setJours(Number(e.target.value))} aria-label="période">{[7, 14, 31, 62].map((n) => <option key={n} value={n}>{n} jours</option>)}</select>
        {g.legende.map((l) => <span key={l.lieu} style={{ whiteSpace: "nowrap" }}><span style={{ display: "inline-block", width: 10, height: 10, borderRadius: 2, background: l.couleur }} /> {l.lieu} ({l.heures} h)</span>)}
      </div>
      <div style={{ overflowX: "auto" }}>
        <table style={{ borderCollapse: "collapse", fontSize: 10, marginTop: 4 }}>
          <thead><tr><th />{Array.from({ length: 24 }, (_, h) => <th key={h} style={{ fontWeight: 400, color: "var(--muted)", padding: 0 }}>{h % 6 === 0 ? `${h}h` : ""}</th>)}</tr></thead>
          <tbody>
            {g.lignes.map((j) => (
              <tr key={j.jour}>
                <td style={{ paddingRight: 4, whiteSpace: "nowrap", color: "var(--muted)" }}>{j.libelle}</td>
                {j.cases.map((c) => (
                  <td key={c.h} style={{ padding: 1 }}>
                    <button type="button" disabled={!c.lieu} onClick={() => setSel(sel && sel.jour === j.jour && sel.h === c.h ? null : { ...c, jour: j.jour, libelle: j.libelle })}
                      title={`${j.libelle} ${c.h} h : ${c.lieu || (c.futur ? "à venir" : "pas vu")}`}
                      style={{ all: "unset", display: "block", width: 10, height: 10, borderRadius: 2, cursor: c.lieu ? "pointer" : "default",
                        background: c.lieu ? g.couleur[c.lieu] || "var(--muted)" : "transparent", border: `1px solid ${c.lieu ? "transparent" : "var(--border)"}`,
                        opacity: c.futur ? 0.3 : 1, outline: sel && sel.jour === j.jour && sel.h === c.h ? "2px solid var(--text)" : "none" }} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {sel && (
        <div style={{ fontSize: 12, marginTop: 4 }}>
          <strong>{sel.libelle}, {sel.h} h – {sel.h + 1} h</strong>
          {sel.sessions.map((s, i) => (
            <div key={i}>{hh(s.de)}{s.a !== s.de ? ` → ${hh(s.a)}` : ""} · <strong>{nomLieu(s)}</strong>{s.borne && s.piece ? ` (${s.borne})` : ""}{s.ssid ? ` · ${s.ssid}` : ""}{s.vlan ? ` · VLAN ${s.vlan}` : ""}{s.ip ? ` · ${s.ip}` : ""}</div>
          ))}
        </div>
      )}
    </div>
  );
}
