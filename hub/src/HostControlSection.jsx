// Section « Poste » de la fiche agent (livraison #613) : redémarrage / arrêt
// programmé (ou annulation), réveil réseau par un autre agent du même site,
// lanceurs au démarrage (Windows : Run, dossier Démarrage, tâches, services)
// avec activation / désactivation, chien de garde applicatif (liste
// d'applications relancées si absentes). Chaque bouton montre sa prise en
// compte, puis l'acquittement de l'agent (règle 8).
import { useEffect, useState } from "react";
import ExtAuditSection from "./ExtAuditSection.jsx";
import { powerAction, wakeOnLan, startupAction, watchdogConfig, benchCommand, imageHost, browsePath, imageTransfer, fetchImages, sendCommand, fetchCommand } from "./siAgentClient.js";

import { AutoColumns } from "./TableColumns.jsx";   // #707 : colonnes réglables
const KIND_LABELS = { run: "clé Run", runonce: "RunOnce", folder: "dossier Démarrage", task: "tâche planifiée", service: "service" };
const STATUS = { ok: ["good", "en service"], restart: ["warn", "relance…"], waiting: ["warn", "en attente de relance"], down: ["bad", "arrêtée"], idle: ["neutral", "hors plage"], disabled: ["neutral", "désactivée"] };
const EMPTY_APP = { id: "", label: "", process: "", command: "", hours: "", days: "", cooldown_seconds: 120, max_restarts_per_hour: 5, enabled: true, session: "console" };

function Tone({ tone, children }) { return <span className={`np-tone ${tone || "neutral"}`}>{children}</span>; }

/** Suit une commande jusqu'à son acquittement (done/failed) -- 20 × 3 s. */
async function follow(apiBase, cmdId, onState) {
  for (let i = 0; i < 20; i++) {
    await new Promise((r) => setTimeout(r, 3000));
    const c = await fetchCommand(apiBase, cmdId).catch(() => null);
    if (c && (c.status === "done" || c.status === "failed")) { onState(c); return c; }
  }
  onState({ status: "pending" });
  return null;
}

function useCommand(apiBase) {
  const [busy, setBusy] = useState("");
  const [result, setResult] = useState(null);
  const run = async (label, send) => {
    setBusy(label); setResult(null);
    try {
      const r = await send();
      const cid = r?.command?.id || r?.id;
      setResult({ status: "sent", text: `${label} : envoyé à l'agent, en attente de l'acquittement…` });
      if (cid) await follow(apiBase, cid, (c) => setResult(c.status === "done" ? { status: "done", text: `${label} : ${c.result?.message || c.result?.result?.message || "fait"}` }
        : c.status === "failed" ? { status: "failed", text: `${label} : refusé — ${c.error || c.result?.error || "?"}` }
        : { status: "pending", text: `${label} : l'agent n'a pas encore acquitté (il relève ses commandes toutes les minutes)` }));
    } catch (e) { setResult({ status: "failed", text: `${label} : ${e.message}` }); }
    setBusy("");
  };
  return { busy, result, run };
}

const gb = (n) => (n == null ? "?" : n >= 1e12 ? (n / 1e12).toFixed(2) + " To" : n >= 1e9 ? (n / 1e9).toFixed(1) + " Go" : Math.round(n / 1e6) + " Mo");

// #627 : parcours de l'arborescence du poste par l'agent (lecteurs, sous-dossiers, espace libre) pour choisir une cible
function PathBrowser({ apiBase, agentId, onPick, start }) {
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState(null);
  const [open, setOpen] = useState(false);
  const go = async (path) => {
    setOpen(true); setBusy(true);
    try {
      const r = await browsePath(apiBase, agentId, path);
      const cid = r?.command?.id || r?.id;
      const c = cid ? await follow(apiBase, cid, () => {}) : null;
      setRes(c ? (c.result?.result || { ok: false, error: c.result?.error || c.error || "sans résultat" }) : { ok: false, error: "l'agent n'a pas répondu (il relève ses commandes toutes les minutes)" });
    } catch (e) { setRes({ ok: false, error: e.message }); }
    setBusy(false);
  };
  return (
    <div style={{ marginTop: 6 }}>
      <button type="button" className="secondary" disabled={busy} onClick={() => go(start || null)}>{busy ? "⏳ parcours…" : "Parcourir depuis le poste…"}</button>
      {open && res && (
        <div style={{ border: "1px solid var(--border)", borderRadius: 8, padding: 8, marginTop: 6 }}>
          {res.ok === false && <div style={{ color: "var(--danger)" }}>{res.error}</div>}
          {res.ok !== false && res.drives && <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>{res.drives.map((d) => <button key={d.path} type="button" className="secondary" onClick={() => go(d.path)}>{d.path} <span className="muted">{gb(d.free)} libres / {gb(d.total)}</span></button>)}</div>}
          {res.ok !== false && res.path && (
            <>
              <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}><b>{res.path}</b><span className="muted">{res.free != null ? `${gb(res.free)} libres / ${gb(res.total)}` : ""}</span>
                <button type="button" className="secondary" onClick={() => { onPick(res.path); setOpen(false); }}>Choisir ce dossier comme cible</button>
                <button type="button" className="secondary" onClick={() => go(res.parent || null)}>↑ {res.parent || "lecteurs"}</button></div>
              <div style={{ maxHeight: 200, overflow: "auto", marginTop: 4 }}>{(res.entries || []).map((e) => <div key={e.path}><button type="button" className="secondary" style={{ padding: "1px 8px" }} onClick={() => go(e.path)}>📁 {e.name}</button></div>)}{res.truncated && <div className="muted">liste tronquée</div>}{!(res.entries || []).length && <div className="muted">aucun sous-dossier</div>}</div>
            </>
          )}
          <div className="muted" style={{ fontSize: 12 }}>Vu par le compte de l'agent (SYSTEM) : les lecteurs réseau d'une session n'y figurent pas ; pour un partage, taper <code>\\serveur\partage</code> dans la cible puis Parcourir depuis ce chemin.</div>
        </div>
      )}
    </div>
  );
}

function Result({ r }) {
  if (!r) return null;
  const color = r.status === "done" ? "var(--ok)" : r.status === "failed" ? "var(--danger)" : "var(--muted)";
  return <p style={{ color, margin: "6px 0" }}>{r.status === "sent" ? "⏳ " : ""}{r.text}</p>;
}

export default function HostControlSection({ apiBase, agentId, detail, fleet, host, when, onRefresh }) {
  const isWindows = host?.system?.os_id === "windows";
  const startup = detail?.latest?.startup;
  const watchdog = detail?.latest?.watchdog;
  const wdCfg = detail?.latest?.inventory?.data?.watchdog || { interval_seconds: 60, apps: [] };
  const power = useCommand(apiBase);
  const wol = useCommand(apiBase);
  const rdp = useCommand(apiBase);
  const sched = useCommand(apiBase);  // #684
  const psCfg = detail?.latest?.inventory?.data?.power_schedule;
  const relaunchPending = detail?.latest?.inventory?.data?.relaunch_pending;
  const [ps, setPs] = useState(null);
  const psForm = ps || { enabled: psCfg?.enabled ?? false, time: psCfg?.time || "00:00", days: psCfg?.days || "1-7", relaunch: psCfg?.relaunch ?? true };
  const start = useCommand(apiBase);
  const wd = useCommand(apiBase);
  const bench = useCommand(apiBase);  // #616
  const img = useCommand(apiBase);  // #621
  const [imgTarget, setImgTarget] = useState("");
  const [imgTransfer, setImgTransfer] = useState(true);   // #634 : transfert vers le serveur après l'image
  const [imgDelete, setImgDelete] = useState(false);
  const [imgExisting, setImgExisting] = useState("");
  const [shUnc, setShUnc] = useState(""); const [shUser, setShUser] = useState(""); const [shPass, setShPass] = useState("");  // #635
  const shareParam = () => { if (!shUnc.trim()) return undefined; const m = shUser.trim().match(/^([^\\]+)\\(.+)$/); return { unc: shUnc.trim(), user: m ? m[2] : shUser.trim(), domain: m ? m[1] : undefined, password: shPass }; };
  const [images, setImages] = useState([]);
  const xfer = useCommand(apiBase);
  useEffect(() => { fetchImages(apiBase).then((r) => setImages((r?.images || []).filter((i) => i.agent_id === agentId))).catch(() => setImages([])); }, [apiBase, agentId, img.result, xfer.result]);
  const [imgDrives, setImgDrives] = useState("*");
  const [imgSha, setImgSha] = useState("");
  const [benchMin, setBenchMin] = useState(10);
  const [benchFactor, setBenchFactor] = useState(6);
  const me = detail?.latest?.["agent-self"]?.data;
  const [delay, setDelay] = useState(60);
  const [message, setMessage] = useState("Redémarrage demandé par la supervision");
  const [force, setForce] = useState(false);
  const [bootTarget, setBootTarget] = useState("");
  const [aluUser, setAluUser] = useState("");
  const [aluPass, setAluPass] = useState("");
  const autologon = () => {  // #628 : réouverture de session une fois ; "DOMAINE\compte" accepté
    if (!aluUser.trim() || !aluPass) return undefined;
    const m = aluUser.trim().match(/^([^\\]+)\\(.+)$/);
    return m ? { domain: m[1], user: m[2], password: aluPass } : { user: aluUser.trim(), password: aluPass };
  };
  const [mac, setMac] = useState("");
  const [via, setVia] = useState("");
  const [apps, setApps] = useState(wdCfg.apps || []);
  const [interval, setInterval_] = useState(wdCfg.interval_seconds || 60);
  const [editing, setEditing] = useState(null);
  const [filter, setFilter] = useState("");
  useEffect(() => { setApps(wdCfg.apps || []); setInterval_(wdCfg.interval_seconds || 60); }, [agentId, detail?.latest?.inventory?.at]);  // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    const nv = detail?.latest?.netview?.data;
    const first = (nv?.interfaces || []).find((i) => i.mac && i.state === "up" && !/^(lo|docker|veth|br-)/.test(i.name));
    if (first && !mac) setMac(first.mac);
  }, [detail]);  // eslint-disable-line react-hooks/exhaustive-deps
  const peers = (fleet || []).filter((a) => a.agent_id !== agentId && a.site === detail?.site && a.online === "online");
  const consoleUser = host?.accounts?.console_user;
  const q = filter.trim().toLowerCase();
  const items = (startup?.data?.items || []).filter((it) => !q || [it.name, it.command, it.location].some((v) => String(v || "").toLowerCase().split(/[\s\\/]+/).some((w) => w.startsWith(q))));

  const saveApps = (next) => wd.run("chien de garde", () => watchdogConfig(apiBase, agentId, { interval_seconds: interval, apps: next })).then(() => onRefresh && onRefresh());

  return (
    <>
      <h3>Poste <span className="muted" style={{ textTransform: "none", letterSpacing: 0 }}>· alimentation, réveil, lanceurs, chien de garde</span></h3>

      <div className="sa-kv">
        <div className="sa-wide"><span className="muted">Alimentation</span>
          <span style={{ display: "inline-flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
            délai <input type="number" min={0} max={3600} value={delay} onChange={(e) => setDelay(Number(e.target.value))} style={{ width: 70 }} /> s ·
            message <input value={message} onChange={(e) => setMessage(e.target.value)} style={{ minWidth: 260 }} maxLength={200} />
            <label style={{ display: "inline-flex", gap: 4, alignItems: "center" }}><input type="checkbox" checked={force} onChange={(e) => setForce(e.target.checked)} /> forcer (fermer les applications sans attendre)</label>
            <select value={bootTarget} onChange={(e) => setBootTarget(e.target.value)} title="Poste multi-amorçage : cible du prochain démarrage, choisie via le firmware UEFI (une fois), sans toucher à GRUB">
              <option value="">redémarrer normalement</option>
              <option value="windows">→ Windows (saute GRUB, une fois)</option>
              <option value="linux">→ Linux / GRUB (une fois)</option>
              <option value="firmware">→ réglages UEFI</option>
            </select>
            <span style={{ display: "inline-flex", gap: 4, alignItems: "center" }} title="Windows : Winlogon rouvre cette session UNE fois au démarrage suivant (AutoLogonCount=1), puis efface le mot de passe ; l'agent vérifie au démarrage suivant. Compte local ou de domaine avec mot de passe.">rouvrir la session (une fois) <input value={aluUser} onChange={(e) => setAluUser(e.target.value)} placeholder="compte ou DOMAINE\compte" style={{ width: 170 }} /><input type="password" value={aluPass} onChange={(e) => setAluPass(e.target.value)} placeholder="mot de passe" autoComplete="new-password" style={{ width: 130 }} /></span>
            <button type="button" className="secondary" disabled={!!power.busy} onClick={() => window.confirm(`Redémarrer ${detail.hostname || agentId} dans ${delay} s${bootTarget ? ` vers ${bootTarget}` : ""}${autologon() ? ` puis rouvrir la session de ${aluUser}` : ""} ?`) && power.run("redémarrage", () => { const r = powerAction(apiBase, agentId, { action: "reboot", delay_seconds: delay, message, force, target: bootTarget || undefined, autologon: autologon() }); setAluPass(""); return r; })}>{power.busy === "redémarrage" ? "⏳ redémarrage…" : "Redémarrer"}</button>
            <button type="button" className="secondary" disabled={!!power.busy} onClick={() => window.confirm(`Arrêter ${detail.hostname || agentId} dans ${delay} s ? (il faudra un réveil réseau ou une présence sur place pour le rallumer)`) && power.run("arrêt", () => powerAction(apiBase, agentId, { action: "shutdown", delay_seconds: delay, message, force }))}>{power.busy === "arrêt" ? "⏳ arrêt…" : "Arrêter"}</button>
            <button type="button" className="secondary" disabled={!!power.busy} onClick={() => power.run("annulation", () => powerAction(apiBase, agentId, { action: "cancel" }))}>{power.busy === "annulation" ? "⏳…" : "Annuler l'arrêt programmé"}</button>
          </span>
          {consoleUser && <div className="muted" style={{ fontSize: 12 }}>Session ouverte sur la console : <b>{consoleUser}</b> — sans « forcer », l'agent refusera.</div>}
          <Result r={power.result} />
        </div>

        <div className="sa-wide"><span className="muted">Réveil réseau</span>
          <span style={{ display: "inline-flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
            MAC <input value={mac} onChange={(e) => setMac(e.target.value)} placeholder="aa:bb:cc:dd:ee:ff" style={{ width: 170 }} />
            via l'agent
            <select value={via} onChange={(e) => setVia(e.target.value)}>
              <option value="">— un agent en ligne du même site —</option>
              {peers.map((a) => <option key={a.agent_id} value={a.agent_id}>{a.hostname || a.agent_id} ({a.last_ip || "?"})</option>)}
            </select>
            <button type="button" className="secondary" disabled={!!wol.busy || !via || !mac} onClick={() => wol.run("réveil", () => wakeOnLan(apiBase, via, { mac }))}>{wol.busy ? "⏳ réveil…" : "Réveiller ce poste"}</button>
          </span>
          <div className="muted" style={{ fontSize: 12 }}>Le paquet magique doit partir d'une machine du même segment : un autre agent du site l'émet (n'importe quel poste allumé du même VLAN, ou un petit Linux qui y est posé). Le poste doit avoir le Wake-on-LAN activé (BIOS + carte réseau) ; {peers.length === 0 && <b>aucun autre agent en ligne sur ce site pour l'instant. </b>}Le hub ne voit le résultat que par le retour en ligne de l'agent.</div>
          <Result r={wol.result} />
        </div>
        <div className="sa-wide"><span className="muted">Redémarrage planifié</span>
          <span style={{ display: "inline-flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
            <label style={{ display: "inline-flex", gap: 4, alignItems: "center" }}><input type="checkbox" checked={!!psForm.enabled} onChange={(e) => setPs({ ...psForm, enabled: e.target.checked })} /> chaque jour</label>
            à <input type="time" value={psForm.time} onChange={(e) => setPs({ ...psForm, time: e.target.value })} style={{ width: 110 }} />
            jours <input value={psForm.days} onChange={(e) => setPs({ ...psForm, days: e.target.value })} placeholder="1-7" style={{ width: 80 }} title="1-7, lundi = 1 ; ex. 1-5 ou 1,3,5" />
            <label style={{ display: "inline-flex", gap: 4, alignItems: "center" }}><input type="checkbox" checked={!!psForm.relaunch} onChange={(e) => setPs({ ...psForm, relaunch: e.target.checked })} /> relancer les applications ouvertes</label>
            <button type="button" className="secondary" disabled={!!sched.busy} onClick={() => sched.run("planification", () => sendCommand(apiBase, agentId, "power_schedule", { ...psForm, action: "reboot", delay_seconds: 60 })).then(() => { setPs(null); onRefresh && onRefresh(); })}>{sched.busy ? "⏳…" : "Enregistrer"}</button>
          </span>
          <div className="muted" style={{ fontSize: 12 }}>
            {psCfg ? (psCfg.enabled ? <>En place : redémarrage à <b>{psCfg.time}</b> (jours {psCfg.days}){psCfg.relaunch ? ", relance des applications" : ""}. </> : "Planification désactivée. ") : "Aucune planification sur cet agent. "}
            {relaunchPending && <Tone tone="warn">relance en attente d'une session utilisateur</Tone>} L'agent note les applications de la session console (Windows), émet « host-reboot », redémarre, puis les relance dans la session de l'utilisateur et émet « host-boot ». Une session doit se rouvrir (autologon) pour la relance.
          </div>
          <Result r={sched.result} />
        </div>
        <div className="sa-wide"><span className="muted">Bureau à distance</span>
          <span style={{ display: "inline-flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
            <button type="button" className="secondary" disabled={!!rdp.busy} onClick={() => rdp.run("état RDP", () => sendCommand(apiBase, agentId, "remote_desktop", { action: "status" }))}>État</button>
            <button type="button" className="secondary" disabled={!!rdp.busy} onClick={() => window.confirm(`Activer le Bureau à distance sur ${detail.hostname || agentId} ? Connexion avec un compte déjà autorisé sur le poste ; NLA exigée.`) && rdp.run("RDP activé", () => sendCommand(apiBase, agentId, "remote_desktop", { action: "enable" }))}>Activer</button>
            <button type="button" className="secondary" disabled={!!rdp.busy} onClick={() => rdp.run("RDP désactivé", () => sendCommand(apiBase, agentId, "remote_desktop", { action: "disable" }))}>Désactiver</button>
          </span>
          <div className="muted" style={{ fontSize: 12 }}>Active le RDP intégré (service + règle de pare-feu « Remote Desktop ») ; aucun compte n'est créé — connexion avec tes identifiants d'administration. Chaque bascule est journalisée.</div>
          <Result r={rdp.result} />
        </div>
      </div>

      <h3 style={{ marginTop: 12 }}>Empreinte de l'agent {me ? <span className="muted" style={{ textTransform: "none", letterSpacing: 0 }}>· fenêtre de {Math.round((me.summary?.window_seconds || 0) / 60)} min, {me.summary?.points} points{me.bench_until && <> · <Tone tone="warn">banc en cours (×{me.bench_factor})</Tone></>}</span> : null}</h3>
      {!me ? <p className="muted">Pas encore de mesure d'introspection (agent ≥ 0.5.18, toutes les 60 s).</p> : (
        <div className="sa-kv">
          <div><span className="muted">Processeur</span>{me.point?.cpu_core_percent} % d'un cœur maintenant · moyenne {me.summary?.all?.cpu_core_avg} %, pointe {me.summary?.all?.cpu_core_max} % · soit {me.summary?.all?.cpu_machine_avg} % de la machine ({me.point?.cores} cœurs){me.point?.host_load1 != null && <> · charge hôte {me.point.host_load1}</>}</div>
          <div><span className="muted">Mémoire / file</span>{Math.round((me.point?.rss_bytes || 0) / 1048576)} Mo résidents · {me.point?.queue_size ?? "?"} mesure(s) en attente</div>
          {me.summary?.bench && me.summary?.normal && (
            <div className="sa-wide"><span className="muted">Banc vs normal</span>en banc : {me.summary.bench.cpu_core_avg} % cœur en moyenne (pointe {me.summary.bench.cpu_core_max} %) sur {me.summary.bench.points} points · hors banc : {me.summary.normal.cpu_core_avg} % (pointe {me.summary.normal.cpu_core_max} %) sur {me.summary.normal.points} points</div>
          )}
          <div className="sa-wide"><span className="muted">Coût par tâche</span>{(me.summary?.costly || []).length === 0 ? "—" : (me.summary.costly || []).map((t) => <span key={t.name} className="na-chip" title={`${t.runs} lancement(s), max ${t.max} s, ${t.failed} échec(s)`}>{t.name.replace("plugin:", "")} {t.avg} s{t.failed ? ` (${t.failed} échec)` : ""}</span>)}</div>
          <div className="sa-wide"><span className="muted">Banc de charge</span>
            <span style={{ display: "inline-flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
              <input type="number" min={1} max={60} value={benchMin} onChange={(e) => setBenchMin(Number(e.target.value))} style={{ width: 60 }} /> min · cadence ×<input type="number" min={2} max={20} value={benchFactor} onChange={(e) => setBenchFactor(Number(e.target.value))} style={{ width: 50 }} />
              <button type="button" className="secondary" disabled={!!bench.busy} onClick={() => window.confirm(`Lancer un banc de charge de ${benchMin} min sur ${detail.hostname || agentId} : toutes les sondes et collectes tourneront ${benchFactor} fois plus souvent. Continuer ?`) && bench.run("banc", () => benchCommand(apiBase, agentId, { minutes: benchMin, factor: benchFactor }))}>{bench.busy ? "⏳…" : "Lancer le banc"}</button>
              {me.bench_until && <button type="button" className="secondary" disabled={!!bench.busy} onClick={() => bench.run("arrêt du banc", () => benchCommand(apiBase, agentId, { stop: true }))}>Arrêter</button>}
            </span>
            <div className="muted" style={{ fontSize: 12 }}>Mesure l'impact réel des sondes : pendant le banc, l'introspection passe à 30 s et la ligne « banc vs normal » compare les deux. Un événement « banc terminé » porte la synthèse.</div>
            <Result r={bench.result} />
          </div>
        </div>
      )}

      {isWindows && (
        <>
          <h3 style={{ marginTop: 12 }}>Lanceurs au démarrage {startup ? <span className="muted" style={{ textTransform: "none", letterSpacing: 0 }}>· relevé du {when(startup.at)} · {startup.data?.summary?.total ?? 0} entrée(s), {startup.data?.summary?.disabled ?? 0} désactivée(s)</span> : null}</h3>
          {!startup ? <p className="muted">Pas encore de relevé (agent ≥ 0.5.17, toutes les 30 min).</p> : !startup.ok && !startup.data ? <p style={{ color: "var(--danger)" }}>{startup.error}</p> : (
            <>
              <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 6 }}>
                <input placeholder="Filtrer (nom, commande)" value={filter} onChange={(e) => setFilter(e.target.value)} style={{ minWidth: 240 }} />
                {startup.data?.partial?.length > 0 && <Tone tone="warn">partiel : {startup.data.partial.join(", ")}</Tone>}
                <Result r={start.result} />
              </div>
              <div className="hub-table-scroll" style={{ maxHeight: 360, overflow: "auto" }}>
                <AutoColumns id="HostControlSection.1"><table>
                  <thead><tr><th>Type</th><th>Portée</th><th>Nom</th><th>Commande</th><th>Où / quand</th><th>État</th><th></th></tr></thead>
                  <tbody>
                    {items.length === 0 && <tr><td colSpan={7} className="muted">aucun lanceur</td></tr>}
                    {items.map((it, i) => {
                      const protectedItem = (it.kind === "task" && /^\\microsoft\\/i.test(it.name)) || it.kind === "runonce";
                      return (
                        <tr key={`${it.kind}-${it.scope}-${it.name}-${i}`}>
                          <td>{KIND_LABELS[it.kind] || it.kind}</td>
                          <td>{it.scope === "user" ? "utilisateur" : "machine"}</td>
                          <td><b>{it.name}</b>{it.user && <span className="muted"> · {it.user}</span>}</td>
                          <td><code style={{ fontSize: 12, wordBreak: "break-all" }}>{it.command || "—"}</code></td>
                          <td className="muted" style={{ fontSize: 12 }}>{it.location}{it.state && <> · {it.state}</>}{it.delayed && <> · différé</>}</td>
                          <td>{it.enabled === false ? <Tone tone="neutral">désactivé</Tone> : <Tone tone="good">actif</Tone>}</td>
                          <td>{!protectedItem && (
                            <button type="button" className="secondary" disabled={!!start.busy} onClick={() => start.run(`${it.enabled === false ? "activation" : "désactivation"} de ${it.name}`, () => startupAction(apiBase, agentId, { kind: it.kind, scope: it.scope, name: it.name, enable: it.enabled === false })).then(() => onRefresh && onRefresh())}>
                              {start.busy && start.busy.endsWith(it.name) ? "⏳…" : it.enabled === false ? "Activer" : "Désactiver"}
                            </button>
                          )}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table></AutoColumns>
              </div>
            </>
          )}
        </>
      )}

      {isWindows && (
        <>
          <h3 style={{ marginTop: 12 }}>Image du poste à chaud (P2V)</h3>
          <div className="sa-kv">
            <div className="sa-wide"><span className="muted">Cible</span>
              <span style={{ display: "inline-flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
                <input value={imgTarget} onChange={(e) => setImgTarget(e.target.value)} placeholder={"\\\\nas\\images\\p2v  ou  D:\\images"} style={{ minWidth: 280 }} />
                lecteurs <input value={imgDrives} onChange={(e) => setImgDrives(e.target.value)} style={{ width: 80 }} title="* = tous, ou C: D:" />
                <input value={imgSha} onChange={(e) => setImgSha(e.target.value)} placeholder="SHA-256 de disk2vhd64.exe (facultatif)" style={{ minWidth: 300 }} />
                <button type="button" className="secondary" disabled={!!img.busy || !imgTarget} onClick={() => window.confirm(`Créer une image complète de ${detail.hostname || agentId} vers ${imgTarget} ? La machine reste en service (instantané VSS) ; 30 à 60 min pour 200-300 Go sur Gigabit.${imgTransfer ? " Elle sera ensuite transférée vers le serveur." : ""}`) && img.run("image", () => imageHost(apiBase, agentId, { target: imgTarget, drives: imgDrives, tool_sha256: imgSha || undefined, transfer: imgTransfer, delete_after: imgDelete, share: shareParam() }).then((r) => { setShPass(""); return r; }))}>{img.busy ? "⏳ lancement…" : "Créer l'image"}</button>
              </span>
              <span style={{ display: "inline-flex", gap: 6, alignItems: "center", flexWrap: "wrap", marginTop: 4 }} title="Écriture directe sur un partage du serveur, monté par l'agent (SYSTEM) le temps de l'image : pas de copie locale. La cible doit être sous l'UNC.">
                partage du serveur <input value={shUnc} onChange={(e) => setShUnc(e.target.value)} placeholder={"\\\\serveur\\p2v"} style={{ width: 200 }} /><input value={shUser} onChange={(e) => setShUser(e.target.value)} placeholder="compte ou DOMAINE\compte" style={{ width: 170 }} /><input type="password" value={shPass} onChange={(e) => setShPass(e.target.value)} placeholder="mot de passe" autoComplete="new-password" style={{ width: 130 }} />
              </span>
              <span style={{ display: "inline-flex", gap: 12, alignItems: "center", flexWrap: "wrap", marginTop: 4 }}>
                <label style={{ display: "inline-flex", gap: 4, alignItems: "center" }}><input type="checkbox" checked={imgTransfer} onChange={(e) => setImgTransfer(e.target.checked)} /> transférer ensuite vers le serveur (canal de l'agent, signé, reprise sur coupure)</label>
                <label style={{ display: "inline-flex", gap: 4, alignItems: "center" }}><input type="checkbox" checked={imgDelete} onChange={(e) => setImgDelete(e.target.checked)} /> supprimer du poste après transfert vérifié</label>
              </span>
              <span style={{ display: "inline-flex", gap: 6, alignItems: "center", flexWrap: "wrap", marginTop: 4 }}>
                <input value={imgExisting} onChange={(e) => setImgExisting(e.target.value)} placeholder={"image déjà sur le poste : D:\\images\\PC-20260926.vhdx"} style={{ minWidth: 320 }} />
                <button type="button" className="secondary" disabled={!!xfer.busy || !imgExisting} onClick={() => xfer.run("transfert", () => imageTransfer(apiBase, agentId, { path: imgExisting, delete_after: imgDelete }))}>{xfer.busy ? "⏳…" : "Transférer / reprendre"}</button>
              </span>
              <Result r={xfer.result} />
              {images.length > 0 && <div style={{ marginTop: 4 }}><span className="muted">Images reçues sur le serveur : </span>{images.map((i) => <div key={i.path}>{i.complete ? "✅" : "⏳"} <code>{i.path}</code> <span className="muted">{gb(i.size)}</span></div>)}</div>}
              <PathBrowser apiBase={apiBase} agentId={agentId} onPick={setImgTarget} start={imgTarget} />
              <div className="muted" style={{ fontSize: 12 }}>Disk2vhd (Sysinternals, téléchargé par l'agent ou déposé dans <code>ProgramData\si-agent\tools</code>), VHDX importable dans Proxmox (<code>qm importdisk</code>). Refus si BitLocker protège un lecteur visé ou si la cible manque de place. Suivi dans le journal : image lancée / en cours (toutes les 5 min) / terminée (avec le mode d'emploi Proxmox) / échouée.</div>
              <Result r={img.result} />
            </div>
          </div>
        </>
      )}

      <h3 style={{ marginTop: 12 }}>Chien de garde applicatif {watchdog ? <span className="muted" style={{ textTransform: "none", letterSpacing: 0 }}>· contrôle du {when(watchdog.at)} · {watchdog.data?.summary?.ok ?? 0} en service, {watchdog.data?.summary?.down ?? 0} en défaut</span> : null}</h3>
      <p className="muted" style={{ margin: "0 0 6px" }}>L'agent vérifie toutes les {interval} s que chaque application listée tourne (nom de l'exécutable) et la relance sinon (commande, détachée), dans la limite du quota par heure ; événements « application arrêtée / relancée / de retour » dans le journal, filtrables (catégorie Applications surveillées).</p>
      <div className="hub-table-scroll">
        <AutoColumns id="HostControlSection.2"><table>
          <thead><tr><th>Id</th><th>Libellé</th><th>Processus</th><th>Commande de relance</th><th>Plage</th><th>Repos / quota</th><th>État</th><th></th></tr></thead>
          <tbody>
            {apps.length === 0 && <tr><td colSpan={8} className="muted">aucune application surveillée</td></tr>}
            {apps.map((a) => {
              const row = (watchdog?.data?.apps || []).find((r) => r.id === a.id);
              const st = row ? STATUS[row.status] || ["neutral", row.status] : ["neutral", "—"];
              return (
                <tr key={a.id}>
                  <td><code>{a.id}</code></td><td>{a.label}</td><td><code>{a.process}</code></td>
                  <td><code style={{ fontSize: 12, wordBreak: "break-all" }}>{a.command || <span className="muted">aucune (alerte seulement)</span>}</code></td>
                  <td className="muted">{a.hours || "24 h/24"}{a.days ? ` · jours ${a.days}` : ""}</td>
                  <td className="muted">{a.cooldown_seconds} s · {a.max_restarts_per_hour}/h</td>
                  <td><Tone tone={st[0]}>{st[1]}</Tone>{row?.restarts_last_hour > 0 && <span className="muted"> · {row.restarts_last_hour} relance(s)/h</span>}{a.enabled === false && <span className="muted"> · désactivée</span>}</td>
                  <td style={{ whiteSpace: "nowrap" }}>
                    <button type="button" className="secondary" onClick={() => setEditing({ ...EMPTY_APP, ...a })}>Modifier</button>{" "}
                    <button type="button" className="secondary" disabled={!!wd.busy} onClick={() => window.confirm(`Retirer « ${a.label} » de la surveillance ?`) && saveApps(apps.filter((x) => x.id !== a.id))}>Retirer</button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table></AutoColumns>
      </div>
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 6, flexWrap: "wrap" }}>
        <button type="button" className="secondary" onClick={() => setEditing({ ...EMPTY_APP })}>Ajouter une application</button>
        <span className="muted">intervalle</span><input type="number" min={15} max={3600} value={interval} onChange={(e) => setInterval_(Number(e.target.value))} style={{ width: 70 }} /><span className="muted">s</span>
        <button type="button" className="secondary" disabled={!!wd.busy} onClick={() => saveApps(apps)}>{wd.busy ? "⏳ envoi…" : "Envoyer la configuration à l'agent"}</button>
        <Result r={wd.result} />
      </div>
      {editing && (
        <form className="lic-form" style={{ marginTop: 8, display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 8 }} onSubmit={(e) => {
          e.preventDefault();
          const clean = { ...editing, id: editing.id.trim().toLowerCase().replace(/[^a-z0-9_-]/g, "-").slice(0, 40) };
          if (!clean.id || !clean.process.trim()) return;
          const next = apps.some((x) => x.id === clean.id) ? apps.map((x) => (x.id === clean.id ? clean : x)) : [...apps, clean];
          setApps(next); setEditing(null); saveApps(next);
        }}>
          <label>Identifiant<input value={editing.id} onChange={(e) => setEditing({ ...editing, id: e.target.value })} placeholder="caisse" required /></label>
          <label>Libellé<input value={editing.label} onChange={(e) => setEditing({ ...editing, label: e.target.value })} placeholder="Logiciel de caisse" /></label>
          <label>Processus attendu<input value={editing.process} onChange={(e) => setEditing({ ...editing, process: e.target.value })} placeholder="caisse.exe" required /></label>
          <label>Commande de relance<input value={editing.command} onChange={(e) => setEditing({ ...editing, command: e.target.value })} placeholder={"C:\\Caisse\\caisse.exe --kiosque"} /></label>
          <label>Session de lancement (Windows)<select value={editing.session || "console"} onChange={(e) => setEditing({ ...editing, session: e.target.value })}>
            <option value="console">utilisateur de la console (application visible)</option>
            <option value="service">service de l'agent (sans fenêtre)</option>
          </select></label>
          <label>Plage horaire (HH:MM-HH:MM)<input value={editing.hours} onChange={(e) => setEditing({ ...editing, hours: e.target.value })} placeholder="08:00-20:00" /></label>
          <label>Jours (1-7, lundi = 1)<input value={editing.days} onChange={(e) => setEditing({ ...editing, days: e.target.value })} placeholder="1-6" /></label>
          <label>Repos entre deux relances (s)<input type="number" min={10} max={3600} value={editing.cooldown_seconds} onChange={(e) => setEditing({ ...editing, cooldown_seconds: Number(e.target.value) })} /></label>
          <label>Relances max par heure<input type="number" min={0} max={60} value={editing.max_restarts_per_hour} onChange={(e) => setEditing({ ...editing, max_restarts_per_hour: Number(e.target.value) })} /></label>
          <label style={{ display: "flex", gap: 6, alignItems: "center" }}><input type="checkbox" checked={editing.enabled !== false} onChange={(e) => setEditing({ ...editing, enabled: e.target.checked })} /> surveillance active</label>
          <div style={{ display: "flex", gap: 8, alignItems: "end" }}>
            <button type="submit">Enregistrer et envoyer</button>
            <button type="button" className="secondary" onClick={() => setEditing(null)}>Annuler</button>
          </div>
        </form>
      )}
      <ExtAuditSection apiBase={apiBase} agentId={agentId} detail={detail} />
    </>
  );
}
