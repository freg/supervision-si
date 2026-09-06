import React, { useState, useEffect, useRef, useMemo } from "react";
import { LOG_SERVICES, mergeLogEntries, summarizeLogEntries } from "./logsLib.js";
import { fetchServiceLogs, fetchAllServiceLogs, fetchPushedSources } from "./logsClient.js";
import { logPresenceTransitions } from "./hubLogClient.js";

// Gestionnaire de logs (hub), livraison #139 -- demandé explicitement
// ("un excellent moyen pour optimiser en déploiement et en
// fonctionnement"), avec les 3 présentations validées par la
// personne : tableau de bord, par service, vue combinée -- simples
// sous-onglets d'un même écran (même motif que HistoryView), pas
// trois écrans séparés. "Tableau de bord" et "vue combinée"
// partagent la MÊME requête réseau (les 15 services) -- jamais deux
// sondages séparés pour la même donnée sous-jacente.

const LIMIT = 200;
const POLL_INTERVAL_MS = 15000;
// Sondage des sources externes CONNUES -- séparé du contenu lui-même
// (juste la LISTE), cadence plus lente : une nouvelle source pousse
// rarement, pas la peine de la découvrir aussi souvent que le
// contenu des logs eux-mêmes.
const SOURCES_POLL_INTERVAL_MS = 30000;

function formatTimestamp(ts) {
  if (typeof ts !== "number") return "—";
  return new Date(ts * 1000).toLocaleString("fr-FR");
}

function levelClass(level) {
  if (level === "ERROR" || level === "CRITICAL") return "log-level-error";
  if (level === "WARNING") return "log-level-warning";
  return "";
}

export default function LogsManagerView({ onBack, prefsApiBase }) {
  const [subTab, setSubTab] = useState("dashboard");
  const [selectedService, setSelectedService] = useState(LOG_SERVICES[0].id);
  const [singleEntries, setSingleEntries] = useState(undefined);
  const [allResults, setAllResults] = useState(undefined);
  const [loading, setLoading] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null);
  // Journalisation des transitions (livraison #141) -- même principe
  // que App.jsx pour les indicateurs de présence : un ref (jamais un
  // second useState), lu de façon SYNCHRONE dans load() pour
  // comparer au sondage précédent. DEUX refs séparés (pas un seul
  // partagé) -- "par service" ne suit qu'UN service à la fois,
  // "tableau de bord"/"vue combinée" en suivent 15 : les partager
  // aurait fait perdre le suivi des 14 autres à chaque changement
  // d'onglet (le ref se serait retrouvé écrasé avec une seule clé).
  const reachabilityRef = useRef(undefined);
  const singleReachabilityRef = useRef(undefined);

  // Sources externes poussées (livraison #142) -- découvertes à
  // l'exécution (POST /push-log), jamais une liste fixe comme
  // LOG_SERVICES. Sondée séparément du CONTENU des logs (cadence
  // plus lente, voir SOURCES_POLL_INTERVAL_MS) -- juste pour savoir
  // QUELLES sources existent, pas ce qu'elles contiennent.
  const [pushedSourceNames, setPushedSourceNames] = useState([]);
  useEffect(() => {
    let cancelled = false;
    async function loadSources() {
      const sources = await fetchPushedSources(prefsApiBase);
      if (!cancelled && Array.isArray(sources)) setPushedSourceNames(sources);
    }
    loadSources();
    const interval = setInterval(loadSources, SOURCES_POLL_INTERVAL_MS);
    return () => { cancelled = true; clearInterval(interval); };
  }, [prefsApiBase]);

  // Liste COMBINÉE (15 fixes + sources externes découvertes) --
  // utilisée PARTOUT à la place de LOG_SERVICES seul (menu déroulant,
  // fusion, résumé, sondage). `id` préfixé "push:" -- distinct des 15
  // id fixes, jamais de collision possible même si une source externe
  // portait par malheur le même nom qu'un service interne (ex.
  // quelqu'un pousserait sous le nom "tickets"). `path` construit
  // depuis le nom RÉEL de la source (encodeURIComponent, jamais le id
  // préfixé -- une distinction à ne pas perdre : le id est un
  // identifiant INTERNE React, le nom de source est ce que l'API
  // attend réellement dans l'URL).
  const allServices = useMemo(() => [
    ...LOG_SERVICES,
    ...pushedSourceNames.map((name) => ({
      id: `push:${name}`,
      label: `${name} (externe)`,
      path: `${prefsApiBase}/push-log/${encodeURIComponent(name)}`,
    })),
  ], [pushedSourceNames, prefsApiBase]);

  const serviceLabels = useMemo(
    () => Object.fromEntries(allServices.map((s) => [s.id, s.label])),
    [allServices]
  );

  // Vue "par service" -- rechargée à chaque changement de service
  // sélectionné, et périodiquement tant que cet onglet est actif.
  useEffect(() => {
    if (subTab !== "single") return;
    let cancelled = false;
    async function load() {
      setLoading(true);
      const svc = allServices.find((s) => s.id === selectedService);
      const entries = svc ? await fetchServiceLogs(svc.path, LIMIT) : undefined;
      if (!cancelled) {
        if (svc) {
          const reachability = { [svc.id]: Array.isArray(entries) };
          logPresenceTransitions(prefsApiBase, singleReachabilityRef.current, reachability, serviceLabels);
          singleReachabilityRef.current = reachability;
        }
        setSingleEntries(entries);
        setLoading(false);
        setLastUpdated(new Date());
      }
    }
    load();
    const interval = setInterval(load, POLL_INTERVAL_MS);
    return () => { cancelled = true; clearInterval(interval); };
  }, [subTab, selectedService, allServices, prefsApiBase]);

  useEffect(() => {
    if (subTab !== "dashboard" && subTab !== "combined") return;
    let cancelled = false;
    async function load() {
      setLoading(true);
      const results = await fetchAllServiceLogs(allServices, LIMIT);
      if (!cancelled) {
        const reachability = {};
        allServices.forEach((s) => { reachability[s.id] = Array.isArray(results[s.id]); });
        logPresenceTransitions(prefsApiBase, reachabilityRef.current, reachability, serviceLabels);
        reachabilityRef.current = reachability;
        setAllResults(results);
        setLoading(false);
        setLastUpdated(new Date());
      }
    }
    load();
    const interval = setInterval(load, POLL_INTERVAL_MS);
    return () => { cancelled = true; clearInterval(interval); };
  }, [subTab, allServices, prefsApiBase]);

  const summary = allResults ? summarizeLogEntries(allResults, allServices) : null;
  const combined = allResults ? mergeLogEntries(allResults, allServices) : null;

  return (
    <div className="hub-settings hub-settings-wide">
      <div className="hub-settings-topbar">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h1>📋 Gestionnaire de logs</h1>
        {lastUpdated && (
          <span className="muted logs-last-updated">
            Actualisé à {lastUpdated.toLocaleTimeString("fr-FR")}{loading ? " · actualisation…" : ""}
          </span>
        )}
      </div>

      <div className="tabs" style={{ marginBottom: 16 }}>
        <button className={subTab === "dashboard" ? "active" : ""} onClick={() => setSubTab("dashboard")}>
          Tableau de bord
        </button>
        <button className={subTab === "single" ? "active" : ""} onClick={() => setSubTab("single")}>
          Par service
        </button>
        <button className={subTab === "combined" ? "active" : ""} onClick={() => setSubTab("combined")}>
          Vue combinée
        </button>
      </div>

      {subTab === "dashboard" && (
        <div className="hub-card hub-settings-section">
          {!summary && <p className="muted">Chargement…</p>}
          {summary && (
            <>
              <p className="muted" style={{ marginTop: 0, fontSize: 13 }}>
                Warnings/erreurs comptés à partir du seuil WARNING seulement -- un service à 0 sur les
                deux colonnes n'a simplement rien signalé récemment, ce n'est pas un chargement en cours
                ni un problème.
              </p>
              <table className="logs-dashboard-table">
              <thead>
                <tr>
                  <th>Service</th>
                  <th>État</th>
                  <th>Warnings</th>
                  <th>Erreurs</th>
                  <th>Dernière entrée</th>
                </tr>
              </thead>
              <tbody>
                {summary.map((s) => {
                  const warnCount = s.counts.WARNING || 0;
                  const errCount = (s.counts.ERROR || 0) + (s.counts.CRITICAL || 0);
                  // Doute réel remonté par la personne ("les logs sont
                  // verts et à 0 alors qu'il y a des logs") -- ce
                  // tableau ne compte QUE les événements ≥ WARNING
                  // (LOG_CAPTURE_LEVEL=WARNING, #145) -- un service
                  // sans souci récent affiche donc légitimement 0/0,
                  // vert -- CORRECT, mais visuellement indiscernable
                  // d'un chargement ou d'un problème au premier coup
                  // d'œil. Rendu EXPLICITE ici plutôt que silencieux.
                  const trulyQuiet = s.reachable && warnCount === 0 && errCount === 0;
                  return (
                    <tr
                      key={s.id}
                      className="logs-dashboard-row"
                      onClick={() => { setSelectedService(s.id); setSubTab("single"); }}
                      title="Cliquer pour voir le détail de ce service"
                    >
                      <td>{s.label}</td>
                      <td>
                        {s.reachable
                          ? <span className="presence-up">● joignable</span>
                          : <span className="presence-down">● injoignable</span>}
                        {trulyQuiet && (
                          <span className="muted" style={{ display: "block", fontSize: 11 }}>
                            aucun événement ≥ warning récemment
                          </span>
                        )}
                      </td>
                      <td>{s.reachable ? warnCount : "—"}</td>
                      <td className={errCount > 0 ? "log-level-error" : ""}>{s.reachable ? errCount : "—"}</td>
                      <td className="muted">{formatTimestamp(s.mostRecent)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            </>
          )}
        </div>
      )}

      {subTab === "single" && (
        <div className="hub-card hub-settings-section">
          <div className="hub-settings-row">
            <label>Service</label>
            <select value={selectedService} onChange={(e) => setSelectedService(e.target.value)}>
              {allServices.map((s) => (
                <option key={s.id} value={s.id}>{s.label}</option>
              ))}
            </select>
          </div>
          {/* undefined + loading = premier chargement en cours ;
              undefined + pas loading = service réellement injoignable
              (distinction utile, jamais confondues). */}
          {singleEntries === undefined && loading && (
            <p className="muted" style={{ marginTop: 12 }}>Chargement…</p>
          )}
          {singleEntries === undefined && !loading && (
            <p className="hub-error" style={{ marginTop: 12 }}>Service injoignable (voir le tableau de bord pour l'ensemble).</p>
          )}
          {Array.isArray(singleEntries) && singleEntries.length === 0 && (
            <p className="muted" style={{ marginTop: 12 }}>Aucune entrée (rien au-delà du seuil WARNING récemment).</p>
          )}
          {Array.isArray(singleEntries) && singleEntries.length > 0 && (
            <table className="logs-entries-table">
              <thead>
                <tr><th>Horodatage</th><th>Niveau</th><th>Message</th></tr>
              </thead>
              <tbody>
                {/* Le tampon serveur est du plus ancien au plus récent
                    (ordre d'insertion) -- inversé ici pour un affichage
                    plus récent en premier, cohérent avec la vue
                    combinée (mergeLogEntries, logsLib.js). */}
                {[...singleEntries].reverse().map((e, i) => (
                  <tr key={i}>
                    <td className="muted">{formatTimestamp(e.timestamp)}</td>
                    <td className={levelClass(e.level)}>{e.level}</td>
                    <td>{e.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {subTab === "combined" && (
        <div className="hub-card hub-settings-section">
          {!combined && <p className="muted">Chargement…</p>}
          {combined && combined.length === 0 && (
            <p className="muted">Aucune entrée récente, tous services confondus.</p>
          )}
          {combined && combined.length > 0 && (
            <table className="logs-entries-table">
              <thead>
                <tr><th>Horodatage</th><th>Service</th><th>Niveau</th><th>Message</th></tr>
              </thead>
              <tbody>
                {combined.map((e, i) => (
                  <tr key={i}>
                    <td className="muted">{formatTimestamp(e.timestamp)}</td>
                    <td>{e.serviceLabel}</td>
                    <td className={levelClass(e.level)}>{e.level}</td>
                    <td>{e.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
