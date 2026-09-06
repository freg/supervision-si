import React, { useState, useEffect, useRef } from "react";
import {
  importDictionary, fetchTerms, deleteTerm, deleteSource, fetchCategories,
  classifyText, confirmClassification, fetchStats,
} from "./classifierClient.js";

// Tuile "Classification" (hub), livraison #260 -- backlog item 34,
// signalé explicitement "à prioriser fort car central" par la
// personne, après observation de noms d'hôte réels (alice,
// bob, dhcp139, nms, ups-groupe-x...) portant chacun un sens
// différent (personne, client DHCP dynamique, service névralgique,
// équipement).
//
// ⚠️ Dictionnaires IMPORTABLES (demandé explicitement -- "une
// interface d'import de dictionnaires ?"), jamais des listes codées
// en dur -- NLTK non installable/non pertinent ici (vérifié), voir
// classifier/README.md pour le raisonnement complet.

const SUGGESTED_CATEGORIES = ["identite_personnelle", "equipement_infrastructure", "client_dhcp_dynamique"];

export default function ClassifierView({ onBack, classifierApiBase }) {
  const [stats, setStats] = useState(null);
  const [categories, setCategories] = useState([]);
  const [terms, setTerms] = useState([]);
  const [filterCategory, setFilterCategory] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const [importCategory, setImportCategory] = useState("");
  const [importSource, setImportSource] = useState("");
  const fileInputRef = useRef(null);

  const [testText, setTestText] = useState("");
  const [testIp, setTestIp] = useState("");
  const [testResult, setTestResult] = useState(null);
  const [confirmCategory, setConfirmCategory] = useState("");

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [classifierApiBase]);

  async function load() {
    setLoading(true);
    const [s, cats] = await Promise.all([fetchStats(classifierApiBase), fetchCategories(classifierApiBase)]);
    setStats(s);
    setCategories(cats);
    setTerms(await fetchTerms(classifierApiBase, filterCategory || undefined));
    setLoading(false);
  }

  async function handleFilterChange(category) {
    setFilterCategory(category);
    setTerms(await fetchTerms(classifierApiBase, category || undefined));
  }

  async function handleImport(e) {
    e.preventDefault();
    const file = fileInputRef.current?.files?.[0];
    if (!file || !importCategory) return;
    setBusy(true);
    setError(null);
    const result = await importDictionary(classifierApiBase, file, importCategory, importSource);
    if (result.error) setError(result.error);
    else {
      fileInputRef.current.value = "";
      setImportSource("");
      await load();
    }
    setBusy(false);
  }

  async function handleDeleteTerm(id) {
    setBusy(true);
    await deleteTerm(classifierApiBase, id);
    await load();
    setBusy(false);
  }

  async function handleDeleteSource(source) {
    setBusy(true);
    await deleteSource(classifierApiBase, source);
    await load();
    setBusy(false);
  }

  async function handleTest(e) {
    e.preventDefault();
    if (!testText) return;
    const result = await classifyText(classifierApiBase, testText, testIp || undefined);
    setTestResult(result);
    setConfirmCategory(result.category || "");
  }

  async function handleConfirm(addToDictionary) {
    if (!confirmCategory) return;
    setBusy(true);
    await confirmClassification(classifierApiBase, testText, confirmCategory, addToDictionary);
    setBusy(false);
    await load();
    const fresh = await classifyText(classifierApiBase, testText, testIp || undefined);
    setTestResult(fresh);
  }

  return (
    <div className="hub-settings hub-settings-wide">
      <div className="hub-settings-topbar">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h1>🏷️ Classification</h1>
      </div>

      <div className="hub-card">
        <p className="muted" style={{ margin: 0 }}>
          Classe automatiquement des noms d'hôte selon des dictionnaires que vous importez (prénoms,
          vocabulaire réseau/métier...) et un motif structurel pour les clients DHCP dynamiques
          (<code>dhcpNNN</code>). Chaque terme utilisé compte ses propres statistiques d'usage -- vous
          voyez ce qui sert vraiment.
        </p>
      </div>

      {error && (
        <div className="hub-card" style={{ borderColor: "var(--hub-danger, #c0392b)" }}>
          <p style={{ margin: 0 }}>⚠️ {error}</p>
        </div>
      )}

      {loading ? (
        <p className="muted">Chargement…</p>
      ) : (
        <>
          <div className="hub-card hub-settings-section">
            <h2>Importer un dictionnaire</h2>
            <form onSubmit={handleImport} style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "flex-end" }}>
              <div className="hub-settings-row" style={{ margin: 0 }}>
                <label>Fichier (un terme par ligne)</label>
                <input type="file" ref={fileInputRef} accept=".txt,.csv" required />
              </div>
              <div className="hub-settings-row" style={{ margin: 0 }}>
                <label>Catégorie</label>
                <input list="categories-suggestions" value={importCategory} onChange={(e) => setImportCategory(e.target.value)} placeholder="ex. identite_personnelle" required />
                <datalist id="categories-suggestions">
                  {[...new Set([...SUGGESTED_CATEGORIES, ...categories])].map((c) => <option key={c} value={c} />)}
                </datalist>
              </div>
              <div className="hub-settings-row" style={{ margin: 0 }}>
                <label>Nom du dictionnaire (optionnel)</label>
                <input value={importSource} onChange={(e) => setImportSource(e.target.value)} placeholder="par défaut : nom du fichier" />
              </div>
              <button type="submit" disabled={busy}>Importer</button>
            </form>
          </div>

          <div className="hub-card hub-settings-section">
            <h2>Statistiques d'usage</h2>
            <p className="muted" style={{ marginTop: -8 }}>
              Quels termes servent vraiment sur vos données réelles.
            </p>
            {!stats || stats.by_category.length === 0 ? (
              <p className="muted">Aucun dictionnaire importé pour l'instant.</p>
            ) : (
              <table>
                <thead><tr><th>Catégorie</th><th>Termes</th><th>Correspondances</th><th>Jamais utilisés</th></tr></thead>
                <tbody>
                  {stats.by_category.map((c) => (
                    <tr key={c.category}>
                      <td>{c.category}</td>
                      <td>{c.total_terms}</td>
                      <td>{c.total_matches || 0}</td>
                      <td className="muted">{c.unused_terms}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          <div className="hub-card hub-settings-section">
            <h2>Tester une classification</h2>
            <form onSubmit={handleTest} style={{ display: "flex", gap: 8, marginBottom: 12 }}>
              <input value={testText} onChange={(e) => setTestText(e.target.value)} placeholder="ex. alice.intranet" style={{ flex: 1 }} required />
              <input value={testIp} onChange={(e) => setTestIp(e.target.value)} placeholder="IP (optionnel)" style={{ width: 160 }} />
              <button type="submit">Classifier</button>
            </form>
            {testResult && (
              <div className="hub-card">
                {testResult.category ? (
                  <p style={{ margin: 0 }}>
                    Catégorie : <strong>{testResult.category}</strong> ({testResult.reason})
                  </p>
                ) : (
                  <p className="muted" style={{ margin: 0 }}>Aucune correspondance trouvée.</p>
                )}
                <div style={{ display: "flex", gap: 8, marginTop: 8, alignItems: "center" }}>
                  <label className="muted">Orienter :</label>
                  <input list="categories-suggestions" value={confirmCategory} onChange={(e) => setConfirmCategory(e.target.value)} placeholder="catégorie correcte" style={{ width: 220 }} />
                  <button className="secondary" disabled={busy} onClick={() => handleConfirm(false)}>Confirmer</button>
                  <button className="secondary" disabled={busy} onClick={() => handleConfirm(true)}>Confirmer + ajouter au dictionnaire</button>
                </div>
              </div>
            )}
          </div>

          <div className="hub-card hub-settings-section">
            <h2>Dictionnaires ({terms.length})</h2>
            <div className="hub-settings-row">
              <label>Filtrer par catégorie</label>
              <select value={filterCategory} onChange={(e) => handleFilterChange(e.target.value)}>
                <option value="">— toutes —</option>
                {categories.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            {terms.length === 0 ? (
              <p className="muted">Aucun terme pour ce filtre.</p>
            ) : (
              <div style={{ maxHeight: 320, overflowY: "auto" }}>
                <table>
                  <thead><tr><th>Terme</th><th>Catégorie</th><th>Source</th><th>Usages</th><th></th></tr></thead>
                  <tbody>
                    {terms.map((t) => (
                      <tr key={t.id}>
                        <td>{t.term}</td>
                        <td className="muted">{t.category}</td>
                        <td className="muted">
                          {t.source}{" "}
                          <button className="secondary" onClick={() => handleDeleteSource(t.source)} title="Retirer tout ce dictionnaire">🗑 tout</button>
                        </td>
                        <td>{t.match_count}</td>
                        <td><button className="secondary" onClick={() => handleDeleteTerm(t.id)}>🗑</button></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
