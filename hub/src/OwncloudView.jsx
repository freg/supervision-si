// #999 : onglet ownCloud (tuile Migration, et vue « owncloud ») -- instances relevées par la sonde owncloud des agents :
// version, système et fin de support, disque, répartition fichiers / corbeilles / versions, activité 90 jours, comptes
// (dernière connexion, statut, volumes, doublons, comptes locaux) et étapes de migration avec leur état (enregistré).
import { useCallback, useEffect, useMemo, useState } from "react";
import { hubLink } from "./hubLinks.js";
import { STATUTS, ETATS, TON_ETAT, FILTRES, go, date, depuis, filtrerComptes, trierComptes, repartition, barresActivite, avancement } from "./owncloudLib.js";

const TON = { ok: "var(--ok)", warn: "var(--warning)", bad: "var(--danger)" };
const FOND = { ok: "var(--ok)", warn: "var(--warning)", "": "var(--muted)" };
const CHAMP = { background: "var(--bg)", color: "var(--text)", border: "1px solid var(--border)", borderRadius: 4, padding: "2px 6px" };   // #1000 : lisible en thème sombre

function Etape({ e, agentId, base, username, onSaved }) {
  const [etat, setEtat] = useState(e.etat);
  const [note, setNote] = useState(e.note);
  const [envoi, setEnvoi] = useState(null);
  useEffect(() => { setEtat(e.etat); setNote(e.note); }, [e.etat, e.note]);
  const change = etat !== e.etat || note !== e.note;
  const enregistrer = async () => {
    setEnvoi("⏳ enregistrement…");
    const r = await fetch(`${base}/owncloud/decisions`, { method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ agent_id: agentId, etape: e.id, etat, note, actor: username }) }).then((x) => x.json()).catch((x) => ({ error: x.message }));
    setEnvoi(r.error ? `✗ ${r.error}` : null);
    if (!r.error) onSaved();
  };
  return (
    <tr>
      <td><strong>{e.titre}</strong> <span className="infra-muted">({e.genre})</span><div className="infra-muted" style={{ fontSize: 12 }}>{e.aide}</div></td>
      <td>{e.detail}</td>
      <td><select value={etat} onChange={(x) => setEtat(x.target.value)} style={{ ...CHAMP, color: TON[TON_ETAT[etat]] || "var(--text)" }}>
        {Object.entries(ETATS).map(([k, v]) => <option key={k} value={k} style={{ background: "var(--bg)", color: "var(--text)" }}>{v}</option>)}</select></td>
      <td><input value={note} onChange={(x) => setNote(x.target.value)} placeholder="décision, date, qui…" style={{ ...CHAMP, width: "100%", minWidth: 160 }} /></td>
      <td style={{ whiteSpace: "nowrap" }}>
        <button type="button" disabled={!change || !!envoi?.startsWith("⏳")} onClick={enregistrer}>{envoi?.startsWith("⏳") ? envoi : "Enregistrer"}</button>
        {envoi && !envoi.startsWith("⏳") && <span className="infra-error"> {envoi}</span>}
        {e.par && <div className="infra-muted" style={{ fontSize: 11 }}>{e.par}, {e.le ? new Date(e.le).toLocaleDateString("fr-FR") : ""}</div>}
      </td>
    </tr>
  );
}

function Instance({ i, base, username, onSaved }) {
  const [filtre, setFiltre] = useState("tous");
  const [texte, setTexte] = useState("");
  const [tri, setTri] = useState("derniere");
  const comptes = useMemo(() => trierComptes(filtrerComptes(i.comptes, filtre, texte), tri), [i.comptes, filtre, texte, tri]);
  const ch = i.chiffres || {};
  const sys = i.instance?.systeme || {};
  const disque = i.instance?.disque || {};
  const rep = repartition(i.totaux);
  const barres = barresActivite(i.activite);
  const av = avancement(i.etapes);
  const Th = ({ cle, children }) => <th style={{ cursor: "pointer", position: "sticky", top: 0, background: "var(--panel)" }} onClick={() => setTri(cle)}>{children}{tri === cle ? " ▾" : ""}</th>;
  return (
    <div className="infra-card" style={{ marginBottom: 12 }}>
      <h3 style={{ margin: "0 0 4px" }}>🗂 {i.hostname || i.agent_id} — ownCloud {i.instance?.version || "?"}
        <span className="infra-muted" style={{ fontSize: 12, fontWeight: 400 }}> · relevé {i.at ? new Date(i.at).toLocaleString("fr-FR") : "?"} · <a href={hubLink("si-agent", { agent: i.agent_id })}>agent {i.agent_id}</a></span></h3>
      {i.error && <p className="infra-error">Sonde : {i.error}</p>}
      <p style={{ margin: "2px 0" }}>
        Système : <span style={{ color: sys.depasse ? TON.bad : "inherit" }}>{sys.nom || "?"}{sys.fin ? ` — support de sécurité jusqu'au ${new Date(sys.fin).toLocaleDateString("fr-FR")}${sys.depasse ? " (dépassé)" : ""}` : ""}</span>
        {" · "}Disque des données : <span style={{ color: disque.pct >= 90 ? TON.bad : disque.pct >= 80 ? TON.warn : "inherit" }}>{disque.pct ?? "?"} %</span> ({go(disque.libre_go)} libres sur {go(disque.total_go)})
        {(i.instance?.domaines || []).length > 0 && <> · domaines : {i.instance.domaines.join(", ")}</>}
      </p>
      {(i.alerts || []).map((a) => <p key={a.code} style={{ margin: "2px 0", color: a.severity === "critical" ? TON.bad : TON.warn }}>⚠ {a.message}</p>)}

      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", margin: "8px 0" }}>
        {[["Comptes actifs (30 j)", `${ch.actifs ?? "?"} / ${ch.comptes ?? "?"}`], ["Inactifs depuis plus d'un an", `${ch.inactifs ?? "?"} · ${go(ch.go_inactifs)}`],
          ["Corbeilles", go(ch.go_corbeilles)], ["Données aujourd'hui", go(ch.go_total)], ["Données vivantes après décisions", go(ch.go_vivantes)],
          ["Actions (30 derniers jours relevés)", (ch.actions_30j ?? 0).toLocaleString("fr-FR")]].map(([l, v]) => (
          <div key={l} className="infra-card" style={{ padding: "6px 10px" }}><div className="infra-muted" style={{ fontSize: 12 }}>{l}</div><div style={{ fontSize: 18, fontWeight: 600 }}>{v}</div></div>
        ))}
      </div>

      {rep.length > 0 && (
        <div style={{ margin: "6px 0" }}>
          <div style={{ display: "flex", height: 14, borderRadius: 4, overflow: "hidden", border: "1px solid var(--border)" }}>
            {rep.map((r) => <div key={r.nom} title={`${r.nom} : ${go(r.go)} (${r.pct} %)`} style={{ width: `${r.pct}%`, background: FOND[r.ton] }} />)}
          </div>
          <div className="infra-muted" style={{ fontSize: 12 }}>{rep.map((r) => `${r.nom} ${go(r.go)} (${r.pct.toLocaleString("fr-FR")} %)`).join(" · ")}</div>
        </div>
      )}

      {barres.length > 0 && (
        <div style={{ margin: "8px 0" }}>
          <div className="infra-muted" style={{ fontSize: 12 }}>Activité des 90 derniers jours (actions par jour, échelle racine)</div>
          <div style={{ display: "flex", alignItems: "flex-end", gap: 1, height: 60 }}>
            {barres.map((b) => <div key={b.jour} title={`${new Date(b.jour).toLocaleDateString("fr-FR")} : ${b.actions.toLocaleString("fr-FR")} actions, ${b.utilisateurs} utilisateur(s)`}
              style={{ flex: 1, height: `${b.h}%`, background: "var(--accent)", minWidth: 2 }} />)}
          </div>
        </div>
      )}

      <h4 style={{ margin: "10px 0 4px" }}>Décisions et étapes de migration <span className="infra-muted">{av.clos} / {av.total} closes{av.decisions ? ` · ${av.decisions} décision(s) à prendre` : ""}</span></h4>
      <div className="infra-table-wrap"><table className="infra-table"><thead><tr><th>Étape</th><th>Constat</th><th>État</th><th>Note</th><th /></tr></thead>
        <tbody>{(i.etapes || []).map((e) => <Etape key={e.id} e={e} agentId={i.agent_id} base={base} username={username} onSaved={onSaved} />)}</tbody></table></div>

      <h4 style={{ margin: "10px 0 4px" }}>Comptes <span className="infra-muted">{comptes.length} / {(i.comptes || []).length}</span></h4>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center", marginBottom: 4 }}>
        {FILTRES.map(([k, l]) => <button key={k} type="button" className={filtre === k ? "" : "secondary"} onClick={() => setFiltre(k)}>{l}</button>)}
        <input value={texte} onChange={(e) => setTexte(e.target.value)} placeholder="filtrer (début de mot)" style={{ ...CHAMP, width: 180 }} />
      </div>
      <div className="infra-table-wrap" style={{ maxHeight: 420 }}>
        <table className="infra-table"><thead><tr>
          <Th cle="nom">Nom</Th><Th cle="derniere">Dernière connexion</Th><th style={{ position: "sticky", top: 0, background: "var(--panel)" }}>Statut</th>
          <th style={{ position: "sticky", top: 0, background: "var(--panel)" }}>Origine</th><Th cle="fichiers">Fichiers</Th><Th cle="corbeille">Corbeille</Th>
          <th style={{ position: "sticky", top: 0, background: "var(--panel)" }}>Versions</th><th style={{ position: "sticky", top: 0, background: "var(--panel)" }}>Plus ancien en corbeille</th></tr></thead>
          <tbody>{comptes.map((c) => (
            <tr key={c.id}>
              <td>{c.nom}{c.doublon && <span style={{ color: TON.warn }}> · en double</span>}<div className="infra-muted" style={{ fontSize: 11 }}>{c.id}</div></td>
              <td>{date(c.derniere_connexion)} <span className="infra-muted">({depuis(c.derniere_connexion)})</span></td>
              <td style={{ color: TON[STATUTS[c.statut]?.ton] || "inherit" }}>{STATUTS[c.statut]?.libelle || c.statut}</td>
              <td>{c.origine === "locale" ? "locale (hors annuaire)" : "annuaire"}</td>
              <td>{go(c.go_fichiers)}</td><td>{go(c.go_corbeille)}</td><td>{go(c.go_versions)}</td>
              <td>{c.corbeille_plus_ancien ? `${date(c.corbeille_plus_ancien)} (${c.corbeille_elements} él.)` : "—"}</td>
            </tr>))}
          </tbody></table>
      </div>
    </div>
  );
}

export default function OwncloudView({ siAgentApiBase, username, onBack }) {
  const [d, setD] = useState(null);
  const charger = useCallback(() => {
    fetch(`${siAgentApiBase}/owncloud`).then(async (r) => { const j = await r.json().catch(() => ({})); setD(r.ok ? j : { erreur: j.error || r.status }); })
      .catch((e) => setD({ erreur: e.message }));
  }, [siAgentApiBase]);
  useEffect(() => { charger(); }, [charger]);
  return (
    <div>
      {onBack && <div className="infra-top"><button className="secondary" onClick={onBack}>◀ Retour</button><h2>ownCloud</h2></div>}
      <p className="infra-muted">Instances ownCloud relevées par la sonde <code>owncloud</code> de leur agent (toutes les heures, lecture seule) : usage réel, volumes, corbeilles, comptes, et les étapes de leur migration.</p>
      {!d && <p className="infra-muted">⏳ lecture…</p>}
      {d?.erreur && <p className="infra-error">ownCloud indisponible : {d.erreur} (si-agent-api)</p>}
      {d?.instances?.length === 0 && (
        <p className="infra-card">Aucune instance relevée. Activer la sonde <strong>owncloud</strong> sur l'agent du serveur ownCloud : <a href={hubLink("si-agent")}>Agents</a> › fiche de l'agent › Sondes › owncloud (privilégiée).</p>
      )}
      {(d?.instances || []).map((i) => <Instance key={i.agent_id} i={i} base={siAgentApiBase} username={username} onSaved={charger} />)}
    </div>
  );
}
