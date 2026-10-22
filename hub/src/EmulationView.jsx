// #831 Tuile « Émulation et déploiement supervisé » : hôtes d'émulation (sonde emulation de leur agent), émulateurs
// Raspberry Pi 3 B / Zero W / Zero 2 W (conteneur Raspberry Pi OS en émulation utilisateur, ou machine QEMU complète)
// et Android (API 24 à 35, x86_64 / x86 avec KVM ; arm64 sur hôte ARM), cycle de vie, installation SUPERVISÉE de
// l'agent dans une instance (son enrôlement se voit dans Agents hôtes). Orchestration Proxmox + k3s : tranche suivante.
import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import { fetchEmulation, sendEmulation } from "./siAgentClient.js";
import { hubLink, viewParams } from "./hubLinks.js";
import BoutonCommande, { suivreCommande, useFinCommandes } from "./BoutonCommande.jsx";

const TABS = [["instances", "Instances"], ["lancer", "Lancer un émulateur"], ["commandes", "Commandes"]];
const ETAT = { en_marche: ["en marche", "good"], demarre: ["démarre", "neutral"], arrete: ["arrêtée", "neutral"], absent: ["absente", "bad"] };
const taille = (o) => (o >= 1073741824 ? `${(o / 1073741824).toFixed(2).replace(".", ",")} Go` : `${Math.round(o / 1048576)} Mo`);
// #835 écran (noVNC sur l'hôte d'émulation, écoute sur son pont Docker) : depuis le poste, par tunnel SSH
const tunnelEcran = (h, i) => `ssh -L ${i.ecran.web}:${i.ecran.ecoute || "127.0.0.1"}:${i.ecran.web} root@${h.agent_id}  puis  http://127.0.0.1:${i.ecran.web}/vnc.html?autoconnect=1&resize=scale`;
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
  useEffect(() => { charger(); const t = setInterval(charger, 5000); return () => clearInterval(t); }, [charger]);
  useFinCommandes(d?.commandes, setTab, setMsg, setErr);
  useEffect(() => { if (d && !hote && d.hotes[0]) setHote(d.hotes[0].agent_id); }, [d, hote]);
  const h = useMemo(() => (d?.hotes || []).find((x) => x.agent_id === hote), [d, hote]);
  async function envoyer(body, quoi) {
    const r = await sendEmulation(base, { ...body, agent: body.agent || hote });
    if (r?.error) { setErr(r.error); return; }
    suivreCommande(r.commande);
    setD((x) => x && { ...x, commandes: [{ id: r.commande, agent_id: body.agent || hote, status: "pending", params: { ...body, instance: r.instance || body.instance }, created_at: new Date().toISOString() }, ...x.commandes] });
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
              <td className="infra-muted">{i.mode === "systeme" ? `ssh -J root@${h.agent_id} -p ${i.port} emul@127.0.0.1 (mot de passe : ${"/var/lib/si-emulation/instances/" + i.id}/mdp)` : i.mode === "avd" ? `ssh -L ${i.port + 1}:127.0.0.1:${i.port + 1} root@${h.agent_id} ; adb connect 127.0.0.1:${i.port + 1}` : `docker exec -it ${i.id} bash (sur l'hôte)`}
                {i.ecran?.web && i.etat === "en_marche" && <div title="écran, clavier, souris / toucher (noVNC) — pas de lien : opération manuelle (tunnel SSH vers l'hôte)">Écran : <code>{tunnelEcran(h, i)}</code></div>}</td>
              <td className="infra-muted">{i.cree ? new Date(i.cree * 1000).toLocaleString("fr-FR") : "—"}</td>
              <td><div className="veille-actions">
                {i.mode === "conteneur" && <BoutonCommande cmds={d.commandes} agent={h.agent_id} critere={{ action: "deployer_agent", instance: i.id }} onClick={() => installer(h.agent_id, i)} title="installation supervisée de l'agent dans l'instance">Installer l'agent</BoutonCommande>}
                {i.mode === "systeme" && <BoutonCommande className="secondary" cmds={d.commandes} agent={h.agent_id} critere={{ action: "exporter_image", instance: i.id }} title="image à graver sur carte SD (généralisée, réduite, xz)" onClick={() => window.confirm(`Exporter ${i.id} en image installable ? (arrêtée pendant l'export)`) && envoyer({ action: "exporter_image", instance: i.id }, `export de ${i.id}`)}>Exporter l'image</BoutonCommande>}
                {i.mode === "avd" && i.etat === "en_marche" && <BoutonCommande className="secondary" cmds={d.commandes} agent={h.agent_id} critere={{ action: "installer_apk", instance: i.id }} onClick={() => { const url = window.prompt("Adresse https de l'APK :", ""); if (!url) return; const sha = window.prompt("Empreinte SHA-256 (conseillée, vide sinon) :", ""); envoyer({ action: "installer_apk", instance: i.id, url: url.trim(), sha256: (sha || "").trim() || undefined }, `APK dans ${i.id}`); }}>Installer une APK…</BoutonCommande>}
                <BoutonCommande className="secondary" cmds={d.commandes} agent={h.agent_id} critere={{ action: "arreter", instance: i.id }} onClick={() => envoyer({ action: "arreter", instance: i.id }, `arrêt de ${i.id}`)}>Arrêter</BoutonCommande>
                <BoutonCommande className="secondary" cmds={d.commandes} agent={h.agent_id} critere={{ action: "detruire", instance: i.id }} onClick={() => window.confirm(`Détruire ${i.id} (disque et état) ?`) && envoyer({ action: "detruire", instance: i.id }, `destruction de ${i.id}`)}>Détruire</BoutonCommande>
              </div></td></tr>))}
            {!h.instances.length && <tr><td colSpan={7} className="infra-muted">Aucune instance : onglet « Lancer un émulateur ».</td></tr>}
          </tbody></table></div>}
        {tab === "instances" && h && <div className="infra-card">
          <b>Images installables (Raspberry Pi)</b>
          <div className="infra-table-wrap"><table className="infra-table"><thead><tr><th>Image</th><th>Taille</th><th>Date</th><th>SHA-256</th><th>Récupérer</th><th></th></tr></thead>
            <tbody>{(h.capacites.exports || []).map((x) => (
              <tr key={x.nom}><td><code>{x.nom}</code></td><td>{taille(x.taille)}</td><td>{quand(x.date * 1000)}</td><td className="infra-muted" title={x.sha256}>{x.sha256 ? `${x.sha256.slice(0, 12)}…` : "—"}</td>
                <td className="infra-muted" title="pas de lien : opération manuelle (l'image reste sur l'hôte d'émulation)"><code>scp root@{h.agent_id}:/var/lib/si-emulation/exports/{x.nom} .</code></td>
                <td><BoutonCommande className="danger" cmds={d.commandes} agent={h.agent_id} critere={{ action: "supprimer_export", nom: x.nom }} onClick={() => window.confirm(`Supprimer ${x.nom} ?`) && envoyer({ action: "supprimer_export", nom: x.nom }, `suppression de ${x.nom}`)}>Supprimer</BoutonCommande></td></tr>))}
              {!(h.capacites.exports || []).length && <tr><td colSpan={6} className="infra-muted">Aucune : « Exporter l'image » sur une machine complète.</td></tr>}</tbody></table></div>
          <p className="infra-muted">Graver : Raspberry Pi Imager (image personnalisée) ou <code>xzcat image.img.xz | sudo dd of=/dev/sdX bs=4M conv=fsync status=progress</code>.
            Premier démarrage : identité unique, partition agrandie ; utilisateur (hash <code>openssl passwd -6</code>), clé SSH, nom, Wi-Fi et ligne d'installation de l'agent
            dans <code>si-premier-demarrage.conf</code> sur la partition de démarrage (modèle <code>.exemple</code> fourni, effacé après usage).</p>
        </div>}
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
                    <BoutonCommande className="secondary" cmds={d.commandes} agent={hote} critere={{ action: "preparer", profil: p.id }} disabled={!ok} onClick={() => envoyer({ action: "preparer", profil: p.id, mode, accepter_licences: licences }, `préparation ${p.titre}`)}>Préparer</BoutonCommande>
                    <BoutonCommande cmds={d.commandes} agent={hote} critere={{ action: "lancer", profil: p.id, mode }} disabled={!ok} onClick={() => envoyer({ action: "lancer", profil: p.id, mode, accepter_licences: licences }, `lancement ${p.titre}`)}>Lancer</BoutonCommande>
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
