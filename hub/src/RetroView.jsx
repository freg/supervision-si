import React, { useState, useEffect } from "react";
import { scanPhpArchive } from "./retroClient.js";
import { fetchDbaConnections, createRelation } from "./schemaAnalyzerClient.js";

// Tuile "Rétro-ingénierie" (hub), livraison #243 -- backlog item 30,
// demandé explicitement en urgence : "vieille application de
// gestion développée avec fatfree en php... développeur génial
// avait ses schémas en tête... aucune note".
//
// Complète `schema-analyzer` (Data → Analyse de schémas, #151-241,
// qui déduit les relations depuis le SCHÉMA et les DONNÉES) -- ici,
// les relations CANDIDATES sont déduites depuis l'USAGE RÉEL dans le
// CODE (jointures SQL écrites en toutes lettres) : une relation
// qu'aucune heuristique de nommage ni de données ne pourrait deviner
// si les noms sont atypiques.
//
// ⚠️ Portée VOLONTAIREMENT LIMITÉE à ce premier volet -- le second
// volet demandé ("proposer un schéma fonctionnel de l'interface")
// n'est PAS construit ici. Pas encore d'envoi automatique vers
// l'éditeur de relations de schema-analyzer -- une fois un candidat
// repéré ici, la confirmation contre les vraies données (bouton
// "🔍 Valider les données", #241) et l'enregistrement définitif se
// font manuellement là-bas pour l'instant.

export default function RetroView({ onBack, retroApiBase, dbaApiBase, schemaApiBase }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  // Envoi direct vers l'éditeur de relations de schema-analyzer
  // (livraison #247) -- ferme la boucle "repérer ici, confirmer
  // là-bas" décrite à la personne : plus besoin de recopier
  // manuellement chaque candidat.
  const [connections, setConnections] = useState([]);
  const [connectionId, setConnectionId] = useState("");
  const [database, setDatabase] = useState("");
  const [sendStatus, setSendStatus] = useState({}); // {idx: "sending" | "sent" | {error}}

  useEffect(() => {
    if (!dbaApiBase) return;
    fetchDbaConnections(dbaApiBase).then((list) => setConnections(Array.isArray(list) ? list : []));
  }, [dbaApiBase]);

  async function handleFileUpload(e) {
    const file = e.target.files[0];
    if (!file) return;
    setBusy(true);
    setError(null);
    setResult(null);
    setSendStatus({});
    const response = await scanPhpArchive(retroApiBase, file);
    if (response.error) setError(response.error);
    else setResult(response);
    setBusy(false);
    e.target.value = "";
  }

  async function handleSendToSchemaAnalyzer(candidate, idx) {
    if (!connectionId) return;
    setSendStatus((prev) => ({ ...prev, [idx]: "sending" }));
    const res = await createRelation(schemaApiBase, {
      connection_id: Number(connectionId),
      database: database || null,
      from_table: candidate.from_table,
      from_column: candidate.from_column,
      to_table: candidate.to_table,
      to_column: candidate.to_column,
      relation_type: "foreign_key",
    });
    setSendStatus((prev) => ({ ...prev, [idx]: res.error ? { error: res.error } : "sent" }));
  }

  return (
    <div className="hub-settings hub-settings-wide">
      <div className="hub-settings-topbar">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h1>🕵️ Rétro-ingénierie</h1>
      </div>

      <div className="hub-card">
        <p className="muted" style={{ margin: 0 }}>
          Dépose une archive ZIP du code source à analyser -- chaque fichier <code>.php</code>,
          <code>.phtml</code>, <code>.html</code> ou <code>.htm</code> est balayé à la recherche de
          requêtes SQL (jointures explicites ou style ancien avec plusieurs tables dans le FROM), de
          structures de données dans les VUES d'écran (champs de formulaire, accès aux champs dans les
          gabarits Fat-Free natifs <code>{"{{@item.champ}}"}</code> ou en PHP brut affiché
          <code>$var['champ']</code>) ET des routes déclarées (<code>$f3-&gt;route(...)</code> ou
          <code>F3::route(...)</code>) pour reconstituer le schéma fonctionnel de l'application. Approche
          par expression régulière, jamais un vrai parseur -- des éléments peuvent être manqués sur du
          code construit dynamiquement, jamais une certitude absolue. ⚠️ Version de Fat-Free non
          confirmée pour cette application -- les motifs couverts sont documentés comme stables sur une
          large part de l'historique F3, mais aucune source officielle spécifique à une lignée 2.x n'a pu
          être trouvée ; les résultats réels restent le meilleur signal. Pour confirmer une relation
          trouvée ici contre les vraies données, utilisez l'éditeur de relations de{" "}
          <strong>Analyse de schémas</strong> (bouton "🔍 Valider les données").
        </p>
      </div>

      <div className="hub-card hub-settings-section">
        <p className="muted" style={{ marginTop: 0 }}>
          Pour envoyer directement une relation candidate vers l'éditeur de <strong>Analyse de
          schémas</strong> (plutôt que de la recopier à la main), choisissez la connexion DBA
          correspondant à cette base -- optionnel, seulement nécessaire pour utiliser le bouton
          "→ Envoyer" sur chaque relation trouvée.
        </p>
        <div className="hub-settings-row">
          <label>Connexion DBA</label>
          <select value={connectionId} onChange={(e) => setConnectionId(e.target.value)}>
            <option value="">— aucune (pas d'envoi) —</option>
            {connections.map((c) => (
              <option key={c.id} value={c.id}>{c.label || c.name || `Connexion #${c.id}`}</option>
            ))}
          </select>
        </div>
        <div className="hub-settings-row">
          <label>Base (optionnel)</label>
          <input value={database} onChange={(e) => setDatabase(e.target.value)} placeholder="laisser vide si non applicable" />
        </div>
      </div>

      <div className="hub-card hub-settings-section">
        <label className="secondary" style={{ cursor: "pointer", display: "inline-block" }}>
          📤 Analyser une archive ZIP
          <input type="file" accept=".zip" onChange={handleFileUpload} disabled={busy} style={{ display: "none" }} />
        </label>
        {busy && <p className="muted">Analyse en cours…</p>}
        {error && (
          <p style={{ color: "var(--hub-danger, #c0392b)" }}>⚠️ {error}</p>
        )}
      </div>

      {result && (
        <>
          <div className="hub-card">
            <p style={{ margin: 0 }}>
              {result.scanned_files} fichier(s) PHP analysé(s)
              {result.skipped_files.length > 0 && `, ${result.skipped_files.length} ignoré(s) (illisible ou hors limite)`}.
            </p>
          </div>

          <div className="hub-card hub-settings-section">
            <h2>Relations candidates ({result.join_candidates.length})</h2>
            {result.join_candidates.length === 0 ? (
              <p className="muted">Aucune jointure SQL trouvée dans les fichiers analysés.</p>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>De</th><th>Vers</th><th>Type</th><th>Occurrences</th><th>1er repérage</th><th>Condition brute</th><th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {result.join_candidates.map((c, idx) => (
                    <tr key={idx}>
                      <td>{c.from_table}.{c.from_column}</td>
                      <td>{c.to_table}.{c.to_column}</td>
                      <td>{c.is_self_reference ? "🔀 hiérarchique" : ""}</td>
                      <td>{c.occurrence_count}</td>
                      <td className="muted">{c.source_file}:{c.source_line}</td>
                      <td className="muted">{c.raw_condition}</td>
                      <td>
                        {!connectionId ? (
                          <span className="muted">—</span>
                        ) : sendStatus[idx] === "sent" ? (
                          <span className="muted">✔ envoyée</span>
                        ) : sendStatus[idx]?.error ? (
                          <span style={{ color: "var(--hub-danger, #c0392b)" }} title={sendStatus[idx].error}>⚠️ échec</span>
                        ) : (
                          <button
                            className="secondary"
                            disabled={sendStatus[idx] === "sending"}
                            onClick={() => handleSendToSchemaAnalyzer(c, idx)}
                          >
                            → Envoyer
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          <div className="hub-card hub-settings-section">
            <h2>Tables identifiées (motif Fat-Free Mapper) ({result.mapper_tables.length})</h2>
            {result.mapper_tables.length === 0 ? (
              <p className="muted">Aucune table via ce motif spécifique.</p>
            ) : (
              <ul>
                {result.mapper_tables.map((t) => <li key={t}>{t}</li>)}
              </ul>
            )}
          </div>

          <div className="hub-card hub-settings-section">
            <h2>Structures de champs déduites des vues ({Object.keys(result.template_fields).length})</h2>
            <p className="muted" style={{ marginTop: -8 }}>
              Un nom de variable de gabarit (ex. <code>item</code>, <code>client</code>) avec les champs
              qui lui sont accédés à travers TOUS les écrans analysés -- fusionné, chaque écran ne
              révélant souvent qu'une partie de la structure complète.
            </p>
            {Object.keys(result.template_fields).length === 0 ? (
              <p className="muted">Aucun accès de champ de gabarit trouvé (ni <code>{"{{@var.champ}}"}</code>, ni <code>$var['champ']</code> affiché).</p>
            ) : (
              <table>
                <thead><tr><th>Variable</th><th>Champs</th></tr></thead>
                <tbody>
                  {Object.entries(result.template_fields).map(([root, fields]) => (
                    <tr key={root}>
                      <td>{root}</td>
                      <td>{fields.join(", ")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          <div className="hub-card hub-settings-section">
            <h2>Formulaires trouvés ({result.forms.length})</h2>
            {result.forms.length === 0 ? (
              <p className="muted">Aucun formulaire avec des champs nommés trouvé.</p>
            ) : (
              <table>
                <thead><tr><th>Fichier</th><th>Action</th><th>Champs</th></tr></thead>
                <tbody>
                  {result.forms.map((f, idx) => (
                    <tr key={idx}>
                      <td className="muted">{f.source_file}</td>
                      <td>{f.form_action || "—"}</td>
                      <td>{f.fields.join(", ")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          <div className="hub-card hub-settings-section">
            <h2>Schéma fonctionnel -- écrans et actions ({result.routes.length})</h2>
            <p className="muted" style={{ marginTop: -8 }}>
              Routes Fat-Free déclarées (<code>$f3-&gt;route(...)</code> ou <code>F3::route(...)</code>),
              regroupées par contrôleur -- une vue d'ensemble des écrans/actions de l'application.
              Une closure inline n'est jamais extraite en détail, seulement signalée -- retrouvez son
              code directement au fichier:ligne indiqués.
            </p>
            {result.routes.length === 0 ? (
              <p className="muted">Aucune route trouvée.</p>
            ) : (
              Object.entries(result.routes_by_controller).map(([controller, routes]) => (
                <div key={controller} style={{ marginBottom: 16 }}>
                  <h3 style={{ marginBottom: 4 }}>{controller}</h3>
                  <table>
                    <thead>
                      <tr><th>Méthode(s)</th><th>Chemin</th><th>Action</th><th>Paramètres</th><th>Alias</th><th>1er repérage</th></tr>
                    </thead>
                    <tbody>
                      {routes.map((r, idx) => (
                        <tr key={idx}>
                          <td>{r.methods.join("|")}</td>
                          <td>{r.path}</td>
                          <td>{r.handler_type === "closure" ? "(closure inline)" : r.controller_method}</td>
                          <td className="muted">{r.url_tokens.length > 0 ? r.url_tokens.join(", ") : "—"}</td>
                          <td className="muted">{r.alias || "—"}</td>
                          <td className="muted">{r.source_file}:{r.source_line}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ))
            )}
          </div>
        </>
      )}
    </div>
  );
}
