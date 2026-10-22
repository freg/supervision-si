// #831 Tuile « Émulation et déploiement supervisé » : hôtes d'émulation (sonde emulation de leur agent), émulateurs
// Raspberry Pi 3 B / Zero W / Zero 2 W (conteneur Raspberry Pi OS en émulation utilisateur, ou machine QEMU complète)
// et Android (API 24 à 35, x86_64 / x86 avec KVM ; arm64 sur hôte ARM), cycle de vie, installation SUPERVISÉE de
// l'agent dans une instance (son enrôlement se voit dans Agents hôtes). Orchestration Proxmox + k3s : tranche suivante.
import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import { fetchEmulation, sendEmulation } from "./siAgentClient.js";
import { hubLink, viewParams } from "./hubLinks.js";

const TABS = [["instances", "Instances"], ["lancer", "Lancer un émulateur"], ["commandes", "Commandes"]];
const ETAT = { en_marche: ["en marche", "good"], demarre: ["démarre", "neutral"], arrete: ["arrêtée", "neutral"], absent: ["absente", "bad"] };
const quand = (t) => (t ? new Date(t).toLocaleString("fr-FR") : "—");
const Oui = ({ v, l }) => <span className={`np-tone ${v ? "good" : "bad"}`}>{v ? "✓" : "✗"} {l}</span>;

export default function EmulationView({ onBack, siAgentApiBase, username }) {
  const base = siAgentApiBase;
  const [tab, setTab] = useState(() => { const v = viewParams().tab; return TABS.some(([k]) => k === v) ? v : "instances"; });
  const [d, setD] = useState(null);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [hote, setHote] = useState("");
  const [famille, setFamille] = useState("raspberry");
  const [modes, setModes] = useState({});
  const [licences, setLicences] = useState(false);
  const [ouvert, setOuvert] = useState(null);
  const charger = useCallback(async () => { const r = await fetchEmulation(base); if (r?.error) setErr(r.error); else { setD(r); setErr(""); } }, [base]);
  useEffect(() => { charger(); const t = setInterval(charger, 10000); return () => clearInterval(t); }, [charger]);
  useEffect(() => { if (d && !hote && d.hotes[0]) setHote(d.hotes[0].agent_id); }, [d, hote]);
  const h = useMemo(() => (d?.hotes || []).find((x) => x.agent_id === hote), [d, hote]);
  async function envoyer(body, quoi) {
    const r = await sendEmulation(base, { ...body, agent: body.agent || hote });
    if (r?.error) { setErr(r.error); return; }
    setMsg(`${quoi} : commande ${r.commande} envoyée${r.instance ? ` (instance ${r.instance}${r.port ? `, port ${r.port}` : ""})` : ""} — suivi dans « Commandes »`);
    charger();
  }
  function installer(a, i) {
    const ligne = window.prompt("Ligne d'installation Linux du central (Agents hôtes › Enrôler un agent › Installation, avec le jeton du site) :", "");
    if (ligne && ligne.trim()) envoyer({ agent: a, action: "deployer_agent", instance: i.id, ligne: ligne.trim() }, `installation de l'agent dans ${i.id}`);
  }
  if (!d) return <div className="infra-root"><p className="infra-muted">{err || "Chargement…"}</p></div>;
  return (
    <div className="infra-root veille">
      <div className="infra-top">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h2>Émulation et déploiement supervisé</h2>
        <div className="infra-tabs">{TABS.map(([k, l]) => <button key={k} className={tab === k ? "active" : ""} onClick={() => setTab(k)}>{l}</button>)}</div>
        <select value={hote} onChange={(e) => setHote(e.target.value)}>{d.hotes.map((x) => <option key={x.agent_id} value={x.agent_id}>{x.agent_id}{x.online ? "" : " (hors ligne)"}</option>)}</select>
      </div>
      {err && <p className="infra-error" onClick={() => setErr("")}>{err}</p>}
      {msg && <p className="infra-muted" onClick={() => setMsg("")}>{msg}</p>}
      <div className="infra-page infra-scroll">
        {!d.hotes.length && <p className="infra-muted">Aucun hôte d'émulation : activer la sonde « emulation » sur l'agent d'un hôte (Docker, QEMU, KVM pour Android) —{" "}
          <a href={hubLink("si-agent", {})}>Agents hôtes › choisir l'agent › Sondes</a>.</p>}
        {h && <div className="veille-ligne">
          <b>{h.agent_id}</b><span className="infra-muted">{h.capacites.arch || "?"} · relevé {quand(h.at)}</span>
          <Oui v={h.capacites.docker} l="Docker" /><Oui v={h.capacites.qemu_arm && h.capacites.qemu_aarch64} l="QEMU système" /><Oui v={h.capacites.kvm} l="KVM" />
          <Oui v={h.capacites.java && h.capacites.sdk_android} l="SDK Android" />
          <span className="infra-muted">images Raspberry : {(h.capacites.images_raspberry || []).join(", ") || "aucune"} · Android : {(h.capacites.images_android || []).join(", ") || "aucune"}</span>
        </div>}
        {tab === "instances" && h && <div className="infra-table-wrap"><table className="infra-table">
          <thead><tr><th>Instance</th><th>Profil</th><th>Mode</th><th>État</th><th>Accès</th><th>Créée</th><th></th></tr></thead>
          <tbody>{h.instances.map((i) => (
            <tr key={i.id}><td>{i.id}</td><td>{i.profil}</td><td>{i.mode}</td>
              <td><span className={`np-tone ${(ETAT[i.etat] || ["", "neutral"])[1]}`}>{(ETAT[i.etat] || [i.etat])[0]}</span>{i.docker ? <span className="infra-muted"> {i.docker}</span> : null}</td>
              <td className="infra-muted">{i.mode === "systeme" ? `ssh -p ${i.port} emul@127.0.0.1 (sur l'hôte)` : i.mode === "avd" ? `adb -s emulator-${i.port}` : `docker exec -it ${i.id} bash`}</td>
              <td className="infra-muted">{i.cree ? new Date(i.cree * 1000).toLocaleString("fr-FR") : "—"}</td>
              <td><div className="veille-actions">
                {i.mode === "conteneur" && <button type="button" onClick={() => installer(h.agent_id, i)} title="installation supervisée de l'agent dans l'instance">Installer l'agent</button>}
                <button type="button" className="secondary" onClick={() => envoyer({ action: "arreter", instance: i.id }, `arrêt de ${i.id}`)}>Arrêter</button>
                <button type="button" className="secondary" onClick={() => window.confirm(`Détruire ${i.id} (disque et état) ?`) && envoyer({ action: "detruire", instance: i.id }, `destruction de ${i.id}`)}>Détruire</button>
              </div></td></tr>))}
            {!h.instances.length && <tr><td colSpan={7} className="infra-muted">Aucune instance : onglet « Lancer un émulateur ».</td></tr>}
          </tbody></table></div>}
        {tab === "lancer" && h && <>
          <div className="veille-ligne">
            {[["raspberry", "Raspberry Pi"], ["android", "Android"]].map(([k, l]) => <button key={k} type="button" className={famille === k ? "" : "secondary"} onClick={() => setFamille(k)}>{l}</button>)}
            {famille === "android" && <label><input type="checkbox" checked={licences} onChange={(e) => setLicences(e.target.checked)} /> j'accepte les licences du SDK Android (sdkmanager --licenses)</label>}
          </div>
          <p className="infra-muted">{famille === "raspberry"
            ? "Conteneur : Raspberry Pi OS Lite officiel (empreinte vérifiée) en émulation utilisateur — rapide, pour l'agent et son installation (armv6 pour la Zero W). Machine complète : QEMU raspi3b / raspi0, noyau de l'image, SSH sur 127.0.0.1 de l'hôte — lent, démarrage réel."
            : "Émulateur Android officiel sans fenêtre : x86_64 / x86 avec KVM sur hôte x86 (Android 11+ x86_64 exécute aussi le code ARM des applications) ; arm64 seulement sur un hôte ARM."}
            {" "}« Préparer » télécharge et prépare une fois ; « Lancer » prépare au besoin puis démarre une instance.</p>
          <div className="infra-table-wrap"><table className="infra-table">
            <thead><tr><th>Profil</th><th>Architecture</th><th>Mode</th><th>Disponible</th><th></th></tr></thead>
            <tbody>{h.profils.filter((p) => p.famille === famille).map((p) => {
              const mode = modes[p.id] || p.modes[0];
              const ok = p.disponible && (famille === "raspberry" || licences);
              return (
                <tr key={p.id}><td>{p.titre}</td><td className="infra-muted">{p.arch}</td>
                  <td>{p.modes.length > 1 ? <select value={mode} onChange={(e) => setModes({ ...modes, [p.id]: e.target.value })}>{p.modes.map((m) => <option key={m} value={m}>{m === "systeme" ? "machine complète" : m}</option>)}</select> : mode}</td>
                  <td>{p.disponible ? <span className="np-tone good">oui</span> : <span className="np-tone bad" title={p.raison}>non — {p.raison}</span>}</td>
                  <td><div className="veille-actions">
                    <button type="button" className="secondary" disabled={!ok} onClick={() => envoyer({ action: "preparer", profil: p.id, mode, accepter_licences: licences }, `préparation ${p.titre}`)}>Préparer</button>
                    <button type="button" disabled={!ok} onClick={() => envoyer({ action: "lancer", profil: p.id, mode, accepter_licences: licences }, `lancement ${p.titre}`)}>Lancer</button>
                  </div></td></tr>);
            })}</tbody></table></div>
        </>}
        {tab === "commandes" && <div className="infra-table-wrap"><table className="infra-table">
          <thead><tr><th>Demandée</th><th>Hôte</th><th>Action</th><th>Cible</th><th>État</th><th>Détail</th></tr></thead>
          <tbody>{d.commandes.map((c) => (
            <Fragment key={c.id}>
              <tr onClick={() => setOuvert(ouvert === c.id ? null : c.id)} style={{ cursor: "pointer" }}>
                <td className="infra-muted">{quand(c.created_at)}</td><td>{c.agent_id}</td><td>{c.params?.action}</td><td>{c.params?.instance || c.params?.profil || "—"}</td>
                <td><span className={`np-tone ${c.status === "done" ? "good" : c.status === "failed" ? "bad" : "neutral"}`}>{c.status === "done" ? "fait" : c.status === "failed" ? "échec" : "en cours"}</span></td>
                <td className="infra-muted">{c.error || (c.sortie || "").split("\n").filter(Boolean).slice(-1)[0] || "—"}</td></tr>
              {ouvert === c.id && c.sortie && <tr><td colSpan={6}><pre className="veille-ia">{c.sortie}</pre></td></tr>}
            </Fragment>))}
            {!d.commandes.length && <tr><td colSpan={6} className="infra-muted">Aucune commande.</td></tr>}
          </tbody></table></div>}
      </div>
    </div>
  );
}
