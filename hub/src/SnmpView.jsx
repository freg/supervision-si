import React, { useState, useEffect } from "react";
import {
  fetchSnmpTargets, createSnmpTarget, deleteSnmpTarget,
  querySnmpSystemInfo, walkSnmpInterfaces, importSnmpTargetsToGlpi,
} from "./snmpClient.js";

// Onglet SNMP (hub), livraison #227 -- interface pour snmp-api
// (#212-213, jusqu'ici accessible seulement via curl). Deux
// sections : Cibles enregistrées (communauté chiffrée côté serveur,
// #213) -> Interrogation (groupe System ou table des interfaces, sur
// une cible enregistrée OU un host+communauté en direct).
//
// ⚠️ Portée héritée de #212 -- SNMPv1/v2c seulement (pas SNMPv3),
// jamais testée contre un vrai équipement dans l'environnement de
// développement (voir snmp/README.md). Cette interface hérite donc
// de la même réserve : le bon FONCTIONNEMENT de cet écran (rendu,
// appels HTTP, affichage) est vérifié, mais pas la fidélité des
// résultats renvoyés par un VRAI équipement SNMP.

const EMPTY_TARGET_FORM = { label: "", host: "", port: "161", community: "" };
const EMPTY_QUERY_FORM = { mode: "target", targetId: "", host: "", community: "", port: "161" };

const IF_STATUS_ICONS = { up: "🟢", down: "🔴", testing: "🟡", unknown: "⚪", dormant: "🟠", notPresent: "⚪", lowerLayerDown: "🔴" };

export default function SnmpView({ onBack, snmpApiBase, glpiApiBase, login }) {
  const [targets, setTargets] = useState([]);
  const [targetForm, setTargetForm] = useState(EMPTY_TARGET_FORM);
  const [queryForm, setQueryForm] = useState(EMPTY_QUERY_FORM);
  const [systemInfo, setSystemInfo] = useState(null);
  const [interfaces, setInterfaces] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [glpiPreview, setGlpiPreview] = useState(null);

  useEffect(() => {
    fetchSnmpTargets(snmpApiBase).then(setTargets);
  }, [snmpApiBase]);

  async function reloadTargets() {
    setTargets(await fetchSnmpTargets(snmpApiBase));
  }

  async function withBusy(fn) {
    setBusy(true);
    setError(null);
    try {
      const result = await fn();
      if (result && result.error) setError(result.error);
      return result;
    } finally {
      setBusy(false);
    }
  }

  async function handleCreateTarget(e) {
    e.preventDefault();
    const result = await withBusy(() => createSnmpTarget(snmpApiBase, { ...targetForm, actor: login }));
    if (result && !result.error) {
      setTargetForm(EMPTY_TARGET_FORM);
      reloadTargets();
    }
  }

  async function handleDeleteTarget(id) {
    await withBusy(() => deleteSnmpTarget(snmpApiBase, id));
    reloadTargets();
  }

  function queryParams() {
    if (queryForm.mode === "target") {
      return { targetId: queryForm.targetId, port: queryForm.port };
    }
    return { host: queryForm.host, community: queryForm.community, port: queryForm.port };
  }

  async function handleQuerySystem() {
    setSystemInfo(null);
    const result = await withBusy(() => querySnmpSystemInfo(snmpApiBase, queryParams()));
    if (result && !result.error) setSystemInfo(result);
  }

  async function handleWalkInterfaces() {
    setInterfaces(null);
    const result = await withBusy(() => walkSnmpInterfaces(snmpApiBase, queryParams()));
    if (result && !result.error) setInterfaces(result.interfaces || []);
  }

  async function handleGlpiPreview() {
    const result = await withBusy(() => importSnmpTargetsToGlpi(glpiApiBase, true));
    if (result && !result.error) setGlpiPreview(result);
  }
  async function handleGlpiConfirm() {
    const result = await withBusy(() => importSnmpTargetsToGlpi(glpiApiBase, false));
    if (result && !result.error) setGlpiPreview(result);
  }

  const canQuery = queryForm.mode === "target" ? !!queryForm.targetId : !!(queryForm.host && queryForm.community);

  return (
    <div className="hub-settings hub-settings-wide">
      <div className="hub-settings-topbar">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h1>📡 SNMP</h1>
      </div>

      {error && (
        <div className="hub-card" style={{ borderColor: "var(--danger)" }}>
          <p style={{ margin: 0 }}>⚠️ {error}</p>
        </div>
      )}

      <div className="hub-card hub-settings-section">
        <h2>Cibles enregistrées ({targets.length})</h2>
        <p className="muted">
          Communauté chiffrée côté serveur (jamais exposée ici). Une cible enregistrée évite de
          ressaisir la communauté à chaque interrogation.
        </p>
        <ul>
          {targets.map((t) => (
            <li key={t.id}>
              <strong>{t.label}</strong> — {t.host}:{t.port}{" "}
              <button className="secondary" disabled={busy} onClick={() => handleDeleteTarget(t.id)}>
                Supprimer
              </button>
            </li>
          ))}
        </ul>
        <form onSubmit={handleCreateTarget} style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "flex-end" }}>
          <div className="hub-settings-row">
            <label>Nom</label>
            <input value={targetForm.label} onChange={(e) => setTargetForm({ ...targetForm, label: e.target.value })} placeholder="ex. Switch étage 2" />
          </div>
          <div className="hub-settings-row">
            <label>Hôte</label>
            <input value={targetForm.host} onChange={(e) => setTargetForm({ ...targetForm, host: e.target.value })} placeholder="ex. 192.168.10.5" />
          </div>
          <div className="hub-settings-row">
            <label>Port</label>
            <input value={targetForm.port} onChange={(e) => setTargetForm({ ...targetForm, port: e.target.value })} style={{ width: 70 }} />
          </div>
          <div className="hub-settings-row">
            <label>Communauté</label>
            <input type="password" value={targetForm.community} onChange={(e) => setTargetForm({ ...targetForm, community: e.target.value })} autoComplete="new-password" />
          </div>
          <button type="submit" disabled={busy || !targetForm.label || !targetForm.host || !targetForm.community}>
            Créer
          </button>
        </form>
      </div>

      <div className="hub-card hub-settings-section">
        <h2>Import vers GLPI (livraison #232)</h2>
        <p className="muted">
          Interroge chaque cible enregistrée ci-dessus et crée/complète l'entrée GLPI
          correspondante (NetworkEquipment). Toujours commencer par un aperçu avant de confirmer.
        </p>
        <div style={{ display: "flex", gap: 8 }}>
          <button disabled={busy || targets.length === 0} onClick={handleGlpiPreview}>Aperçu (dry-run)</button>
          {glpiPreview && (
            <button disabled={busy} onClick={handleGlpiConfirm}>Confirmer l'import</button>
          )}
        </div>
        {glpiPreview && (
          <div style={{ marginTop: 12 }}>
            <p className="muted">
              {glpiPreview.source_target_count} cible(s) analysée(s) --{" "}
              {(glpiPreview.created || []).length} à créer,{" "}
              {(glpiPreview.skipped_existing || []).length} déjà présente(s),{" "}
              {(glpiPreview.errors || []).length} erreur(s) (cible injoignable, etc.).
            </p>
            {(glpiPreview.errors || []).length > 0 && (
              <ul>
                {glpiPreview.errors.map((line, idx) => <li key={idx} style={{ color: "var(--danger)" }}>{line}</li>)}
              </ul>
            )}
          </div>
        )}
      </div>

      <div className="hub-card hub-settings-section">
        <h2>Interroger une cible</h2>
        <div className="hub-settings-row">
          <label>Source</label>
          <select value={queryForm.mode} onChange={(e) => setQueryForm({ ...queryForm, mode: e.target.value })}>
            <option value="target">Cible enregistrée</option>
            <option value="direct">Host + communauté en direct</option>
          </select>
        </div>
        {queryForm.mode === "target" ? (
          <div className="hub-settings-row">
            <label>Cible</label>
            <select value={queryForm.targetId} onChange={(e) => setQueryForm({ ...queryForm, targetId: e.target.value })}>
              <option value="">— choisir —</option>
              {targets.map((t) => (
                <option key={t.id} value={t.id}>{t.label} ({t.host})</option>
              ))}
            </select>
          </div>
        ) : (
          <>
            <div className="hub-settings-row">
              <label>Hôte</label>
              <input value={queryForm.host} onChange={(e) => setQueryForm({ ...queryForm, host: e.target.value })} placeholder="ex. 192.168.10.5" />
            </div>
            <div className="hub-settings-row">
              <label>Communauté</label>
              <input type="password" value={queryForm.community} onChange={(e) => setQueryForm({ ...queryForm, community: e.target.value })} autoComplete="new-password" />
            </div>
          </>
        )}
        <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
          <button disabled={busy || !canQuery} onClick={handleQuerySystem}>
            Interroger (informations système)
          </button>
          <button disabled={busy || !canQuery} onClick={handleWalkInterfaces}>
            Lister les interfaces
          </button>
        </div>

        {systemInfo && (
          <div style={{ marginTop: 16 }}>
            <h3>Informations système — {systemInfo.host}:{systemInfo.port}</h3>
            <table>
              <tbody>
                {Object.entries(systemInfo.system || {}).map(([key, value]) => (
                  <tr key={key}><td className="muted">{key}</td><td>{value || <span className="muted">—</span>}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {interfaces && (
          <div style={{ marginTop: 16 }}>
            <h3>Interfaces ({interfaces.length})</h3>
            {interfaces.length === 0 ? (
              <p className="muted">Aucune interface renvoyée par la cible.</p>
            ) : (
              <table>
                <thead>
                  <tr><th>Description</th><th>Statut</th><th>Débit</th></tr>
                </thead>
                <tbody>
                  {interfaces.map((iface, idx) => (
                    <tr key={idx}>
                      <td>{iface.ifDescr}</td>
                      <td>{IF_STATUS_ICONS[iface.ifOperStatus] || ""} {iface.ifOperStatus}</td>
                      <td>{iface.ifSpeed}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
