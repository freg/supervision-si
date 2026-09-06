import React, { useEffect, useState } from "react";
import {
  fetchAgents, createAgent, updateAgent, deleteAgent, rotateAgentSecret,
  fetchAgentsLatest, fetchAgentMeasurements,
} from "./netprobeClient.js";
import {
  ageSeconds, formatAge, liveness, groupLatestByAgent, describeWifiLink, describePing,
  describeScan, describeSys, detectBssidChanges, seriesOf, buildLinePath, taskLabel,
} from "./netprobeAgents.js";

// Onglet « Sondes WiFi » de la tuile Sondes réseau (livraison #407, items
// 45/47/48/51) -- flotte de sondes (Pi Zero W) et collecteurs (Pi 3B),
// dernières mesures remontées, détail par sonde : ligne de signal,
// changements de borne (itinérance), édition des tâches. Premier socle
// de l'item 51 (« guider les techniciens ») : on affiche ce que les
// sondes voient, la corrélation multi-couches viendra quand il y aura
// de vraies données. Toute la logique non-React est dans
// netprobeAgents.js (testée à part).

const REFRESH_MS = 60000;
const LINE_W = 600;
const LINE_H = 90;

const ROLE_LABEL = { probe: "sonde", collector: "collecteur" };

function Tone({ d }) {
  if (!d) return <span className="muted">—</span>;
  return <span className={`np-tone ${d.tone || "neutral"}`}>{d.text}</span>;
}

function LivenessDot({ agent, now }) {
  const state = liveness(agent, now);
  const age = ageSeconds(agent.last_seen_at, now);
  const title = state === "never" ? "jamais vue" : `vue il y a ${formatAge(age)}${agent.last_seen_via ? ` via ${agent.last_seen_via}` : ""}`;
  return <span className={`np-live ${state}`} title={title}>● {state === "never" ? "jamais" : formatAge(age)}</span>;
}

function SignalLine({ series }) {
  const { path, min, max, points } = buildLinePath(series, LINE_W, LINE_H, 6);
  if (!path) return <p className="muted">Pas assez de relevés wifi_link pour tracer une courbe (2 minimum).</p>;
  return (
    <div className="np-line-wrap">
      <svg viewBox={`0 0 ${LINE_W} ${LINE_H}`} preserveAspectRatio="none" className="np-line-svg" role="img" aria-label="Signal reçu dans le temps">
        <path d={path} className="np-line-path" />
        {points.map((p, i) => (
          <circle key={i} cx={p.x} cy={p.y} r="2.5" className="np-line-point">
            <title>{new Date(p.at).toLocaleString("fr-FR")} : {p.value} dBm</title>
          </circle>
        ))}
      </svg>
      <div className="np-line-caption muted">
        {series.length} relevés · min {min} dBm · max {max} dBm · de {new Date(series[0].at).toLocaleString("fr-FR")} à {new Date(series[series.length - 1].at).toLocaleString("fr-FR")}
      </div>
    </div>
  );
}

export default function NetprobeAgentsTab({ netprobeApiBase }) {
  const [agents, setAgents] = useState([]);
  const [latest, setLatest] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [now, setNow] = useState(Date.now());
  const [siteFilter, setSiteFilter] = useState("");

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ agentId: "", site: "", role: "probe", label: "" });
  const [created, setCreated] = useState(null);       // {agent_id, secret} affiché UNE fois
  const [busy, setBusy] = useState(false);

  const [selectedId, setSelectedId] = useState(null);
  const [history, setHistory] = useState(null);       // mesures wifi_link de la sonde sélectionnée
  const [tasksText, setTasksText] = useState("");
  const [tasksError, setTasksError] = useState(null);

  async function load() {
    const [a, l] = await Promise.all([fetchAgents(netprobeApiBase), fetchAgentsLatest(netprobeApiBase)]);
    setAgents(a);
    setLatest(l);
    setNow(Date.now());
    setLoading(false);
  }

  useEffect(() => {
    load();
    const id = setInterval(load, REFRESH_MS);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [netprobeApiBase]);

  const selected = agents.find((a) => a.agent_id === selectedId) || null;

  useEffect(() => {
    if (!selected) { setHistory(null); return; }
    setTasksText(JSON.stringify(selected.tasks || [], null, 2));
    setTasksError(null);
    setHistory(null);
    let cancelled = false;
    fetchAgentMeasurements(netprobeApiBase, selected.agent_id, "wifi_link", 300).then((rows) => {
      if (!cancelled) setHistory(rows);
    });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId, netprobeApiBase]);

  async function handleCreate(e) {
    e.preventDefault();
    setBusy(true); setError(null);
    const res = await createAgent(netprobeApiBase, { agentId: form.agentId.trim(), site: form.site.trim(), role: form.role, label: form.label.trim() });
    setBusy(false);
    if (res?.error) { setError(res.error); return; }
    setCreated({ agent_id: res.agent_id, secret: res.secret, role: res.role, site: res.site });
    setForm({ agentId: "", site: form.site, role: "probe", label: "" });
    setShowForm(false);
    load();
  }

  async function handleSaveTasks() {
    let parsed;
    try {
      parsed = JSON.parse(tasksText);
      if (!Array.isArray(parsed)) throw new Error("une liste de tâches est attendue");
    } catch (err) {
      setTasksError(`JSON invalide : ${err.message}`);
      return;
    }
    setBusy(true);
    const res = await updateAgent(netprobeApiBase, selected.agent_id, { tasks: parsed });
    setBusy(false);
    if (res?.error) { setTasksError(res.error); return; }
    setTasksError(null);
    load();
  }

  async function handleToggleActive(agent) {
    setBusy(true);
    await updateAgent(netprobeApiBase, agent.agent_id, { active: !agent.active });
    setBusy(false);
    load();
  }

  async function handleRotate(agent) {
    if (!window.confirm(`Régénérer le secret de ${agent.agent_id} ? L'appareil actuel ne pourra plus s'authentifier tant que sa configuration n'est pas mise à jour.`)) return;
    setBusy(true);
    const res = await rotateAgentSecret(netprobeApiBase, agent.agent_id);
    setBusy(false);
    if (res?.error) { setError(res.error); return; }
    setCreated({ agent_id: res.agent_id, secret: res.secret, role: res.role, site: res.site, rotated: true });
  }

  async function handleDelete(agent) {
    if (!window.confirm(`Supprimer ${agent.agent_id} ? Ses mesures sont conservées (suppression douce de la flotte).`)) return;
    setBusy(true);
    await deleteAgent(netprobeApiBase, agent.agent_id, false);
    setBusy(false);
    if (selectedId === agent.agent_id) setSelectedId(null);
    load();
  }

  const sites = [...new Set(agents.map((a) => a.site))].sort();
  const visible = siteFilter ? agents.filter((a) => a.site === siteFilter) : agents;
  const byAgent = groupLatestByAgent(latest);
  const roaming = history ? detectBssidChanges(history) : [];
  const signalSeries = history ? seriesOf(history, "signal_dbm") : [];

  return (
    <div>
      {error && <p className="hub-error">{error}</p>}

      {created && (
        <div className="hub-card hub-settings-section np-secret-box">
          <h3 style={{ marginTop: 0 }}>
            {created.rotated ? "Nouveau secret" : "Appareil créé"} : {created.agent_id} <span className="muted">({ROLE_LABEL[created.role] || created.role}, site {created.site})</span>
          </h3>
          <p>
            Ce secret n'est affiché <strong>qu'une seule fois</strong> — copiez-le dans la configuration de l'image
            (ou laissez <code>build-image.sh</code> le récupérer par <code>/agents/{created.agent_id}/provision</code>).
          </p>
          <pre className="np-secret">{created.secret}</pre>
          <p className="muted" style={{ marginBottom: 4 }}>
            Image : <code>./netprobe/agent/image/build-image.sh --api {netprobeApiBase} --agent {created.agent_id} {created.role === "probe" ? "--collector-url http://IP-DU-COLLECTEUR:6127 --wifi-ssid ... --wifi-psk ..." : "--central-url " + netprobeApiBase}</code>
          </p>
          <button className="secondary" onClick={() => setCreated(null)}>J'ai copié le secret</button>
        </div>
      )}

      <div className="hub-card hub-settings-section">
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <h3 style={{ margin: 0 }}>Flotte ({visible.length})</h3>
          {sites.length > 1 && (
            <select value={siteFilter} onChange={(e) => setSiteFilter(e.target.value)}>
              <option value="">tous les sites</option>
              {sites.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          )}
          <button className="secondary" onClick={load} disabled={busy}>⟳</button>
          <span className="muted" style={{ fontSize: 12 }}>rafraîchi toutes les {REFRESH_MS / 1000} s</span>
          <button className="secondary" style={{ marginLeft: "auto" }} onClick={() => setShowForm((v) => !v)}>{showForm ? "✕" : "+"}</button>
        </div>

        {showForm && (
          <form onSubmit={handleCreate} className="hub-settings-row" style={{ marginTop: 10, gap: 8, flexWrap: "wrap" }}>
            <input placeholder="identifiant (ex. alpha-sonde-01)" value={form.agentId} onChange={(e) => setForm({ ...form, agentId: e.target.value })} required pattern="[A-Za-z0-9][A-Za-z0-9._-]{0,63}" title="lettres, chiffres, - . _ (64 max)" />
            <input placeholder="site (ex. alpha)" value={form.site} onChange={(e) => setForm({ ...form, site: e.target.value })} required />
            <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
              <option value="probe">sonde (Pi Zero W)</option>
              <option value="collector">collecteur (Pi 3B)</option>
            </select>
            <input placeholder="libellé (emplacement)" value={form.label} onChange={(e) => setForm({ ...form, label: e.target.value })} />
            <button type="submit" disabled={busy}>Créer</button>
          </form>
        )}

        {loading ? (
          <p className="muted">Chargement…</p>
        ) : visible.length === 0 ? (
          <p className="muted">
            Aucune sonde déclarée. Créez-en une avec « + », puis construisez son image avec
            <code> netprobe/agent/image/build-image.sh</code>.
          </p>
        ) : (
          <div className="hub-table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Appareil</th><th>Rôle</th><th>Site</th><th>Libellé</th><th>Vue</th>
                  <th>WiFi</th><th>Ping</th><th>Voisinage</th><th>Pi</th><th></th>
                </tr>
              </thead>
              <tbody>
                {visible.map((a) => {
                  const m = byAgent[a.agent_id] || {};
                  const pingTask = Object.keys(m).find((t) => t.startsWith("ping:"));
                  return (
                    <tr
                      key={a.agent_id}
                      className={`np-agent-row${selectedId === a.agent_id ? " active" : ""}${a.active ? "" : " inactive"}`}
                      onClick={() => setSelectedId(selectedId === a.agent_id ? null : a.agent_id)}
                      title={a.active ? "Cliquer pour le détail" : "Désactivé : ses envois sont refusés"}
                    >
                      <td><strong>{a.agent_id}</strong>{!a.active && <span className="muted"> (inactif)</span>}</td>
                      <td>{ROLE_LABEL[a.role] || a.role}</td>
                      <td>{a.site}</td>
                      <td>{a.label || <span className="muted">—</span>}</td>
                      <td><LivenessDot agent={a} now={now} /></td>
                      <td>{a.role === "probe" ? <Tone d={describeWifiLink(m.wifi_link)} /> : <span className="muted">n/a</span>}</td>
                      <td><Tone d={pingTask ? describePing(m[pingTask]) : null} /></td>
                      <td><Tone d={describeScan(m.wifi_scan)} /></td>
                      <td><Tone d={describeSys(m.sys)} /></td>
                      <td style={{ whiteSpace: "nowrap" }} onClick={(e) => e.stopPropagation()}>
                        <button className="secondary" title={a.active ? "Désactiver" : "Réactiver"} onClick={() => handleToggleActive(a)} disabled={busy}>{a.active ? "⏸" : "▶"}</button>{" "}
                        <button className="secondary" title="Régénérer le secret" onClick={() => handleRotate(a)} disabled={busy}>🔑</button>{" "}
                        <button className="secondary" title="Supprimer de la flotte" onClick={() => handleDelete(a)} disabled={busy}>🗑</button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {selected && (
        <div className="hub-card hub-settings-section">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", flexWrap: "wrap", gap: 8 }}>
            <h3 style={{ margin: 0 }}>
              {selected.agent_id} <span className="muted">— {ROLE_LABEL[selected.role]}, {selected.site}{selected.label ? `, ${selected.label}` : ""}</span>
            </h3>
            <span className="muted" style={{ fontSize: 12 }}>
              créé le {new Date(selected.created_at).toLocaleString("fr-FR")}
              {selected.last_ip ? ` · dernière IP ${selected.last_ip}` : ""}
              {selected.last_seen_via ? ` · via ${selected.last_seen_via}` : ""}
            </span>
          </div>

          {selected.role === "probe" && (
            <>
              <h4 style={{ marginBottom: 4 }}>Signal reçu (wifi_link, {history ? history.length : "…"} derniers relevés)</h4>
              {history === null ? <p className="muted">Chargement…</p> : <SignalLine series={signalSeries} />}

              <h4 style={{ marginBottom: 4 }}>Changements de borne ({roaming.length})</h4>
              <p className="muted" style={{ marginTop: -4, marginBottom: 6 }}>
                Suivi d'itinérance : un changement de BSSID entre deux relevés. Une reconnexion sur la même borne après
                une coupure est listée à part — ce n'est pas une itinérance.
              </p>
              {history === null ? null : roaming.length === 0 ? (
                <p className="muted">Aucun changement de borne sur ces relevés.</p>
              ) : (
                <div className="hub-table-scroll" style={{ maxHeight: 220, overflowY: "auto" }}>
                  <table>
                    <thead><tr><th>Quand</th><th>De</th><th>Vers</th><th>Signal avant → après</th><th>Contexte</th></tr></thead>
                    <tbody>
                      {roaming.slice().reverse().map((ev, i) => (
                        <tr key={i}>
                          <td className="muted">{new Date(ev.at).toLocaleString("fr-FR")}</td>
                          <td><code>{ev.from}</code>{ev.from_ssid ? <span className="muted"> {ev.from_ssid}</span> : null}</td>
                          <td><code>{ev.to}</code>{ev.to_ssid ? <span className="muted"> {ev.to_ssid}</span> : null}</td>
                          <td>{ev.reconnect ? "—" : `${ev.signal_before ?? "?"} → ${ev.signal_after ?? "?"} dBm`}</td>
                          <td>
                            {ev.reconnect
                              ? <span className="np-tone warn">reconnexion même borne, coupure depuis {new Date(ev.disconnected_since).toLocaleTimeString("fr-FR")}</span>
                              : ev.after_disconnect
                                ? <span className="np-tone bad">après coupure (depuis {new Date(ev.disconnected_since).toLocaleTimeString("fr-FR")})</span>
                                : <span className="np-tone good">itinérance sans coupure</span>}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}

          <h4 style={{ marginBottom: 4 }}>Tâches {selected.role === "probe" ? "de la sonde" : "(sans objet pour un collecteur)"}</h4>
          {selected.role === "probe" && (
            <>
              <p className="muted" style={{ marginTop: -4, marginBottom: 6 }}>
                Version <code>{selected.tasks_version || "—"}</code>. Une modification est reprise par le collecteur du site à sa prochaine
                synchronisation (5 min), puis par la sonde à son prochain passage (5 min) — jamais de reflash.
                Types : <code>wifi_link</code>, <code>wifi_scan</code>, <code>ping</code>, <code>dns</code>, <code>http</code>, <code>iperf3</code>, <code>sys</code> ;
                <code> every</code> en secondes (5 minimum).
              </p>
              <textarea
                value={tasksText}
                onChange={(e) => setTasksText(e.target.value)}
                rows={Math.min(16, Math.max(4, tasksText.split("\n").length))}
                spellCheck={false}
                style={{ width: "100%", fontFamily: "monospace", fontSize: 12 }}
              />
              {tasksError && <p className="hub-error">{tasksError}</p>}
              <div style={{ display: "flex", gap: 8, marginTop: 6 }}>
                <button onClick={handleSaveTasks} disabled={busy}>Enregistrer les tâches</button>
                <button className="secondary" onClick={() => { setTasksText(JSON.stringify(selected.tasks || [], null, 2)); setTasksError(null); }}>Annuler</button>
              </div>
            </>
          )}

          {Object.keys(byAgent[selected.agent_id] || {}).length > 0 && (
            <>
              <h4 style={{ marginBottom: 4 }}>Dernière mesure par tâche</h4>
              <div className="hub-table-scroll">
                <table>
                  <thead><tr><th>Tâche</th><th>Quand</th><th>État</th><th>Données</th></tr></thead>
                  <tbody>
                    {Object.values(byAgent[selected.agent_id]).map((m) => (
                      <tr key={m.task}>
                        <td>{taskLabel(m.task)}</td>
                        <td className="muted">{new Date(m.at).toLocaleString("fr-FR")}</td>
                        <td>{m.ok ? <span className="np-tone good">ok</span> : <span className="np-tone bad">{m.error || "erreur"}</span>}</td>
                        <td><code style={{ fontSize: 11, whiteSpace: "pre-wrap", wordBreak: "break-all" }}>{JSON.stringify(m.data)}</code></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
