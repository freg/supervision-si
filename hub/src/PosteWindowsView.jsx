// #896 : tuile « Postes Windows » -- par poste : ce qu'il faut pour le réinstaller (partages, lecteurs réseau,
// imprimantes, abonnements et licences, comptes de messagerie et agendas, logiciels) et diagnostic d'une panne
// intermittente (évènements critiques, plantages, disques, stabilité) ; résultats des tests de charge à la demande.
import { useCallback, useEffect, useState } from "react";
import { fetchPostesWindows } from "./siAgentClient.js";
import { hubLink } from "./hubLinks.js";
import IpPing from "./IpPing.jsx";

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
    {!charge ? <div className="infra-muted">aucun test lancé — fiche de l'agent › Sondes › <b>poste-charge</b> › Exécuter… (poste très ralenti une dizaine de minutes : prévenir l'utilisateur)</div> : (
      <div>
        <div className={`np-tone ${charge.verdict === "aucun défaut reproduit" ? "good" : "bad"}`}><b>{charge.verdict}</b> · {date(charge.debut || charge.at)}</div>
        <div>Processeur : {charge.processeur?.coeurs} cœurs, {charge.processeur?.duree_s} s, {charge.processeur?.erreurs_calcul} erreur(s) de calcul</div>
        <div>Mémoire : {charge.memoire?.mo} Mo testés sur {charge.memoire?.libre_mo} Mo libres, {charge.memoire?.blocs_errones} bloc(s) erroné(s)</div>
        <div>Disque : {charge.disque?.mo} Mo, écriture {charge.disque?.ecriture_mo_s ?? "?"} Mo/s, lecture {charge.disque?.lecture_mo_s ?? "?"} Mo/s, relecture {charge.disque?.identique === true ? "identique" : charge.disque?.identique === false ? "DIFFÉRENTE" : charge.disque?.erreur || "?"}</div>
        {(charge.temperatures_apres || []).length > 0 && <div>Températures : {(charge.temperatures_avant || []).map((t) => t.celsius).join(" / ") || "?"} °C avant → {charge.temperatures_apres.map((t) => t.celsius).join(" / ")} °C après</div>}
        {(charge.alerts || []).map((a, k) => <div key={k} className={`np-tone ${TON[a.severity] || "neutral"}`}>• {a.message}</div>)}
      </div>)}
  </>);
}

export default function PosteWindowsView({ onBack, siAgentApiBase }) {
  const [liste, setListe] = useState(null);
  const [choix, setChoix] = useState("");
  const [detail, setDetail] = useState(null);
  const [onglet, setOnglet] = useState("diagnostic");
  useEffect(() => { fetchPostesWindows(siAgentApiBase).then((l) => { setListe(l); if (l.length === 1) setChoix(l[0].agent); }); }, [siAgentApiBase]);
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
              <td>{date(p.at)}</td><td>{p.charge ? <span className={`np-tone ${p.charge.verdict === "aucun défaut reproduit" ? "good" : "bad"}`}>{p.charge.verdict}</span> : "—"}</td>
            </tr>))}</tbody></table>
        {detail && (
          <section className="infra-card">
            <h3 style={{ margin: "0 0 6px" }}>{detail.poste?.nom || detail.agent} <span className="infra-muted" style={{ fontSize: 13 }}>· {detail.poste?.systeme} {detail.poste?.version} · démarré le {date(detail.poste?.demarrage)} · {go(detail.poste?.memoire_octets)} de mémoire</span></h3>
            {detail.alertes.map((a, k) => <div key={k} className={`np-tone ${TON[a.severity] || "neutral"}`}>• {a.message}</div>)}
            <div style={{ display: "flex", gap: 8, margin: "10px 0" }}>
              <button className={onglet === "diagnostic" ? "primary" : "secondary"} onClick={() => setOnglet("diagnostic")}>Diagnostic</button>
              <button className={onglet === "reinstallation" ? "primary" : "secondary"} onClick={() => setOnglet("reinstallation")}>Réinstallation</button>
              <button className="secondary" onClick={() => window.print()} title="imprimer ou enregistrer en PDF la fiche affichée">Imprimer</button>
              <button className="secondary" onClick={charger}>⟳</button>
            </div>
            {onglet === "diagnostic" ? <Diagnostic d={detail.diagnostic} charge={detail.charge} /> : <Reinstallation r={detail.reinstallation} />}
          </section>)}
      </>)}
    </div>
  );
}
