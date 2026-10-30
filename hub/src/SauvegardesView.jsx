// #937 : tuile « Sauvegardes » -- aperçu central de toutes les sauvegardes du SI (lecture seule : rien n'est lancé d'ici,
// chaque ligne renvoie vers l'endroit qui agit). Onglets : Vue d'ensemble · Postes (sauvegarde de conf par agent + poussée
// PBS) · PBS (pbs10) · Copies host / VM · BackupPC (sonde à venir) · NAS QNAP (volumes ; snapshots / TimeMachine à venir).
// Données : GET /sauvegardes/apercu (si-agent-api). Les info-bulles importantes ont leur mini bouton (fenêtre copiable).
import { useCallback, useEffect, useState } from "react";
import { fetchSauvegardesApercu } from "./siAgentClient.js";
import { hubLink, viewParams, clearViewParams } from "./hubLinks.js";
import BoutonDetail from "./FenetreTexte.jsx";
import { ONGLETS, ton, urgence, libelle, to, ageTexte, detailPoste, filtrerPostes, etatHote, points, csvPostes } from "./sauvegardesLib.js";

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
        <Compteur titre="BackupPC" valeur={r.backuppc || "non relevé"} etat={r.backuppc || "non relevé"} onClick={() => aller("backuppc")} />
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
        <tr><td>BackupPC</td><td className="infra-muted">{ap.backuppc?.message}</td><td><Etat etat={ap.backuppc?.etat} /></td><td>—</td><td>—</td></tr>
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

function BackupPc({ b }) {
  return (
    <section className="infra-card" style={{ margin: "8px 0" }}>
      <h4 style={{ margin: "0 0 4px" }}>BackupPC <Etat etat={b?.etat} /></h4>
      <p>{b?.message}</p>
      <p className="infra-muted" style={{ fontSize: 12 }}>Prévu (#938) : sonde <b>backuppc</b> sur le serveur BackupPC (lecture seule : état des hôtes, dernière complète / incrémentale, erreurs, espace du pool), reprise ici et dans la fiche de chaque poste.</p>
    </section>
  );
}

function Nas({ nas }) {
  if (!nas.length) return <p className="infra-muted">Aucun NAS relevé : activer la sonde <b>nas-snmp</b> (<a href={hubLink("nas", {})}>tuile NAS</a> pour la marche à suivre).</p>;
  return nas.map((n) => (
    <section key={n.nom} className="infra-card" style={{ margin: "8px 0" }}>
      <h4 style={{ margin: "0 0 4px" }}>{n.nom} <Etat etat={n.etat} /> <span className="infra-muted" style={{ fontSize: 12 }}>relevé par {n.relais} {quand(n.at)} · <a href={hubLink("nas", {})}>détail NAS (disques, RAID, évolution)</a></span></h4>
      {n.erreur && <p className="np-tone bad">{n.erreur}</p>}
      <table className="infra-table"><thead><tr><th>Volume</th><th>Remplissage</th><th>Libre</th><th>Taille</th></tr></thead><tbody>
        {n.volumes.map((v, i) => <tr key={i}><td>{v.nom}</td><td className={v.pct >= 95 ? "np-tone bad" : v.pct >= 85 ? "np-tone warn" : ""}>{pct(v.pct)}</td><td>{koTo(v.libre_ko)}</td><td>{koTo(v.ko)}</td></tr>)}
      </tbody></table>
      <p className="infra-muted" style={{ fontSize: 12, margin: "6px 0 0" }}>Snapshots et TimeMachine : connecteur QNAP à venir (lecture seule par SSH / API QTS) -- rien n'est relevé pour l'instant.</p>
    </section>
  ));
}

export default function SauvegardesView({ onBack, siAgentApiBase }) {
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
              : onglet === "backuppc" ? <BackupPc b={ap.backuppc} />
                : onglet === "nas" ? <Nas nas={ap.nas || []} />
                  : <Ensemble ap={ap} aller={setOnglet} />
      )}
    </div>
  );
}
