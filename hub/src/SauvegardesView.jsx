// #937 : tuile « Sauvegardes » -- aperçu central de toutes les sauvegardes du SI (lecture seule : rien n'est lancé d'ici,
// chaque ligne renvoie vers l'endroit qui agit). Onglets : Vue d'ensemble · Postes (sauvegarde de conf par agent + poussée
// PBS) · PBS (pbs10) · Copies host / VM · BackupPC (#939 : sonde backuppc + lancer/arrêter une sauvegarde, intervention) · NAS QNAP
// (#939 : volumes SNMP + snapshots, Time Machine, RAID, partages par SSH, lecture seule).
// Données : GET /sauvegardes/apercu (si-agent-api). Les info-bulles importantes ont leur mini bouton (fenêtre copiable).
import { useCallback, useEffect, useState } from "react";
import { fetchSauvegardesApercu, runBackuppc } from "./siAgentClient.js";
import { hubLink, viewParams, clearViewParams } from "./hubLinks.js";
import BoutonDetail from "./FenetreTexte.jsx";
import { ONGLETS, ton, urgence, libelle, to, ageTexte, detailPoste, filtrerPostes, etatHote, points, csvPostes, etatBackuppcHote, detailBackuppc, conseilBackuppc, detailNas } from "./sauvegardesLib.js";

const quand = (at) => { if (!at) return "—"; const s = (Date.now() - Date.parse(at)) / 1000; return s < 3600 ? `il y a ${Math.round(s / 60)} min` : s < 172800 ? `il y a ${Math.round(s / 3600)} h` : `il y a ${Math.round(s / 86400)} j`; };
const pct = (v) => (v == null ? "—" : `${String(Math.round(v * 10) / 10).replace(".", ",")} %`);
const koTo = (k) => (k == null ? "—" : to(k * 1024));

function Etat({ etat, texte }) {
  return <span className={`np-tone ${ton(etat)}`}>{texte || libelle(etat)}</span>;
}

function Compteur({ titre, valeur, etat, sur, onClick }) {
  return (
    <button type="button" className="infra-card" onClick={onClick} style={{ minWidth: 150, textAlign: "left", cursor: "pointer", padding: "8px 12px" }} title={`ouvrir ${titre}`}>
      <div className="infra-muted" style={{ fontSize: 12 }}>{titre}</div>
      <div style={{ fontSize: 22, fontWeight: 600 }}><Etat etat={etat} texte={String(valeur)} />{sur != null && <span className="infra-muted" style={{ fontSize: 13 }}> / {sur}</span>}</div>
    </button>
  );
}

function Ensemble({ ap, aller }) {
  const r = ap.resume || {};
  const pts = points(ap);
  return (
    <>
      <p style={{ margin: "8px 0" }}>Verdict global : <Etat etat={r.verdict} /> <span className="infra-muted">({r.critiques || 0} critique(s), {r.attentions || 0} à surveiller)</span>
        {pts.length > 0 && <BoutonDetail titre="Points à traiter" urgence={urgence(r.verdict)} texte={pts.map((p) => `[${p.etat}] ${p.texte}`).join("\n")} />}</p>
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", margin: "8px 0" }}>
        <Compteur titre="Postes à jour" valeur={r.postes?.ok ?? 0} sur={r.postes?.total ?? 0} etat={(r.postes?.ok ?? 0) === (r.postes?.total ?? 0) ? "ok" : "attention"} onClick={() => aller("postes")} />
        <Compteur titre="Postes jamais sauvegardés" valeur={r.postes?.jamais ?? 0} etat={r.postes?.jamais ? "attention" : "ok"} onClick={() => aller("postes")} />
        <Compteur titre="PBS : groupes en retard" valeur={r.pbs?.en_retard ?? 0} sur={r.pbs?.groupes ?? 0} etat={r.pbs?.en_retard ? "attention" : r.pbs?.serveurs ? "ok" : "non relevé"} onClick={() => aller("pbs")} />
        <Compteur titre="Copies host / VM en échec" valeur={r.copies?.echecs ?? 0} sur={r.copies?.copies ?? 0} etat={r.copies?.echecs ? "critique" : r.copies?.hotes ? "ok" : "non relevé"} onClick={() => aller("copies")} />
        <Compteur titre="VM/CT sans copie fraîche" valeur={r.copies?.invites?.critique ?? 0} etat={r.copies?.invites?.critique ? "critique" : r.copies?.invites?.attention ? "attention" : "ok"} onClick={() => aller("copies")} />
        <Compteur titre="BackupPC : échecs" valeur={ap.backuppc?.serveurs?.length ? ap.backuppc.serveurs.reduce((n, x) => n + (x.echecs || 0), 0) : "non relevé"} sur={ap.backuppc?.serveurs?.length ? ap.backuppc.serveurs.reduce((n, x) => n + (x.hotes || 0), 0) : null} etat={r.backuppc || "non relevé"} onClick={() => aller("backuppc")} />
        <Compteur titre="NAS relevés" valeur={r.nas?.total ?? 0} etat={r.nas?.total ? "ok" : "non relevé"} onClick={() => aller("nas")} />
      </div>
      <h4 style={{ marginBottom: 4 }}>À traiter en premier</h4>
      {pts.length === 0 ? <p className="infra-muted">Rien à signaler.</p> : (
        <ul style={{ margin: 0, paddingLeft: 18 }}>{pts.slice(0, 12).map((p, i) => <li key={i}><Etat etat={p.etat} texte={p.etat} /> {p.texte} <button type="button" className="secondary" style={{ padding: "0 6px", fontSize: 12 }} onClick={() => aller(p.onglet)}>voir</button></li>)}
          {pts.length > 12 && <li className="infra-muted">… {pts.length - 12} de plus (mini bouton ci-dessus : liste complète copiable)</li>}</ul>
      )}
      <h4 style={{ marginBottom: 4 }}>Espaces de sauvegarde</h4>
      <table className="infra-table"><thead><tr><th>Espace</th><th>Quoi</th><th>État</th><th>Relevé</th><th>Détail</th></tr></thead><tbody>
        {(ap.pbs || []).map((b) => <tr key={b.agent_id}><td>PBS {b.serveur}</td><td>{b.groupes} groupe(s) · {b.datastores.map((d) => `${d.nom} ${pct(d.pct)}`).join(", ") || "—"}</td><td><Etat etat={b.etat} /></td><td>{quand(b.at)}</td><td><a href={hubLink("infra", {})}>Infra PVE / PBS</a></td></tr>)}
        {(ap.copies?.hotes || []).map((h) => <tr key={h.agent_id}><td>copies tirées {h.hote}</td><td>{h.copies} copie(s), libre {to(h.libre)}</td><td><Etat etat={etatHote(h)} /></td><td>{quand(h.at)}</td><td><a href={hubLink("pve-maint", {})}>Maintenance PVE</a> · <a href={hubLink("migration", { page: "copies" })}>inventaire des copies</a></td></tr>)}
        {(ap.nas || []).map((n) => <tr key={n.nom}><td>NAS {n.nom}</td><td>{n.volumes.map((v) => `${v.nom} ${pct(v.pct)}`).join(", ") || "—"}</td><td><Etat etat={n.etat} /></td><td>{quand(n.at)}</td><td><a href={hubLink("nas", {})}>NAS</a></td></tr>)}
        {(ap.backuppc?.serveurs || []).length ? ap.backuppc.serveurs.map((srv) => <tr key={srv.agent_id}><td>BackupPC {srv.serveur}</td><td>{srv.hotes} hôte(s), {srv.echecs} échec(s), pool {pct(srv.pool_pct)}</td><td><Etat etat={srv.etat} /></td><td>{quand(srv.at)}</td><td><button type="button" className="secondary" style={{ padding: "0 6px", fontSize: 12 }} onClick={() => aller("backuppc")}>onglet BackupPC</button></td></tr>)
          : <tr><td>BackupPC</td><td className="infra-muted">{ap.backuppc?.message}</td><td><Etat etat={ap.backuppc?.etat} /></td><td>—</td><td>—</td></tr>}
        <tr><td>Hub (si-hub lui-même)</td><td className="infra-muted">base, réglages, journaux</td><td>—</td><td>—</td><td><a href={hubLink("backup-restore", {})}>Sauvegardes du hub</a></td></tr>
      </tbody></table>
    </>
  );
}

function Postes({ postes }) {
  const [filtre, setFiltre] = useState("a-traiter");
  const l = filtrerPostes(postes, filtre);
  const exporter = () => {
    try {
      const blob = new Blob([csvPostes(l)], { type: "text/csv;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = "sauvegardes-postes.csv";
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch { /* téléchargement indisponible */ }
  };
  return (
    <>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", margin: "8px 0" }}>
        <span className="infra-muted">Sauvegarde des confs logicielles et montages (archive → clé USB / partage → PBS). Lancer / régler : fiche de l'agent › Sauvegardes.</span>
        <span style={{ flex: 1 }} />
        {[["a-traiter", "à traiter"], ["ok", "à jour"], ["tous", "tous"]].map(([k, t]) => <button key={k} type="button" className={filtre === k ? "primary" : "secondary"} onClick={() => setFiltre(k)}>{t}</button>)}
        <button type="button" className="secondary" onClick={exporter} disabled={!l.length}>CSV</button>
      </div>
      {l.length === 0 ? <p className="infra-muted">{filtre === "a-traiter" ? "Tous les postes connus sont à jour." : "Aucun poste."}</p> : (
        <table className="infra-table"><thead><tr><th>Poste</th><th>État</th><th>Dernière conf</th><th>Archive</th><th>Destinations</th><th>PBS (pbs10)</th><th>Agir</th></tr></thead><tbody>
          {l.map((p) => <tr key={p.agent_id}>
            <td>{p.hostname} <span className="infra-muted" style={{ fontSize: 12 }}>{p.agent_id !== p.hostname ? p.agent_id : ""}</span></td>
            <td><Etat etat={p.etat} /> <BoutonDetail titre={`${p.hostname} : sauvegarde`} urgence={urgence(p.etat)} texte={detailPoste(p)} /></td>
            <td title={p.at || ""}>{ageTexte(p.age_j)}</td>
            <td>{p.archive ? <>{p.archive} <span className="infra-muted">({to(p.octets)}, {p.confs} conf(s), {p.montages} montage(s))</span></> : "—"}</td>
            <td>{p.destinations_ok?.map((d) => <span key={d} className="np-tone good" style={{ marginRight: 4 }}>{d}</span>)}{p.destinations_ko?.map((d) => <span key={d} className="np-tone bad" style={{ marginRight: 4 }}>{d} ✕</span>)}{!p.destinations_ok?.length && !p.destinations_ko?.length ? "—" : null}</td>
            <td>{p.pbs ? <Etat etat={p.pbs.ok ? "ok" : "critique"} texte={p.pbs.ok ? "poussé" : "échec"} /> : <span className="infra-muted">jamais poussé</span>}</td>
            <td><a href={hubLink("si-agent", { agent: p.agent_id, section: "sauvegardes" })}>fiche › Sauvegardes</a></td>
          </tr>)}
        </tbody></table>
      )}
    </>
  );
}

function Pbs({ pbs }) {
  if (!pbs.length) return <p className="infra-muted">Aucun serveur PBS relevé : activer la sonde <b>pbs</b> sur l'agent de pbs10 (<a href={hubLink("si-agent", { section: "plugins" })}>Agents › Sondes</a>).</p>;
  return pbs.map((b) => (
    <section key={b.agent_id} className="infra-card" style={{ margin: "8px 0" }}>
      <h4 style={{ margin: "0 0 4px" }}>{b.serveur} <Etat etat={b.etat} /> <span className="infra-muted" style={{ fontSize: 12 }}>relevé {quand(b.at)}</span>
        {b.alertes.length > 0 && <BoutonDetail titre={`PBS ${b.serveur} : alertes`} urgence={urgence(b.etat)} texte={b.alertes.join("\n")} />}</h4>
      {b.erreur && <p className="np-tone bad">{b.erreur}</p>}
      <table className="infra-table"><thead><tr><th>Datastore</th><th>Remplissage</th><th>Libre</th><th>Total</th></tr></thead><tbody>
        {b.datastores.map((d) => <tr key={d.nom}><td>{d.nom}</td><td className={d.pct >= 90 ? "np-tone bad" : d.pct >= 80 ? "np-tone warn" : ""}>{pct(d.pct)}</td><td>{to(d.libre)}</td><td>{to(d.total)}</td></tr>)}
      </tbody></table>
      <p style={{ margin: "6px 0 0" }}>{b.groupes} groupe(s) de sauvegarde · {b.en_retard || 0} en retard · {b.inactifs || 0} inactif(s) · détail : <a href={hubLink("infra", {})}>Infra PVE / PBS</a> · <a href={hubLink("pve-maint", {})}>Maintenance PVE</a></p>
      <p className="infra-muted" style={{ margin: "4px 0 0", fontSize: 12 }}>Les archives des postes (onglet Postes) sont poussées dans l'espace de noms <code>postes</code> de ce serveur par son agent.</p>
    </section>
  ));
}

function Copies({ copies }) {
  const hotes = copies?.hotes || [];
  const inv = copies?.invites || {};
  return (
    <>
      <p style={{ margin: "8px 0" }}>VM / CT : <Etat etat="ok" texte={`${inv.ok ?? 0} à jour`} /> · <Etat etat="attention" texte={`${inv.attention ?? 0} à surveiller`} /> · <Etat etat="critique" texte={`${inv.critique ?? 0} sans copie fraîche`} /> · {inv.info ?? 0} copie(s) restaurée(s)
        {" "}— détail par invité : <a href={hubLink("migration", { page: "copies" })}>inventaire des copies</a> (où sont les copies, distance à la source, survie à la perte du nœud).</p>
      {hotes.length === 0 ? <p className="infra-muted">Aucun journal de copies tirées : activer la sonde <b>pulled-backups</b> sur l'hôte de secours (pve-pull-backup.sh / zfs-secours.sh).</p> : (
        <table className="infra-table"><thead><tr><th>Hôte de secours</th><th>État</th><th>Copies</th><th>Échecs</th><th>Absentes</th><th>Plus ancienne</th><th>Libre</th><th>Relevé</th></tr></thead><tbody>
          {hotes.map((h) => { const e = etatHote(h); return <tr key={h.agent_id}><td>{h.hote}</td><td><Etat etat={e} /> {(h.alertes?.length || h.erreur) ? <BoutonDetail titre={`copies ${h.hote}`} urgence={urgence(e)} texte={[h.erreur, ...(h.alertes || [])].filter(Boolean).join("\n")} /> : null}</td>
            <td>{h.copies}</td><td className={h.echecs ? "np-tone bad" : ""}>{h.echecs}</td><td className={h.absentes ? "np-tone bad" : ""}>{h.absentes}</td><td>{h.plus_vieille_h != null ? `${Math.round(h.plus_vieille_h)} h` : "—"}</td><td>{to(h.libre)}</td><td>{quand(h.at)}</td></tr>; })}
        </tbody></table>
      )}
      <p className="infra-muted" style={{ fontSize: 12 }}>Récapitulatif par hôte / VM (sauvegarde on/off, dernière, planification, données / image) : <a href={hubLink("pve-maint", {})}>Maintenance PVE</a> (sauvegardes PBS et tirées) · <a href={hubLink("infra", {})}>Infra PVE / PBS</a>.</p>
    </>
  );
}

const dateU = (t) => (t ? new Date(t * 1000).toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }) : "—");

// #939 : BackupPC -- hôtes, échecs à traiter (conseil + commandes copiables), actions (intervention).
function BackupPc({ b, base, actor, recharger }) {
  const [msg, setMsg] = useState("");
  const [occupe, setOccupe] = useState("");
  const agir = async (agent, action, host) => {
    const lib = { "backup-full": "sauvegarde COMPLÈTE", "backup-incr": "sauvegarde incrémentale", stop: "ARRÊT de la sauvegarde" }[action];
    if (!window.confirm(`${lib} de « ${host} » sur BackupPC ${agent} : confirmer ? (intervention, journalisée)`)) return;
    setOccupe(host + action); setMsg("");
    const r = await runBackuppc(base, agent, { action, host, actor });
    setOccupe("");
    setMsg(r?.error ? `refusé : ${r.error}` : `${lib} de « ${host} » demandée (commande ${r.command}) -- l'état suivra au prochain relevé de la sonde.`);
    if (!r?.error && recharger) setTimeout(recharger, 15000);
  };
  if (!b?.serveurs?.length) return (
    <section className="infra-card" style={{ margin: "8px 0" }}>
      <h4 style={{ margin: "0 0 4px" }}>BackupPC <Etat etat={b?.etat} /></h4>
      <p>{b?.message}</p>
      <p className="infra-muted" style={{ fontSize: 12 }}>Marche à suivre : installer l'agent sur le serveur BackupPC, puis activer la sonde <b>backuppc</b> (<a href={hubLink("si-agent", { section: "plugins" })}>Agents › Sondes</a>, privilégiée : elle lit <code>pc/</code> et interroge <code>BackupPC_serverMesg</code> sous l'utilisateur backuppc). Pour lancer / arrêter des sauvegardes d'ici : Commandes à distance de cet agent en « intervention ».</p>
    </section>);
  return b.serveurs.map((srv) => (
    <section key={srv.agent_id} className="infra-card" style={{ margin: "8px 0" }}>
      <h4 style={{ margin: "0 0 4px" }}>BackupPC {srv.serveur} <Etat etat={srv.etat} /> <span className="infra-muted" style={{ fontSize: 12 }}>version {srv.version || "?"} · {srv.hotes} hôte(s) · {srv.echecs} échec(s) · {srv.en_cours} en cours · pool {pct(srv.pool_pct)}{srv.pool_octets ? ` (${to(srv.pool_octets)})` : ""} · prochain réveil {dateU(srv.prochain_reveil)} · relevé {quand(srv.at)}</span>
        {srv.alertes?.length > 0 && <BoutonDetail titre={`BackupPC ${srv.serveur} : alertes`} urgence={urgence(srv.etat)} texte={srv.alertes.join("\n")} />}</h4>
      {srv.erreur && <p className="np-tone bad">{srv.erreur}</p>}
      {msg && <p className={msg.startsWith("refusé") ? "np-tone bad" : "np-tone good"}>{msg}</p>}
      {srv.echecs_detail?.length > 0 && <>
        <h5 style={{ margin: "8px 0 2px" }}>Échecs à traiter</h5>
        <table className="infra-table"><thead><tr><th>Hôte</th><th>Type</th><th>Dernière tentative</th><th>Erreur</th><th>Dernière réussie</th><th>Que faire</th></tr></thead><tbody>
          {srv.echecs_detail.map((e) => { const c = conseilBackuppc(e.erreur, e.host); return <tr key={e.host}><td>{e.host}</td><td>{e.type || "—"}</td><td>{dateU(e.quand)}</td><td className="np-tone bad">{e.erreur}</td>
            <td className={e.age_h == null || e.age_h > 168 ? "np-tone bad" : ""}>{e.age_h == null ? "jamais" : ageTexte(e.age_h / 24)}</td>
            <td>{c ? <>{c.texte.slice(0, 80)}… <BoutonDetail titre={`${e.host} : que faire`} urgence={e.age_h == null || e.age_h > 168 ? "critique" : "alerte"} texte={`${e.host} -- ${e.erreur}\n\n${c.texte}\n\nCommandes (serveur BackupPC, lecture seule) :\n${c.commandes.join("\n")}`} /></> : "—"}</td></tr>; })}
        </tbody></table></>}
      <h5 style={{ margin: "8px 0 2px" }}>Hôtes sauvegardés</h5>
      <table className="infra-table"><thead><tr><th>Hôte</th><th>État</th><th>Dernière réussie</th><th>Pleine</th><th>Incr.</th><th>Conservées</th><th>Dernière erreur</th><th>Agir (intervention)</th></tr></thead><tbody>
        {(srv.hotes_detail || []).map((h) => { const e = etatBackuppcHote(h); const oc = occupe.startsWith(h.host); return <tr key={h.host}>
          <td>{h.host} {h.en_cours ? <span className="np-tone warn">en cours</span> : null}</td>
          <td><Etat etat={e} /> <BoutonDetail titre={`${h.host} : BackupPC`} urgence={urgence(e)} texte={detailBackuppc(h)} /></td>
          <td title={dateU(h.derniere_bonne)}>{h.age_h == null ? "jamais" : ageTexte(h.age_h / 24)}</td><td>{dateU(h.derniere_pleine)}</td><td>{dateU(h.derniere_incr)}</td>
          <td>{h.sauvegardes ?? 0}{h.pleines != null ? ` (${h.pleines} pleines)` : ""}{h.taille ? ` · ${to(h.taille)}` : ""}</td>
          <td className={h.erreur ? "np-tone bad" : ""} style={{ fontSize: 12 }}>{h.erreur || "—"}</td>
          <td style={{ whiteSpace: "nowrap" }}>
            {h.en_cours ? <button type="button" className="secondary" disabled={!!oc} onClick={() => agir(srv.agent_id, "stop", h.host)}>Arrêter</button>
              : <><button type="button" className="secondary" disabled={!!oc} onClick={() => agir(srv.agent_id, "backup-incr", h.host)}>Incrémentale</button>{" "}
                <button type="button" className="secondary" disabled={!!oc} onClick={() => agir(srv.agent_id, "backup-full", h.host)}>Complète</button></>}
          </td></tr>; })}
      </tbody></table>
      <p className="infra-muted" style={{ fontSize: 12, margin: "6px 0 0" }}>Files : {Object.entries(srv.files || {}).map(([k, v]) => `${k} ${v}`).join(" · ") || "—"}. Les actions passent par l'agent du serveur (BackupPC_serverMesg) et exigent « intervention » dans ses Commandes à distance ; la sauvegarde elle-même se suit ici au relevé suivant (15 min) ou dans l'interface BackupPC.</p>
    </section>
  ));
}

// #939 : NAS -- volumes (SNMP), snapshots / Time Machine / RAID / partages / outils (SSH, lecture seule).
function Nas({ nas }) {
  if (!nas.length) return <p className="infra-muted">Aucun NAS relevé : activer la sonde <b>nas-snmp</b> (<a href={hubLink("nas", {})}>tuile NAS</a>) et, pour les snapshots et Time Machine, la sonde <b>nas-qnap</b> (SSH, clé sans mot de passe, fichier /etc/si-agent/nas-qnap.json sur l'hôte de l'agent).</p>;
  return nas.map((n) => (
    <section key={n.nom} className="infra-card" style={{ margin: "8px 0" }}>
      <h4 style={{ margin: "0 0 4px" }}>{n.nom} <Etat etat={n.etat} /> <BoutonDetail titre={`NAS ${n.nom}`} urgence={urgence(n.etat)} texte={detailNas(n)} /> <span className="infra-muted" style={{ fontSize: 12 }}>
        {n.ssh?.systeme?.modele ? `${n.ssh.systeme.modele} · QTS ${n.ssh.systeme.version || "?"} · ` : ""}relevé par {n.relais} {quand(n.at)}{n.ssh?.ok ? ` · SSH par ${n.ssh.relais} ${quand(n.ssh.at)}` : ""} · <a href={hubLink("nas", {})}>détail NAS (disques, RAID, évolution)</a></span></h4>
      {n.erreur && <p className="np-tone bad">{n.erreur}</p>}
      {n.ssh?.ok === false && <p className="np-tone warn">SSH : {n.ssh.erreur} -- vérifier la clé et /etc/si-agent/nas-qnap.json sur l'hôte de l'agent {n.ssh.relais}.</p>}
      <div style={{ display: "flex", gap: 24, flexWrap: "wrap", alignItems: "flex-start" }}>
        <div><h5 style={{ margin: "6px 0 2px" }}>Volumes</h5>
          <table className="infra-table"><thead><tr><th>Volume</th><th>Remplissage</th><th>Libre</th><th>Taille</th><th>Snapshots</th></tr></thead><tbody>
            {n.volumes.map((v, i) => { const sn = (n.snapshots || []).find((x) => x.volume === v.nom || (x.montage || "").endsWith(v.nom)); return <tr key={i}><td>{v.nom}</td><td className={v.pct >= 95 ? "np-tone bad" : v.pct >= 85 ? "np-tone warn" : ""}>{pct(v.pct)}</td><td>{koTo(v.libre_ko)}</td><td>{koTo(v.ko)}</td>
              <td>{n.snapshots == null ? <span className="infra-muted">SSH non relevé</span> : sn && sn.nombre ? <span className={sn.dernier_age_h > 48 ? "np-tone warn" : "np-tone good"}>{sn.nombre}, dernier il y a {Math.round(sn.dernier_age_h ?? 0)} h</span> : <span className="np-tone warn">aucun</span>}</td></tr>; })}
          </tbody></table></div>
        {n.snapshots != null && <div><h5 style={{ margin: "6px 0 2px" }}>Time Machine</h5>
          {n.timemachine?.length ? <table className="infra-table"><thead><tr><th>Mac</th><th>Dernière écriture</th><th>Taille</th></tr></thead><tbody>
            {n.timemachine.map((t) => <tr key={t.chemin}><td title={t.chemin}>{t.machine}</td><td className={t.age_h > 168 ? "np-tone warn" : ""}>{ageTexte(t.age_h / 24)}</td><td>{t.ko ? to(t.ko * 1024) : "—"}</td></tr>)}
          </tbody></table> : <p className="infra-muted">aucune sauvegarde Time Machine trouvée{n.ssh?.partages_timemachine?.length ? ` (partage(s) déclaré(s) : ${n.ssh.partages_timemachine.join(", ")})` : ""}</p>}
          <h5 style={{ margin: "6px 0 2px" }}>RAID</h5>
          {(n.ssh?.raid || []).map((r) => <div key={r.dev} className={r.degrade ? "np-tone bad" : ""}>{r.dev} : {r.niveau} · {r.degrade ? `DÉGRADÉ ${r.etat}` : r.etat || "ok"} · {(r.disques || []).length} disque(s)</div>)}
        </div>}
        {n.ssh?.ok && <div><h5 style={{ margin: "6px 0 2px" }}>Partages ({n.ssh.partages.length})</h5>
          <div style={{ maxHeight: 180, overflow: "auto", fontSize: 12 }}>{n.ssh.partages.map((p) => <div key={p.nom}>{p.nom}{p.timemachine ? " · Time Machine" : ""}{p.lecture_seule ? " · lecture seule" : ""}{p.navigable ? "" : " · caché"} <span className="infra-muted">{p.chemin}</span></div>)}</div>
          <h5 style={{ margin: "6px 0 2px" }}>Outils de sauvegarde détectés</h5>
          <div style={{ fontSize: 12 }}>{n.ssh.outils.length ? n.ssh.outils.join(" · ") : "aucun (HBS / RTRR non trouvés)"}</div>
          <p className="infra-muted" style={{ fontSize: 12 }}>Gestion à distance (prendre un snapshot, lancer une tâche HBS) : à brancher sur les outils détectés ci-dessus, après essai en lecture -- rien n'est modifié sur le NAS pour l'instant.</p>
        </div>}
      </div>
    </section>
  ));
}

export default function SauvegardesView({ onBack, siAgentApiBase, actor }) {
  const [params] = useState(() => { const p = viewParams(); clearViewParams(); return p; });
  const [onglet, setOnglet] = useState(ONGLETS.some(([id]) => id === params.onglet) ? params.onglet : "ensemble");
  const [ap, setAp] = useState(null);
  const [err, setErr] = useState("");
  const load = useCallback(() => fetchSauvegardesApercu(siAgentApiBase).then((d) => { setAp(d); setErr(""); }).catch((e) => setErr(String(e?.message || e))), [siAgentApiBase]);
  useEffect(() => { load(); const t = setInterval(load, 120000); return () => clearInterval(t); }, [load]);
  return (
    <div className="infra-page">
      <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
        {onBack && <button type="button" className="secondary" onClick={onBack}>◀ Retour</button>}
        <h2 style={{ margin: 0 }}>Sauvegardes</h2>
        <span className="infra-muted">vue d'ensemble, lecture seule -- postes, PBS, copies host/VM, BackupPC, NAS</span>
        <span style={{ flex: 1 }} />
        <button type="button" className="secondary" onClick={load}>Rafraîchir</button>
      </div>
      <div role="tablist" style={{ display: "flex", gap: 6, flexWrap: "wrap", margin: "10px 0" }}>
        {ONGLETS.map(([id, t]) => <button key={id} role="tab" type="button" aria-selected={onglet === id} className={onglet === id ? "primary" : "secondary"} onClick={() => setOnglet(id)}>{t}</button>)}
      </div>
      {err && <p className="np-tone bad">{err}</p>}
      {ap === null ? <p className="infra-muted">lecture…</p> : (
        onglet === "postes" ? <Postes postes={ap.postes || []} />
          : onglet === "pbs" ? <Pbs pbs={ap.pbs || []} />
            : onglet === "copies" ? <Copies copies={ap.copies} />
              : onglet === "backuppc" ? <BackupPc b={ap.backuppc} base={siAgentApiBase} actor={actor} recharger={load} />
                : onglet === "nas" ? <Nas nas={ap.nas || []} />
                  : <Ensemble ap={ap} aller={setOnglet} />
      )}
    </div>
  );
}
