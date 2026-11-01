// #826 Tuile « Banc d'installation » (BACKLOG 133) : déployer et gérer le pool de VM de test des agents.
//   - Modèles de VM : fabriquer sur le nœud un modèle Linux depuis l'image cloud officielle (empreinte vérifiée, agent
//     invité QEMU, cloud-init), voir les modèles présents, les ajouter au pool ; Windows : marche à suivre ;
//   - Pool et passages : réglage du pool, lancement, suivi étape par étape (BancSection, #825).
import { useCallback, useEffect, useState } from "react";
import { fetchBanc, buildBancTemplate, saveBancPool } from "./siAgentClient.js";
import BancSection from "./BancSection.jsx";
import { viewParams } from "./hubLinks.js";

const TABS = [["modeles", "Modèles de VM"], ["passages", "Pool et passages"], ["windows", "Modèles Windows"]];
const quand = (t) => (t ? new Date(t).toLocaleString("fr-FR") : "—");

function Modeles({ base }) {
  const [d, setD] = useState(null);
  const [err, setErr] = useState(null);
  const [msg, setMsg] = useState("");
  const [f, setF] = useState({ recette: "debian13", vmid: 9000, stockage: "local-lvm", pont: "vmbr0", disque_go: 12, autoriser_snippets: false });
  const load = useCallback(async () => { const r = await fetchBanc(base); if (r?.error) setErr(r.error); else { setD(r); setErr(null); } }, [base]);
  useEffect(() => { load(); const t = setInterval(load, 15000); return () => clearInterval(t); }, [load]);
  async function fabriquer() {
    const r = await buildBancTemplate(base, f);
    if (r?.error) setErr(r.error); else { setMsg(`commande ${r.commande} envoyée à ${r.noeud} : téléchargement, vérification puis création du modèle (quelques minutes)`); load(); }
  }
  async function ajouter(m) {
    const p = d.pool;
    if (!p) { setErr("configurer d'abord le pool (onglet Pool et passages)"); return; }
    const nom = (m.recette || m.nom.replace(/^banc-modele-/, "")).toLowerCase().replace(/[^a-z0-9-]/g, "-").slice(0, 31);
    const r = await saveBancPool(base, { ...p, modeles: [...p.modeles.filter((x) => x.vmid !== m.vmid), { nom, os: m.os, vmid: m.vmid }] });
    if (r?.error) setErr(r.error); else { setMsg(`modèle ${m.vmid} ajouté au pool (${nom}, ${m.os})`); load(); }
  }
  if (!d) return <p className="infra-muted">{err || "Chargement…"}</p>;
  const auPool = new Set((d.pool?.modeles || []).map((m) => m.vmid));
  return (
    <>
      {err && <p className="infra-error" onClick={() => setErr(null)}>{err}</p>}
      {msg && <p className="infra-muted" onClick={() => setMsg("")}>{msg}</p>}
      <div className="infra-card">
        <h3>Fabriquer un modèle Linux sur le nœud {d.pool?.noeud || "(pool à configurer)"}</h3>
        <p className="infra-muted">Image cloud officielle, empreinte vérifiée contre le fichier de sommes de l'éditeur, VM avec l'agent invité QEMU (installé
          au premier démarrage par cloud-init), disque agrandi, puis transformée en modèle. Le stockage « local » doit accepter les snippets
          (case ci-dessous pour l'activer).</p>
        <div className="veille-ligne">
          <select value={f.recette} onChange={(e) => setF({ ...f, recette: e.target.value })}>{d.recettes.map((r) => <option key={r.id} value={r.id}>{r.titre}</option>)}</select>
          <label>vmid <input type="number" value={f.vmid} onChange={(e) => setF({ ...f, vmid: Number(e.target.value) })} style={{ width: 90 }} /></label>
          <label>stockage <input value={f.stockage} onChange={(e) => setF({ ...f, stockage: e.target.value })} style={{ width: 110 }} /></label>
          <label>pont <input value={f.pont} onChange={(e) => setF({ ...f, pont: e.target.value })} style={{ width: 80 }} /></label>
          <label>disque (Go) <input type="number" value={f.disque_go} onChange={(e) => setF({ ...f, disque_go: Number(e.target.value) })} style={{ width: 60 }} /></label>
          <label><input type="checkbox" checked={f.autoriser_snippets} onChange={(e) => setF({ ...f, autoriser_snippets: e.target.checked })} /> activer les snippets sur « local »</label>
          <button type="button" disabled={!d.pool} onClick={fabriquer}>Fabriquer</button>
        </div>
      </div>
      <div className="infra-card">
        <h3>Modèles présents sur le nœud</h3>
        <div className="infra-table-wrap"><table className="infra-table">
          <thead><tr><th>vmid</th><th>Nom</th><th>OS</th><th>Recette</th><th></th></tr></thead>
          <tbody>
            {d.modeles_noeud.map((m) => (
              <tr key={m.vmid}><td>{m.vmid}</td><td>{m.nom}</td><td>{m.os}</td><td className="infra-muted">{m.recette || "—"}</td>
                <td>{auPool.has(m.vmid) ? <span className="np-tone good">au pool</span> : <button type="button" className="secondary" onClick={() => ajouter(m)}>Ajouter au pool</button>}</td></tr>))}
            {!d.modeles_noeud.length && <tr><td colSpan={5} className="infra-muted">Aucun modèle vu : la sonde proxmox du nœud doit être active (relevé toutes les 5 min).</td></tr>}
          </tbody>
        </table></div>
      </div>
      <div className="infra-card">
        <h3>Fabrications</h3>
        <div className="infra-table-wrap"><table className="infra-table">
          <thead><tr><th>Demandée</th><th>Recette</th><th>vmid</th><th>État</th><th>Détail</th></tr></thead>
          <tbody>
            {d.fabrications.map((c) => (
              <tr key={c.id}><td className="infra-muted">{quand(c.created_at)}</td><td>{c.params?.recette}</td><td>{c.params?.vmid}</td>
                <td><span className={`np-tone ${c.status === "done" ? "good" : c.status === "failed" ? "bad" : "neutral"}`}>{c.status === "done" ? "prêt" : c.status === "failed" ? "échec" : "en cours"}</span></td>
                <td className="infra-muted">{c.error || (c.stdout || "").split("\n").filter(Boolean).slice(-1)[0] || "—"}</td></tr>))}
            {!d.fabrications.length && <tr><td colSpan={5} className="infra-muted">Aucune.</td></tr>}
          </tbody>
        </table></div>
      </div>
    </>
  );
}

function Windows() {
  return (
    <div className="infra-card">
      <h3>Préparer un modèle Windows (pas de lien : opération manuelle sur le nœud)</h3>
      <ol>
        <li>Déposer sur le stockage ISO du nœud l'ISO Windows (10/11, Server 2019/2022) et l'ISO des pilotes VirtIO (virtio-win).</li>
        <li>Créer la VM : machine q35, BIOS OVMF (UEFI) + TPM pour Windows 11, disque SCSI (VirtIO SCSI), carte réseau VirtIO, <b>agent invité QEMU activé</b>,
          nom <code>banc-modele-w11</code> (ou w10, ws2022…).</li>
        <li>Installer Windows (pilote de disque depuis l'ISO VirtIO), puis depuis l'ISO VirtIO : <code>virtio-win-gt-x64.msi</code> et <code>guest-agent\qemu-ga-x86_64.msi</code>.</li>
        <li>Mises à jour Windows, pare-feu par défaut, aucun compte de domaine ; Sysprep : <code>C:\Windows\System32\Sysprep\sysprep.exe /generalize /oobe /shutdown</code>
          (fichier de réponse pour passer l'OOBE : voir docs/banc-installation.md).</li>
        <li>Sur le nœud : <code>qm template &lt;vmid&gt;</code>. Le modèle apparaît dans l'onglet « Modèles de VM » (OS deviné « windows » par le nom) : « Ajouter au pool ».</li>
        <li>Commande d'installation Windows du pool : ligne PowerShell du central (bouton Installation de la fiche agent) ou MSI
          (<code>msiexec /i … /qn CENTRAL=… TOKEN=…</code>, déposé dans le modèle, voir si-agent/agent/windows/msi/README.md).</li>
      </ol>
    </div>
  );
}

export default function BancView({ onBack, siAgentApiBase }) {
  const [tab, setTab] = useState(() => { const v = viewParams().tab; return TABS.some(([k]) => k === v) ? v : "modeles"; });
  return (
    <div className="infra-root veille">
      <div className="infra-top">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h2>Banc d'installation</h2>
        <div className="infra-tabs">{TABS.map(([k, l]) => <button key={k} className={tab === k ? "active" : ""} onClick={() => setTab(k)}>{l}</button>)}</div>
      </div>
      <div className="infra-page infra-scroll">
        {tab === "modeles" && <Modeles base={siAgentApiBase} />}
        {tab === "passages" && <BancSection base={siAgentApiBase} />}
        {tab === "windows" && <Windows />}
      </div>
    </div>
  );
}
