// #896 : tuile « Postes Windows » -- par poste : ce qu'il faut pour le réinstaller (partages, lecteurs réseau,
// imprimantes, abonnements et licences, comptes de messagerie et agendas, logiciels) et diagnostic d'une panne
// intermittente (évènements critiques, plantages, disques, stabilité) ; résultats des tests de charge à la demande.
import { useCallback, useEffect, useState } from "react";
import { fetchPostesWindows, lancerCharge, stopCharge, fetchChargeLive } from "./siAgentClient.js";
import { hubLink, viewParams, clearViewParams } from "./hubLinks.js";
import { echantillons, serieDisque, dernierEtat, estFini } from "./chargeLive.js";
import IpPing from "./IpPing.jsx";
import AnalyseDistance from "./AnalyseDistance.jsx";   // #919

const TON = { critical: "bad", warning: "warn", info: "neutral" };
const date = (iso) => (iso ? new Date(iso).toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", year: "2-digit", hour: "2-digit", minute: "2-digit" }) : "—");
const go = (o) => (o == null ? "—" : o >= 1e12 ? `${(o / 1e12).toFixed(1).replace(".", ",")} To` : o >= 1e9 ? `${(o / 1e9).toFixed(1).replace(".", ",")} Go` : `${Math.round(o / 1e6)} Mo`);
const CAT = { ecran_bleu: "écrans bleus", materiel: "erreurs matérielles (WHEA)", diag_memoire_erreur: "mémoire défectueuse", disque: "erreurs disque / contrôleur",
  fichiers: "système de fichiers", arret_brutal: "arrêts brutaux", graphique: "pilote graphique relancé", memoire: "mémoire épuisée", diag_memoire: "diagnostic mémoire" };

function Tableau({ titre, lignes, cols, vide }) {
  return (<><h4 style={{ margin: "12px 0 4px" }}>{titre} ({(lignes || []).length})</h4>
    {!(lignes || []).length ? <div className="infra-muted">{vide || "aucun"}</div> : (
      <div style={{ maxHeight: 320, overflow: "auto" }}><table className="infra-table"><thead><tr>{cols.map(([t]) => <th key={t}>{t}</th>)}</tr></thead>
        <tbody>{lignes.map((l, i) => <tr key={i}>{cols.map(([t, f]) => <td key={t}>{f(l)}</td>)}</tr>)}</tbody></table></div>)}</>);
}

function Reinstallation({ r }) {
  if (!r) return <p className="infra-muted">pas encore de relevé</p>;
  return (<>
    {(r.profils_non_lus || []).length > 0 && <div className="np-tone warn">Profils non lus (utilisateur non connecté lors du relevé) : {r.profils_non_lus.join(", ")} — leurs lecteurs réseau, comptes Office et logiciels personnels manquent.</div>}
    <Tableau titre="Lecteurs réseau" lignes={r.lecteurs} cols={[["Utilisateur", (l) => l.utilisateur], ["Lettre", (l) => l.lettre], ["Chemin", (l) => <code>{l.chemin}</code>], ["Compte", (l) => l.compte || "—"]]} />
    <Tableau titre="Raccourcis réseau" lignes={r.raccourcis_reseau} cols={[["Utilisateur", (l) => l.utilisateur], ["Nom", (l) => l.nom]]} />
    <Tableau titre="Partages servis par le poste" lignes={r.partages} cols={[["Nom", (l) => l.nom], ["Dossier", (l) => <code>{l.chemin}</code>], ["Accès", (l) => (l.acces || []).join(" ; ")]]} />
    <Tableau titre="Imprimantes" lignes={r.imprimantes} cols={[["Nom", (l) => l.nom], ["Adresse", (l) => (l.adresse && /^\d/.test(l.adresse) ? <IpPing ip={l.adresse} /> : l.adresse || l.port)], ["Pilote", (l) => l.pilote], ["Partagée", (l) => (l.partagee ? "oui" : "non")]]} />
    <h4 style={{ margin: "12px 0 4px" }}>Office / Microsoft 365</h4>
    {r.office ? <div>{r.office.produits} · version {r.office.version} · canal {r.office.canal || "—"} · {r.office.plateforme}</div> : <div className="infra-muted">Office Click-to-Run absent</div>}
    {(r.identites_office || []).length > 0 && <div>Comptes : {r.identites_office.map((i) => `${i.courriel} (${i.utilisateur})`).join(", ")}</div>}
    {(r.outlook || []).length > 0 && <div>Profils Outlook : {r.outlook.map((o) => `${o.profil} (${o.utilisateur})`).join(", ")}</div>}
    <Tableau titre="Fichiers de messagerie Outlook à sauvegarder" lignes={r.fichiers_outlook} cols={[["Utilisateur", (l) => l.utilisateur], ["Fichier", (l) => <code>{l.fichier}</code>], ["Taille", (l) => go(l.octets)], ["Modifié", (l) => date(l.modifie)]]} />
    {(r.thunderbird || []).map((t, i) => (
      <div key={i}>
        <h4 style={{ margin: "12px 0 4px" }}>Thunderbird · {t.utilisateur}</h4>
        <div className="infra-muted" style={{ fontSize: 12 }}>{t.profil} (copier ce dossier conserve tout : courriels locaux, filtres, carnets d'adresses)</div>
        {t.comptes.map((c, k) => <div key={k}>• {c.type?.toUpperCase()} {c.serveur}:{c.port} ({c.securite}) — {c.utilisateur}</div>)}
        {t.envoi.map((c, k) => <div key={k}>• envoi SMTP {c.serveur}:{c.port} — {c.utilisateur || "—"}</div>)}
        {t.agendas.length > 0 && <div>Agendas : {t.agendas.map((a) => `${a.nom} (${a.nature}${a.desactive ? ", désactivé" : ""})`).join(", ")}</div>}
      </div>))}
    <Tableau titre="Licences" lignes={r.licences} cols={[["Produit", (l) => l.nom], ["État", (l) => l.etat_lib], ["Clé (fin)", (l) => l.cle_partielle], ["Type", (l) => (l.description || "").replace(/^.*?,\s*/, "")]]} />
    <Tableau titre="Antivirus" lignes={r.antivirus} cols={[["Produit", (l) => l.nom], ["Actif", (l) => (l.actif ? "oui" : "non")], ["À jour", (l) => (l.a_jour ? "oui" : "non")]]} />
    <Tableau titre="Logiciels" lignes={r.logiciels} cols={[["Nom", (l) => l.nom], ["Version", (l) => l.version], ["Éditeur", (l) => l.editeur], ["Portée", (l) => l.portee], ["Installé", (l) => (l.installe ? `${l.installe.slice(6, 8)}/${l.installe.slice(4, 6)}/${l.installe.slice(0, 4)}` : "—")]]} />
  </>);
}

function Diagnostic({ d, charge }) {
  if (!d) return <p className="infra-muted">pas encore de relevé</p>;
  const cats = Object.entries(d.categories || {}).filter(([k]) => CAT[k]);
  return (<>
    <h4 style={{ margin: "12px 0 4px" }}>Synthèse sur la période</h4>
    {cats.length ? <div style={{ display: "flex", gap: 14, flexWrap: "wrap" }}>{cats.map(([k, n]) => <span key={k} className={`np-tone ${["ecran_bleu", "materiel", "diag_memoire_erreur", "disque"].includes(k) ? "bad" : "warn"}`}>{n} {CAT[k]}</span>)}</div>
      : <div className="np-tone good">aucun évènement critique</div>}
    <Tableau titre="Chronologie des évènements critiques" lignes={d.critiques} cols={[["Date", (l) => date(l.t)], ["Nature", (l) => l.libelle], ["Source", (l) => `${l.source} ${l.id}`], ["Message", (l) => <span style={{ fontSize: 12 }}>{l.message}</span>]]} vide="aucun" />
    <Tableau titre="Applications qui plantent" lignes={d.plantages} cols={[["Application", (l) => l.application], ["Plantages", (l) => l.plantages], ["Blocages", (l) => l.blocages], ["Module en cause", (l) => (l.modules || []).join(", ") || "—"], ["Dernier", (l) => date(l.dernier)]]} />
    <Tableau titre="Disques" lignes={d.disques} cols={[["Modèle", (l) => l.modele], ["Type", (l) => `${l.media} ${l.bus}`], ["Santé", (l) => l.sante], ["Temp.", (l) => (l.temperature != null ? `${l.temperature} °C (max ${l.temperature_max ?? "?"})` : "—")], ["Usure", (l) => (l.usure != null ? `${l.usure} %` : "—")], ["Erreurs lect. / écr.", (l) => `${l.erreurs_lecture ?? "—"} / ${l.erreurs_ecriture ?? "—"}`], ["Heures", (l) => l.heures ?? "—"]]} />
    <Tableau titre="Volumes" lignes={d.volumes} cols={[["Lecteur", (l) => l.lettre], ["Taille", (l) => go(l.octets)], ["Libre", (l) => `${go(l.libre)} (${l.octets ? Math.round((100 * l.libre) / l.octets) : "?"} %)`], ["Santé", (l) => l.sante]]} />
    {(d.stabilite || []).length > 0 && <div style={{ marginTop: 8 }}>Indice de stabilité Windows : {d.stabilite.slice(0, 10).map((s) => s.indice?.toFixed(1)).join(" ← ")} (le plus récent à gauche, sur 10)</div>}
    {(d.vidages || []).length > 0 && <div className="np-tone bad" style={{ marginTop: 6 }}>Vidages mémoire : {d.vidages.map((v) => `${v.fichier} (${date(v.t)})`).join(", ")}</div>}
    <Tableau titre="Erreurs et avertissements des journaux (regroupés)" lignes={d.evenements} cols={[["Journal", (l) => l.journal], ["Source", (l) => `${l.source} ${l.id}`], ["Niveau", (l) => ({ 1: "critique", 2: "erreur", 3: "avertissement" }[l.niveau] || l.niveau)], ["Nombre", (l) => l.nombre], ["Dernier", (l) => date(l.dernier)], ["Exemple", (l) => <span style={{ fontSize: 12 }}>{l.exemple}</span>]]} />
    <h4 style={{ margin: "14px 0 4px" }}>Tests de charge</h4>
    {!charge ? <div className="infra-muted">aucun test lancé — onglet <b>Tests de charge</b> pour lancer, suivre en direct et interrompre.</div> : <ResultatCharge charge={charge} />}
  </>);
}

// #926 : « non concluant » (épreuve processeur calée sans gel ni erreur) n'est pas un défaut.
const tonVerdict = (v) => (v === "aucun défaut reproduit" ? "good" : v === "interrompu" ? "neutral" : v === "non concluant" ? "warn" : "bad");

function ResultatCharge({ charge }) {
  if (!charge) return <div className="infra-muted">aucun test encore — choisis les épreuves ci-dessus et lance.</div>;
  const d = charge.disque;
  const suffixe = (r) => (r && r.statut && r.statut !== "ok" ? ` — ${r.statut}` : "");
  return (
    <div>
      <div className={`np-tone ${tonVerdict(charge.verdict)}`}><b>{charge.verdict}</b> · {date(charge.debut || charge.at)}{(charge.epreuves || []).length ? ` · ${charge.epreuves.join(", ")}` : ""}</div>
      {charge.processeur && <div>Processeur : {charge.processeur.coeurs} cœurs{charge.processeur.coeurs_finis != null && charge.processeur.coeurs_finis !== charge.processeur.coeurs ? ` (${charge.processeur.coeurs_finis} ont fini)` : ""}, {charge.processeur.duree_s} s, {charge.processeur.erreurs_calcul ?? 0} erreur(s) de calcul{charge.processeur.gel_max_s >= 2 ? `, poste figé jusqu'à ${charge.processeur.gel_max_s} s` : ""}{suffixe(charge.processeur)}</div>}
      {charge.memoire && <div>Mémoire : {charge.memoire.mo} Mo testés sur {charge.memoire.libre_mo} Mo libres, {charge.memoire.blocs_errones} bloc(s) erroné(s){suffixe(charge.memoire)}</div>}
      {d && <div>Disque : {d.mo} Mo, écriture {d.ecriture_mo_s ?? "?"} Mo/s, lecture {d.lecture_mo_s ?? "?"} Mo/s, relecture {d.identique === true ? "identique" : d.identique === false ? "DIFFÉRENTE" : d.erreur || "?"}{suffixe(d)}</div>}
      {(charge.temperatures_apres || []).length > 0 && <div>Températures : {(charge.temperatures_avant || []).map((t) => t.celsius).join(" / ") || "?"} °C avant → {charge.temperatures_apres.map((t) => t.celsius).join(" / ")} °C après</div>}
      {(charge.alerts || []).map((a, k) => <div key={k} className={`np-tone ${TON[a.severity] || "neutral"}`}>• {a.message}</div>)}
    </div>
  );
}

function Jauge({ pct }) {
  const p = Math.max(0, Math.min(100, pct || 0));
  return (
    <div style={{ background: "var(--panel)", border: "1px solid var(--border)", borderRadius: 6, height: 10, overflow: "hidden" }}>
      <div style={{ width: `${p}%`, height: "100%", background: "var(--accent)" }} />
    </div>
  );
}

function GrapheDebit({ serie }) {
  const { points, moSMax, tMax } = serie;
  if (points.length < 2) return <div className="infra-muted">débit disque : en attente d'échantillons…</div>;
  const W = 520, H = 120, pad = 26;
  const px = (t) => pad + (tMax ? t / tMax : 0) * (W - 2 * pad);
  const py = (v) => H - pad - (moSMax ? v / moSMax : 0) * (H - 2 * pad);
  const d = points.map((p, i) => `${i ? "L" : "M"}${px(p.t).toFixed(1)},${py(p.mo_s).toFixed(1)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", maxWidth: W, height: "auto" }} role="img" aria-label="débit disque dans le temps">
      <line x1={pad} y1={H - pad} x2={W - pad} y2={H - pad} stroke="var(--border)" />
      <line x1={pad} y1={pad} x2={pad} y2={H - pad} stroke="var(--border)" />
      <path d={d} fill="none" stroke="var(--accent)" strokeWidth="2" />
      <text x={pad} y={pad - 8} fontSize="10" fill="var(--muted)">{Math.round(moSMax)} Mo/s</text>
      <text x={W - pad} y={H - pad + 16} fontSize="10" fill="var(--muted)" textAnchor="end">{tMax.toFixed(0)} s</text>
      <text x={pad} y={H - pad + 16} fontSize="10" fill="var(--muted)">0</text>
    </svg>
  );
}

const EPR = [["cpu", "Processeur"], ["memoire", "Mémoire"], ["disque", "Disque"]];

function ChargePilotage({ agent, base, charge }) {
  const [epr, setEpr] = useState(["disque"]);          // défaut : juste le disque (piste n°1 sur pc-paul)
  const [cpuS, setCpuS] = useState(120);
  const [memPct, setMemPct] = useState(60);
  const [disqueMo, setDisqueMo] = useState(2048);
  const [maxS, setMaxS] = useState(240);
  const [live, setLive] = useState(null);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const rafraichir = useCallback(() => { if (agent) fetchChargeLive(base, agent).then(setLive); }, [base, agent]);
  useEffect(() => { rafraichir(); const i = setInterval(rafraichir, 2000); return () => clearInterval(i); }, [rafraichir]);
  const ech = echantillons(live && live.live && live.live.data);
  const serie = serieDisque(ech);
  const etat = dernierEtat(ech);
  const fini = estFini(ech);
  const resultat = (live && live.resultat && live.resultat.data) || charge;
  const toggle = (k) => setEpr((l) => (l.includes(k) ? l.filter((x) => x !== k) : [...l, k]));
  async function lancer() {
    if (!epr.length) { setMsg("choisir au moins une épreuve"); return; }
    setBusy(true); setMsg("");
    const r = await lancerCharge(base, { agent, epreuves: epr, cpu_s: cpuS, mem_pct: memPct, disque_mo: disqueMo, max_s: maxS });
    setMsg(r && r.error ? `échec : ${r.error}` : "test demandé — l'agent le relève sous peu. Prévenir l'utilisateur : poste fortement ralenti.");
    setBusy(false);
  }
  async function interrompre() {
    setBusy(true);
    const r = await stopCharge(base, agent);
    setMsg(r && r.error ? `échec : ${r.error}` : "arrêt demandé — effectif dès que l'agent relève la commande.");
    setBusy(false);
  }
  return (
    <div>
      <div className="infra-muted" style={{ marginBottom: 8 }}>Lancer un test de charge à la demande et le suivre en direct. Le poste est fortement ralenti pendant le test — <b>prévenir l'utilisateur</b>. Chaque épreuve est bornée ({maxS} s) et interruptible ; (re)jouer une partie = cocher seulement les épreuves voulues.</div>
      <div style={{ display: "flex", gap: 14, flexWrap: "wrap", alignItems: "center", margin: "6px 0" }}>
        {EPR.map(([k, t]) => <label key={k}><input type="checkbox" checked={epr.includes(k)} onChange={() => toggle(k)} /> {t}</label>)}
        <label>CPU <input type="number" style={{ width: 60 }} value={cpuS} onChange={(e) => setCpuS(+e.target.value)} /> s</label>
        <label>Mém. <input type="number" style={{ width: 55 }} value={memPct} onChange={(e) => setMemPct(+e.target.value)} /> %</label>
        <label>Disque <input type="number" style={{ width: 70 }} value={disqueMo} onChange={(e) => setDisqueMo(+e.target.value)} /> Mo</label>
        <label>Plafond/épreuve <input type="number" style={{ width: 60 }} value={maxS} onChange={(e) => setMaxS(+e.target.value)} /> s</label>
      </div>
      <div style={{ display: "flex", gap: 8, alignItems: "center", margin: "6px 0", flexWrap: "wrap" }}>
        <button type="button" className="primary" disabled={busy} onClick={lancer}>▶ Lancer</button>
        <button type="button" className="secondary" disabled={busy} onClick={interrompre}>⏹ Interrompre</button>
        <button type="button" className="secondary" onClick={rafraichir}>⟳</button>
        {msg && <span className="infra-muted">{msg}</span>}
      </div>
      <h4 style={{ margin: "12px 0 4px" }}>Tension en direct {fini && <span className="np-tone good">terminé</span>}</h4>
      {etat ? (
        <div className="np-tone neutral">Phase : <b>{etat.phase}{etat.sous ? ` / ${etat.sous}` : ""}</b>{etat.pct != null ? ` · ${etat.pct} %` : ""}{etat.mo_s != null ? ` · ${etat.mo_s} Mo/s` : ""}{etat.elapsed_s != null ? ` · ${etat.elapsed_s} s` : ""}</div>
      ) : <div className="infra-muted">aucun échantillon en direct (test non démarré, ou agent pas encore à jour du suivi direct).</div>}
      {etat && etat.pct != null && <div style={{ margin: "6px 0", maxWidth: 520 }}><Jauge pct={etat.pct} /></div>}
      <div style={{ marginTop: 8 }}><GrapheDebit serie={serie} /></div>
      <h4 style={{ margin: "14px 0 4px" }}>Dernier résultat</h4>
      <ResultatCharge charge={resultat} />
    </div>
  );
}

export default function PosteWindowsView({ onBack, siAgentApiBase, actor }) {
  const [liste, setListe] = useState(null);
  const [params] = useState(() => { const p = viewParams(); clearViewParams(); return p; });   // #923 : ?agent=pc-paul&onglet=distance
  const [choix, setChoix] = useState(params.agent || "");
  const [detail, setDetail] = useState(null);
  const [onglet, setOnglet] = useState(["diagnostic", "charge", "distance", "reinstallation"].includes(params.onglet) ? params.onglet : "diagnostic");
  useEffect(() => { fetchPostesWindows(siAgentApiBase).then((l) => { setListe(l); if (l.length === 1 && !params.agent) setChoix(l[0].agent); }); }, [siAgentApiBase]);
  const charger = useCallback(() => { if (choix) fetchPostesWindows(siAgentApiBase, choix).then((l) => setDetail(l[0] || null)); }, [siAgentApiBase, choix]);
  useEffect(() => { setDetail(null); charger(); }, [charger]);
  return (
    <div className="infra-page">
      <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
        {onBack && <button type="button" className="secondary" onClick={onBack}>◀ Retour</button>}
        <h2 style={{ margin: 0 }}>Postes Windows</h2>
        <span className="infra-muted">sonde poste-windows (lecture seule, toutes les 6 h) · tests de charge à la demande (poste-charge)</span>
      </div>
      {liste === null ? <p className="infra-muted">lecture…</p> : liste.length === 0 ? (
        <p className="infra-muted">Aucun poste relevé. Installer l'agent sur le poste (<a href={hubLink("si-agent")}>Agents</a> › Installation › Windows), puis activer la sonde <b>poste-windows</b> sur sa fiche (Commandes › « Activer une sonde (sur l'hôte) »).</p>
      ) : (<>
        <table className="infra-table" style={{ margin: "10px 0" }}><thead><tr><th>Poste</th><th>Système</th><th>Modèle</th><th>Constats</th><th>Relevé</th><th>Test de charge</th></tr></thead>
          <tbody>{liste.map((p) => (
            <tr key={p.agent} onClick={() => setChoix(p.agent)} style={{ cursor: "pointer", fontWeight: p.agent === choix ? 600 : 400 }}>
              <td>{p.poste?.nom || p.agent} <span className="infra-muted">({p.agent})</span></td><td>{p.poste?.systeme || "—"}</td><td>{[p.poste?.fabricant, p.poste?.modele].filter(Boolean).join(" ") || "—"}</td>
              <td>{p.alertes.filter((a) => a.severity === "critical").length > 0 && <span className="np-tone bad">{p.alertes.filter((a) => a.severity === "critical").length} critique(s) </span>}
                {p.alertes.filter((a) => a.severity === "warning").length > 0 && <span className="np-tone warn">{p.alertes.filter((a) => a.severity === "warning").length} avertissement(s)</span>}
                {!p.alertes.length && <span className="np-tone good">aucun</span>}</td>
              <td>{date(p.at)}</td><td>{p.charge ? <span className={`np-tone ${tonVerdict(p.charge.verdict)}`}>{p.charge.verdict}</span> : "—"}</td>
            </tr>))}</tbody></table>
        {detail && (
          <section className="infra-card">
            <h3 style={{ margin: "0 0 6px" }}>{detail.poste?.nom || detail.agent} <a href={hubLink("si-agent", { agent: detail.agent })} style={{ fontSize: 13, fontWeight: 400 }} title="fiche de l'agent : sondes, commandes, réglages">fiche de l'agent ↗</a> <span className="infra-muted" style={{ fontSize: 13 }}>· {detail.poste?.systeme} {detail.poste?.version} · démarré le {date(detail.poste?.demarrage)} · {go(detail.poste?.memoire_octets)} de mémoire</span></h3>
            {detail.alertes.map((a, k) => <div key={k} className={`np-tone ${TON[a.severity] || "neutral"}`}>• {a.message}</div>)}
            <div style={{ display: "flex", gap: 8, margin: "10px 0" }}>
              <button className={onglet === "diagnostic" ? "primary" : "secondary"} onClick={() => setOnglet("diagnostic")}>Diagnostic</button>
              <button className={onglet === "charge" ? "primary" : "secondary"} onClick={() => setOnglet("charge")}>Tests de charge</button>
              <button className={onglet === "reinstallation" ? "primary" : "secondary"} onClick={() => setOnglet("reinstallation")}>Réinstallation</button>
              <button className={onglet === "distance" ? "primary" : "secondary"} onClick={() => setOnglet("distance")} title="commandes PowerShell passées par l'agent, résultats interprétés">Analyse à distance</button>
              <button className="secondary" onClick={() => window.print()} title="imprimer ou enregistrer en PDF la fiche affichée">Imprimer</button>
              <button className="secondary" onClick={charger}>⟳</button>
            </div>
            {onglet === "distance" ? <AnalyseDistance agent={detail.agent} base={siAgentApiBase} actor={actor} /> : onglet === "diagnostic" ? <Diagnostic d={detail.diagnostic} charge={detail.charge} /> : onglet === "charge" ? <ChargePilotage agent={detail.agent} base={siAgentApiBase} charge={detail.charge} /> : <Reinstallation r={detail.reinstallation} />}
          </section>)}
      </>)}
    </div>
  );
}
