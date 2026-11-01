// #825 Agents hôtes › Banc d'installation (BACKLOG 133) : pool de VM de test (nœud Proxmox, plage de vmid, modèles
// Linux / Windows avec l'agent invité QEMU) ; un passage par modèle : cloner -> démarrer -> attendre l'invité ->
// installer -> vérifier -> désinstaller -> arrêter -> détruire. Un échec saute au nettoyage : aucune VM de banc ne reste.
import { useCallback, useEffect, useState } from "react";
import { fetchBanc, saveBancPool, startBanc, stopBancRun, purgeBanc } from "./siAgentClient.js";

const TON = { fait: "good", en_cours: "neutral", attente: "neutral", saute: "neutral", echec: "bad" };
const MOT = { fait: "fait", en_cours: "en cours", attente: "—", saute: "sauté", echec: "échec" };
const quand = (t) => (t ? new Date(t * 1000).toLocaleString("fr-FR") : "—");
const EXEMPLE = {
  noeud: "pve-banc", vmid_min: 9500, vmid_max: 9599, stockage: "", complet: false,
  modeles: [{ nom: "debian13", os: "linux", vmid: 9000 }, { nom: "w11", os: "windows", vmid: 9001 }],
  commandes: {
    linux: { installer: "curl -fsSL -k 'https://<central local>:6445/deploy/linux?token=<jeton>' | sh" },
    windows: { installer: "msiexec /i C:\\banc\\si-agent.msi /qn CENTRAL=https://<central>/api/si-agent TOKEN=<jeton> CAFINGERPRINT=<empreinte>" },
  },
};

export default function BancSection({ base }) {
  const [d, setD] = useState(null);
  const [err, setErr] = useState(null);
  const [edit, setEdit] = useState(null);
  const [ouvert, setOuvert] = useState(null);
  const load = useCallback(async () => { const r = await fetchBanc(base); if (r?.error) setErr(r.error); else { setD(r); setErr(null); } }, [base]);
  useEffect(() => { load(); const t = setInterval(load, 15000); return () => clearInterval(t); }, [load]);
  const act = async (p) => { const r = await p; if (r?.error) setErr(r.error); else load(); };
  async function enregistrer() {
    let pool;
    try { pool = JSON.parse(edit); } catch (e) { setErr(`JSON invalide : ${e.message}`); return; }
    const r = await saveBancPool(base, pool);
    if (r?.error) setErr(r.error); else { setEdit(null); load(); }
  }
  if (!d) return <p className="muted">{err || "Chargement du banc…"}</p>;
  const p = d.pool;
  return (
    <div className="infra-card">
      <div className="veille-ligne"><h3 style={{ margin: 0 }}>Banc d'installation des agents</h3>
        <span className="infra-muted">{p ? `nœud ${p.noeud} · clones ${p.vmid_min}–${p.vmid_max} · ${p.modeles.length} modèle(s)` : "pool non configuré"}</span>
        <span style={{ flex: 1 }} />
        <button type="button" className="secondary" onClick={() => setEdit(JSON.stringify(p || EXEMPLE, null, 2))}>{p ? "Régler le pool" : "Configurer le pool"}</button>
        {p && <button type="button" onClick={() => act(startBanc(base, null))}>Tout lancer</button>}
        <button type="button" className="secondary" disabled={!d.runs.some((r) => r.fin)} onClick={() => act(purgeBanc(base))}>Effacer les passages terminés</button>
      </div>
      <p className="infra-muted">Préparer sur le nœud des modèles de VM (Proxmox « template ») avec l'agent invité QEMU activé (Linux : qemu-guest-agent ;
        Windows : pilotes VirtIO + guest agent). L'exécution dans l'invité est refusée par l'agent du nœud si la VM ne s'appelle pas « banc-… ».
        Réseau isolé conseillé ; les jetons d'enrôlement sont masqués à l'affichage (pas de lien : préparation des modèles manuelle sur le nœud).</p>
      {err && <p className="infra-error" onClick={() => setErr(null)}>{err}</p>}
      {edit != null && (
        <div className="veille-bloc">
          <p className="infra-muted">Pool en JSON : noeud (agent du nœud), vmid_min / vmid_max (clones), stockage, complet (clone complet au lieu de lié), modeles
            (nom, os linux | windows, vmid du modèle), commandes par OS (installer, verifier, desinstaller — vides : valeurs par défaut). Un jeton laissé « ••• » garde l'ancien.</p>
          <textarea rows={18} style={{ width: "100%", fontFamily: "monospace" }} value={edit} onChange={(e) => setEdit(e.target.value)} />
          <div className="veille-ligne"><button type="button" onClick={enregistrer}>Enregistrer</button><button type="button" className="secondary" onClick={() => setEdit(null)}>Annuler</button></div>
        </div>)}
      {p && <div className="veille-ligne">{p.modeles.map((m) => <button key={m.nom} type="button" className="secondary" onClick={() => act(startBanc(base, [m.nom]))}>Lancer {m.nom} ({m.os})</button>)}</div>}
      <div className="infra-table-wrap"><table className="infra-table">
        <thead><tr><th>Passage</th><th>Modèle</th><th>Clone</th><th>Début</th>{d.etapes.map((e) => <th key={e.id} title={e.libelle}>{e.libelle}</th>)}<th>Résultat</th><th></th></tr></thead>
        <tbody>
          {d.runs.map((r) => (
            <tr key={r.id}>
              <td>{r.nom}</td><td>{r.modele} ({r.os})</td><td className="infra-muted">{r.vmid}</td><td className="infra-muted">{quand(r.debut)}</td>
              {r.etapes.map((e) => <td key={e.id}><span className={`np-tone ${TON[e.etat] || "neutral"}`} title={e.detail || ""} onClick={() => setOuvert(ouvert === `${r.id}-${e.id}` ? null : `${r.id}-${e.id}`)}>{MOT[e.etat] || e.etat}</span>
                {ouvert === `${r.id}-${e.id}` && e.detail && <pre className="veille-ia">{e.detail}</pre>}</td>)}
              <td className={r.echec ? "infra-status critical" : r.fin ? "infra-status good" : ""}>{r.resultat}</td>
              <td>{!r.fin && <button type="button" className="secondary" title="arrêter et nettoyer (arrêt puis destruction du clone)" onClick={() => act(stopBancRun(base, r.id))}>Arrêter</button>}</td>
            </tr>))}
          {!d.runs.length && <tr><td colSpan={6 + d.etapes.length} className="infra-muted">Aucun passage.</td></tr>}
        </tbody>
      </table></div>
    </div>
  );
}
