import React, { useState, useEffect } from "react";
import { fetchStats, fetchServices, fetchEntries } from "./memoryClient.js";

// Tuile "Mémoire" (hub), livraison #259 -- backlog item 32, demandé
// explicitement : "api/service de rémanence du memcached... en faire
// une tuile pas simplement un outil". Rend persistant le tampon de
// logs Memcached (shared/log_buffer.py, volontairement volatile par
// conception) -- collecte périodique, repopulation après un
// redémarrage de Memcached, rétention bornée, et ici la partie
// "interface d'accès et de calcul" demandée : navigation dans
// l'historique + statistiques par service.
//
// ⚠️ Portée SCOPÉE au tampon de logs partagé, jamais un "tout
// Memcached" générique -- voir memory/README.md pour le
// raisonnement complet (Memcached n'offre pas de "lister les clés").

const LEVEL_COLORS = { ERROR: "var(--hub-danger, #c0392b)", WARNING: "var(--warning, #b7791f)" };

export default function MemoryView({ onBack, memoryApiBase }) {
  const [stats, setStats] = useState(null);
  const [services, setServices] = useState([]);
  const [entries, setEntries] = useState(null);
  const [filterService, setFilterService] = useState("");
  const [filterLevel, setFilterLevel] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [memoryApiBase]);

  async function load() {
    setLoading(true);
    const [s, svc] = await Promise.all([fetchStats(memoryApiBase), fetchServices(memoryApiBase)]);
    setStats(s);
    setServices(svc);
    setLoading(false);
  }

  async function applyFilters() {
    setEntries(await fetchEntries(memoryApiBase, { service: filterService || undefined, level: filterLevel || undefined, limit: 200 }));
  }

  return (
    <div className="hub-settings hub-settings-wide">
      <div className="hub-settings-topbar">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h1>🧠 Mémoire</h1>
      </div>

      <div className="hub-card">
        <p className="muted" style={{ margin: 0 }}>
          Le tampon de logs partagé (Memcached) est volontairement volatile -- il repart à zéro à
          chaque redémarrage du conteneur Memcached lui-même. Cet écran conserve un historique
          persistant, collecté périodiquement, et le repeuple automatiquement après un redémarrage.
        </p>
      </div>

      {loading ? (
        <p className="muted">Chargement…</p>
      ) : (
        <>
          <div className="hub-card hub-settings-section">
            <h2>Statistiques par service ({stats ? stats.length : 0})</h2>
            <p className="muted" style={{ marginTop: -8 }}>
              Volume d'entrées persistées, par service et par niveau -- le service le plus bavard en
              premier.
            </p>
            {!stats || stats.length === 0 ? (
              <p className="muted">Aucune entrée persistée pour l'instant -- la collecte tourne
                périodiquement en arrière-plan, laissez-lui le temps d'un premier passage.</p>
            ) : (
              <table>
                <thead><tr><th>Service</th><th>Total</th><th>Détail par niveau</th></tr></thead>
                <tbody>
                  {stats.map((s) => (
                    <tr key={s.service}>
                      <td>{s.service}</td>
                      <td>{s.total}</td>
                      <td>
                        {Object.entries(s.by_level).map(([level, n]) => (
                          <span key={level} style={{ marginRight: 10, color: LEVEL_COLORS[level] || "inherit" }}>
                            {level} : {n}
                          </span>
                        ))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          <div className="hub-card hub-settings-section">
            <h2>Parcourir l'historique</h2>
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 12 }}>
              <div className="hub-settings-row" style={{ margin: 0 }}>
                <label>Service</label>
                <select value={filterService} onChange={(e) => setFilterService(e.target.value)}>
                  <option value="">— tous —</option>
                  {services.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <div className="hub-settings-row" style={{ margin: 0 }}>
                <label>Niveau</label>
                <select value={filterLevel} onChange={(e) => setFilterLevel(e.target.value)}>
                  <option value="">— tous —</option>
                  <option value="ERROR">ERROR</option>
                  <option value="WARNING">WARNING</option>
                  <option value="INFO">INFO</option>
                  <option value="DEBUG">DEBUG</option>
                </select>
              </div>
              <button onClick={applyFilters} style={{ alignSelf: "flex-end" }}>Filtrer</button>
            </div>

            {entries === null ? (
              <p className="muted">Choisissez un filtre puis cliquez "Filtrer" pour parcourir l'historique.</p>
            ) : entries.length === 0 ? (
              <p className="muted">Aucune entrée pour ces filtres.</p>
            ) : (
              <div style={{ maxHeight: 400, overflowY: "auto" }}>
                <table>
                  <thead><tr><th>Horodatage</th><th>Service</th><th>Niveau</th><th>Message</th></tr></thead>
                  <tbody>
                    {entries.map((e) => (
                      <tr key={e.id}>
                        <td className="muted">{new Date(e.entry_timestamp * 1000).toLocaleString("fr-FR")}</td>
                        <td>{e.service}</td>
                        <td style={{ color: LEVEL_COLORS[e.level] || "inherit" }}>{e.level}</td>
                        <td>{e.message}</td>
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
