import React, { useEffect, useState } from "react";
import { API_BASE_URL, getJson, postJson, putJson, deleteJson } from "../api.js";
import { ROLE_LABELS, statsMax, fmtDuration, fmtTsShort, fmtTs, mergeImportResults } from "../lib.js";
import TicketThread from "../components/TicketThread.jsx";
import TicketDocuments from "../components/TicketDocuments.jsx";
import { postHubEvent } from "../hubEvents.js";

const ROLES = ["demandeur", "technicien", "politique", "admin"];
const PREFS_API_BASE_URL = import.meta.env.VITE_PREFS_API_BASE_URL || "";

// --- 👥 Utilisateurs & rôles ---
function UsersTab() {
  const [users, setUsers] = useState([]);
  const [login, setLogin] = useState("");
  const [name, setName] = useState("");
  const [role, setRole] = useState("demandeur");
  const [error, setError] = useState(null);
  const [importBusy, setImportBusy] = useState(false);
  const [importResult, setImportResult] = useState(null);

  const load = () => getJson("/users").then((r) => r.ok && setUsers(r.data));
  useEffect(() => { load(); }, []);

  const changeRole = async (u, newRole) => {
    // Mise à jour optimiste locale AVANT rechargement (convention du
    // projet : la liste doit refléter la valeur sans latence).
    setUsers((prev) => prev.map((x) => (x.id === u.id ? { ...x, role: newRole } : x)));
    const res = await putJson(`/users/${u.id}`, { role: newRole });
    if (!res.ok) {
      setError(res.data.error || "changement impossible");
      load();
    }
  };

  const createUser = async () => {
    const l = login.trim();
    if (!l) return;
    const res = await postJson("/users", { login: l, name: name.trim() || null, role });
    if (res.ok) {
      setUsers((prev) => [...prev, { id: res.data.id, login: l, name: name.trim() || null, role }]);
      setLogin(""); setName(""); setRole("demandeur");
      setError(null);
      load();
    } else {
      setError(res.data.error || "création impossible");
    }
  };

  // Import direct des membres du groupe Keycloak "demandeurs" --
  // n'écrase JAMAIS un compte déjà présent localement (testé côté
  // backend : un rôle changé à la main survit à un réimport). Groupe
  // LOCAL complémentaire, configurable par un admin depuis la page
  // "⚙️ Paramètres" du hub (app_settings, application "tickets",
  // champ local_requester_group) -- demandé explicitement, importé
  // EN PLUS de "demandeurs", jamais à la place.
  const importFromKeycloak = async () => {
    setImportBusy(true);
    setImportResult(null);
    setError(null);

    const mainResult = await postJson("/users/import-keycloak-group", { group: "demandeurs" });
    if (!mainResult.ok) {
      setImportBusy(false);
      setError(mainResult.data.error || "import Keycloak impossible");
      return;
    }

    let localResult = null;
    try {
      const settingsRes = await fetch(`${PREFS_API_BASE_URL}/app-settings?app=tickets`);
      const settings = settingsRes.ok ? await settingsRes.json() : {};
      const localGroup = (settings.local_requester_group || "").trim();
      if (localGroup) {
        const res = await postJson("/users/import-keycloak-group", { group: localGroup });
        if (res.ok) localResult = res.data;
        // Un échec sur le groupe local (ex. mal nommé) ne doit jamais
        // faire perdre le succès déjà acquis sur "demandeurs" --
        // affiché comme partiel plutôt que de tout faire échouer.
      }
    } catch {
      // Paramétrage indisponible -- l'import de "demandeurs" reste valable
    }

    setImportBusy(false);
    setImportResult(mergeImportResults(mainResult.data, localResult));
    load();
  };

  return (
    <div>
      <h3>Créer un utilisateur</h3>
      <div className="form-row">
        <input placeholder="login" value={login} onChange={(e) => setLogin(e.target.value)}
               onKeyDown={(e) => e.key === "Enter" && createUser()} />
        <input placeholder="nom affiché" value={name} onChange={(e) => setName(e.target.value)}
               onKeyDown={(e) => e.key === "Enter" && createUser()} />
        <select value={role} onChange={(e) => setRole(e.target.value)}>
          {ROLES.map((r) => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
        </select>
        <button className="primary" onClick={createUser} disabled={!login.trim()}>➕ Créer</button>
      </div>

      <h3>Importer depuis Keycloak</h3>
      <div className="form-row">
        <button onClick={importFromKeycloak} disabled={importBusy}>
          {importBusy ? "Import en cours…" : "📥 Importer les demandeurs depuis Keycloak"}
        </button>
      </div>
      {importResult && (
        <p className="hint">
          {importResult.created.length} compte{importResult.created.length > 1 ? "s" : ""} créé
          {importResult.created.length > 1 ? "s" : ""}
          {importResult.created.length > 0 && ` (${importResult.created.join(", ")})`}
          {" — "}
          {importResult.skipped.length} déjà présent{importResult.skipped.length > 1 ? "s" : ""} (ignoré
          {importResult.skipped.length > 1 ? "s" : ""}, jamais écrasé{importResult.skipped.length > 1 ? "s" : ""})
          {" — "}{importResult.total_in_group} au total dans le groupe Keycloak.
        </p>
      )}

      {error && <p className="error-text">{error}</p>}
      <h3>Comptes ({users.length})</h3>
      <table className="portal-table">
        <thead>
          <tr><th>Login</th><th>Nom</th><th>Rôle</th></tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.id}>
              <td>{u.login}</td>
              <td>{u.name || "—"}</td>
              <td>
                <select value={u.role} onChange={(e) => changeRole(u, e.target.value)}>
                  {ROLES.map((r) => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
                </select>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// --- 🏷️ Types & niveaux (référentiel des tickets) ---
// Composant générique réutilisé pour les deux tables — le backend a
// déjà tout le CRUD (REFERENCE_TABLES dans app.py), ce composant
// n'est qu'une interface dessus. `fields[0]` sert de libellé
// d'affichage (confirmation de suppression) et de champ requis à la
// création.
function ReferenceTableEditor({ table, fields }) {
  const [rows, setRows] = useState([]);
  const [newValues, setNewValues] = useState({});
  const [error, setError] = useState(null);

  const load = () => getJson(`/${table}`).then((r) => r.ok && setRows(r.data));
  useEffect(() => { load(); }, [table]);

  const castValue = (field, raw) => (field.type === "number" ? Number(raw || 0) : (raw || "").trim());

  const create = async () => {
    const body = {};
    fields.forEach((f) => { body[f.key] = castValue(f, newValues[f.key]); });
    if (!body[fields[0].key]) return;
    const res = await postJson(`/${table}`, body);
    if (res.ok) {
      setNewValues({});
      setError(null);
      load();
    } else {
      setError(res.data.error || "création impossible");
    }
  };

  const updateField = async (row, field, raw) => {
    const value = castValue(field, raw);
    // Mise à jour optimiste locale AVANT rechargement (convention du
    // projet : la liste doit refléter la valeur sans latence).
    setRows((prev) => prev.map((r) => (r.id === row.id ? { ...r, [field.key]: value } : r)));
    const res = await putJson(`/${table}/${row.id}`, { [field.key]: value });
    if (!res.ok) {
      setError(res.data.error || "modification impossible");
      load();
    }
  };

  const remove = async (row) => {
    if (!window.confirm(`Supprimer "${row[fields[0].key]}" ? Impossible si encore référencé par des tickets.`)) return;
    const res = await deleteJson(`/${table}/${row.id}`);
    if (res.ok) {
      setRows((prev) => prev.filter((r) => r.id !== row.id));
    } else {
      setError(res.data.error || "suppression impossible");
    }
  };

  return (
    <div>
      <div className="form-row">
        {fields.map((f) => (
          <input
            key={f.key}
            type={f.type === "number" ? "number" : "text"}
            placeholder={f.placeholder}
            value={newValues[f.key] ?? ""}
            onChange={(e) => setNewValues((prev) => ({ ...prev, [f.key]: e.target.value }))}
            onKeyDown={(e) => e.key === "Enter" && create()}
          />
        ))}
        <button className="primary" onClick={create} disabled={!(newValues[fields[0].key] || "").trim()}>
          ➕ Ajouter
        </button>
      </div>
      {error && <p className="error-text">{error}</p>}
      <table className="portal-table">
        <thead>
          <tr>{fields.map((f) => <th key={f.key}>{f.label}</th>)}<th></th></tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              {fields.map((f) => (
                <td key={f.key}>
                  <input
                    type={f.type === "number" ? "number" : "text"}
                    value={row[f.key] ?? ""}
                    onChange={(e) => updateField(row, f, e.target.value)}
                  />
                </td>
              ))}
              <td><button onClick={() => remove(row)} title="Supprimer">🗑️</button></td>
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length === 0 && <p className="muted">Aucune entrée pour l'instant.</p>}
    </div>
  );
}

// --- ⏰ Règles d'escalade par deadline (niveau cible = liste
// déroulante des niveaux existants, pas un simple champ texte comme
// ReferenceTableEditor -- composant dédié plutôt que forcé dans le
// motif générique). ---
function DeadlineEscalationRulesEditor() {
  const [rules, setRules] = useState([]);
  const [levels, setLevels] = useState([]);
  const [threshold, setThreshold] = useState("");
  const [targetLevelId, setTargetLevelId] = useState("");
  const [error, setError] = useState(null);

  const load = () => getJson("/deadline-escalation-rules").then((r) => r.ok && setRules(r.data));
  useEffect(() => {
    load();
    getJson("/levels").then((r) => {
      if (r.ok) {
        setLevels(r.data);
        if (r.data.length > 0) setTargetLevelId(String(r.data[0].id));
      }
    });
  }, []);

  const create = async () => {
    if (!threshold || !targetLevelId) return;
    const res = await postJson("/deadline-escalation-rules", {
      threshold_hours: Number(threshold),
      target_level_id: Number(targetLevelId),
    });
    if (res.ok) {
      setThreshold("");
      setError(null);
      load();
    } else {
      setError(res.data.error || "création impossible");
    }
  };

  const toggleActive = async (rule) => {
    setRules((prev) => prev.map((r) => (r.id === rule.id ? { ...r, active: rule.active ? 0 : 1 } : r)));
    const res = await putJson(`/deadline-escalation-rules/${rule.id}`, { active: rule.active ? 0 : 1 });
    if (!res.ok) load();
  };

  const remove = async (rule) => {
    if (!window.confirm(`Supprimer cette règle (${rule.threshold_hours}h → ${rule.target_level_label}) ?`)) return;
    const res = await deleteJson(`/deadline-escalation-rules/${rule.id}`);
    if (res.ok) setRules((prev) => prev.filter((r) => r.id !== rule.id));
    else setError(res.data.error || "suppression impossible");
  };

  return (
    <div>
      <p className="muted">
        À mesure que l'échéance d'un ticket approche, son niveau d'urgence
        MONTE automatiquement vers le niveau cible (jamais ne redescend) —
        indépendamment de son niveau initial. Plusieurs seuils possibles ;
        le seuil franchi le plus urgent l'emporte.
      </p>
      <div className="form-row">
        <input
          type="number"
          placeholder="heures avant échéance (ex. 48)"
          value={threshold}
          onChange={(e) => setThreshold(e.target.value)}
        />
        <span>→</span>
        <select value={targetLevelId} onChange={(e) => setTargetLevelId(e.target.value)}>
          {levels.map((l) => <option key={l.id} value={l.id}>{l.label}</option>)}
        </select>
        <button className="primary" onClick={create} disabled={!threshold || !targetLevelId}>
          ➕ Ajouter
        </button>
      </div>
      {error && <p className="error-text">{error}</p>}
      <table className="portal-table">
        <thead>
          <tr><th>Seuil (avant échéance)</th><th>Niveau cible</th><th>Active</th><th></th></tr>
        </thead>
        <tbody>
          {rules.map((r) => (
            <tr key={r.id}>
              <td>{r.threshold_hours} h</td>
              <td>{r.target_level_label || `#${r.target_level_id}`}</td>
              <td>
                <input type="checkbox" checked={!!r.active} onChange={() => toggleActive(r)} />
              </td>
              <td><button onClick={() => remove(r)} title="Supprimer">🗑️</button></td>
            </tr>
          ))}
        </tbody>
      </table>
      {rules.length === 0 && <p className="muted">Aucune règle — l'échéance des tickets n'influence pas encore leur urgence.</p>}
    </div>
  );
}

// --- 🏁 Statuts -- composant dédié (pas ReferenceTableEditor,
// générique texte/nombre) : le "type" est un menu contraint, pas un
// champ libre. Décidé avec la personne après plusieurs allers-
// retours : le type ne catégorise QUE les statuts représentant un
// travail actif (en_cours/en_pause/en_attente) -- sert à détecter
// la "prise en charge" d'un ticket (premier passage à un statut de
// type en_cours, voir tickets/api/app.py). Les statuts de clôture
// (résolu, livré, abandonné...) n'ont délibérément PAS de type -- la
// fermeture réelle reste un geste séparé (bouton "Fermer" dans la
// vue technicien, ts_closed), indépendant du statut choisi.
const STATUT_TYPE_LABELS = {
  "": "(aucun — statut de clôture)",
  en_cours: "En cours",
  en_pause: "En pause",
  en_attente: "En attente",
};

function StatutsEditor() {
  const [statuts, setStatuts] = useState([]);
  const [label, setLabel] = useState("");
  const [type, setType] = useState("");
  const [error, setError] = useState(null);

  const load = () => getJson("/statuts").then((r) => r.ok && setStatuts(r.data));
  useEffect(() => { load(); }, []);

  const create = async () => {
    if (!label.trim()) return;
    const res = await postJson("/statuts", { label: label.trim(), type: type || null });
    if (res.ok) {
      setLabel("");
      setType("");
      setError(null);
      load();
    } else {
      setError(res.data.error || "création impossible");
    }
  };

  const updateLabel = async (statut, newLabel) => {
    setStatuts((prev) => prev.map((s) => (s.id === statut.id ? { ...s, label: newLabel } : s)));
    const res = await putJson(`/statuts/${statut.id}`, { label: newLabel });
    if (!res.ok) {
      setError(res.data.error || "modification impossible");
      load();
    }
  };

  const updateType = async (statut, newType) => {
    setStatuts((prev) => prev.map((s) => (s.id === statut.id ? { ...s, type: newType || null } : s)));
    const res = await putJson(`/statuts/${statut.id}`, { type: newType });
    if (!res.ok) {
      setError(res.data.error || "modification impossible");
      load();
    }
  };

  const remove = async (statut) => {
    if (!window.confirm(`Supprimer "${statut.label}" ? Impossible si encore référencé par des tickets.`)) return;
    const res = await deleteJson(`/statuts/${statut.id}`);
    if (res.ok) {
      setStatuts((prev) => prev.filter((s) => s.id !== statut.id));
    } else {
      setError(res.data.error || "suppression impossible");
    }
  };

  return (
    <div>
      <p className="muted">
        Le "type" ne s'applique qu'aux statuts représentant un travail ACTIF (en cours / en
        pause / en attente) -- sert à détecter la "prise en charge" d'un ticket. Un statut de
        clôture (résolu, livré, abandonné...) n'a pas besoin de type : fermer réellement le
        ticket reste un geste séparé, indépendant du statut choisi.
      </p>
      <div className="form-row">
        <input
          placeholder="libellé (ex. Résolu)"
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && create()}
        />
        <select value={type} onChange={(e) => setType(e.target.value)}>
          {Object.entries(STATUT_TYPE_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
        <button className="primary" onClick={create} disabled={!label.trim()}>➕ Ajouter</button>
      </div>
      {error && <p className="error-text">{error}</p>}
      <table className="portal-table">
        <thead>
          <tr><th>Libellé</th><th>Type</th><th></th></tr>
        </thead>
        <tbody>
          {statuts.map((s) => (
            <tr key={s.id}>
              <td><input value={s.label} onChange={(e) => updateLabel(s, e.target.value)} /></td>
              <td>
                <select value={s.type || ""} onChange={(e) => updateType(s, e.target.value)}>
                  {Object.entries(STATUT_TYPE_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                </select>
              </td>
              <td><button onClick={() => remove(s)} title="Supprimer">🗑️</button></td>
            </tr>
          ))}
        </tbody>
      </table>
      {statuts.length === 0 && <p className="muted">Aucun statut pour l'instant.</p>}
    </div>
  );
}

// --- 📍 Sites -- table de référence + import en masse depuis un
// fichier texte (un site par ligne), demandé explicitement. Fichier
// envoyé BRUT (FormData, jamais file.text() côté navigateur qui
// forcerait un décodage UTF-8 prématuré) -- le décodage
// multi-encodage (UTF-8/CP1252/Latin-1) se fait côté serveur sur les
// VRAIS octets, voir tickets/api/app.py, decode_uploaded_text().
function SitesImporter({ onImported }) {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const handleFile = async (file) => {
    if (!file) return;
    setBusy(true);
    setError(null);
    setResult(null);
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch(`${API_BASE_URL}/sites/import-text`, { method: "POST", body: formData });
    const data = await res.json().catch(() => ({}));
    setBusy(false);
    if (res.ok) {
      setResult(data);
      onImported();
    } else {
      setError(data.error || "import échoué");
    }
  };

  return (
    <div className="form-row">
      <label className="secondary" style={{ cursor: "pointer", display: "inline-block" }}>
        📥 Importer depuis un fichier texte (un site par ligne)
        <input
          type="file"
          accept=".txt,text/plain"
          style={{ display: "none" }}
          disabled={busy}
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) handleFile(f);
            e.target.value = ""; // permet de réimporter le même fichier une seconde fois si besoin
          }}
        />
      </label>
      {busy && <span className="hint">Import en cours…</span>}
      {result && (
        <span className="hint">
          {result.created.length} créé{result.created.length > 1 ? "s" : ""}, {result.skipped.length} déjà présent{result.skipped.length > 1 ? "s" : ""}
          {" "}(encodage détecté : {result.encoding_used})
        </span>
      )}
      {error && <p className="error-text">{error}</p>}
    </div>
  );
}

// Remontage forcé de ReferenceTableEditor après un import réussi
// (via la prop key) -- plus simple que de modifier le composant
// générique pour exposer un rechargement externe.
function SitesSection() {
  const [refreshKey, setRefreshKey] = useState(0);
  return (
    <div>
      <SitesImporter onImported={() => setRefreshKey((k) => k + 1)} />
      <ReferenceTableEditor
        key={refreshKey}
        table="sites"
        fields={[{ key: "label", placeholder: "libellé (ex. Nom du site)", label: "Libellé" }]}
      />
    </div>
  );
}

function ReferenceDataTab() {
  return (
    <div>
      <h3>Niveaux (priorité/urgence)</h3>
      <ReferenceTableEditor
        table="levels"
        fields={[
          { key: "label", placeholder: "libellé (ex. Urgent)", label: "Libellé" },
          { key: "rank", placeholder: "ordre (0 = plus prioritaire)", label: "Ordre", type: "number" },
        ]}
      />
      <h3 style={{ marginTop: "2rem" }}>Types de demande</h3>
      <ReferenceTableEditor
        table="types"
        fields={[{ key: "label", placeholder: "libellé (ex. Incident)", label: "Libellé" }]}
      />
      <h3 style={{ marginTop: "2rem" }}>Statuts</h3>
      <StatutsEditor />
      <h3 style={{ marginTop: "2rem" }}>Sites</h3>
      <SitesSection />
      <h3 style={{ marginTop: "2rem" }}>⏰ Escalade automatique par échéance</h3>
      <DeadlineEscalationRulesEditor />
    </div>
  );
}

// --- 🗄️ Base de données ---

// Navigateur/éditeur générique de tables -- demandé explicitement.
// Édition cellule par cellule (au blur, jamais à chaque frappe),
// sauvegarde automatique déclenchée côté serveur AVANT toute
// écriture (voir tickets/api/app.py, run_backup("avant-edition")) --
// jamais la clé primaire éditable, quelle que soit la table.
function TableBrowserSection() {
  const [tables, setTables] = useState([]);
  const [selectedTable, setSelectedTable] = useState("");
  const [columns, setColumns] = useState([]);
  const [primaryKey, setPrimaryKey] = useState(null);
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const limit = 50;
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [savingCell, setSavingCell] = useState(null); // `${pk}:${col}`

  useEffect(() => { getJson("/db/tables").then((r) => r.ok && setTables(r.data)); }, []);

  const loadTable = async (table, newOffset) => {
    setLoading(true);
    setError(null);
    const [colsRes, rowsRes] = await Promise.all([
      getJson(`/db/tables/${table}/columns`),
      getJson(`/db/tables/${table}/rows?limit=${limit}&offset=${newOffset}`),
    ]);
    setLoading(false);
    if (colsRes.ok) {
      setColumns(colsRes.data.columns);
      setPrimaryKey(colsRes.data.primary_key);
    }
    if (rowsRes.ok) {
      setRows(rowsRes.data.rows);
      setTotal(rowsRes.data.total);
      setOffset(newOffset);
    } else {
      setError(rowsRes.data.error || "chargement impossible");
    }
  };

  const selectTable = (table) => {
    setSelectedTable(table);
    setRows([]);
    setColumns([]);
    if (table) loadTable(table, 0);
  };

  const updateCell = async (row, col, value) => {
    if (!primaryKey) return;
    const cellKey = `${row[primaryKey]}:${col}`;
    setSavingCell(cellKey);
    const res = await putJson(`/db/tables/${selectedTable}/rows/${row[primaryKey]}`, { [col]: value });
    setSavingCell(null);
    if (res.ok) {
      setRows((prev) => prev.map((r) => (r[primaryKey] === row[primaryKey] ? { ...r, [col]: value } : r)));
    } else {
      setError(res.data.error || "modification impossible");
    }
  };

  return (
    <div>
      <p className="muted">
        Sauvegarde automatique déclenchée avant chaque modification (onglet "Sauvegardes" pour
        restaurer si besoin). Édition directe -- prudence sur les tables techniques
        (journaux, temps saisis...). La clé primaire (🔑) n'est jamais modifiable ici.
        Un champ vidé est enregistré comme une chaîne vide, pas comme NULL -- limite connue.
      </p>
      <div className="form-row">
        <select value={selectedTable} onChange={(e) => selectTable(e.target.value)}>
          <option value="">— Choisir une table —</option>
          {tables.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
      </div>
      {error && <p className="error-text">{error}</p>}
      {loading && <p className="muted">Chargement…</p>}
      {selectedTable && !loading && columns.length > 0 && (
        <>
          <p className="hint">
            {total} ligne{total > 1 ? "s" : ""} au total
            {total > 0 && ` — ${offset + 1} à ${Math.min(offset + limit, total)} affichée${Math.min(offset + limit, total) - offset > 1 ? "s" : ""}`}.
          </p>
          <div style={{ overflowX: "auto" }}>
            <table className="portal-table">
              <thead>
                <tr>{columns.map((c) => <th key={c.name}>{c.name}{c.is_primary_key ? " 🔑" : ""}</th>)}</tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row[primaryKey]}>
                    {columns.map((c) => (
                      <td key={c.name}>
                        {c.is_primary_key ? (
                          <span className="muted">{String(row[c.name])}</span>
                        ) : (
                          <input
                            defaultValue={row[c.name] ?? ""}
                            onBlur={(e) => {
                              if (e.target.value !== String(row[c.name] ?? "")) updateCell(row, c.name, e.target.value);
                            }}
                            disabled={savingCell === `${row[primaryKey]}:${c.name}`}
                          />
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {rows.length === 0 && <p className="muted">Aucune ligne dans cette table.</p>}
          <div className="form-row" style={{ marginTop: 10 }}>
            <button onClick={() => loadTable(selectedTable, Math.max(0, offset - limit))} disabled={offset === 0}>◀ Précédent</button>
            <button onClick={() => loadTable(selectedTable, offset + limit)} disabled={offset + limit >= total}>Suivant ▶</button>
          </div>
        </>
      )}
    </div>
  );
}

// Arborescence des relations -- déclarées (vraies contraintes) et
// probables (déduites du nom de colonne, ex. "site_id" -> table
// "sites"), demandé explicitement ("contraintes ou non"). Rendu en
// liste groupée par table d'origine plutôt qu'un diagramme graphique
// -- lisible et suffisant pour un premier jet, une vraie
// visualisation graphique pourrait suivre si besoin.
function RelationshipsSection() {
  const [relationships, setRelationships] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    getJson("/db/relationships").then((r) => {
      if (r.ok) setRelationships(r.data);
      else setError(r.data.error || "chargement impossible");
    });
  }, []);

  if (error) return <p className="error-text">{error}</p>;
  if (!relationships) return <p className="muted">Chargement…</p>;

  const byTable = {};
  for (const r of relationships) {
    if (!byTable[r.from_table]) byTable[r.from_table] = [];
    byTable[r.from_table].push(r);
  }
  const tableNames = Object.keys(byTable).sort((a, b) => a.localeCompare(b));

  return (
    <div>
      <p className="muted">
        Relations DÉCLARÉES (vraies contraintes du schéma) et PROBABLES (déduites du nom de
        colonne, ex. "site_id" → table "sites" -- marquées "≈", jamais garanties à 100%,
        utile pour repérer visuellement le schéma, pas pour en valider l'intégrité).
      </p>
      {tableNames.length === 0 && <p className="muted">Aucune relation détectée.</p>}
      {tableNames.map((table) => (
        <div key={table} className="db-relations-group">
          <strong>{table}</strong>
          <ul>
            {byTable[table].map((r, i) => (
              <li key={i}>
                {r.from_column} → {r.to_table}.{r.to_column}
                {!r.declared && <span className="muted"> (≈ probable, non déclarée)</span>}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

// Console SQL directe -- dernier morceau du gestionnaire de BDD.
// "Vérifier la syntaxe" ne modifie JAMAIS les données (EXPLAIN,
// vérifié empiriquement côté backend, voir sql_console.py) --
// jamais de confirmation nécessaire pour ce bouton. "Exécuter" lance
// réellement la requête -- confirmation explicite exigée pour tout
// ce qui n'est pas un SELECT (même détection côté client que
// sql_console.is_select_statement côté serveur, jamais divergente
// dans son PRINCIPE même si dupliquée dans son CODE).
function SqlConsoleSection() {
  const [sql, setSql] = useState("");
  const [checking, setChecking] = useState(false);
  const [checkResult, setCheckResult] = useState(null);
  const [executing, setExecuting] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const isSelect = /^\s*select\b/i.test(sql);

  const resetOutcome = () => {
    setCheckResult(null);
    setResult(null);
    setError(null);
  };

  const handleCheck = async () => {
    setChecking(true);
    setCheckResult(null);
    const res = await postJson("/db/sql/check", { sql });
    setChecking(false);
    setCheckResult(res.ok ? res.data : { ok: false, error: res.data.error || "vérification impossible" });
  };

  const handleExecute = async () => {
    if (!isSelect) {
      const confirmed = window.confirm(
        "Cette requête n'est pas un SELECT -- elle va MODIFIER la base.\n\n" +
        "Une sauvegarde automatique sera prise juste avant l'exécution.\n\n" +
        "Continuer ?"
      );
      if (!confirmed) return;
    }
    setExecuting(true);
    setError(null);
    setResult(null);
    const res = await postJson("/db/sql/execute", { sql });
    setExecuting(false);
    if (res.ok) {
      setResult(res.data);
    } else {
      setError(res.data.error || "exécution impossible");
    }
  };

  return (
    <div>
      <p className="muted">
        "🔍 Vérifier la syntaxe" ne modifie JAMAIS les données (test sans exécution réelle) --
        utile pour tester avant de se lancer. "▶️ Exécuter" lance réellement la requête ; pour
        tout ce qui n'est pas un SELECT, une sauvegarde automatique est prise juste avant, et
        une confirmation est demandée.
      </p>
      <textarea
        value={sql}
        onChange={(e) => { setSql(e.target.value); resetOutcome(); }}
        placeholder="SELECT * FROM tickets WHERE ..."
        rows={6}
        style={{ width: "100%", fontFamily: "ui-monospace, monospace", fontSize: 13 }}
      />
      <div className="form-row">
        <button className="secondary" onClick={handleCheck} disabled={checking || !sql.trim()}>
          {checking ? "…" : "🔍 Vérifier la syntaxe"}
        </button>
        <button className="primary" onClick={handleExecute} disabled={executing || !sql.trim()}>
          {executing ? "…" : "▶️ Exécuter"}
        </button>
        {!isSelect && sql.trim() && (
          <span className="hint">⚠️ Requête d'écriture -- sauvegarde + confirmation avant exécution</span>
        )}
      </div>

      {checkResult && (checkResult.ok
        ? <p className="hint">✓ Syntaxe valide.</p>
        : <p className="error-text">✗ {checkResult.error}</p>
      )}
      {error && <p className="error-text">✗ {error}</p>}

      {result && result.kind === "affected" && (
        <p className="hint">
          ✓ {result.affected_rows} ligne{result.affected_rows > 1 ? "s" : ""} affectée{result.affected_rows > 1 ? "s" : ""}.
        </p>
      )}
      {result && result.kind === "rows" && (
        <>
          <p className="hint">
            {result.rows.length} ligne{result.rows.length > 1 ? "s" : ""} renvoyée{result.rows.length > 1 ? "s" : ""}.
          </p>
          <div style={{ overflowX: "auto" }}>
            <table className="portal-table">
              <thead><tr>{result.columns.map((c) => <th key={c}>{c}</th>)}</tr></thead>
              <tbody>
                {result.rows.map((row, i) => (
                  <tr key={i}>
                    {row.map((v, j) => <td key={j}>{v === null ? <span className="muted">NULL</span> : String(v)}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {result.rows.length === 0 && <p className="muted">Aucune ligne renvoyée.</p>}
        </>
      )}
    </div>
  );
}

function DatabaseTab() {
  const [subTab, setSubTab] = useState("export");
  const [counts, setCounts] = useState(null);
  const [importMode, setImportMode] = useState("merge");
  const [message, setMessage] = useState(null);

  const loadCounts = async () => {
    const res = await getJson("/export");
    if (res.ok) {
      setCounts(Object.fromEntries(Object.entries(res.data).map(([t, rows]) => [t, rows.length])));
    }
  };
  useEffect(() => { loadCounts(); }, []);

  const download = async () => {
    const res = await getJson("/export");
    if (!res.ok) return;
    const blob = new Blob([JSON.stringify(res.data, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `tickets-export-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  const importFile = async (file) => {
    if (!file) return;
    if (importMode === "replace" &&
        !window.confirm("Mode REPLACE : toute la base sera vidée puis rechargée depuis le fichier. Continuer ?")) {
      return;
    }
    const text = await file.text();
    let body;
    try {
      body = JSON.parse(text);
    } catch {
      setMessage("fichier JSON illisible");
      return;
    }
    const res = await fetch(`${API_BASE_URL}/import?mode=${importMode}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    setMessage(res.ok ? "import terminé ✓" : (data.error || "import en échec"));
    loadCounts();
  };

  return (
    <div>
      <div className="tabs">
        <button className={subTab === "export" ? "active" : ""} onClick={() => setSubTab("export")}>Export/Import</button>
        <button className={subTab === "browse" ? "active" : ""} onClick={() => setSubTab("browse")}>📋 Parcourir/éditer</button>
        <button className={subTab === "relations" ? "active" : ""} onClick={() => setSubTab("relations")}>🌳 Relations</button>
        <button className={subTab === "sql" ? "active" : ""} onClick={() => setSubTab("sql")}>💻 SQL</button>
      </div>

      {subTab === "export" && (
        <div>
          <h3>Export / import JSON (toute la base)</h3>
          <div className="form-row">
            <button className="primary" onClick={download}>⬇️ Exporter la base</button>
            <select value={importMode} onChange={(e) => setImportMode(e.target.value)}>
              <option value="merge">Import : merge (upsert par id)</option>
              <option value="replace">Import : replace (vide TOUT d'abord)</option>
            </select>
            <input type="file" accept=".json,application/json"
                   onChange={(e) => { importFile(e.target.files[0]); e.target.value = ""; }} />
          </div>
          {message && <p className="hint">{message}</p>}
          <h3>Volumes par table</h3>
          {!counts && <p className="muted">Chargement…</p>}
          {counts && (
            <dl className="kv-list">
              {Object.entries(counts).map(([t, n]) => (
                <React.Fragment key={t}>
                  <dt>{t}</dt>
                  <dd>{n} ligne{n > 1 ? "s" : ""}</dd>
                </React.Fragment>
              ))}
            </dl>
          )}
        </div>
      )}
      {subTab === "browse" && <TableBrowserSection />}
      {subTab === "relations" && <RelationshipsSection />}
      {subTab === "sql" && <SqlConsoleSection />}
    </div>
  );
}

// --- 🛠️ Incidents sur le projet lui-même ---
function ProjectIncidentsTab({ me }) {
  const [tickets, setTickets] = useState([]);
  const [hasLoadedOnce, setHasLoadedOnce] = useState(false);
  const [subject, setSubject] = useState("");
  const [description, setDescription] = useState("");
  const [selectedId, setSelectedId] = useState(null);

  const load = async () => {
    const res = await getJson("/queue?state=all&source_type=projet");
    if (res.ok) setTickets(res.data.tickets);
    setHasLoadedOnce(true);
  };
  useEffect(() => { load(); }, []);

  const create = async () => {
    const s = subject.trim();
    if (!s) return;
    const res = await postJson("/tickets", {
      user_id: me.id,
      subject: s,
      description: description.trim() || null,
      source_type: "projet",
      source_nom: "portail-tickets",
    });
    if (res.ok) {
      setSubject(""); setDescription("");
      // Timeline hub (backlog, livraison #119) -- jamais bloquant, un
      // échec ici ne doit jamais remettre en cause la création du
      // ticket elle-même (déjà réussie à ce stade).
      postHubEvent(PREFS_API_BASE_URL, {
        login: me.login, category: "ticket_cree", label: `#${res.data.id} — ${s}`,
      });
      await load();
      setSelectedId(res.data.id);
    }
  };

  const toggleClosed = async (t) => {
    const closing = !t.ts_closed;
    if (!window.confirm(`${closing ? "Fermer" : "Rouvrir"} l'incident #${t.id} ?`)) return;
    await putJson(`/tickets/${t.id}`, { ts_closed: closing ? Math.round(Date.now() / 1000) : null });
    await load();
  };

  return (
    <div>
      <p className="hint">
        Incidents concernant la plateforme supervision/tickets elle-même —
        tracés comme des tickets normaux avec <code>source_type = "projet"</code>,
        donc visibles aussi dans le module interne.
      </p>
      <h3>Déclarer un incident projet</h3>
      <div className="form-grid">
        <div className="form-row">
          <input placeholder="Sujet de l'incident" value={subject}
                 onChange={(e) => setSubject(e.target.value)}
                 onKeyDown={(e) => e.key === "Enter" && create()} />
          <button className="primary" onClick={create} disabled={!subject.trim()}>➕ Déclarer</button>
        </div>
        <textarea rows={2} placeholder="Détails (facultatif)" value={description}
                  onChange={(e) => setDescription(e.target.value)} />
      </div>
      <h3>Incidents ({tickets.length})</h3>
      {!hasLoadedOnce && <p className="muted">Chargement…</p>}
      {hasLoadedOnce && tickets.length === 0 && <p className="muted">Aucun incident déclaré.</p>}
      {tickets.map((t) => (
        <div key={t.id}
             className={`ticket-item${t.id === selectedId ? " selected" : ""}`}
             onClick={() => setSelectedId(t.id === selectedId ? null : t.id)}>
          <div className="subject">#{t.id} — {t.subject}</div>
          <div className="meta">
            <span className={`badge ${t.ts_closed ? "closed" : "open"}`}>
              {t.ts_closed ? "Fermé" : "Ouvert"}
            </span>
            <span>créé {fmtTsShort(t.ts_created)}</span>
            <button onClick={(e) => { e.stopPropagation(); toggleClosed(t); }}>
              {t.ts_closed ? "🔓 Rouvrir" : "🔒 Fermer"}
            </button>
          </div>
        </div>
      ))}
      {selectedId && <TicketThread ticketId={selectedId} me={me} />}
      {selectedId && <TicketDocuments ticketId={selectedId} me={me} />}
    </div>
  );
}

// --- 🔁 Réouvertures & archivage ---
function ReopeningsArchiveTab({ me }) {
  const [sub, setSub] = useState("reopenings");

  const [reopenings, setReopenings] = useState([]);
  const [reopeningsLoaded, setReopeningsLoaded] = useState(false);

  const [active, setActive] = useState([]);
  const [activeLoaded, setActiveLoaded] = useState(false);

  const [archived, setArchived] = useState([]);
  const [archivedLoaded, setArchivedLoaded] = useState(false);

  const [selectedId, setSelectedId] = useState(null);

  const loadReopenings = () => getJson("/stats/reopenings").then((r) => {
    if (r.ok) setReopenings(r.data.tickets);
    setReopeningsLoaded(true);
  });
  const loadActive = () => getJson("/queue?state=all").then((r) => {
    if (r.ok) setActive(r.data.tickets);
    setActiveLoaded(true);
  });
  const loadArchived = () => getJson("/queue?state=archived").then((r) => {
    if (r.ok) setArchived(r.data.tickets);
    setArchivedLoaded(true);
  });

  useEffect(() => { loadReopenings(); loadActive(); loadArchived(); }, []);

  const reopenTicket = async (t) => {
    if (!window.confirm(`Rouvrir la demande #${t.id} — « ${t.subject} » ?`)) return;
    const res = await putJson(`/tickets/${t.id}`, { ts_closed: null });
    if (res.ok) { await loadReopenings(); await loadActive(); }
  };

  // "Supprimer" côté admin = archiver, décidé avec la personne : rien
  // n'est jamais vraiment effacé, l'action reste réversible via
  // "Désarchiver" ci-dessous. Le libellé du bouton dit "Supprimer" —
  // c'est le mot que l'équipe utilise — le mécanisme est un archivage.
  const archiveTicket = async (t) => {
    if (!window.confirm(`Supprimer (archiver) la demande #${t.id} — « ${t.subject} » ?\n\nElle disparaîtra des vues normales mais reste récupérable ici.`)) return;
    const res = await putJson(`/tickets/${t.id}`, { archived_at: Math.round(Date.now() / 1000) });
    if (res.ok) { await loadActive(); await loadArchived(); }
  };

  const unarchiveTicket = async (t) => {
    if (!window.confirm(`Désarchiver la demande #${t.id} — « ${t.subject} » ?`)) return;
    const res = await putJson(`/tickets/${t.id}`, { archived_at: null });
    if (res.ok) { await loadActive(); await loadArchived(); }
  };

  return (
    <div>
      <div className="tabs">
        <button className={sub === "reopenings" ? "active" : ""} onClick={() => setSub("reopenings")}>
          🔁 Réouvertures {reopeningsLoaded && `(${reopenings.length})`}
        </button>
        <button className={sub === "archive" ? "active" : ""} onClick={() => setSub("archive")}>
          🗑️ Suppression / archivage
        </button>
        <button className={sub === "archived" ? "active" : ""} onClick={() => setSub("archived")}>
          📦 Archivées {archivedLoaded && `(${archived.length})`}
        </button>
      </div>

      {sub === "reopenings" && (
        <div>
          <p className="hint">
            Demandes rouvertes au moins une fois après clôture. Une réouverture répétée
            sur le même ticket peut signaler une résolution qui ne tient pas.
          </p>
          {!reopeningsLoaded && <p className="muted">Chargement…</p>}
          {reopeningsLoaded && reopenings.length === 0 && <p className="muted">Aucune demande rouverte.</p>}
          {reopenings.length > 0 && (
            <table className="portal-table">
              <thead>
                <tr><th>#</th><th>Sujet</th><th>Demandeur</th><th>Réouvertures</th><th>Dernière réouverture</th><th>État</th></tr>
              </thead>
              <tbody>
                {reopenings.map((t) => (
                  <tr key={t.id} onClick={() => setSelectedId(t.id)} style={{ cursor: "pointer" }}>
                    <td>{t.id}</td>
                    <td>{t.subject}</td>
                    <td>{t.user_login || "—"}</td>
                    <td><span className="badge">{t.reopen_count}×</span></td>
                    <td>{fmtTs(t.last_reopened_ts)}</td>
                    <td>
                      {t.archived_at ? <span className="badge">📦 archivée</span>
                        : t.ts_closed ? <span className="badge closed">Fermée</span>
                        : <span className="badge open">Ouverte</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {sub === "archive" && (
        <div>
          <p className="hint">
            "Supprimer" une demande ne l'efface jamais réellement — elle est archivée
            (masquée des vues normales), récupérable depuis l'onglet "📦 Archivées".
          </p>
          {!activeLoaded && <p className="muted">Chargement…</p>}
          {activeLoaded && active.length === 0 && <p className="muted">Aucune demande.</p>}
          {active.length > 0 && (
            <table className="portal-table">
              <thead>
                <tr><th>#</th><th>Sujet</th><th>Demandeur</th><th>État</th><th>Réouvertures</th><th>Actions</th></tr>
              </thead>
              <tbody>
                {active.map((t) => (
                  <tr key={t.id}>
                    <td>{t.id}</td>
                    <td>{t.subject}</td>
                    <td>{t.user_login || "—"}</td>
                    <td>
                      {t.ts_closed ? <span className="badge closed">Fermée</span> : <span className="badge open">Ouverte</span>}
                    </td>
                    <td>{t.reopen_count > 0 ? <span className="badge">{t.reopen_count}×</span> : "—"}</td>
                    <td>
                      {t.ts_closed && (
                        <button onClick={() => reopenTicket(t)}>🔓 Rouvrir</button>
                      )}
                      <button className="danger" onClick={() => archiveTicket(t)}>🗑️ Supprimer</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {sub === "archived" && (
        <div>
          <p className="hint">Demandes archivées — masquées de toutes les vues normales, jamais effacées.</p>
          {!archivedLoaded && <p className="muted">Chargement…</p>}
          {archivedLoaded && archived.length === 0 && <p className="muted">Aucune demande archivée.</p>}
          {archived.length > 0 && (
            <table className="portal-table">
              <thead>
                <tr><th>#</th><th>Sujet</th><th>Demandeur</th><th>Archivée le</th><th>Actions</th></tr>
              </thead>
              <tbody>
                {archived.map((t) => (
                  <tr key={t.id}>
                    <td>{t.id}</td>
                    <td>{t.subject}</td>
                    <td>{t.user_login || "—"}</td>
                    <td>{fmtTs(t.archived_at)}</td>
                    <td><button onClick={() => unarchiveTicket(t)}>♻️ Désarchiver</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {selectedId && (
        <div style={{ marginTop: 12 }}>
          <TicketThread ticketId={selectedId} me={me} />
          <TicketDocuments ticketId={selectedId} me={me} />
        </div>
      )}
    </div>
  );
}

// --- 📈 Éditeur de statistiques ---
function StatsTab() {
  const [groupBy, setGroupBy] = useState("statut");
  const [measure, setMeasure] = useState("count");
  const [state, setState] = useState("all");
  const [rows, setRows] = useState([]);
  const [hasLoadedOnce, setHasLoadedOnce] = useState(false);

  useEffect(() => {
    getJson(`/stats/aggregate?group_by=${groupBy}&measure=${measure}&state=${state}`)
      .then((r) => {
        if (r.ok) setRows(r.data.rows);
        setHasLoadedOnce(true);
      });
  }, [groupBy, measure, state]);

  const max = statsMax(rows);
  const fmtValue = (v) => (measure === "time" ? fmtDuration(v) : v);

  return (
    <div>
      <p className="hint">
        Composez la statistique : dimension × mesure × périmètre. La requête
        est whitelistée côté API (<code>/stats/aggregate</code>) — réutilisable
        telle quelle par d'autres outils.
      </p>
      <div className="filters-bar">
        <select value={groupBy} onChange={(e) => setGroupBy(e.target.value)}>
          <option value="statut">Par statut</option>
          <option value="user">Par demandeur</option>
          <option value="type">Par type</option>
          <option value="level">Par niveau</option>
        </select>
        <select value={measure} onChange={(e) => setMeasure(e.target.value)}>
          <option value="count">Nombre de tickets</option>
          <option value="time">Temps passé</option>
        </select>
        <select value={state} onChange={(e) => setState(e.target.value)}>
          <option value="all">Tous</option>
          <option value="open">Ouverts</option>
          <option value="closed">Fermés</option>
        </select>
      </div>
      {!hasLoadedOnce && <p className="muted">Chargement…</p>}
      {hasLoadedOnce && rows.length === 0 && <p className="muted">Aucune donnée.</p>}
      {rows.map((r) => (
        <div key={r.label} className="stat-bar-row">
          <div className="stat-bar-label" title={r.label}>{r.label}</div>
          <div className="stat-bar-track">
            <div className="stat-bar-fill"
                 style={{ width: max > 0 ? `${(r.value / max) * 100}%` : "0%" }} />
          </div>
          <div className="stat-bar-value">{fmtValue(r.value)}</div>
        </div>
      ))}
    </div>
  );
}

// --- 🔌 Connecteurs ---
function ConnectorsTab() {
  const [oauth, setOauth] = useState(null);
  const [settings, setSettings] = useState(null);
  const [keyword, setKeyword] = useState("");
  const [ruleCounts, setRuleCounts] = useState(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    getJson("/oauth/google/status").then((r) => r.ok && setOauth(r.data));
    getJson("/settings").then((r) => {
      if (r.ok) {
        setSettings(r.data);
        setKeyword(r.data.trigger_keyword || "");
      }
    });
    Promise.all([
      getJson("/filter_rules"), getJson("/exclusion_rules"), getJson("/priority_keywords"),
    ]).then(([f, e, p]) => {
      setRuleCounts({
        "règles de rattachement": f.ok ? f.data.length : "?",
        "règles d'exclusion (véto)": e.ok ? e.data.length : "?",
        "mots-clés d'urgence": p.ok ? p.data.length : "?",
      });
    });
  }, []);

  const saveKeyword = async () => {
    const res = await postJson("/settings", { trigger_keyword: keyword });
    if (res.ok) {
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    }
  };

  return (
    <div>
      <h3>Agenda Google (OAuth2)</h3>
      {!oauth && <p className="muted">Chargement…</p>}
      {oauth && (
        <dl className="kv-list">
          <dt>Identifiants configurés</dt>
          <dd>{oauth.configured ? "oui ✓" : "non — renseigner GOOGLE_OAUTH_* dans .env"}</dd>
          <dt>Agenda connecté</dt>
          <dd>{oauth.connected ? "oui ✓" : "non"}</dd>
        </dl>
      )}
      <h3>Mot-clé déclencheur (revue calendrier)</h3>
      {settings && (
        <div className="form-row">
          <input value={keyword} onChange={(e) => setKeyword(e.target.value)}
                 onKeyDown={(e) => e.key === "Enter" && saveKeyword()} />
          <button className="primary" onClick={saveKeyword}>Enregistrer</button>
          {saved && <span className="badge open">enregistré ✓</span>}
        </div>
      )}
      <h3>Règles configurées</h3>
      {!ruleCounts && <p className="muted">Chargement…</p>}
      {ruleCounts && (
        <dl className="kv-list">
          {Object.entries(ruleCounts).map(([k, v]) => (
            <React.Fragment key={k}>
              <dt>{k}</dt><dd>{v}</dd>
            </React.Fragment>
          ))}
        </dl>
      )}
      <p className="hint">
        La connexion de l'agenda, l'import et l'édition détaillée des règles
        se font dans le module interne (panneau d'import et ⚙️ Règles
        calendrier) — même API, même configuration.
      </p>
    </div>
  );
}

const TABS = [
  { id: "users", label: "👥 Utilisateurs" },
  { id: "reference", label: "🏷️ Types & niveaux" },
  { id: "reopenings", label: "🔁 Réouvertures & archivage" },
  { id: "db", label: "🗄️ Base" },
  { id: "incidents", label: "🛠️ Incidents projet" },
  { id: "stats", label: "📈 Statistiques" },
  { id: "connectors", label: "🔌 Connecteurs" },
];

export default function AdminView({ me }) {
  const [tab, setTab] = useState("users");
  return (
    <div className="panel">
      <div className="tabs">
        {TABS.map((t) => (
          <button key={t.id} className={tab === t.id ? "active" : ""} onClick={() => setTab(t.id)}>
            {t.label}
          </button>
        ))}
      </div>
      {tab === "users" && <UsersTab />}
      {tab === "reference" && <ReferenceDataTab />}
      {tab === "reopenings" && <ReopeningsArchiveTab me={me} />}
      {tab === "db" && <DatabaseTab />}
      {tab === "incidents" && <ProjectIncidentsTab me={me} />}
      {tab === "stats" && <StatsTab />}
      {tab === "connectors" && <ConnectorsTab />}
    </div>
  );
}
