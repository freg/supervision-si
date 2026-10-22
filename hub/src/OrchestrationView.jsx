// #832 Tuile « Orchestration » -- un « OpenStack » maison : machines virtuelles (Proxmox, vues de l'infrastructure ;
// création depuis les modèles du banc) et conteneurs (k3s, Nomad) des hôtes supervisés -- clusters, nœuds, charges,
// placement automatique, quotas (k3s), durée de vie (TTL, appliquée par la sonde). Ordres : commande « orchestration ».
import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import { fetchImages, fetchImageTags, fetchOrchestration, sendOrchestration } from "./siAgentClient.js";
import { hubLink, viewParams } from "./hubLinks.js";
import BoutonCommande, { suivreCommande, useFinCommandes } from "./BoutonCommande.jsx";

const TABS = [["charges", "Conteneurs"], ["deployer", "Déployer"], ["clusters", "Clusters"], ["vms", "Machines virtuelles"], ["commandes", "Commandes"]];
const MOTEURS = { k3s: "k3s (Kubernetes)", nomad: "Nomad" };
const VIDE = { moteur: "k3s", agent: "auto", nom: "", image: "", repliques: 1, port: "", cpu: 250, memoire: 256, ttl_h: "", espace: "si" };
const quand = (t) => (t ? new Date(typeof t === "number" ? t * 1000 : t).toLocaleString("fr-FR") : "—");
const Ton = ({ ok, children }) => <span className={`np-tone ${ok ? "good" : "bad"}`}>{children}</span>;

// #834 Catalogue d'images : sélection de départ, recherche Docker Hub, étiquettes avec leurs architectures -> formulaire.
function Catalogue({ base, choisir }) {
  const [q, setQ] = useState("");
  const [liste, setListe] = useState(null);
  const [sel, setSel] = useState(null);
  const [tags, setTags] = useState(null);
  const [err, setErr] = useState("");
  const [att, setAtt] = useState(false);
  const chercher = useCallback(async (x) => {
    setAtt(true); setSel(null);
    const r = await fetchImages(base, x);
    setAtt(false);
    if (r?.error) setErr(r.error); else { setListe(r.images); setErr(""); }
  }, [base]);
  useEffect(() => { chercher(""); }, [chercher]);
  async function ouvrir(i) {
    if (sel?.image === i.image) { setSel(null); return; }
    setSel(i); setTags(null);
    const r = await fetchImageTags(base, i.image);
    if (r?.error) setErr(r.error); else setTags(r.tags);
  }
  return (
    <div className="infra-card">
      <div className="veille-ligne"><b>Catalogue d'images</b>
        <input value={q} onChange={(x) => setQ(x.target.value)} onKeyDown={(x) => { if (x.key === "Enter") { x.preventDefault(); chercher(q); } }} placeholder="chercher sur Docker Hub (ex. wordpress)" />
        <button type="button" className={att ? "en-cours" : ""} disabled={att} onClick={() => chercher(q)}>{att ? "recherche…" : "Chercher"}</button>
        {q && <button type="button" className="secondary" onClick={() => { setQ(""); chercher(""); }}>Sélection</button>}</div>
      {err && <p className="infra-error">{err}</p>}
      <div className="infra-table-wrap"><table className="infra-table"><thead><tr><th>Image</th><th>Usage</th><th>Téléchargements</th><th>Port</th></tr></thead>
        <tbody>{(liste || []).map((i) => (
          <Fragment key={i.image}>
            <tr onClick={() => ouvrir(i)} style={{ cursor: "pointer" }}>
              <td><b>{i.image}</b>{i.officielle && <span className="np-tone good"> officielle</span>}</td><td className="infra-muted">{i.description}</td>
              <td className="infra-muted">{i.telechargements != null ? i.telechargements.toLocaleString("fr-FR") : ""}</td><td>{i.port || "—"}</td></tr>
            {sel?.image === i.image && <tr><td colSpan={4}>
              {!tags ? <span className="infra-muted">étiquettes…</span> : <div className="veille-ligne">{tags.map((t) => (
                <button type="button" key={t.tag} className="secondary" title={`${(t.architectures || []).join(", ")}${t.maj ? ` · ${t.maj.slice(0, 10)}` : ""}`}
                  onClick={() => choisir(`${i.image}:${t.tag}`, i.port)}>{t.tag} <small>{(t.architectures || []).filter((a) => /^(amd64|arm64)/.test(a)).map((a) => a.split("/")[0]).join(" ")}</small></button>))}
                {!tags.length && <span className="infra-muted">aucune étiquette</span>}</div>}
            </td></tr>}
          </Fragment>))}
          {liste && !liste.length && <tr><td colSpan={4} className="infra-muted">aucun résultat</td></tr>}</tbody></table></div>
    </div>
  );
}

export default function OrchestrationView({ onBack, siAgentApiBase }) {
  const base = siAgentApiBase;
  const [tab, setTab] = useState(() => { const v = viewParams().tab; return TABS.some(([k]) => k === v) ? v : "charges"; });
  const [d, setD] = useState(null);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [f, setF] = useState(VIDE);
  const [q, setQ] = useState({ agent: "", espace: "si", cpu: 2000, memoire: 4096, pods: 20 });
  const [ouvert, setOuvert] = useState(null);
  const charger = useCallback(async () => { const r = await fetchOrchestration(base); if (r?.error) setErr(r.error); else { setD(r); setErr(""); } }, [base]);
  useEffect(() => { charger(); const t = setInterval(charger, 5000); return () => clearInterval(t); }, [charger]);
  useFinCommandes(d?.commandes, setTab, setMsg, setErr);
  const charges = useMemo(() => (d?.clusters || []).flatMap((c) => ["k3s", "nomad"].flatMap((m) => (c[m]?.charges || []).map((x) => ({ ...x, agent: c.agent_id })))), [d]);
  async function envoyer(body, quoi) {
    const r = await sendOrchestration(base, body);
    if (r?.error) { setErr(r.error); return false; }
    suivreCommande(r.commande);
    setD((x) => x && { ...x, commandes: [{ id: r.commande, agent_id: r.agent, status: "pending", params: body, created_at: new Date().toISOString() }, ...x.commandes] });
    setMsg(`${quoi} : commande ${r.commande} envoyée à ${r.agent} — suivi dans « Commandes »`); setErr(""); charger();
    return true;
  }
  function rejoindre(c, moteur) {
    const serveur = window.prompt(moteur === "k3s" ? "URL du serveur k3s (https://<serveur>:6443) :" : "Adresse du serveur Nomad (port 4647) :", "");
    if (!serveur) return;
    const jeton = moteur === "k3s" ? window.prompt("Jeton de jonction — pas de lien : opération manuelle sur le serveur : sudo cat /var/lib/rancher/k3s/server/node-token", "") : null;
    if (moteur === "k3s" && !jeton) return;
    envoyer({ agent: c.agent_id, action: "rejoindre", moteur, serveur: serveur.trim(), jeton: jeton?.trim() }, `${c.agent_id} rejoint ${serveur}`);
  }
  if (!d) return <div className="infra-root"><p className="infra-muted">{err || "Chargement…"}</p></div>;
  const avec = (m) => d.clusters.filter((c) => c[m]?.installe);
  return (
    <div className="infra-root veille">
      <div className="infra-top">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h2>Orchestration — VM et conteneurs</h2>
        <div className="infra-tabs">{TABS.map(([k, l]) => <button key={k} className={tab === k ? "active" : ""} onClick={() => setTab(k)}>{l}{k === "charges" ? ` (${charges.length})` : ""}</button>)}</div>
      </div>
      {err && <p className="infra-error" onClick={() => setErr("")}>{err}</p>}
      {msg && <p className="infra-muted" onClick={() => setMsg("")}>{msg}</p>}
      <div className="infra-page infra-scroll">
        {!d.clusters.length && <p className="infra-muted">Aucun hôte d'orchestration : activer la sonde « orchestration » sur l'agent d'un hôte —{" "}
          <a href={hubLink("si-agent", {})}>Agents hôtes › choisir l'agent › Sondes</a>, puis onglet Clusters › Installer k3s / Nomad.</p>}
        {tab === "charges" && <div className="infra-table-wrap"><table className="infra-table">
          <thead><tr><th>Charge</th><th>Moteur</th><th>Hôte</th><th>Espace</th><th>Image</th><th>Répliques</th><th>Accès</th><th>Expire</th><th></th></tr></thead>
          <tbody>{charges.map((x) => (
            <tr key={`${x.agent}-${x.moteur}-${x.espace}-${x.nom}`}>
              <td><b>{x.nom}</b>{x.statut && <span className="infra-muted"> · {x.statut}</span>}</td><td>{x.moteur}</td><td>{x.agent}</td><td>{x.espace || "—"}</td><td><code>{x.image || "—"}</code></td>
              <td><Ton ok={x.voulu == null ? x.pret > 0 : x.pret >= x.voulu}>{x.pret}{x.voulu != null ? ` / ${x.voulu}` : ""}</Ton></td>
              <td>{x.acces ? <code>&lt;nœud&gt;:{x.acces}</code> : <span className="infra-muted">{x.moteur === "nomad" ? "port dynamique (allocation)" : "—"}</span>}</td>
              <td>{x.expire ? quand(x.expire) : "jamais"}</td>
              <td className="veille-actions">
                <BoutonCommande className="secondary" cmds={d.commandes} agent={x.agent} critere={{ action: "echelle", moteur: x.moteur, nom: x.nom }} onClick={() => { const n = window.prompt(`Répliques de ${x.nom} :`, String(x.voulu ?? x.pret ?? 1)); if (n !== null) envoyer({ agent: x.agent, action: "echelle", moteur: x.moteur, nom: x.nom, espace: x.espace, repliques: n }, `${x.nom} → ${n} réplique(s)`); }}>Échelle</BoutonCommande>
                <BoutonCommande className="danger" cmds={d.commandes} agent={x.agent} critere={{ action: "supprimer", moteur: x.moteur, nom: x.nom }} onClick={() => window.confirm(`Supprimer ${x.nom} (${x.moteur}, ${x.agent}) ?`) && envoyer({ agent: x.agent, action: "supprimer", moteur: x.moteur, nom: x.nom, espace: x.espace }, `suppression de ${x.nom}`)}>Supprimer</BoutonCommande>
              </td></tr>))}
            {!charges.length && <tr><td colSpan={9} className="infra-muted">Aucune charge : onglet Déployer.</td></tr>}</tbody></table></div>}
        {tab === "deployer" && <Catalogue base={base} choisir={(image, port) => setF((x) => ({ ...x, image, port: x.port || port || "",
          nom: x.nom || image.split(":")[0].split("/").pop().toLowerCase().replace(/[^a-z0-9-]/g, "-").slice(0, 40) }))} />}
        {tab === "deployer" && <form className="veille-form" onSubmit={async (e) => { e.preventDefault(); if (await envoyer(f, `déploiement de ${f.nom}`)) setF({ ...VIDE, moteur: f.moteur }); }}>
          <label>Moteur <select value={f.moteur} onChange={(e) => setF({ ...f, moteur: e.target.value, agent: "auto" })}>{Object.entries(MOTEURS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>
          <label>Hôte <select value={f.agent} onChange={(e) => setF({ ...f, agent: e.target.value })}>
            <option value="auto">placement automatique (le moins chargé)</option>{avec(f.moteur).map((c) => <option key={c.agent_id} value={c.agent_id}>{c.agent_id}{c.online ? "" : " (hors ligne)"}</option>)}</select></label>
          <label>Nom <input value={f.nom} onChange={(e) => setF({ ...f, nom: e.target.value })} placeholder="web-test" required /></label>
          <label>Image <input value={f.image} onChange={(e) => setF({ ...f, image: e.target.value })} placeholder="nginx:1.27-alpine" required /></label>
          <label>Répliques <input type="number" min={0} max={50} value={f.repliques} onChange={(e) => setF({ ...f, repliques: e.target.value })} /></label>
          <label>Port du conteneur <input type="number" min={1} max={65535} value={f.port} onChange={(e) => setF({ ...f, port: e.target.value })} placeholder="80" /></label>
          <label>CPU (millicœurs ; Nomad : MHz) <input type="number" min={10} value={f.cpu} onChange={(e) => setF({ ...f, cpu: e.target.value })} /></label>
          <label>Mémoire (Mio) <input type="number" min={16} value={f.memoire} onChange={(e) => setF({ ...f, memoire: e.target.value })} /></label>
          <label>Espace <input value={f.espace} onChange={(e) => setF({ ...f, espace: e.target.value })} /></label>
          <label>Durée de vie (h, vide = permanente) <input type="number" min={1} value={f.ttl_h} onChange={(e) => setF({ ...f, ttl_h: e.target.value })} /></label>
          <button type="submit" disabled={!avec(f.moteur).length}>Déployer</button>
          {!avec(f.moteur).length && <span className="infra-muted">{MOTEURS[f.moteur]} n'est installé sur aucun hôte : onglet Clusters.</span>}
        </form>}
        {tab === "clusters" && <>
          {d.clusters.map((c) => (
            <div key={c.agent_id} className="infra-card">
              <div className="veille-ligne"><b>{c.agent_id}</b><Ton ok={c.online}>{c.online ? "en ligne" : "hors ligne"}</Ton><span className="infra-muted">relevé {quand(c.at)}</span>
                <BoutonCommande className="secondary" cmds={d.commandes} agent={c.agent_id} critere={{ action: "etat" }} onClick={() => envoyer({ agent: c.agent_id, action: "etat" }, `état de ${c.agent_id}`)}>Relever</BoutonCommande></div>
              {["k3s", "nomad"].map((m) => (
                <div key={m} className="veille-ligne">
                  <b>{MOTEURS[m]}</b>
                  {c[m].installe ? <>
                    {c[m].noeuds.map((n) => <Ton key={n.nom} ok={n.pret}>{n.nom} · {(n.roles || []).join(", ")}{n.version ? ` · ${n.version}` : ""}{n.cpu ? ` · ${n.cpu} CPU` : ""}</Ton>)}
                    <span className="infra-muted">{c[m].charges.length} charge(s)</span>
                    <BoutonCommande className="danger" cmds={d.commandes} agent={c.agent_id} critere={{ action: "desinstaller", moteur: m }} onClick={() => window.confirm(`Désinstaller ${m} de ${c.agent_id} (charges comprises) ?`) && envoyer({ agent: c.agent_id, action: "desinstaller", moteur: m }, `désinstallation de ${m}`)}>Désinstaller</BoutonCommande>
                  </> : <>
                    <span className="infra-muted">non installé</span>
                    <BoutonCommande cmds={d.commandes} agent={c.agent_id} critere={{ action: "installer", moteur: m }} onClick={() => envoyer({ agent: c.agent_id, action: "installer", moteur: m }, `installation de ${m} sur ${c.agent_id}`)}>Installer ({m === "k3s" ? "serveur" : "serveur + client"})</BoutonCommande>
                    <BoutonCommande className="secondary" cmds={d.commandes} agent={c.agent_id} critere={{ action: "rejoindre", moteur: m }} onClick={() => rejoindre(c, m)}>Rejoindre un serveur…</BoutonCommande>
                  </>}
                </div>))}
              {!!c.expirees.length && <p className="infra-muted">Expirées au dernier relevé : {c.expirees.map((x) => `${x.moteur} ${x.nom}${x.ok ? "" : " (échec)"}`).join(", ")}</p>}
            </div>))}
          <form className="veille-form" onSubmit={(e) => { e.preventDefault(); envoyer({ ...q, action: "quota", moteur: "k3s" }, `quota de l'espace ${q.espace}`); }}>
            <b>Quota d'un espace k3s</b>
            <label>Hôte <select value={q.agent} onChange={(e) => setQ({ ...q, agent: e.target.value })} required><option value="">—</option>{avec("k3s").map((c) => <option key={c.agent_id}>{c.agent_id}</option>)}</select></label>
            <label>Espace <input value={q.espace} onChange={(e) => setQ({ ...q, espace: e.target.value })} /></label>
            <label>CPU (millicœurs) <input type="number" value={q.cpu} onChange={(e) => setQ({ ...q, cpu: e.target.value })} /></label>
            <label>Mémoire (Mio) <input type="number" value={q.memoire} onChange={(e) => setQ({ ...q, memoire: e.target.value })} /></label>
            <label>Pods <input type="number" value={q.pods} onChange={(e) => setQ({ ...q, pods: e.target.value })} /></label>
            <button type="submit">Appliquer</button><span className="infra-muted">Nomad : quotas réservés à Nomad Enterprise.</span>
          </form>
        </>}
        {tab === "vms" && <>
          <p className="infra-muted">Créer une VM depuis un modèle (Debian, Ubuntu, Rocky, Windows…) : <a href={hubLink("banc", { tab: "modeles" })}>Banc › Modèles</a> ;
            opérations Proxmox : <a href={hubLink("pve-ops", {})}>Opérations Proxmox</a> ; vue complète : <a href={hubLink("infra", {})}>Infrastructure</a>.</p>
          {d.machines.erreur && <p className="infra-error">{d.machines.erreur}</p>}
          <div className="veille-ligne">{d.machines.nodes.map((n) => <Ton key={n.name} ok={n.ok}>{n.name} · {n.guests?.running ?? 0} / {n.guests?.total ?? 0} en marche</Ton>)}</div>
          <div className="infra-table-wrap"><table className="infra-table">
            <thead><tr><th>VMID</th><th>Nom</th><th>Nœud</th><th>Type</th><th>État</th></tr></thead>
            <tbody>{d.machines.vms.map((v) => <tr key={`${v.node}-${v.vmid}`}><td>{v.vmid}</td><td>{v.name}</td><td>{v.node}</td><td>{v.type}</td><td><Ton ok={v.status === "running"}>{v.status}</Ton></td></tr>)}
              {!d.machines.vms.length && <tr><td colSpan={5} className="infra-muted">Aucune VM remontée (sonde proxmox des nœuds).</td></tr>}</tbody></table></div>
        </>}
        {tab === "commandes" && <div className="infra-table-wrap"><table className="infra-table">
          <thead><tr><th>Quand</th><th>Hôte</th><th>Ordre</th><th>État</th><th></th></tr></thead>
          <tbody>{d.commandes.map((c) => (
            <Fragment key={c.id}>
              <tr><td>{quand(c.created_at)}</td><td>{c.agent_id}</td><td><b>{c.params.action}</b> {c.params.moteur || ""} {c.params.nom || c.params.espace || ""}</td>
                <td><Ton ok={c.status !== "failed" && !c.error}>{c.status}</Ton>{c.error && <span className="infra-muted"> {c.error}</span>}</td>
                <td>{c.sortie && <button className="secondary" onClick={() => setOuvert(ouvert === c.id ? null : c.id)}>Sortie</button>}</td></tr>
              {ouvert === c.id && <tr><td colSpan={5}><pre className="infra-muted" style={{ whiteSpace: "pre-wrap" }}>{c.sortie}</pre></td></tr>}
            </Fragment>))}
            {!d.commandes.length && <tr><td colSpan={5} className="infra-muted">Aucune commande.</td></tr>}</tbody></table></div>}
      </div>
    </div>
  );
}
