// Parc des terminaux d'un site (#971) : synthèse par catégorie et lab, MAC associées automatiquement par le nom réseau
// (nom DHCP = nom du terminal), MAC inconnues, changements de bail DHCP, IP réattribuées, déplacements (pièce du plan, SSID,
// borne) d'après l'historique horaire des clients (#872). API : nebula-api /sites/<site>/reperage/parc*.
import { useCallback, useEffect, useState } from "react";
import { horodatage, lieuTexte, ficheDepuisInconnu } from "./reperageLib.js";

async function getJson(url, init) {
  const r = await fetch(url, { credentials: "include", ...(init || {}) });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || `${r.status}`);
  return j;
}
const ONGLETS = [["synthese", "Synthèse"], ["associer", "Associations"], ["baux", "Baux DHCP"], ["lieux", "Déplacements"], ["inconnus", "MAC inconnues"]];

export default function ParcSite({ base, actor, selection, onOuvrir, onInscrire, onChange }) {
  const [jours, setJours] = useState(30);
  const [d, setD] = useState(null);
  const [onglet, setOnglet] = useState("synthese");
  const [busy, setBusy] = useState(null);
  const [msg, setMsg] = useState(null);
  const [lieux, setLieux] = useState(null);
  const charger = useCallback(() => { setBusy("charger"); getJson(`${base}/reperage/parc?jours=${jours}`).then((x) => { setD(x); setMsg(null); }).catch((e) => setMsg({ ok: false, text: e.message })).finally(() => setBusy(null)); }, [base, jours]);
  useEffect(() => { charger(); }, [charger]);
  useEffect(() => {
    setLieux(null);
    if (selection) getJson(`${base}/reperage/parc/terminal/${selection}?jours=${jours}`).then(setLieux).catch(() => setLieux(null));
  }, [base, selection, jours]);
  const associer = async (ids) => {
    setBusy("associer"); setMsg(null);
    try {
      const r = await getJson(`${base}/reperage/parc/associer`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ids, par: actor }) });
      setMsg({ ok: true, text: `✓ ${r.associes} fiche(s) associée(s) à leur MAC` }); charger(); onChange && onChange();
    } catch (e) { setMsg({ ok: false, text: e.message }); } finally { setBusy(null); }
  };
  const s = d?.synthese;
  const labs = s ? s.labs.map((l) => l.nom) : [];
  return (
    <div className="panel" style={{ marginTop: 10 }}>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
        <strong>📊 Parc des terminaux</strong>
        {ONGLETS.map(([k, l]) => <button key={k} type="button" className={onglet === k ? "" : "secondary"} onClick={() => setOnglet(k)}>{l}
          {k === "associer" && d?.propositions?.length ? ` (${d.propositions.length})` : ""}{k === "baux" && d?.baux?.changements?.length ? ` (${d.baux.changements.length})` : ""}
          {k === "inconnus" && d?.inconnus?.length ? ` (${d.inconnus.length})` : ""}</button>)}
        <select value={jours} onChange={(e) => setJours(Number(e.target.value))} aria-label="période">{[7, 30, 90, 365].map((j) => <option key={j} value={j}>{j} jours</option>)}</select>
        <button type="button" className="secondary" onClick={charger} disabled={!!busy}>{busy === "charger" ? "⏳" : "↻"}</button>
        <small className="muted">dernière relève du réseau : {horodatage(d?.derniere_releve)} (toutes les heures)</small>
      </div>
      {msg && <p className={msg.ok ? "ok" : "error"}>{msg.text}</p>}
      {d?.erreur && <p className="muted">{d.erreur} — l'historique des clients se remplit à chaque relève horaire (tuile Nebula › Historique des clients).</p>}

      {selection && lieux && (
        <div className="panel" style={{ margin: "8px 0" }}>
          <strong>📍 {lieux.nom} : où a-t-il été ?</strong>{lieux.message && <span className="muted"> {lieux.message}</span>}
          {lieux.lieux?.length > 0 && <table className="table"><thead><tr><th>Du</th><th>Au</th><th>Lieu (pièce · SSID · borne)</th><th>IP</th></tr></thead><tbody>
            {[...lieux.lieux].reverse().slice(0, 50).map((l, i) => <tr key={i}><td>{horodatage(l.de)}</td><td>{horodatage(l.a)}</td><td>{lieuTexte(l)}</td><td>{l.ip || ""}</td></tr>)}
          </tbody></table>}
        </div>
      )}

      {onglet === "synthese" && s && (
        <div style={{ overflowX: "auto" }}>
          <p>{s.total} terminaux au registre · {s.avec_mac} avec MAC · <strong>{s.sans_mac} sans MAC</strong>{d.propositions?.length ? ` (${d.propositions.length} associables tout de suite)` : ""}</p>
          <table className="table"><thead><tr><th>Catégorie</th>{labs.map((l) => <th key={l}>{l}</th>)}<th>Total</th></tr></thead><tbody>
            {s.categories.map((c) => <tr key={c.nom}><td><strong>{c.nom}</strong></td>{labs.map((l) => <td key={l}>{s.tableau[c.nom]?.[l] || ""}</td>)}<td><strong>{c.n}</strong></td></tr>)}
            <tr><td><strong>Total</strong></td>{s.labs.map((l) => <td key={l.nom}><strong>{l.n}</strong></td>)}<td><strong>{s.total}</strong></td></tr>
          </tbody></table>
          <p className="muted">Importer l'inventaire : bouton « 📥 Importer » (colonnes nom, catégorie, type, désignation, modèle, n° de série, MAC, lab, localisation, stockage, compte…). Une ligne sans MAC ni IP complète la fiche de même nom.</p>
        </div>
      )}

      {onglet === "associer" && (
        <div>
          <p className="muted">Fiches sans MAC dont le nom est celui qu'un seul appareil annonce sur le réseau (nom DHCP). Rien n'est écrit sans « Associer ».</p>
          {d?.propositions?.length ? <>
            <p><button type="button" onClick={() => associer([])} disabled={!!busy}>{busy === "associer" ? "⏳ association…" : `Associer les ${d.propositions.length} MAC`}</button></p>
            <table className="table"><thead><tr><th>Fiche</th><th>Nom réseau</th><th>MAC</th><th>IP</th><th>Fabricant</th><th>Vu</th><th /></tr></thead><tbody>
              {d.propositions.map((p) => <tr key={p.id}><td><a href="#fiche" onClick={(e) => { e.preventDefault(); onOuvrir(p.id); }}>{p.nom}</a></td><td>{p.nom_reseau}</td><td><code>{p.mac}</code></td><td>{p.ip || ""}</td><td>{p.fabricant || ""}</td><td>{horodatage(p.derniere_vue)}</td>
                <td><button type="button" className="secondary" disabled={!!busy} onClick={() => associer([p.id])}>associer</button></td></tr>)}
            </tbody></table></> : <p>Aucune association en attente.</p>}
        </div>
      )}

      {onglet === "baux" && d && (
        <div>
          <h4>Changements d'adresse ({d.baux.changements.length})</h4>
          <table className="table"><thead><tr><th>Quand</th><th>Terminal</th><th>MAC</th><th>Ancienne IP</th><th>Nouvelle IP</th></tr></thead><tbody>
            {d.baux.changements.slice(0, 200).map((c, i) => <tr key={i}><td>{horodatage(c.at)}</td><td>{c.nom || <span className="muted">hors registre</span>}</td><td><code>{c.mac}</code></td><td>{c.ancienne}</td><td>{c.nouvelle}</td></tr>)}
            {!d.baux.changements.length && <tr><td colSpan={5} className="muted">aucun changement sur la période</td></tr>}
          </tbody></table>
          <h4>Adresses IP passées d'un appareil à un autre ({d.baux.ip_partagees.length})</h4>
          <table className="table"><thead><tr><th>IP</th><th>Appareils successifs</th></tr></thead><tbody>
            {d.baux.ip_partagees.slice(0, 200).map((p) => <tr key={p.ip}><td>{p.ip}</td><td>{p.macs.map((m) => `${m.nom || m.mac} (${horodatage(m.de)} → ${horodatage(m.a)})`).join(" ; ")}</td></tr>)}
          </tbody></table>
        </div>
      )}

      {onglet === "lieux" && d && (
        <table className="table"><thead><tr><th>Quand</th><th>Terminal</th><th>De</th><th>Vers</th></tr></thead><tbody>
          {d.deplacements.map((c, i) => <tr key={i}><td>{horodatage(c.at)}</td><td>{c.nom}</td><td>{c.de}</td><td>{c.vers}</td></tr>)}
          {!d.deplacements.length && <tr><td colSpan={4} className="muted">aucun déplacement : il faut des terminaux avec MAC, et les bornes inscrites au registre avec leur pièce (champ Local) pour nommer la pièce</td></tr>}
        </tbody></table>
      )}

      {onglet === "inconnus" && d && (
        <table className="table"><thead><tr><th>MAC</th><th>Nom réseau</th><th>Fabricant</th><th>IP</th><th>Où</th><th>Vu</th><th /></tr></thead><tbody>
          {d.inconnus.map((x) => <tr key={x.mac}><td><code>{x.mac}</code></td><td>{x.nom_reseau || ""}</td><td>{x.fabricant || ""}</td><td>{x.ip || ""}</td><td>{x.ou || ""}{x.vlan ? ` · VLAN ${x.vlan}` : ""}</td><td>{horodatage(x.derniere_vue)}</td>
            <td><button type="button" className="secondary" onClick={() => onInscrire(ficheDepuisInconnu(x))}>＋ inscrire</button></td></tr>)}
          {!d.inconnus.length && <tr><td colSpan={7} className="muted">aucune MAC inconnue sur la période</td></tr>}
        </tbody></table>
      )}
    </div>
  );
}
