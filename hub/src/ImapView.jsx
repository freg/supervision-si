import React, { useState, useEffect } from "react";
import {
  fetchFolders, createFolder, deleteFolder,
  fetchMessages, fetchMessage, moveMessage, interpretMessage,
  fetchRules, createRule, updateRule, deleteRule, applyRules,
  fetchInterpreters, createInterpreter, updateInterpreter, deleteInterpreter,
} from "./imapClient.js";

// Onglet client IMAP (hub), livraison #230 -- PREMIÈRE interface pour
// imap-client-api : le backend était déjà construit (#179-191) mais
// AUCUNE interface n'existait, malgré ce que le backlog laissait
// entendre ("livré") -- découvert en cherchant où l'ajouter.
//
// Quatre sous-onglets : Dossiers -> Messages (lecture, déplacement,
// interprétation à la demande) -> Règles de tri -> Interpréteurs
// (dont le connecteur source, #230 -- champ "target_source").
//
// ⚠️ Jamais testé contre un vrai serveur IMAP (réseau restreint dans
// l'environnement de développement, voir imap-client/README.md).

const EMPTY_INTERPRETER_FORM = { name: "", match_subject: "", match_from: "", target_source: "", fields: [{ name: "", source: "subject", pattern: "" }] };
const EMPTY_RULE_FORM = { name: "", watch_folder: "INBOX", match_subject: "", match_from: "", match_unseen_only: false, action_move_to: "", action_add_label: "", action_mark_seen: false };

export default function ImapView({ onBack, imapApiBase }) {
  const [subTab, setSubTab] = useState("folders");
  const [folders, setFolders] = useState([]);
  const [newFolderName, setNewFolderName] = useState("");
  const [messages, setMessages] = useState([]);
  const [messagesFolder, setMessagesFolder] = useState("INBOX");
  const [selectedMessage, setSelectedMessage] = useState(null);
  const [interpretResult, setInterpretResult] = useState(null);
  const [rules, setRules] = useState([]);
  const [ruleForm, setRuleForm] = useState(EMPTY_RULE_FORM);
  const [interpreters, setInterpreters] = useState([]);
  const [interpreterForm, setInterpreterForm] = useState(EMPTY_INTERPRETER_FORM);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  // Suivi SÉPARÉ de busy (livraison #369, backlog item 18) -- "busy"
  // est partagé par TOUTES les actions de ce composant (créer/
  // activer/supprimer une règle, interpréter un message...), jamais
  // assez précis pour distinguer QUEL message est en cours
  // d'interprétation -- ce bouton restait juste désactivé sans jamais
  // changer de texte, contrairement au motif déjà établi ailleurs
  // (SshTunnelsView.jsx, GedView.jsx, SchemaAnalyzerView.jsx).
  const [interpretingUid, setInterpretingUid] = useState(null);

  useEffect(() => { loadFolders(); }, [imapApiBase]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (subTab === "rules") loadRules();
    if (subTab === "interpreters") loadInterpreters();
    if (subTab === "messages") loadMessages();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [subTab]);

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

  async function loadFolders() {
    setFolders(await fetchFolders(imapApiBase));
  }
  async function loadMessages() {
    const result = await withBusy(() => fetchMessages(imapApiBase, { folder: messagesFolder, limit: 50 }));
    if (result && !result.error) setMessages(result.messages || []);
  }
  async function loadRules() {
    setRules(await fetchRules(imapApiBase));
  }
  async function loadInterpreters() {
    setInterpreters(await fetchInterpreters(imapApiBase));
  }

  async function handleCreateFolder(e) {
    e.preventDefault();
    const result = await withBusy(() => createFolder(imapApiBase, newFolderName));
    if (result && !result.error) { setNewFolderName(""); loadFolders(); }
  }
  async function handleDeleteFolder(name) {
    await withBusy(() => deleteFolder(imapApiBase, name));
    loadFolders();
  }

  async function handleOpenMessage(uid) {
    setInterpretResult(null);
    const result = await withBusy(() => fetchMessage(imapApiBase, uid, messagesFolder));
    if (result && !result.error) setSelectedMessage(result);
  }
  async function handleMoveMessage(uid, toFolder) {
    await withBusy(() => moveMessage(imapApiBase, uid, messagesFolder, toFolder));
    setSelectedMessage(null);
    loadMessages();
  }
  async function handleInterpret(uid) {
    setInterpretingUid(uid);
    const result = await withBusy(() => interpretMessage(imapApiBase, uid, messagesFolder));
    setInterpretingUid(null);
    setInterpretResult(result);
  }

  async function handleCreateRule(e) {
    e.preventDefault();
    const result = await withBusy(() => createRule(imapApiBase, ruleForm));
    if (result && !result.error) { setRuleForm(EMPTY_RULE_FORM); loadRules(); }
  }
  async function handleToggleRule(rule) {
    await withBusy(() => updateRule(imapApiBase, rule.id, { enabled: !rule.enabled }));
    loadRules();
  }
  async function handleDeleteRule(id) {
    await withBusy(() => deleteRule(imapApiBase, id));
    loadRules();
  }
  async function handleApplyRules() {
    const result = await withBusy(() => applyRules(imapApiBase));
    if (result && result.results) setError(null);
  }

  function updateInterpreterField(idx, key, value) {
    const fields = [...interpreterForm.fields];
    fields[idx] = { ...fields[idx], [key]: value };
    setInterpreterForm({ ...interpreterForm, fields });
  }
  function addInterpreterField() {
    setInterpreterForm({ ...interpreterForm, fields: [...interpreterForm.fields, { name: "", source: "subject", pattern: "" }] });
  }
  async function handleCreateInterpreter(e) {
    e.preventDefault();
    const result = await withBusy(() => createInterpreter(imapApiBase, interpreterForm));
    if (result && !result.error) { setInterpreterForm(EMPTY_INTERPRETER_FORM); loadInterpreters(); }
  }
  async function handleDeleteInterpreter(id) {
    await withBusy(() => deleteInterpreter(imapApiBase, id));
    loadInterpreters();
  }

  return (
    <div className="hub-settings hub-settings-wide">
      <div className="hub-settings-topbar">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h1>📧 Client IMAP</h1>
      </div>

      {error && (
        <div className="hub-card" style={{ borderColor: "var(--danger)" }}>
          <p style={{ margin: 0 }}>⚠️ {error}</p>
        </div>
      )}

      <div className="tabs" style={{ marginBottom: 16 }}>
        <button className={subTab === "folders" ? "active" : ""} onClick={() => setSubTab("folders")}>Dossiers</button>
        <button className={subTab === "messages" ? "active" : ""} onClick={() => setSubTab("messages")}>Messages</button>
        <button className={subTab === "rules" ? "active" : ""} onClick={() => setSubTab("rules")}>Règles de tri</button>
        <button className={subTab === "interpreters" ? "active" : ""} onClick={() => setSubTab("interpreters")}>Interpréteurs</button>
      </div>

      {subTab === "folders" && (
        <div className="hub-card hub-settings-section">
          <h2>Dossiers ({folders.length})</h2>
          <ul>
            {folders.map((f) => (
              <li key={f.name || f}>
                {f.name || f}{" "}
                <button className="secondary" disabled={busy} onClick={() => handleDeleteFolder(f.name || f)}>Supprimer</button>
              </li>
            ))}
          </ul>
          <form onSubmit={handleCreateFolder} style={{ display: "flex", gap: 8 }}>
            <input value={newFolderName} onChange={(e) => setNewFolderName(e.target.value)} placeholder="Nom du nouveau dossier" />
            <button type="submit" disabled={busy || !newFolderName.trim()}>Créer</button>
          </form>
        </div>
      )}

      {subTab === "messages" && (
        <div className="hub-card hub-settings-section">
          <div style={{ display: "flex", gap: 8, alignItems: "flex-end", marginBottom: 12 }}>
            <div className="hub-settings-row">
              <label>Dossier</label>
              <select value={messagesFolder} onChange={(e) => setMessagesFolder(e.target.value)}>
                {folders.map((f) => <option key={f.name || f} value={f.name || f}>{f.name || f}</option>)}
              </select>
            </div>
            <button disabled={busy} onClick={loadMessages}>Actualiser</button>
          </div>
          <table>
            <thead><tr><th>Sujet</th><th>De</th><th>Date</th><th></th></tr></thead>
            <tbody>
              {messages.map((m) => (
                <tr key={m.uid}>
                  <td>{m.subject}</td>
                  <td>{m.from}</td>
                  <td className="muted">{m.date}</td>
                  <td>
                    <button className="secondary" disabled={busy} onClick={() => handleOpenMessage(m.uid)}>Ouvrir</button>{" "}
                    <button className="secondary" disabled={busy} onClick={() => handleInterpret(m.uid)}>{interpretingUid === m.uid ? "Interprétation…" : "Interpréter"}</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {selectedMessage && (
            <div style={{ marginTop: 16, borderTop: "1px solid var(--border)", paddingTop: 12 }}>
              <h3>{selectedMessage.subject}</h3>
              <p className="muted">De {selectedMessage.from} — {selectedMessage.date}</p>
              <pre style={{ whiteSpace: "pre-wrap" }}>{selectedMessage.body_text || "(pas de corps texte)"}</pre>
              <div style={{ display: "flex", gap: 8 }}>
                <select onChange={(e) => e.target.value && handleMoveMessage(selectedMessage.uid, e.target.value)} defaultValue="">
                  <option value="" disabled>Déplacer vers…</option>
                  {folders.filter((f) => (f.name || f) !== messagesFolder).map((f) => <option key={f.name || f} value={f.name || f}>{f.name || f}</option>)}
                </select>
                <button className="secondary" onClick={() => setSelectedMessage(null)}>Fermer</button>
              </div>
            </div>
          )}

          {interpretResult && (
            <div style={{ marginTop: 16, borderTop: "1px solid var(--border)", paddingTop: 12 }}>
              <h3>Résultat d'interprétation</h3>
              {interpretResult.error ? (
                <p>⚠️ {interpretResult.error}</p>
              ) : (
                <>
                  <p className="muted">Interpréteur : {interpretResult.interpreter_name}</p>
                  <table>
                    <tbody>
                      {Object.entries(interpretResult.result || {}).map(([k, v]) => (
                        <tr key={k}><td className="muted">{k}</td><td>{v}</td></tr>
                      ))}
                    </tbody>
                  </table>
                  {interpretResult.pushed_to_source && (
                    <p className="muted">
                      Poussé vers la source "{interpretResult.pushed_to_source}" —{" "}
                      {interpretResult.push_ok ? "✅ succès" : `❌ échec (${interpretResult.push_error})`}
                    </p>
                  )}
                </>
              )}
            </div>
          )}
        </div>
      )}

      {subTab === "rules" && (
        <div className="hub-card hub-settings-section">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h2>Règles de tri ({rules.length})</h2>
            <button disabled={busy || rules.length === 0} onClick={handleApplyRules}>Appliquer maintenant</button>
          </div>
          <ul>
            {rules.map((r) => (
              <li key={r.id}>
                {r.enabled ? "🟢" : "⚪"} <strong>{r.name}</strong> (dossier {r.watch_folder}){" "}
                <button className="secondary" disabled={busy} onClick={() => handleToggleRule(r)}>{r.enabled ? "Désactiver" : "Activer"}</button>{" "}
                <button className="secondary" disabled={busy} onClick={() => handleDeleteRule(r.id)}>Supprimer</button>
              </li>
            ))}
          </ul>
          <form onSubmit={handleCreateRule} style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "flex-end" }}>
            <div className="hub-settings-row">
              <label>Nom</label>
              <input value={ruleForm.name} onChange={(e) => setRuleForm({ ...ruleForm, name: e.target.value })} />
            </div>
            <div className="hub-settings-row">
              <label>Dossier surveillé</label>
              <input value={ruleForm.watch_folder} onChange={(e) => setRuleForm({ ...ruleForm, watch_folder: e.target.value })} />
            </div>
            <div className="hub-settings-row">
              <label>Sujet contient</label>
              <input value={ruleForm.match_subject} onChange={(e) => setRuleForm({ ...ruleForm, match_subject: e.target.value })} />
            </div>
            <div className="hub-settings-row">
              <label>Déplacer vers</label>
              <input value={ruleForm.action_move_to} onChange={(e) => setRuleForm({ ...ruleForm, action_move_to: e.target.value })} />
            </div>
            <button type="submit" disabled={busy || !ruleForm.name.trim() || !ruleForm.action_move_to.trim()}>Créer</button>
          </form>
        </div>
      )}

      {subTab === "interpreters" && (
        <div className="hub-card hub-settings-section">
          <h2>Interpréteurs ({interpreters.length})</h2>
          <p className="muted">
            Un interpréteur transforme un message en données structurées. Avec une "source cible"
            renseignée, le résultat est aussi poussé vers cette source (connecteur, livraison #230).
          </p>
          <ul>
            {interpreters.map((it) => (
              <li key={it.id}>
                {it.enabled ? "🟢" : "⚪"} <strong>{it.name}</strong>
                {it.target_source && <> → source "{it.target_source}"</>}{" "}
                <button className="secondary" disabled={busy} onClick={() => handleDeleteInterpreter(it.id)}>Supprimer</button>
              </li>
            ))}
          </ul>
          <form onSubmit={handleCreateInterpreter} style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <div className="hub-settings-row">
                <label>Nom</label>
                <input value={interpreterForm.name} onChange={(e) => setInterpreterForm({ ...interpreterForm, name: e.target.value })} />
              </div>
              <div className="hub-settings-row">
                <label>Sujet contient</label>
                <input value={interpreterForm.match_subject} onChange={(e) => setInterpreterForm({ ...interpreterForm, match_subject: e.target.value })} />
              </div>
              <div className="hub-settings-row">
                <label>Source cible (connecteur, optionnel)</label>
                <input value={interpreterForm.target_source} onChange={(e) => setInterpreterForm({ ...interpreterForm, target_source: e.target.value })} placeholder="ex. alertes-mail" />
              </div>
            </div>
            <div>
              <strong>Champs à extraire</strong>
              {interpreterForm.fields.map((f, idx) => (
                <div key={idx} style={{ display: "flex", gap: 8, marginTop: 4 }}>
                  <input placeholder="nom" value={f.name} onChange={(e) => updateInterpreterField(idx, "name", e.target.value)} />
                  <select value={f.source} onChange={(e) => updateInterpreterField(idx, "source", e.target.value)}>
                    <option value="subject">Sujet</option>
                    <option value="body">Corps</option>
                  </select>
                  <input placeholder="motif regex, groupe nommé" value={f.pattern} onChange={(e) => updateInterpreterField(idx, "pattern", e.target.value)} style={{ flex: 1 }} />
                </div>
              ))}
              <button type="button" className="secondary" onClick={addInterpreterField} style={{ marginTop: 4 }}>+ Ajouter un champ</button>
            </div>
            <button type="submit" disabled={busy || !interpreterForm.name.trim()}>Créer</button>
          </form>
        </div>
      )}
    </div>
  );
}
