import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  fetchConnectors, createConnector, updateConnector, deleteConnector, testConnector, runConnector,
  fetchConnectorStats, fetchConnectorMessages,
} from "./imapConnectorsClient.js";

// Tuile « Connecteurs IMAP » (livraison #489) : gestion des boîtes de
// réception routées vers les API du hub (tickets SAV, pont OPTLINE/
// ProjeQtOr, alertes Zenoss → pixel-grid, SMS des passerelles,
// notifications), avec journal, statistiques et grille d'activité
// dense (jour × connecteur, esprit pixel-grid).

const REFRESH_MS = 30000;
const GRID_DAYS = 30;
// Tons de la grille : palette d'états du hub (SupervisionSiView).
const TONE_HEX = { ok: "#2f9e5b", warning: "#d69a2b", critical: "#d64545", none: "#3a3f47" };

const TARGETS = [
  { id: "tickets", label: "Tickets SAV (hub)" },
  { id: "projeqtor", label: "Demandes ProjeQtOr (pont OPTLINE)" },
  { id: "zenoss", label: "Alertes Zenoss → pixel-grid" },
  { id: "sms", label: "SMS entrants (passerelles)" },
  { id: "notification", label: "Notifications diverses" },
];

const EMPTY_FORM = {
  name: "", host: "", port: "993", tls: true, username: "", password: "",
  folder: "INBOX", target: "tickets", interval_seconds: "300",
  mark_seen: true, auto_ack: true, enabled: false, notes: "",
};

function Tone({ tone, children }) {
  return <span className={`np-tone ${tone || "neutral"}`}>{children}</span>;
}

function when(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString("fr-FR");
}

// Grille d'activité dense : lignes = connecteurs, colonnes = jours
// (le plus récent à droite). Cellule : vert si des messages sans
// erreur, orange si au moins un non interprété, gris si rien.
function ActivityGrid({ connectors, grid }) {
  const days = useMemo(() => {
    const out = [];
    const today = new Date();
    for (let i = GRID_DAYS - 1; i >= 0; i--) {
      const d = new Date(today.getTime() - i * 86400000);
      out.push(d.toISOString().slice(0, 10));
    }
    return out;
  }, []);
  const byKey = useMemo(() => {
    const m = new Map();
    for (const g of grid || []) m.set(`${g.connector_id}|${g.day}`, g);
    return m;
  }, [grid]);
  if (!connectors.length) return null;
  return (
    <div className="panel" style={{ marginBottom: 12 }}>
      <h4 style={{ margin: "4px 0 8px" }}>Activité — {GRID_DAYS} jours <span className="muted" style={{ fontSize: 11 }}>(survoler une cellule pour le détail)</span></h4>
      <div style={{ overflowX: "auto" }}>
        {connectors.map((c) => (
          <div key={c.id} style={{ display: "flex", alignItems: "center", gap: 2, marginBottom: 2 }}>
            <span style={{ width: 180, fontSize: 11, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={c.name}>{c.name}</span>
            {days.map((day) => {
              const g = byKey.get(`${c.id}|${day}`);
              const color = !g ? TONE_HEX.none : g.errors > 0 ? TONE_HEX.warning : TONE_HEX.ok;
              const title = g ? `${day} — ${g.n} message(s)${g.errors ? `, ${g.errors} non interprété(s)` : ""}` : `${day} — rien`;
              return <span key={day} title={title} style={{ width: 10, height: 10, background: color, borderRadius: 1, flexShrink: 0 }} />;
            })}
          </div>
        ))}
      </div>
      <p className="muted" style={{ fontSize: 11, margin: "6px 0 0" }}>
        <i style={{ background: TONE_HEX.ok, display: "inline-block", width: 10, height: 10, borderRadius: 1 }} /> messages pris en charge{" "}
        <i style={{ background: TONE_HEX.warning, display: "inline-block", width: 10, height: 10, borderRadius: 1 }} /> avec non interprétés{" "}
        <i style={{ background: TONE_HEX.none, display: "inline-block", width: 10, height: 10, borderRadius: 1 }} /> rien
      </p>
    </div>
  );
}

export default function ImapConnectorsView({ onBack, imapConnectorsApiBase }) {
  const [connectors, setConnectors] = useState([]);
  const [stats, setStats] = useState(null);
  const [messages, setMessages] = useState([]);
  const [onlyErrors, setOnlyErrors] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [editingId, setEditingId] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const [list, st, msgs] = await Promise.all([
      fetchConnectors(imapConnectorsApiBase),
      fetchConnectorStats(imapConnectorsApiBase, GRID_DAYS),
      fetchConnectorMessages(imapConnectorsApiBase, { errors: onlyErrors }),
    ]);
    setConnectors(list);
    setStats(st?.error ? null : st);
    setMessages(msgs);
    setError(st?.error || null);
    setLoading(false);
  }, [imapConnectorsApiBase, onlyErrors]);

  useEffect(() => { load(); const id = setInterval(load, REFRESH_MS); return () => clearInterval(id); }, [load]);

  const act = async (fn, okText) => {
    setBusy(true); setNotice(null);
    const r = await fn();
    setBusy(false);
    if (r?.error) setNotice({ ok: false, text: r.error });
    else { setNotice({ ok: true, text: okText }); await load(); }
  };

  const submit = async (e) => {
    e.preventDefault();
    const body = { ...form, port: parseInt(form.port, 10) || 993, interval_seconds: parseInt(form.interval_seconds, 10) || 300 };
    if (editingId && !body.password) delete body.password; // inchangé si vide
    await act(
      () => (editingId ? updateConnector(imapConnectorsApiBase, editingId, body) : createConnector(imapConnectorsApiBase, body)),
      editingId ? "connecteur mis à jour" : "connecteur créé — activez-le après un test",
    );
    setShowForm(false); setEditingId(null); setForm(EMPTY_FORM);
  };

  const edit = (c) => {
    setForm({ name: c.name, host: c.host, port: String(c.port), tls: c.tls, username: c.username,
      password: "", folder: c.folder, target: c.target, interval_seconds: String(c.interval_seconds),
      mark_seen: c.mark_seen, auto_ack: c.auto_ack !== false, enabled: c.enabled, notes: c.notes || "" });
    setEditingId(c.id); setShowForm(true);
  };

  const per = stats?.per_connector || {};

  return (
    <div className="view-imap-connectors">
      <div className="panel" style={{ marginBottom: 12 }}>
        <button className="secondary" onClick={onBack}>← Retour</button>{" "}
        <strong>Connecteurs IMAP</strong>{" "}
        <span className="muted" style={{ fontSize: 12 }}>
          — boîtes de réception → tickets SAV, ProjeQtOr, alertes Zenoss (pixel-grid), SMS, notifications
        </span>{" "}
        <button className="secondary" onClick={() => { setShowForm(!showForm); setEditingId(null); setForm(EMPTY_FORM); }}>
          {showForm ? "Fermer" : "＋ Nouveau connecteur"}
        </button>
        <label style={{ marginLeft: 12, fontSize: 12 }}>
          <input type="checkbox" checked={onlyErrors} onChange={(e) => setOnlyErrors(e.target.checked)} /> erreurs seulement
        </label>
      </div>

      {notice && <p><Tone tone={notice.ok ? "ok" : "critical"}>{notice.text}</Tone></p>}
      {error && <p><Tone tone="critical">{error}</Tone></p>}

      {showForm && (
        <div className="panel" style={{ marginBottom: 12 }}>
          <h4 style={{ margin: "4px 0 8px" }}>{editingId ? "Modifier le connecteur" : "Nouveau connecteur"}</h4>
          <form onSubmit={submit} style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
            <input required placeholder="nom (ex. sav-entrant)" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            <input required placeholder="hôte IMAP" value={form.host} onChange={(e) => setForm({ ...form, host: e.target.value })} />
            <input style={{ width: 70 }} placeholder="port" value={form.port} onChange={(e) => setForm({ ...form, port: e.target.value })} />
            <label style={{ fontSize: 12 }}><input type="checkbox" checked={form.tls} onChange={(e) => setForm({ ...form, tls: e.target.checked })} /> SSL</label>
            <input required placeholder="identifiant" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} />
            <input type="password" placeholder={editingId ? "mot de passe (vide = inchangé)" : "mot de passe"} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
            <input style={{ width: 110 }} placeholder="dossier" value={form.folder} onChange={(e) => setForm({ ...form, folder: e.target.value })} />
            <select value={form.target} onChange={(e) => setForm({ ...form, target: e.target.value })}>
              {TARGETS.map((t) => <option key={t.id} value={t.id}>{t.label}</option>)}
            </select>
            <input style={{ width: 90 }} title="intervalle entre relevés (secondes)" placeholder="intervalle s" value={form.interval_seconds} onChange={(e) => setForm({ ...form, interval_seconds: e.target.value })} />
            <label style={{ fontSize: 12 }}><input type="checkbox" checked={form.mark_seen} onChange={(e) => setForm({ ...form, mark_seen: e.target.checked })} /> marquer lu</label>
            {form.target === "zenoss" && (
              <label style={{ fontSize: 12 }} title="Une résolution Zenoss acquitte automatiquement les alertes actives non lues du même équipement (cloche du hub)">
                <input type="checkbox" checked={form.auto_ack} onChange={(e) => setForm({ ...form, auto_ack: e.target.checked })} /> acquitter à la résolution
              </label>
            )}
            <label style={{ fontSize: 12 }}><input type="checkbox" checked={form.enabled} onChange={(e) => setForm({ ...form, enabled: e.target.checked })} /> activé</label>
            <button type="submit" disabled={busy}>{editingId ? "Enregistrer" : "Créer"}</button>
          </form>
        </div>
      )}

      <ActivityGrid connectors={connectors} grid={stats?.grid} />

      <div className="panel" style={{ marginBottom: 12 }}>
        <h4 style={{ margin: "4px 0 8px" }}>Connecteurs ({connectors.length})</h4>
        <div className="hub-table-scroll">
          <table>
            <thead><tr><th></th><th>Nom</th><th>Boîte</th><th>Cible</th><th>Dernier relevé</th><th>Messages</th><th>Livraisons</th><th>Actions</th></tr></thead>
            <tbody>{connectors.map((c) => {
              const s = per[c.id] || {};
              return (
                <tr key={c.id}>
                  <td><Tone tone={!c.enabled ? "neutral" : c.last_ok === false ? "critical" : c.last_ok ? "ok" : "neutral"}>{c.enabled ? (c.last_ok === false ? "en échec" : c.last_ok ? "actif" : "jamais relevé") : "désactivé"}</Tone></td>
                  <td><strong>{c.name}</strong>{c.notes && <div className="muted" style={{ fontSize: 11 }}>{c.notes}</div>}</td>
                  <td style={{ fontSize: 12 }}><code>{c.username}@{c.host}:{c.port}</code><div className="muted">{c.folder}{c.tls ? " · SSL" : ""} · {c.interval_seconds}s</div></td>
                  <td style={{ fontSize: 12 }}>{TARGETS.find((t) => t.id === c.target)?.label || c.target}{c.target === "zenoss" && c.auto_ack !== false && <div className="muted" style={{ fontSize: 11 }}>acquittement auto à la résolution</div>}</td>
                  <td className="muted" style={{ fontSize: 12 }}>{when(c.last_poll_at)}{c.last_error && <div><Tone tone="critical">{c.last_error}</Tone></div>}</td>
                  <td style={{ fontSize: 12 }}>{s.messages ?? 0}{(s.non_interpretes ?? 0) > 0 && <Tone tone="warning"> dont {s.non_interpretes} non interprétés</Tone>}</td>
                  <td style={{ fontSize: 12 }}><Tone tone="ok">{s.livraisons_ok ?? 0} ok</Tone>{(s.livraisons_ko ?? 0) > 0 && <> <Tone tone="critical">{s.livraisons_ko} ko</Tone></>}</td>
                  <td style={{ whiteSpace: "nowrap" }}>
                    <button className="secondary" disabled={busy} onClick={() => act(() => testConnector(imapConnectorsApiBase, c.id), "connexion OK")}>Tester</button>{" "}
                    <button className="secondary" disabled={busy} onClick={() => act(async () => { const r = await runConnector(imapConnectorsApiBase, c.id); return r?.error ? r : { handled: r?.handled }; }, "relevé effectué")}>Relever</button>{" "}
                    <button className="secondary" onClick={() => edit(c)}>Modifier</button>{" "}
                    <button className="secondary" onClick={() => { if (window.confirm(`Supprimer le connecteur « ${c.name} » et tout son journal ?`)) act(() => deleteConnector(imapConnectorsApiBase, c.id), "connecteur supprimé"); }}>Suppr.</button>
                  </td>
                </tr>
              );
            })}</tbody>
          </table>
          {connectors.length === 0 && !loading && <p className="muted" style={{ padding: 8 }}>Aucun connecteur — créez le premier (une boîte par adresse de réception).</p>}
        </div>
      </div>

      <div className="panel">
        <h4 style={{ margin: "4px 0 8px" }}>Journal des messages ({messages.length})</h4>
        <div className="hub-table-scroll">
          <table>
            <thead><tr><th>Reçu</th><th>Connecteur</th><th>De</th><th>Sujet</th><th>Interprétation</th><th>Livraisons</th></tr></thead>
            <tbody>{messages.map((m) => (
              <tr key={m.id}>
                <td className="muted" style={{ fontSize: 12, whiteSpace: "nowrap" }}>{when(m.fetched_at)}</td>
                <td style={{ fontSize: 12 }}>{m.connector_name}</td>
                <td style={{ fontSize: 12, maxWidth: 180, overflow: "hidden", textOverflow: "ellipsis" }}>{m.from_addr}</td>
                <td style={{ fontSize: 12, maxWidth: 260, overflow: "hidden", textOverflow: "ellipsis" }} title={m.subject}>{m.subject}</td>
                <td style={{ fontSize: 12 }}>{m.parsed ? <Tone tone="ok">{m.kind}</Tone> : <Tone tone="warning">non interprété</Tone>} <span className="muted">{m.summary}</span></td>
                <td style={{ fontSize: 12 }}>{(m.deliveries || []).map((d, i) => (
                  <div key={i}><Tone tone={d.ok ? "ok" : "critical"}>{d.target} {d.ok ? "✓" : "✗"}</Tone> <span className="muted">{d.detail}</span></div>
                ))}</td>
              </tr>
            ))}</tbody>
          </table>
          {messages.length === 0 && !loading && <p className="muted" style={{ padding: 8 }}>Aucun message{onlyErrors ? " en erreur" : ""} pour l'instant.</p>}
        </div>
      </div>
    </div>
  );
}
