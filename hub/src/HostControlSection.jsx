// Section « Poste » de la fiche agent (livraison #613) : redémarrage / arrêt
// programmé (ou annulation), réveil réseau par un autre agent du même site,
// lanceurs au démarrage (Windows : Run, dossier Démarrage, tâches, services)
// avec activation / désactivation, chien de garde applicatif (liste
// d'applications relancées si absentes). Chaque bouton montre sa prise en
// compte, puis l'acquittement de l'agent (règle 8).
import { useEffect, useState } from "react";
import { powerAction, wakeOnLan, startupAction, watchdogConfig, fetchCommand } from "./siAgentClient.js";

const KIND_LABELS = { run: "clé Run", runonce: "RunOnce", folder: "dossier Démarrage", task: "tâche planifiée", service: "service" };
const STATUS = { ok: ["good", "en service"], restart: ["warn", "relance…"], waiting: ["warn", "en attente de relance"], down: ["bad", "arrêtée"], idle: ["neutral", "hors plage"], disabled: ["neutral", "désactivée"] };
const EMPTY_APP = { id: "", label: "", process: "", command: "", hours: "", days: "", cooldown_seconds: 120, max_restarts_per_hour: 5, enabled: true };

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
  const start = useCommand(apiBase);
  const wd = useCommand(apiBase);
  const [delay, setDelay] = useState(60);
  const [message, setMessage] = useState("Redémarrage demandé par la supervision");
  const [force, setForce] = useState(false);
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
  const peers = (fleet || []).filter((a) => a.agent_id !== agentId && a.site === detail?.site && a.state === "online");
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
            <button type="button" className="secondary" disabled={!!power.busy} onClick={() => window.confirm(`Redémarrer ${detail.hostname || agentId} dans ${delay} s ?`) && power.run("redémarrage", () => powerAction(apiBase, agentId, { action: "reboot", delay_seconds: delay, message, force }))}>{power.busy === "redémarrage" ? "⏳ redémarrage…" : "Redémarrer"}</button>
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
          <div className="muted" style={{ fontSize: 12 }}>Le paquet magique doit partir d'une machine du même segment : un autre agent du site l'émet (le routeur MikroTik du site peut aussi le faire : <code>/tool wol mac=…</code>). Le poste doit avoir le Wake-on-LAN activé (BIOS + carte réseau) ; {peers.length === 0 && <b>aucun autre agent en ligne sur ce site pour l'instant. </b>}Le hub ne voit le résultat que par le retour en ligne de l'agent.</div>
          <Result r={wol.result} />
        </div>
      </div>

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
                <table>
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
                </table>
              </div>
            </>
          )}
        </>
      )}

      <h3 style={{ marginTop: 12 }}>Chien de garde applicatif {watchdog ? <span className="muted" style={{ textTransform: "none", letterSpacing: 0 }}>· contrôle du {when(watchdog.at)} · {watchdog.data?.summary?.ok ?? 0} en service, {watchdog.data?.summary?.down ?? 0} en défaut</span> : null}</h3>
      <p className="muted" style={{ margin: "0 0 6px" }}>L'agent vérifie toutes les {interval} s que chaque application listée tourne (nom de l'exécutable) et la relance sinon (commande, détachée), dans la limite du quota par heure ; événements « application arrêtée / relancée / de retour » dans le journal, filtrables (catégorie Applications surveillées).</p>
      <div className="hub-table-scroll">
        <table>
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
        </table>
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
    </>
  );
}
