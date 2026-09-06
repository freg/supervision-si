import React, { useEffect, useMemo, useState } from "react";
import { createLocalThemeStore } from "./preferences.js";
import { getJson, postJson, putJson, getText } from "./api.js";
import { buildTree, usersUnder, buildColumns } from "./ldapTree.js";
import versionInfo from "./VERSION.json";

const themeStore = createLocalThemeStore();
const HUB_URL = import.meta.env.VITE_HUB_URL || "/";

// Même liste que côté serveur (ldap-admin/api/app.py, SENSITIVE_ATTRS)
// -- affichée en lecture seule ici, jamais éditable via ce panneau
// générique (la réinitialisation de mot de passe dédiée garantit le
// hachage SSHA, ce panneau ne doit jamais pouvoir envoyer un mot de
// passe en clair).
const SENSITIVE_ATTRS = ["userpassword", "krbprincipalkey", "sambantpassword", "sambalmpassword", "authpassword"];

// --- Panneau de détail/édition d'une entrée -- demandé explicitement
// ("accéder et éditer tous les attributs à tous les niveaux, en
// particulier les feuilles de l'arbre") : jusqu'ici, une entrée sans
// uid (un groupe comme cn=Parapheur, par exemple) n'apparaissait
// nulle part -- ce panneau montre TOUJOURS l'entrée actuellement
// sélectionnée, quelle que soit sa nature (feuille, groupe,
// utilisateur, unité organisationnelle).
// --- Visualiseur JSON de l'arbre complet -- demandé explicitement :
// couvrir tout l'arbre LDIF par défaut (pas seulement la racine),
// navigable avec des +/- pour développer/réduire chaque nœud. État
// d'expansion levé au niveau du parent (LdapBrowser) plutôt qu'une
// state locale par nœud -- permet "tout déplier"/"tout replier" en
// manipulant un seul ensemble partagé, jamais besoin de redescendre
// dans chaque composant individuellement.
function JsonTreeNode({ tree, dn, depth, expandedDns, onToggle }) {
  const node = tree.nodes[dn];
  if (!node) return null;
  const hasChildren = node.children.length > 0;
  const isExpanded = expandedDns.has(dn);

  return (
    <div className="ldap-json-node" style={{ marginLeft: depth > 0 ? 16 : 0 }}>
      <div className="ldap-json-node-header" onClick={() => hasChildren && onToggle(dn)}>
        {hasChildren ? (
          <span className="ldap-json-toggle">{isExpanded ? "−" : "+"}</span>
        ) : (
          <span className="ldap-json-toggle-spacer" />
        )}
        <span className="ldap-json-dn">{node.label}</span>
        {hasChildren && <span className="ldap-column-count">{node.children.length}</span>}
      </div>
      {isExpanded && (
        <div className="ldap-json-node-body">
          {Object.keys(node.attrs).length > 0 && (
            <pre className="ldap-json-attrs">{JSON.stringify(node.attrs, null, 2)}</pre>
          )}
          {node.children.map((childDn) => (
            <JsonTreeNode key={childDn} tree={tree} dn={childDn} depth={depth + 1} expandedDns={expandedDns} onToggle={onToggle} />
          ))}
        </div>
      )}
    </div>
  );
}

function EntryDetailPanel({ node, bindPassword, onAuthError, onSaved, compact }) {
  const [editedAttrs, setEditedAttrs] = useState(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);

  useEffect(() => {
    // Réinitialise l'édition à chaque changement de sélection --
    // jamais un brouillon d'une entrée qui traîne sur une autre.
    setEditedAttrs(node ? { ...node.attrs } : null);
    setMessage(null);
  }, [node?.dn]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!node || !editedAttrs) {
    return <p className="muted">Sélectionnez une entrée pour voir et éditer ses attributs.</p>;
  }

  const attrNames = Object.keys(editedAttrs).sort();

  const updateValue = (attr, index, value) => {
    setEditedAttrs((prev) => {
      const next = { ...prev, [attr]: [...prev[attr]] };
      next[attr][index] = value;
      return next;
    });
  };
  const removeValue = (attr, index) => {
    setEditedAttrs((prev) => ({ ...prev, [attr]: prev[attr].filter((_, i) => i !== index) }));
  };
  const addValue = (attr) => {
    setEditedAttrs((prev) => ({ ...prev, [attr]: [...prev[attr], ""] }));
  };

  const changedAttrs = () => {
    const changes = {};
    for (const attr of attrNames) {
      const cleaned = editedAttrs[attr].map((v) => v.trim()).filter(Boolean);
      const original = node.attrs[attr] || [];
      if (JSON.stringify(cleaned) !== JSON.stringify(original)) changes[attr] = cleaned;
    }
    return changes;
  };
  const hasChanges = Object.keys(changedAttrs()).length > 0;

  const save = async () => {
    const changes = changedAttrs();
    if (Object.keys(changes).length === 0) return;
    setSaving(true);
    const res = await putJson(`/entries/${encodeURIComponent(node.dn)}`, { attr_changes: changes, actor: "" }, bindPassword);
    setSaving(false);
    if (res.ok) {
      setMessage({ ok: true, text: "Modifications enregistrées." });
      onSaved();
    } else if (res.status === 401) {
      onAuthError();
    } else {
      setMessage({ ok: false, text: res.data.error || "échec de l'enregistrement" });
    }
  };

  return (
    <div className={`ldap-detail-panel${compact ? " ldap-detail-panel-compact" : ""}`}>
      <h4>{node.label}</h4>
      <p className="muted ldap-detail-dn">{node.dn}</p>
      {attrNames.map((attr) => {
        const isSensitive = SENSITIVE_ATTRS.includes(attr.toLowerCase());
        return (
          <div key={attr} className="ldap-detail-attr">
            <label>{attr}</label>
            {isSensitive ? (
              <p className="muted">(non modifiable ici -- voir la réinitialisation de mot de passe)</p>
            ) : (
              <>
                {editedAttrs[attr].map((value, i) => (
                  <div key={i} className="ldap-detail-value-row">
                    <input value={value} onChange={(e) => updateValue(attr, i, e.target.value)} />
                    <button className="secondary" onClick={() => removeValue(attr, i)}>✕</button>
                  </div>
                ))}
                <button className="secondary" onClick={() => addValue(attr)}>+ valeur</button>
              </>
            )}
          </div>
        );
      })}
      {message && <p className={message.ok ? "ldap-success" : "ldap-error"}>{message.text}</p>}
      <button className="primary" onClick={save} disabled={saving || !hasChanges}>
        {saving ? "…" : "💾 Enregistrer les modifications"}
      </button>
    </div>
  );
}

// --- Écran de déverrouillage -- demandé explicitement : le mot de
// passe de liaison n'est JAMAIS stocké côté serveur ni sur ce
// navigateur (aucun localStorage, aucun cookie) -- redemandé à
// chaque nouvelle session (rechargement de page = re-verrouillage).
function UnlockScreen({ onUnlock }) {
  const [input, setInput] = useState("");

  return (
    <div className="ldap-shell">
      <div className="ldap-unlock-panel">
        <h1>🔐 Gestion OpenLDAP</h1>
        <p className="muted">
          Le mot de passe de liaison n'est jamais conservé côté serveur ni sur ce
          navigateur -- à saisir à chaque nouvelle session. Il sera utilisé
          uniquement pour les actions de cette session, jamais écrit sur disque.
        </p>
        <input
          type="password"
          placeholder="Mot de passe de liaison LDAP"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && input.trim() && onUnlock(input)}
          autoFocus
        />
        <button className="primary" onClick={() => input.trim() && onUnlock(input)} disabled={!input.trim()}>
          Déverrouiller
        </button>
      </div>
    </div>
  );
}

// --- Navigateur LDAP en colonnes -- demandé explicitement, façon
// phpLDAPadmin/Finder : une colonne par niveau de profondeur,
// chaque sélection propage vers la droite, la colonne finale montre
// les utilisateurs (récursivement) sous le nœud sélectionné --
// "les filtres = les groupes sélectionnés". Arbre construit UNE
// SEULE FOIS au chargement (GET /entries, tout l'annuaire d'un
// coup) -- toute la navigation ensuite est locale, aucun aller-
// retour réseau par clic de colonne.
function LdapBrowser({ bindPassword, onAuthError }) {
  const [entries, setEntries] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedPath, setSelectedPath] = useState([]); // [dn niveau 0, dn niveau 1, ...]
  const [viewMode, setViewMode] = useState("tree"); // "tree" | "json"
  // DN développés en mode JSON -- demandé explicitement (couvrir
  // tout l'arbre par défaut, navigable avec +/-). Ensemble partagé
  // plutôt qu'une state locale par nœud -- "tout déplier"/"tout
  // replier" manipule directement cet ensemble unique.
  const [jsonExpandedDns, setJsonExpandedDns] = useState(new Set());
  const toggleJsonExpand = (dn) => {
    setJsonExpandedDns((prev) => {
      const next = new Set(prev);
      if (next.has(dn)) next.delete(dn);
      else next.add(dn);
      return next;
    });
  };

  const [resetTarget, setResetTarget] = useState(null);
  const [newPassword, setNewPassword] = useState("");
  const [confirmText, setConfirmText] = useState("");
  const [resetBusy, setResetBusy] = useState(false);
  const [resetMessage, setResetMessage] = useState(null);

  // Sélection dans la liste des utilisateurs (colonne finale) --
  // demandé explicitement : cliquer un utilisateur y montre son
  // détail, séparée de `selectedPath` puisqu'un utilisateur listé là
  // n'est pas forcément un enfant direct du dernier niveau de
  // navigation (la liste est récursive, potentiellement plus
  // profonde).
  const [recursiveUserDetailDn, setRecursiveUserDetailDn] = useState(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    const res = await getJson("/entries", bindPassword);
    setLoading(false);
    if (res.ok) {
      setEntries(res.data);
    } else if (res.status === 401) {
      onAuthError();
    } else {
      setError(res.data.error || "chargement impossible");
    }
  };

  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Reconstruit l'arbre seulement quand les entrées changent (pas à
  // chaque clic de colonne) -- la navigation elle-même ne touche
  // jamais `entries`.
  const tree = useMemo(() => (entries ? buildTree(entries) : null), [entries]);

  // Sélectionne automatiquement la première racine au premier
  // chargement, pour ne jamais présenter un navigateur "vide" alors
  // que l'annuaire a bien été chargé.
  useEffect(() => {
    if (tree && tree.roots.length > 0 && selectedPath.length === 0) {
      setSelectedPath([tree.roots[0]]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tree]);

  // Pré-déplie les racines en mode JSON au premier chargement --
  // montre immédiatement quelque chose plutôt qu'un arbre entièrement
  // replié et vide en apparence.
  useEffect(() => {
    if (tree && tree.roots.length > 0 && jsonExpandedDns.size === 0) {
      setJsonExpandedDns(new Set(tree.roots));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tree]);

  const selectAtLevel = (level, dn) => {
    // Sélectionne `dn` au niveau `level` -- tronque le chemin après
    // ce niveau (une sélection plus profonde devient invalide dès
    // qu'on change de branche en amont). Efface aussi la sélection
    // dans la liste des utilisateurs -- jamais un détail périmé
    // affiché pendant qu'on navigue ailleurs.
    setSelectedPath((prev) => [...prev.slice(0, level), dn]);
    setRecursiveUserDetailDn(null);
  };

  const startReset = (node) => {
    setResetTarget(node);
    setNewPassword("");
    setConfirmText("");
    setResetMessage(null);
  };

  const confirmReset = async () => {
    const uid = (resetTarget?.attrs.uid || [""])[0];
    if (!resetTarget || newPassword.length < 8 || confirmText !== uid) return;
    setResetBusy(true);
    const res = await putJson(
      `/users/${encodeURIComponent(resetTarget.dn)}/password`,
      { new_password: newPassword, actor: "" },
      bindPassword
    );
    setResetBusy(false);
    if (res.ok) {
      setResetMessage({ ok: true, text: "Mot de passe réinitialisé." });
      setTimeout(() => setResetTarget(null), 1500);
    } else if (res.status === 401) {
      onAuthError();
    } else {
      setResetMessage({ ok: false, text: res.data.error || "échec de la réinitialisation" });
    }
  };

  if (loading) return <p className="muted">Chargement…</p>;
  if (error) return <p className="ldap-error">{error}</p>;
  if (!tree || tree.roots.length === 0) return <p className="muted">Annuaire vide ou inaccessible.</p>;

  const lastSelectedDn = selectedPath[selectedPath.length - 1];
  const finalUsers = lastSelectedDn ? usersUnder(tree, lastSelectedDn) : [];
  // Construit les colonnes ET les attributs de chaque parent à
  // afficher en tête -- voir buildColumns (ldapTree.js), demandé
  // explicitement.
  const columns = buildColumns(tree, selectedPath);

  return (
    <div>
      <div className="ldap-browser-toolbar">
        <button className={viewMode === "tree" ? "active" : ""} onClick={() => setViewMode("tree")}>🌳 Arbre</button>
        <button className={viewMode === "json" ? "active" : ""} onClick={() => setViewMode("json")}>{"{ }"} JSON</button>
        {viewMode === "json" && (
          <>
            <button className="secondary" onClick={() => setJsonExpandedDns(new Set(Object.keys(tree.nodes)))}>Tout déplier</button>
            <button className="secondary" onClick={() => setJsonExpandedDns(new Set())}>Tout replier</button>
          </>
        )}
      </div>

      {viewMode === "json" ? (
        <div className="ldap-json-view">
          {tree.roots.map((rootDn) => (
            <JsonTreeNode key={rootDn} tree={tree} dn={rootDn} depth={0} expandedDns={jsonExpandedDns} onToggle={toggleJsonExpand} />
          ))}
        </div>
      ) : (
        <div className="ldap-columns">
          {columns.map((col) => (
            <div key={col.level} className="ldap-column">
              {/* Attributs du PARENT dont les enfants sont listés
                  juste en dessous -- demandé explicitement : "la
                  colonne suivante doit montrer en tête les attributs".
                  Absent pour la colonne 0 (les racines, aucun parent
                  à ce niveau). */}
              {col.parentDn && (
                <EntryDetailPanel
                  node={tree.nodes[col.parentDn]}
                  bindPassword={bindPassword}
                  onAuthError={onAuthError}
                  onSaved={load}
                  compact
                />
              )}
              {col.dns.length === 0 && col.parentDn && (
                <p className="muted ldap-column-no-children">Aucun sous-nœud.</p>
              )}
              {col.dns.map((dn) => {
                const node = tree.nodes[dn];
                return (
                  <button
                    key={dn}
                    className={`ldap-column-item${selectedPath[col.level] === dn ? " selected" : ""}`}
                    onClick={() => selectAtLevel(col.level, dn)}
                  >
                    <span>{node.label}</span>
                    {node.children.length > 0 && <span className="ldap-column-count">{node.children.length}</span>}
                  </button>
                );
              })}
            </div>
          ))}

          <div className="ldap-column ldap-column-users">
            <h4>{finalUsers.length} utilisateur{finalUsers.length !== 1 ? "s" : ""}</h4>
            {finalUsers.length === 0 && <p className="muted">Aucun utilisateur sous cette sélection.</p>}
            {finalUsers.map((u) => (
              <div
                key={u.dn}
                className={`ldap-user-item${recursiveUserDetailDn === u.dn ? " selected" : ""}`}
                onClick={() => setRecursiveUserDetailDn(u.dn)}
              >
                <div>
                  <div>{(u.attrs.uid || [""])[0]}</div>
                  <div className="muted">{(u.attrs.cn || [""])[0]}</div>
                </div>
                <button className="secondary" onClick={(e) => { e.stopPropagation(); startReset(u); }}>🔑</button>
              </div>
            ))}
          </div>

          {/* Demandé explicitement : sélectionner un élément de la
              liste des utilisateurs (potentiellement plus profond que
              la colonne de navigation actuelle) doit aussi montrer
              son détail -- colonne séparée, la sélection dans les
              utilisateurs n'est pas forcément un enfant direct du
              dernier niveau de navigation, jamais mélangée à
              `selectedPath`. */}
          {recursiveUserDetailDn && tree.nodes[recursiveUserDetailDn] && (
            <div className="ldap-column">
              <EntryDetailPanel
                node={tree.nodes[recursiveUserDetailDn]}
                bindPassword={bindPassword}
                onAuthError={onAuthError}
                onSaved={load}
                compact
              />
            </div>
          )}
        </div>
      )}

      {resetTarget && (
        <div className="ldap-modal-overlay" onClick={() => setResetTarget(null)}>
          <div className="ldap-modal" onClick={(e) => e.stopPropagation()}>
            <h2>🔑 Réinitialiser le mot de passe de {(resetTarget.attrs.uid || [""])[0]}</h2>
            <p className="muted">
              Une sauvegarde de l'annuaire est prise automatiquement avant cette
              opération. Le nouveau mot de passe est haché (SSHA) avant tout envoi.
            </p>
            <label>Nouveau mot de passe (8 caractères minimum)</label>
            <input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} autoFocus />
            <label>
              Tapez <strong>{(resetTarget.attrs.uid || [""])[0]}</strong> pour confirmer cette action irréversible
            </label>
            <input value={confirmText} onChange={(e) => setConfirmText(e.target.value)} />
            {resetMessage && (
              <p className={resetMessage.ok ? "ldap-success" : "ldap-error"}>{resetMessage.text}</p>
            )}
            <div className="ldap-modal-actions">
              <button onClick={() => setResetTarget(null)}>Annuler</button>
              <button
                className="danger"
                onClick={confirmReset}
                disabled={resetBusy || newPassword.length < 8 || confirmText !== (resetTarget.attrs.uid || [""])[0]}
              >
                {resetBusy ? "…" : "Confirmer la réinitialisation"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// --- Onglet Sauvegardes -- liste, création manuelle, diff, contenu brut ---
function BackupsTab({ bindPassword, onAuthError }) {
  const [backups, setBackups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [creating, setCreating] = useState(false);
  const [diffSelection, setDiffSelection] = useState({ before: "", after: "" });
  const [diffResult, setDiffResult] = useState(null);
  const [diffError, setDiffError] = useState(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    const res = await getJson("/backups");
    setLoading(false);
    if (res.ok) setBackups(res.data);
    else setError(res.data.error || "chargement impossible");
  };

  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleCreate = async () => {
    setCreating(true);
    const res = await postJson("/backups", {}, bindPassword);
    setCreating(false);
    if (res.ok) {
      load();
    } else if (res.status === 401) {
      onAuthError();
    } else {
      setError(res.data.error || "sauvegarde échouée");
    }
  };

  const handleDownload = async (filename) => {
    const res = await getText(`/backups/${encodeURIComponent(filename)}`);
    if (!res.ok) return;
    const blob = new Blob([res.text], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleDiff = async () => {
    setDiffResult(null);
    setDiffError(null);
    if (!diffSelection.before || !diffSelection.after) return;
    const res = await getJson(
      `/backups/diff?before=${encodeURIComponent(diffSelection.before)}&after=${encodeURIComponent(diffSelection.after)}`
    );
    if (res.ok) setDiffResult(res.data);
    else setDiffError(res.data.error || "diff impossible");
  };

  return (
    <div>
      <div className="ldap-form-row">
        <button className="primary" onClick={handleCreate} disabled={creating}>
          {creating ? "…" : "💾 Sauvegarder maintenant"}
        </button>
      </div>
      {error && <p className="ldap-error">{error}</p>}
      {loading && <p className="muted">Chargement…</p>}
      {!loading && backups.length === 0 && <p className="muted">Aucune sauvegarde pour l'instant.</p>}
      {!loading && backups.length > 0 && (
        <table className="ldap-table">
          <thead><tr><th>Fichier</th><th>Taille</th><th></th></tr></thead>
          <tbody>
            {backups.map((b) => (
              <tr key={b.filename}>
                <td>{b.filename}</td>
                <td>{b.size_bytes != null ? `${Math.round(b.size_bytes / 1024)} ko` : "—"}</td>
                <td><button className="secondary" onClick={() => handleDownload(b.filename)}>⬇️ Télécharger</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <h3 style={{ marginTop: "1.5rem" }}>🌳 Comparer deux sauvegardes ("historique façon git")</h3>
      <div className="ldap-form-row">
        <select value={diffSelection.before} onChange={(e) => setDiffSelection({ ...diffSelection, before: e.target.value })}>
          <option value="">— avant —</option>
          {backups.map((b) => <option key={b.filename} value={b.filename}>{b.filename}</option>)}
        </select>
        <select value={diffSelection.after} onChange={(e) => setDiffSelection({ ...diffSelection, after: e.target.value })}>
          <option value="">— après —</option>
          {backups.map((b) => <option key={b.filename} value={b.filename}>{b.filename}</option>)}
        </select>
        <button onClick={handleDiff} disabled={!diffSelection.before || !diffSelection.after}>Comparer</button>
      </div>
      {diffError && <p className="ldap-error">{diffError}</p>}
      {diffResult && (
        <div className="ldap-diff-result">
          {diffResult.added.length === 0 && diffResult.removed.length === 0 && diffResult.modified.length === 0 && (
            <p className="muted">Aucune différence entre ces deux sauvegardes.</p>
          )}
          {diffResult.added.length > 0 && (
            <div className="ldap-diff-group ldap-diff-added">
              <strong>➕ Ajoutées ({diffResult.added.length})</strong>
              <ul>{diffResult.added.map((dn) => <li key={dn}>{dn}</li>)}</ul>
            </div>
          )}
          {diffResult.removed.length > 0 && (
            <div className="ldap-diff-group ldap-diff-removed">
              <strong>➖ Supprimées ({diffResult.removed.length})</strong>
              <ul>{diffResult.removed.map((dn) => <li key={dn}>{dn}</li>)}</ul>
            </div>
          )}
          {diffResult.modified.length > 0 && (
            <div className="ldap-diff-group ldap-diff-modified">
              <strong>✏️ Modifiées ({diffResult.modified.length})</strong>
              {diffResult.modified.map((m) => (
                <div key={m.dn} className="ldap-diff-entry">
                  <div className="ldap-diff-dn">{m.dn}</div>
                  {Object.entries(m.attr_changes).map(([attr, change]) => (
                    <div key={attr} className="ldap-diff-attr">
                      <span className="ldap-diff-attr-name">{attr}</span>
                      <span className="ldap-diff-old">{change.old.join(", ") || "(vide)"}</span>
                      {" → "}
                      <span className="ldap-diff-new">{change.new.join(", ") || "(vide)"}</span>
                    </div>
                  ))}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function App() {
  const [bindPassword, setBindPassword] = useState(""); // JAMAIS persisté -- état React en mémoire uniquement
  const [unlocked, setUnlocked] = useState(false);
  const [tab, setTab] = useState("users");
  const [theme, setThemeState] = useState(themeStore.get() || "light");

  useEffect(() => themeStore.onChange(setThemeState), []);
  const toggleTheme = () => themeStore.set(theme === "dark" ? "light" : "dark");

  const handleUnlock = (password) => {
    setBindPassword(password);
    setUnlocked(true);
  };

  // Reverrouille sur toute erreur d'authentification (mot de passe
  // erroné ou expiré côté serveur LDAP) -- jamais continuer à
  // afficher un état "déverrouillé" trompeur si le mot de passe en
  // mémoire ne fonctionne plus.
  const handleAuthError = () => {
    setBindPassword("");
    setUnlocked(false);
  };

  const handleLock = () => {
    setBindPassword("");
    setUnlocked(false);
  };

  if (!unlocked) {
    return <UnlockScreen onUnlock={handleUnlock} />;
  }

  return (
    <div className="ldap-shell">
      <header className="ldap-header">
        <a href={HUB_URL} className="ldap-hub-link" title="Retour au hub">🏠 Hub</a>
        <h1>🔐 Gestion OpenLDAP</h1>
        <div className="ldap-header-actions">
          <button onClick={toggleTheme} title={theme === "dark" ? "Thème clair" : "Thème sombre"}>
            {theme === "dark" ? "☀️" : "🌙"}
          </button>
          <button onClick={handleLock} title="Oublier le mot de passe de cette session">🔒 Verrouiller</button>
        </div>
      </header>

      <div className="tabs">
        <button className={tab === "users" ? "active" : ""} onClick={() => setTab("users")}>👤 Utilisateurs</button>
        <button className={tab === "backups" ? "active" : ""} onClick={() => setTab("backups")}>💾 Sauvegardes</button>
      </div>

      {tab === "users" && <LdapBrowser bindPassword={bindPassword} onAuthError={handleAuthError} />}
      {tab === "backups" && <BackupsTab bindPassword={bindPassword} onAuthError={handleAuthError} />}

      <div className="version-badge" title={`hash contenu : ${versionInfo.content_hash} · hash git : ${versionInfo.git_hash} · dernière vérification : ${versionInfo.last_checked_at}`}>
        #{versionInfo.delivery_number || "?"}
      </div>
    </div>
  );
}
