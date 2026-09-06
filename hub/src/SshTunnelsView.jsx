import React, { useState, useEffect } from "react";
import {
  fetchKeys, setKeyEnabled, deleteKey, generateKey,
  fetchConnections, createConnection, deleteConnection, fetchConnectionUsageHistory,
  fetchTunnels, createTunnel, deleteTunnel, startTunnel, stopTunnel,
  fetchMounts, createMount, deleteMount, mountAction, unmountAction, fetchMountStats,
} from "./sshTunnelsClient.js";

// Onglet ssh-tunnels (hub), livraison #175 -- interface pour
// ssh-tunnels-api (#159, jusqu'ici accessible seulement via curl).
// Quatre sections dans l'ordre logique d'usage : Clés (déjà en
// place sur le disque, juste activables/consultables ici -- jamais
// gérées/générées par ce module, voir ssh-tunnels/README.md) ->
// Connexions (regroupent host/user/clé) -> Tunnels (le cœur du
// module, démarrage/arrêt de vrais processus ssh) -> Montages SSHFS
// (interface préparée, action réelle PAS ENCORE implémentée --
// boutons présents mais le message d'erreur 501 de l'API s'affiche
// tel quel, jamais masqué ou contourné ici).

const EMPTY_CONNECTION_FORM = {
  label: "", sshHost: "", sshPort: "22", sshUser: "", sshKeyId: "",
  authMethod: "key", passwordUsername: "", password: "",
};
const EMPTY_TUNNEL_FORM = { connectionId: "", label: "", remoteHost: "", remotePort: "", localPort: "" };
const EMPTY_MOUNT_FORM = { connectionId: "", label: "", remotePath: "", localMountPath: "" };
// Génération de clé (livraison #277) -- filename vide par défaut,
// jamais pré-rempli (éviter une génération accidentelle avec un nom
// générique non voulu).
const EMPTY_GENERATE_KEY_FORM = { filename: "", passphrase: "", keyType: "ed25519" };

// Supervision (livraison #182) -- formatage lisible d'un nombre
// d'octets. Pure, testée directement (voir tests).
function formatBytes(bytes) {
  if (typeof bytes !== "number" || Number.isNaN(bytes)) return "?";
  const units = ["o", "Ko", "Mo", "Go", "To"];
  let value = bytes;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  return `${value.toFixed(unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
}

export default function SshTunnelsView({ onBack, sshTunnelsApiBase, login }) {
  const [keys, setKeys] = useState([]);
  const [connections, setConnections] = useState([]);
  // Historique d'usage (livraison #210, backlog item 12) -- chargé
  // à la demande, PAR connexion (jamais tout charger d'un coup pour
  // toutes les connexions -- inutile tant que la personne ne
  // consulte pas cet historique précis).
  const [expandedHistoryId, setExpandedHistoryId] = useState(null);
  const [usageHistory, setUsageHistory] = useState({});
  const [tunnels, setTunnels] = useState([]);
  const [mounts, setMounts] = useState([]);
  const [hasLoadedOnce, setHasLoadedOnce] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [connectionForm, setConnectionForm] = useState(EMPTY_CONNECTION_FORM);
  const [generateKeyForm, setGenerateKeyForm] = useState(EMPTY_GENERATE_KEY_FORM);
  const [tunnelForm, setTunnelForm] = useState(EMPTY_TUNNEL_FORM);
  const [mountForm, setMountForm] = useState(EMPTY_MOUNT_FORM);
  // Indicateur visuel "action EN COURS" (livraison #197, demandé
  // explicitement -- "ajouter une prise en compte visuel des
  // tentatives de lancement (diode orange ?)"). `busy` (ci-dessus)
  // est un booléen GLOBAL (désactive TOUS les boutons pendant N'IMPORTE
  // QUELLE action) -- insuffisant pour distinguer VISUELLEMENT LEQUEL
  // tunnel/montage est concerné. Deux Set() séparés (démarrage vs
  // arrêt) -- une même ligne peut en théorie enchaîner les deux
  // (rare mais pas exclu), jamais une seule clé qui écraserait l'état
  // de l'autre action.
  const [startingTunnelIds, setStartingTunnelIds] = useState(() => new Set());
  const [stoppingTunnelIds, setStoppingTunnelIds] = useState(() => new Set());
  // Même motif que ci-dessus, pour les actions de montage SSHFS
  // (livraison #197, "idem partout où un délai est normal" -- le
  // montage a un délai RÉEL souvent plus long qu'un tunnel, cette
  // diode y est donc au moins aussi utile).
  const [mountingIds, setMountingIds] = useState(() => new Set());
  const [unmountingIds, setUnmountingIds] = useState(() => new Set());
  // Supervision (livraison #182) -- résultat par montage, indexé par
  // id. undefined = jamais demandé, null = en cours de calcul,
  // objet = résultat (ou {error: ...}).
  const [mountStats, setMountStats] = useState({});

  async function loadAll() {
    const [k, c, t, m] = await Promise.all([
      fetchKeys(sshTunnelsApiBase),
      fetchConnections(sshTunnelsApiBase),
      fetchTunnels(sshTunnelsApiBase),
      fetchMounts(sshTunnelsApiBase),
    ]);
    setKeys(k);
    setConnections(c);
    setTunnels(t);
    setMounts(m);
    setHasLoadedOnce(true);
  }

  useEffect(() => {
    loadAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function connectionLabel(connectionId) {
    const c = connections.find((x) => x.id === connectionId);
    return c ? c.label : `#${connectionId}`;
  }

  async function withBusy(fn) {
    setBusy(true);
    setError(null);
    const result = await fn();
    setBusy(false);
    if (result && result.error) {
      setError(result.error);
    }
    return result;
  }

  async function handleToggleKey(key) {
    await withBusy(() => setKeyEnabled(sshTunnelsApiBase, key.id, !key.enabled));
    loadAll();
  }

  async function handleDeleteKey(key) {
    if (!window.confirm(`Supprimer définitivement "${key.filename}" ? Fichier ET registre, AUCUNE sauvegarde conservée -- irréversible.`)) return;
    const result = await withBusy(() => deleteKey(sshTunnelsApiBase, key.id));
    if (result.error) setError(result.error);
    else loadAll();
  }

  async function handleGenerateKey(e) {
    e.preventDefault();
    const result = await withBusy(() => generateKey(sshTunnelsApiBase, generateKeyForm));
    if (!result.error) {
      setGenerateKeyForm(EMPTY_GENERATE_KEY_FORM);
      loadAll();
    } else {
      setError(result.error);
    }
  }

  async function handleCreateConnection(e) {
    e.preventDefault();
    const result = await withBusy(() => createConnection(sshTunnelsApiBase, { ...connectionForm, actor: login }));
    if (!result.error) {
      setConnectionForm(EMPTY_CONNECTION_FORM);
      loadAll();
    }
  }

  async function handleDeleteConnection(id) {
    await withBusy(() => deleteConnection(sshTunnelsApiBase, id));
    loadAll();
  }

  async function handleToggleHistory(connectionId) {
    if (expandedHistoryId === connectionId) {
      setExpandedHistoryId(null);
      return;
    }
    setExpandedHistoryId(connectionId);
    if (!usageHistory[connectionId]) {
      const result = await fetchConnectionUsageHistory(sshTunnelsApiBase, connectionId);
      setUsageHistory((prev) => ({ ...prev, [connectionId]: result.error ? [] : result }));
    }
  }

  async function handleCreateTunnel(e) {
    e.preventDefault();
    const result = await withBusy(() => createTunnel(sshTunnelsApiBase, { ...tunnelForm, actor: login }));
    if (!result.error) {
      setTunnelForm(EMPTY_TUNNEL_FORM);
      loadAll();
    }
  }

  async function handleDeleteTunnel(id) {
    await withBusy(() => deleteTunnel(sshTunnelsApiBase, id));
    loadAll();
  }

  async function handleStartTunnel(id) {
    setStartingTunnelIds((prev) => new Set(prev).add(id));
    await withBusy(() => startTunnel(sshTunnelsApiBase, id));
    setStartingTunnelIds((prev) => { const next = new Set(prev); next.delete(id); return next; });
    loadAll();
  }

  async function handleStopTunnel(id) {
    setStoppingTunnelIds((prev) => new Set(prev).add(id));
    await withBusy(() => stopTunnel(sshTunnelsApiBase, id));
    setStoppingTunnelIds((prev) => { const next = new Set(prev); next.delete(id); return next; });
    loadAll();
  }

  async function handleCreateMount(e) {
    e.preventDefault();
    const result = await withBusy(() => createMount(sshTunnelsApiBase, { ...mountForm, actor: login }));
    if (!result.error) {
      setMountForm(EMPTY_MOUNT_FORM);
      loadAll();
    }
  }

  async function handleDeleteMount(id) {
    await withBusy(() => deleteMount(sshTunnelsApiBase, id));
    loadAll();
  }

  async function handleMountAction(id) {
    setMountingIds((prev) => new Set(prev).add(id));
    await withBusy(() => mountAction(sshTunnelsApiBase, id));
    setMountingIds((prev) => { const next = new Set(prev); next.delete(id); return next; });
    loadAll();
  }

  async function handleUnmountAction(id) {
    setUnmountingIds((prev) => new Set(prev).add(id));
    await withBusy(() => unmountAction(sshTunnelsApiBase, id));
    setUnmountingIds((prev) => { const next = new Set(prev); next.delete(id); return next; });
    setMountStats((prev) => ({ ...prev, [id]: undefined }));
    loadAll();
  }

  async function handleFetchStats(id) {
    setMountStats((prev) => ({ ...prev, [id]: null }));
    const result = await fetchMountStats(sshTunnelsApiBase, id);
    setMountStats((prev) => ({ ...prev, [id]: result }));
  }

  const statusLabel = { running: "🟢 en cours", stopped: "⚪ arrêté", error: "🔴 erreur" };
  const mountStatusLabel = { mounted: "🟢 monté", unmounted: "⚪ démonté", error: "🔴 erreur" };

  return (
    <div className="hub-settings hub-settings-wide">
      <div className="hub-settings-topbar">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h1>🔐 Tunnels SSH</h1>
      </div>
      {error && <p className="hub-error">{error}</p>}
      {!hasLoadedOnce && <p className="muted">Chargement…</p>}

      <div className="hub-card hub-settings-section">
        <h2>Clés SSH ({keys.length})</h2>
        <p className="muted">
          Déposées manuellement sur le disque (répertoire protégé), OU générées directement
          ci-dessous (livraison #277) -- consultation, activation/désactivation, génération et
          suppression réelle (fichier + registre, aucune sauvegarde conservée).
        </p>
        {keys.length === 0 && <p className="muted">Aucune clé trouvée.</p>}
        <ul>
          {keys.map((k) => (
            <li key={k.id}>
              {k.filename} {k.key_type ? `(${k.key_type})` : ""}{" "}
              {k.fingerprint && <span className="muted">{k.fingerprint}</span>}{" "}
              <button className="secondary" disabled={busy} onClick={() => handleToggleKey(k)}>
                {k.enabled ? "Désactiver" : "Activer"}
              </button>
              {" "}{k.enabled ? "✅" : "🚫"}{" "}
              <button className="secondary" disabled={busy} onClick={() => handleDeleteKey(k)}>🗑 Supprimer</button>
            </li>
          ))}
        </ul>

        <h3>Générer une nouvelle clé</h3>
        <p className="muted" style={{ marginTop: -4 }}>
          Avec passphrase (plus sûre, saisie requise à chaque déverrouillage) ou sans (usage
          automatisé non interactif). ⚠️ Sans navigateur disponible pour tester ici -- vérifié
          uniquement contre la logique du backend, pas en conditions réelles.
        </p>
        <form onSubmit={handleGenerateKey} style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "flex-end" }}>
          <div className="hub-settings-row" style={{ margin: 0 }}>
            <label>Nom du fichier</label>
            <input value={generateKeyForm.filename} onChange={(e) => setGenerateKeyForm({ ...generateKeyForm, filename: e.target.value })} required />
          </div>
          <div className="hub-settings-row" style={{ margin: 0 }}>
            <label>Type</label>
            <select value={generateKeyForm.keyType} onChange={(e) => setGenerateKeyForm({ ...generateKeyForm, keyType: e.target.value })}>
              <option value="ed25519">ed25519</option>
              <option value="rsa">rsa</option>
              <option value="ecdsa">ecdsa</option>
            </select>
          </div>
          <div className="hub-settings-row" style={{ margin: 0 }}>
            <label>Passphrase (optionnel)</label>
            <input type="password" value={generateKeyForm.passphrase} onChange={(e) => setGenerateKeyForm({ ...generateKeyForm, passphrase: e.target.value })} placeholder="vide = sans passphrase" />
          </div>
          <button type="submit" disabled={busy}>Générer</button>
        </form>
      </div>

      <div className="hub-card hub-settings-section">
        <h2>Connexions SSH ({connections.length})</h2>
        <ul>
          {connections.map((c) => (
            <li key={c.id} style={{ marginBottom: 6 }}>
              <strong>{c.label}</strong> — {c.auth_method === "password" ? "🔒" : "🔑"}{" "}
              {c.ssh_user}@{c.ssh_host}:{c.ssh_port}{" "}
              <button className="secondary" disabled={busy} onClick={() => handleDeleteConnection(c.id)}>
                Supprimer
              </button>{" "}
              <button className="secondary" onClick={() => handleToggleHistory(c.id)}>
                {expandedHistoryId === c.id ? "Masquer l'historique" : "Historique"}
              </button>
              {expandedHistoryId === c.id && (
                <div style={{ marginTop: 6, marginLeft: 16 }}>
                  {!usageHistory[c.id] ? (
                    <p className="muted">Chargement…</p>
                  ) : usageHistory[c.id].length === 0 ? (
                    <p className="muted">Aucun usage enregistré pour cette connexion.</p>
                  ) : (
                    <table style={{ fontSize: 13 }}>
                      <thead>
                        <tr><th>Date</th><th>Action</th><th>Auth.</th><th>Résultat</th><th>Durée</th></tr>
                      </thead>
                      <tbody>
                        {usageHistory[c.id].map((h) => (
                          <tr key={h.id}>
                            <td className="muted">{new Date(h.started_at).toLocaleString("fr-FR")}</td>
                            <td>{h.action_type === "mount" ? "Montage" : "Tunnel"}</td>
                            <td>{h.auth_method === "password" ? "🔒 mot de passe" : "🔑 clé"}</td>
                            <td>{h.success ? "✅ succès" : `❌ échec${h.error_message ? ` (${h.error_message})` : ""}`}</td>
                            <td className="muted">
                              {h.ended_at
                                ? `${Math.round((new Date(h.ended_at) - new Date(h.started_at)) / 60000)} min`
                                : h.success ? "en cours" : "—"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              )}
            </li>
          ))}
        </ul>
        <form onSubmit={handleCreateConnection} style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "flex-end" }}>
          <div className="hub-settings-row">
            <label>Nom</label>
            <input value={connectionForm.label} onChange={(e) => setConnectionForm({ ...connectionForm, label: e.target.value })} placeholder="ex. Serveur legacy" />
          </div>
          <div className="hub-settings-row">
            <label>Hôte SSH</label>
            <input value={connectionForm.sshHost} onChange={(e) => setConnectionForm({ ...connectionForm, sshHost: e.target.value })} placeholder="ex. srv.exemple.local" />
          </div>
          <div className="hub-settings-row">
            <label>Port</label>
            <input value={connectionForm.sshPort} onChange={(e) => setConnectionForm({ ...connectionForm, sshPort: e.target.value })} style={{ width: 70 }} />
          </div>
          <div className="hub-settings-row">
            <label>Authentification</label>
            <select value={connectionForm.authMethod} onChange={(e) => setConnectionForm({ ...connectionForm, authMethod: e.target.value })}>
              <option value="key">Par clé</option>
              <option value="password">Par mot de passe (livraison #210 -- vieux systèmes)</option>
            </select>
          </div>
          {connectionForm.authMethod === "key" ? (
            <>
              <div className="hub-settings-row">
                <label>Utilisateur</label>
                <input value={connectionForm.sshUser} onChange={(e) => setConnectionForm({ ...connectionForm, sshUser: e.target.value })} />
              </div>
              <div className="hub-settings-row">
                <label>Clé</label>
                <select value={connectionForm.sshKeyId} onChange={(e) => setConnectionForm({ ...connectionForm, sshKeyId: e.target.value })}>
                  <option value="">— choisir —</option>
                  {keys.filter((k) => k.enabled).map((k) => (
                    <option key={k.id} value={k.id}>{k.filename}</option>
                  ))}
                </select>
              </div>
            </>
          ) : (
            <>
              <div className="hub-settings-row">
                <label>Utilisateur</label>
                <input value={connectionForm.passwordUsername} onChange={(e) => setConnectionForm({ ...connectionForm, passwordUsername: e.target.value })} />
              </div>
              <div className="hub-settings-row">
                <label>Mot de passe</label>
                <input type="password" value={connectionForm.password} onChange={(e) => setConnectionForm({ ...connectionForm, password: e.target.value })} autoComplete="new-password" />
              </div>
            </>
          )}
          <button
            type="submit"
            disabled={
              busy || !connectionForm.label || !connectionForm.sshHost ||
              (connectionForm.authMethod === "key"
                ? !connectionForm.sshUser || !connectionForm.sshKeyId
                : !connectionForm.passwordUsername || !connectionForm.password)
            }
          >
            Créer
          </button>
        </form>
      </div>

      <div className="hub-card hub-settings-section">
        <h2>Tunnels ({tunnels.length})</h2>
        <ul>
          {tunnels.map((t) => {
            // Diode ORANGE (livraison #197, demandé explicitement)
            // -- affichée PENDANT l'appel réseau de démarrage/arrêt,
            // AVANT que le serveur ait confirmé quoi que ce soit --
            // remplace temporairement le statut réel (qui resterait
            // "arrêté" jusqu'à la fin de l'appel, laissant croire à
            // tort que rien ne se passe).
            const displayStatus = startingTunnelIds.has(t.id) ? "🟠 démarrage…"
              : stoppingTunnelIds.has(t.id) ? "🟠 arrêt…"
              : statusLabel[t.status] || t.status;
            return (
            <li key={t.id}>
              <strong>{t.label}</strong> — via {connectionLabel(t.connection_id)} —{" "}
              127.0.0.1:{t.local_port} → {t.remote_host}:{t.remote_port} —{" "}
              {displayStatus}
              {t.last_error && <span className="hub-error"> ({t.last_error})</span>}{" "}
              {t.status === "running" ? (
                <button className="secondary" disabled={busy} onClick={() => handleStopTunnel(t.id)}>Arrêter</button>
              ) : (
                <button className="secondary" disabled={busy} onClick={() => handleStartTunnel(t.id)}>Démarrer</button>
              )}
              {" "}
              <button className="secondary" disabled={busy} onClick={() => handleDeleteTunnel(t.id)}>Supprimer</button>
            </li>
            );
          })}
        </ul>
        <form onSubmit={handleCreateTunnel} style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "flex-end" }}>
          <div className="hub-settings-row">
            <label>Connexion</label>
            <select value={tunnelForm.connectionId} onChange={(e) => setTunnelForm({ ...tunnelForm, connectionId: e.target.value })}>
              <option value="">— choisir —</option>
              {connections.map((c) => (
                <option key={c.id} value={c.id}>{c.label}</option>
              ))}
            </select>
          </div>
          <div className="hub-settings-row">
            <label>Nom</label>
            <input value={tunnelForm.label} onChange={(e) => setTunnelForm({ ...tunnelForm, label: e.target.value })} placeholder="ex. MySQL prod" />
          </div>
          <div className="hub-settings-row">
            <label>Hôte distant</label>
            <input value={tunnelForm.remoteHost} onChange={(e) => setTunnelForm({ ...tunnelForm, remoteHost: e.target.value })} placeholder="ex. 127.0.0.1" />
          </div>
          <div className="hub-settings-row">
            <label>Port distant</label>
            <input value={tunnelForm.remotePort} onChange={(e) => setTunnelForm({ ...tunnelForm, remotePort: e.target.value })} style={{ width: 80 }} />
          </div>
          <div className="hub-settings-row">
            <label>Port local</label>
            <input value={tunnelForm.localPort} onChange={(e) => setTunnelForm({ ...tunnelForm, localPort: e.target.value })} style={{ width: 80 }} />
          </div>
          <button
            type="submit"
            disabled={busy || !tunnelForm.connectionId || !tunnelForm.label || !tunnelForm.remoteHost || !tunnelForm.remotePort || !tunnelForm.localPort}
          >
            Créer
          </button>
        </form>
      </div>

      <div className="hub-card hub-settings-section">
        <h2>Montages SSHFS ({mounts.length})</h2>
        <p className="muted">
          Le point de montage est un NOM (jamais un chemin absolu ni <code>..</code>) --
          il apparaîtra sous le dossier de montages partagé configuré côté serveur.
        </p>
        <ul>
          {mounts.map((m) => {
            const stats = mountStats[m.id];
            const displayMountStatus = mountingIds.has(m.id) ? "🟠 montage…"
              : unmountingIds.has(m.id) ? "🟠 démontage…"
              : mountStatusLabel[m.status] || m.status;
            return (
              <li key={m.id} style={{ marginBottom: 8 }}>
                <strong>{m.label}</strong> — via {connectionLabel(m.connection_id)} —{" "}
                {m.remote_path} → {m.local_mount_path} —{" "}
                {displayMountStatus}
                {m.last_error && <span className="hub-error"> ({m.last_error})</span>}{" "}
                <button className="secondary" disabled={busy} onClick={() => handleMountAction(m.id)}>Monter</button>
                {" "}
                <button className="secondary" disabled={busy} onClick={() => handleUnmountAction(m.id)}>Démonter</button>
                {" "}
                <button className="secondary" disabled={busy} onClick={() => handleDeleteMount(m.id)}>Supprimer</button>
                {m.status === "mounted" && (
                  <>
                    {" "}
                    <button className="secondary" disabled={busy || stats === null} onClick={() => handleFetchStats(m.id)}>
                      {stats === null ? "Calcul…" : "Stats"}
                    </button>
                  </>
                )}
                {stats && stats !== null && (
                  <div className="muted" style={{ marginLeft: 16, fontSize: 13 }}>
                    {stats.error ? (
                      <span className="hub-error">{stats.error}</span>
                    ) : stats.warning ? (
                      <span className="hub-error">{stats.warning}</span>
                    ) : (
                      <>
                        Espace : {formatBytes(stats.disk.available_bytes)} libres sur {formatBytes(stats.disk.total_bytes)}
                        {" — "}Inodes : {stats.inodes.free.toLocaleString()} libres sur {stats.inodes.total.toLocaleString()}
                        {typeof stats.latency_ms === "number" && <> — Latence : {stats.latency_ms.toFixed(1)} ms</>}
                        {!stats.pid_alive && <span className="hub-error"> — ⚠️ processus introuvable</span>}
                      </>
                    )}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
        <form onSubmit={handleCreateMount} style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "flex-end" }}>
          <div className="hub-settings-row">
            <label>Connexion</label>
            <select value={mountForm.connectionId} onChange={(e) => setMountForm({ ...mountForm, connectionId: e.target.value })}>
              <option value="">— choisir —</option>
              {connections.map((c) => (
                <option key={c.id} value={c.id}>{c.label}</option>
              ))}
            </select>
          </div>
          <div className="hub-settings-row">
            <label>Nom</label>
            <input value={mountForm.label} onChange={(e) => setMountForm({ ...mountForm, label: e.target.value })} placeholder="ex. Partage docs" />
          </div>
          <div className="hub-settings-row">
            <label>Chemin distant</label>
            <input value={mountForm.remotePath} onChange={(e) => setMountForm({ ...mountForm, remotePath: e.target.value })} placeholder="ex. /srv/partage" />
          </div>
          <div className="hub-settings-row">
            <label>Nom du point de montage</label>
            <input value={mountForm.localMountPath} onChange={(e) => setMountForm({ ...mountForm, localMountPath: e.target.value })} placeholder="ex. partage-docs" />
          </div>
          <button
            type="submit"
            disabled={busy || !mountForm.connectionId || !mountForm.label || !mountForm.remotePath || !mountForm.localMountPath}
          >
            Créer
          </button>
        </form>
      </div>
    </div>
  );
}
