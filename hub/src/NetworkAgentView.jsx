import React, { useState, useEffect } from "react";
import {
  fetchCaptureStatus, fetchSites, fetchDevices, fetchDeviceServices,
  fetchAllServices, fetchLinks, fetchPresenceHistory, fetchObservedSubnets,
  fetchFilterOptions, fetchDevicesForPeriod, fetchLinkHistory,
} from "./networkAgentClient.js";
import { formatBytes, computeDeltaSeries, buildBarLayout, sumDeltas } from "./networkAgentHistory.js";
import { classifyBatch } from "./classifierClient.js";
import AlluvialFlowChart from "./components/AlluvialFlowChart.jsx";
import WeightedRadialTree from "./components/WeightedRadialTree.jsx";

// Tuile UNIQUE de l'agent d'exploration réseau (hub), livraison #233
// -- backlog item 20, CLARIFIÉ explicitement avec la personne avant
// de coder : "un seul agent... une seule tuile même si on
// distinguera les sites et les réseaux dans l'organisation des
// données". D'où la structure ici : sélection site -> segment (les
// données), mais UN SEUL écran, jamais plusieurs tuiles séparées.
//
// Ergonomie/fonctionnalités livraison #250, demandées explicitement
// par la personne après un premier usage réel : en-têtes de colonnes
// fixes au défilement (voir .na-device-list-wrap, hub.css), services
// en petits points colorés avec le nom au survol, détails d'un
// appareil (services + échanges) en pied de page fixe plutôt qu'un
// panneau qui décale la mise en page, résolution DNS affichée,
// détection des échanges entre appareils ("qui parle à qui").
//
// ⚠️ Capture confirmée fonctionnelle en déploiement réel (#240) --
// voir network-agent/README.md pour le détail complet.

const ROLE_ICONS = { "passerelle probable (NAT/routeur)": "🔀" };
// Limite d'affichage des points de service par ligne (livraison
// #257) -- au-delà, résumé par un compteur "+N" plutôt qu'un mur de
// points illisible (capture d'écran réelle : plus de 200 points sur
// une seule ligne pour un appareil très actif, probablement une
// passerelle relayant un trafic très divers -- voir capture.py).
const MAX_VISIBLE_SERVICE_DOTS = 15;

// Barres de delta entre relevés cumulatifs -- SVG maison, aucune
// bibliothèque (même approche que AlluvialFlowChart/WeightedRadialTree,
// #389). Lève la limite notée dans network-agent/README.md ("pas de
// graphique -- tableau simple, faute de bibliothèque côté hub").
// Une barre par intervalle entre deux relevés ; le premier relevé n'a pas
// de barre (aucune base de comparaison). Un recul du compteur (redémarrage
// de capture) est dessiné en couleur d'avertissement, jamais lissé.
const HISTORY_BARS_W = 320;
const HISTORY_BARS_H = 48;

function HistoryBars({ rows, label }) {
  const series = computeDeltaSeries(rows);
  if (series.length < 2) {
    return (
      <p className="muted na-history-empty">
        {series.length === 0 ? "Aucun relevé." : "Un seul relevé -- un deuxième est nécessaire pour un premier delta."}
      </p>
    );
  }
  const { bars, max } = buildBarLayout(series, HISTORY_BARS_W, HISTORY_BARS_H);
  const total = sumDeltas(series);
  const resets = series.filter((p) => p.reset).length;
  return (
    <div className="na-history-bars">
      <svg
        viewBox={`0 0 ${HISTORY_BARS_W} ${HISTORY_BARS_H}`}
        preserveAspectRatio="none"
        className="na-history-svg"
        role="img"
        aria-label={label || "Volume échangé par intervalle"}
      >
        <line x1="0" y1={HISTORY_BARS_H - 0.5} x2={HISTORY_BARS_W} y2={HISTORY_BARS_H - 0.5} className="na-history-axis" />
        {bars.map((b) => (
          <rect
            key={b.index}
            x={b.x} y={b.y} width={b.w} height={b.h}
            className={`na-history-bar${b.reset ? " reset" : ""}`}
          >
            <title>
              {new Date(b.at).toLocaleString("fr-FR")}
              {"\n"}+{formatBytes(b.delta)} sur l'intervalle · cumul {formatBytes(b.cumulative)}
              {b.reset ? "\n⚠ compteur remis à zéro (redémarrage de capture ?)" : ""}
            </title>
          </rect>
        ))}
      </svg>
      <div className="na-history-caption muted">
        {series.length} relevés · {formatBytes(total)} échangés · pic {formatBytes(max)} / intervalle
        {resets > 0 && <span className="na-history-reset-note"> · ⚠ {resets} remise(s) à zéro</span>}
      </div>
    </div>
  );
}

export default function NetworkAgentView({ onBack, networkAgentApiBase, classifierApiBase }) {
  const [status, setStatus] = useState(null);
  const [sites, setSites] = useState([]);
  const [selectedSegment, setSelectedSegment] = useState(null);
  const [devices, setDevices] = useState([]);
  const [allServices, setAllServices] = useState({});
  const [links, setLinks] = useState([]);
  const [observedSubnets, setObservedSubnets] = useState([]);
  const [subnetPrefixLength, setSubnetPrefixLength] = useState(24);
  const [showSubnets, setShowSubnets] = useState(false);
  const [showFlowVisualizations, setShowFlowVisualizations] = useState(false);
  // Filtres profondeur/géographie/volume (livraison #392, backlog
  // item 58) -- options peuplées depuis les valeurs RÉELLEMENT
  // présentes (fetchFilterOptions), jamais une liste devinée.
  const [filterOptions, setFilterOptions] = useState({ depths: [], buildings: [], rooms: [], zones: [] });
  const [selectedDepths, setSelectedDepths] = useState([]);
  const [selectedBuilding, setSelectedBuilding] = useState("");
  const [selectedZone, setSelectedZone] = useState("");
  const [minVolumeKo, setMinVolumeKo] = useState("");
  // Filtre "période temporelle" (livraison #394, dernier des 4
  // filtres demandés) -- vide = comportement inchangé (état actuel
  // cumulatif). Les deux dates DOIVENT être renseignées ensemble
  // pour activer ce mode -- une seule ne suffit pas à définir une
  // période.
  const [periodStart, setPeriodStart] = useState("");
  const [periodEnd, setPeriodEnd] = useState("");
  const [classifications, setClassifications] = useState({});
  const [loading, setLoading] = useState(true);
  const [activeDevice, setActiveDevice] = useState(null);
  const [activeDeviceServices, setActiveDeviceServices] = useState(null);
  const [activeDeviceHistory, setActiveDeviceHistory] = useState(null);
  // Historique du volume d'UNE paire (clic sur une ligne "Échanges") --
  // `/links/history` existait côté API depuis #251 sans jamais être
  // affiché côté hub (noté "reste à faire" dans network-agent/README.md).
  const [activeLink, setActiveLink] = useState(null);
  const [activeLinkHistory, setActiveLinkHistory] = useState(null);

  useEffect(() => {
    Promise.all([fetchCaptureStatus(networkAgentApiBase), fetchSites(networkAgentApiBase)]).then(([s, sitesList]) => {
      setStatus(s);
      setSites(sitesList);
      setLoading(false);
      const firstSegment = sitesList[0]?.segments?.[0];
      if (firstSegment) setSelectedSegment(firstSegment);
    });
  }, [networkAgentApiBase]);

  useEffect(() => {
    if (selectedSegment) {
      setActiveDevice(null);
      setClassifications({});
      // Filtres réinitialisés au changement de segment -- un
      // "Bâtiment B" choisi sur un autre segment n'aurait aucun sens
      // ici, jamais conservé implicitement.
      setSelectedDepths([]);
      setSelectedBuilding("");
      setSelectedZone("");
      setMinVolumeKo("");
      setPeriodStart("");
      setPeriodEnd("");
      fetchFilterOptions(networkAgentApiBase, selectedSegment.id).then(setFilterOptions);
      loadDevicesAndClassify();
      fetchAllServices(networkAgentApiBase, selectedSegment.id).then(setAllServices);
      fetchLinks(networkAgentApiBase, selectedSegment.id).then(setLinks);
      if (showSubnets) loadSubnets();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedSegment, networkAgentApiBase]);

  // Rechargement des appareils SEUL quand un filtre change --
  // séparé de l'effet ci-dessus pour ne jamais re-fetch links/services/
  // options à chaque ajustement de filtre, seulement les appareils.
  useEffect(() => {
    if (selectedSegment) loadDevicesAndClassify();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedDepths, selectedBuilding, selectedZone, minVolumeKo, periodStart, periodEnd]);

  async function loadDevicesAndClassify() {
    const hasPeriod = periodStart && periodEnd;
    let deviceList;
    if (hasPeriod) {
      // Les champs <input type="date"> renvoient "YYYY-MM-DD" (sans
      // heure) -- converti en ISO 8601 complet AVANT l'appel, sinon
      // une comparaison de CHAÎNES côté serveur (snapshot_at <= "YYYY-MM-DD")
      // décalerait la borne d'un jour (une date sans heure est
      // TOUJOURS "inférieure" à une même date AVEC heure, en
      // comparaison lexicographique). Minuit pour le début, fin de
      // journée pour la fin -- borne INCLUSIVE du jour choisi.
      const startIso = `${periodStart}T00:00:00Z`;
      const endIso = `${periodEnd}T23:59:59Z`;
      // Livraison #394 -- /devices/for-period ne connaît PAS encore
      // les filtres profondeur/bâtiment/zone/volume (nature de
      // requête différente, voir store.list_devices_for_period) --
      // appliqués ici CÔTÉ CLIENT sur le résultat, chaque appareil
      // renvoyé portant déjà ses attributs statiques (depth/building/
      // zone) en plus de `bytes_total_period`.
      const raw = await fetchDevicesForPeriod(networkAgentApiBase, selectedSegment.id, startIso, endIso);
      const minBytes = minVolumeKo ? Number(minVolumeKo) * 1024 : 0;
      deviceList = raw.filter((d) => {
        if (selectedDepths.length > 0 && !selectedDepths.includes(d.network_depth)) return false;
        if (selectedBuilding && d.building !== selectedBuilding) return false;
        if (selectedZone && d.zone !== selectedZone) return false;
        if (d.bytes_total_period < minBytes) return false;
        return true;
      });
    } else {
      const minBytesTotal = minVolumeKo ? Number(minVolumeKo) * 1024 : undefined;
      deviceList = await fetchDevices(networkAgentApiBase, selectedSegment.id, {
        depths: selectedDepths, building: selectedBuilding || undefined,
        zone: selectedZone || undefined, minBytesTotal,
      });
    }
    setDevices(deviceList);
    // Classification (livraison #261) -- best-effort explicite,
    // classifier-api indisponible/non configuré ne doit JAMAIS
    // empêcher l'affichage des appareils eux-mêmes (voir
    // classifierClient.classifyBatch, renvoie {} proprement sur
    // échec). Seuls les appareils AVEC un nom d'hôte résolu ont
    // quelque chose à classifier.
    if (!classifierApiBase) return;
    const withHostname = deviceList.filter((d) => d.hostname);
    if (withHostname.length === 0) return;
    const items = withHostname.map((d) => ({ text: d.hostname, ip_address: d.ip_address }));
    setClassifications(await classifyBatch(classifierApiBase, items));
  }

  async function loadSubnets(prefixLength) {
    if (!selectedSegment) return;
    const p = prefixLength || subnetPrefixLength;
    setObservedSubnets(await fetchObservedSubnets(networkAgentApiBase, selectedSegment.id, p));
  }

  function toggleShowSubnets() {
    setShowSubnets((v) => {
      const next = !v;
      if (next) loadSubnets();
      return next;
    });
  }

  async function handleSelectDevice(device) {
    setActiveLink(null);
    setActiveLinkHistory(null);
    if (activeDevice?.id === device.id) {
      setActiveDevice(null);
      setActiveDeviceHistory(null);
      return;
    }
    setActiveDevice(device);
    setActiveDeviceServices(null);
    setActiveDeviceHistory(null);
    setActiveDeviceServices(await fetchDeviceServices(networkAgentApiBase, device.id));
    setActiveDeviceHistory(await fetchPresenceHistory(networkAgentApiBase, device.id));
  }

  async function handleSelectLink(link) {
    if (activeLink?.id === link.id) {
      setActiveLink(null);
      setActiveLinkHistory(null);
      return;
    }
    setActiveLink(link);
    setActiveLinkHistory(null);
    const rows = await fetchLinkHistory(networkAgentApiBase, link.device_a_id, link.device_b_id);
    // Garde contre une réponse arrivée après un autre clic entre-temps.
    setActiveLink((cur) => {
      if (cur?.id === link.id) setActiveLinkHistory(rows);
      return cur;
    });
  }

  const macToDevice = Object.fromEntries(devices.map((d) => [d.id, d]));
  const deviceLinks = activeDevice
    ? links.filter((l) => l.device_a_id === activeDevice.id || l.device_b_id === activeDevice.id)
    : [];

  return (
    <div className="hub-settings hub-settings-wide">
      <div className="hub-settings-topbar">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h1>🕸️ Exploration réseau</h1>
      </div>

      {status && (
        <div className="hub-card">
          {status.error ? (
            <p style={{ margin: 0, color: "var(--danger)" }}>
              ⚠️ Impossible de joindre network-agent-api : {status.error}
            </p>
          ) : (
            <p style={{ margin: 0 }}>
              Capture : {status.running ? "🟢 en cours" : "⚪ arrêtée"}
              {status.started_at && ` (depuis ${new Date(status.started_at).toLocaleString("fr-FR")})`}
              {" — "}{status.packets_processed ?? 0} paquet(s) traité(s) au total.
              {status.last_error && <><br /><span style={{ color: "var(--danger)" }}>⚠️ {status.last_error}</span></>}
            </p>
          )}
        </div>
      )}

      {loading ? (
        <p className="muted">Chargement…</p>
      ) : sites.length === 0 ? (
        <div className="hub-card">
          <p className="muted" style={{ margin: 0 }}>
            Aucune donnée pour l'instant -- la capture n'a probablement pas encore démarré (voir le
            statut ci-dessus) ou vient tout juste de commencer. Les appareils apparaîtront ici
            progressivement, au fil du trafic observé.
          </p>
        </div>
      ) : (
        <div className="hub-card hub-settings-section">
          <div className="hub-settings-row">
            <label>Site / segment</label>
            <select
              value={selectedSegment ? `${selectedSegment.id}` : ""}
              onChange={(e) => {
                const seg = sites.flatMap((s) => s.segments).find((sg) => `${sg.id}` === e.target.value);
                setSelectedSegment(seg);
              }}
            >
              {sites.map((site) => (
                <optgroup key={site.id} label={site.name}>
                  {site.segments.map((seg) => (
                    <option key={seg.id} value={seg.id}>{seg.label}{seg.cidr ? ` (${seg.cidr})` : ""}</option>
                  ))}
                </optgroup>
              ))}
            </select>
          </div>

          {(filterOptions.depths.length > 0 || filterOptions.buildings.length > 0) && (
            <div className="hub-settings-row" style={{ flexWrap: "wrap", gap: "8px 16px" }}>
              {filterOptions.depths.length > 0 && (
                <div>
                  <label style={{ marginRight: 6 }}>Profondeur</label>
                  {filterOptions.depths.map((d) => (
                    <label key={d} style={{ marginRight: 8, fontWeight: "normal" }}>
                      <input
                        type="checkbox"
                        checked={selectedDepths.includes(d)}
                        onChange={(e) => {
                          setSelectedDepths((prev) =>
                            e.target.checked ? [...prev, d] : prev.filter((x) => x !== d)
                          );
                        }}
                      />{" "}
                      {d}
                    </label>
                  ))}
                </div>
              )}
              {filterOptions.buildings.length > 0 && (
                <div>
                  <label style={{ marginRight: 6 }}>Bâtiment</label>
                  <select value={selectedBuilding} onChange={(e) => setSelectedBuilding(e.target.value)}>
                    <option value="">Tous</option>
                    {filterOptions.buildings.map((b) => (
                      <option key={b} value={b}>{b}</option>
                    ))}
                  </select>
                </div>
              )}
              {filterOptions.zones.length > 0 && (
                <div>
                  <label style={{ marginRight: 6 }}>Zone</label>
                  <select value={selectedZone} onChange={(e) => setSelectedZone(e.target.value)}>
                    <option value="">Toutes</option>
                    {filterOptions.zones.map((z) => (
                      <option key={z} value={z}>{z}</option>
                    ))}
                  </select>
                </div>
              )}
              <div>
                <label style={{ marginRight: 6 }}>Volume min. (Ko)</label>
                <input
                  type="number"
                  min="0"
                  value={minVolumeKo}
                  onChange={(e) => setMinVolumeKo(e.target.value)}
                  style={{ width: 80 }}
                  placeholder="0"
                />
              </div>
              <div>
                <label style={{ marginRight: 6 }}>Période</label>
                <input
                  type="date"
                  value={periodStart}
                  onChange={(e) => setPeriodStart(e.target.value)}
                  title="Début de période -- les deux dates doivent être renseignées pour activer ce filtre"
                />
                {" → "}
                <input
                  type="date"
                  value={periodEnd}
                  onChange={(e) => setPeriodEnd(e.target.value)}
                  title="Fin de période -- les deux dates doivent être renseignées pour activer ce filtre"
                />
              </div>
              {(selectedDepths.length > 0 || selectedBuilding || selectedZone || minVolumeKo) && (
                <button
                  className="secondary"
                  onClick={() => { setSelectedDepths([]); setSelectedBuilding(""); setSelectedZone(""); setMinVolumeKo(""); setPeriodStart(""); setPeriodEnd(""); }}
                >
                  ✕ Réinitialiser les filtres
                </button>
              )}
            </div>
          )}

          <button className="secondary" onClick={toggleShowSubnets} style={{ marginBottom: 12 }}>
            {showSubnets ? "▾" : "▸"} Sous-réseaux découverts depuis le trafic
          </button>
          {showSubnets && (
            <div style={{ marginBottom: 16, borderBottom: "1px solid var(--border)", paddingBottom: 12 }}>
              <p className="muted" style={{ marginTop: 0 }}>
                Regroupe les appareils déjà découverts par préfixe réseau -- répond directement à
                "combien de segments distincts faut-il couvrir", à partir du trafic RÉEL plutôt que
                d'un recensement préalable. Configurez <code>NETWORK_AGENT_SEGMENT_CIDR</code> sur le
                supernet le plus large pertinent (ex. un /16) pour voir apparaître sa structure interne
                réelle (les /24 effectivement en usage).
              </p>
              <div className="hub-settings-row">
                <label>Granularité</label>
                <select value={subnetPrefixLength} onChange={(e) => { const p = Number(e.target.value); setSubnetPrefixLength(p); loadSubnets(p); }}>
                  <option value={16}>/16</option>
                  <option value={20}>/20</option>
                  <option value={24}>/24</option>
                  <option value={28}>/28</option>
                </select>
              </div>
              {observedSubnets.length === 0 ? (
                <p className="muted">Aucun sous-réseau observé pour l'instant.</p>
              ) : (
                <table>
                  <thead><tr><th>Sous-réseau</th><th>Appareils</th><th>Vu la 1ère fois</th><th>Vu la dernière fois</th></tr></thead>
                  <tbody>
                    {observedSubnets.map((s) => (
                      <tr key={s.subnet}>
                        <td>{s.subnet}</td>
                        <td>{s.device_count}</td>
                        <td className="muted">{new Date(s.first_seen).toLocaleString("fr-FR")}</td>
                        <td className="muted">{new Date(s.last_seen).toLocaleString("fr-FR")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}

          <button className="secondary" onClick={() => setShowFlowVisualizations((v) => !v)} style={{ marginBottom: 12 }}>
            {showFlowVisualizations ? "▾" : "▸"} Visualisations des flux (livraison #389)
          </button>
          {showFlowVisualizations && (
            <div style={{ marginBottom: 16, borderBottom: "1px solid var(--border)", paddingBottom: 12 }}>
              <p className="muted" style={{ marginTop: 0 }}>
                À partir des mêmes échanges affichés ci-dessous ("qui parle à qui") -- backlog item 58,
                démarré avec netmap-orchestrator (#388). Deux premières vues, d'autres suivront ("cycle
                permanent de retour" sur ce sujet).
              </p>
              {links.length === 0 ? (
                <p className="muted">Aucun échange détecté pour l'instant sur ce segment.</p>
              ) : (
                <>
                  <h3 style={{ marginBottom: 4 }}>Graphe alluvial (flux TCP/IP/UDP)</h3>
                  <AlluvialFlowChart
                    links={links}
                    deviceLabels={Object.fromEntries(devices.map((d) => [d.id, d.hostname || d.ip_address || d.mac_address || `#${d.id}`]))}
                  />
                  <h3 style={{ marginTop: 20, marginBottom: 4 }}>Radial tree augmenté (épaisseur = volume échangé)</h3>
                  <WeightedRadialTree
                    devices={devices}
                    links={links}
                    segmentLabels={Object.fromEntries(sites.flatMap((s) => s.segments).map((seg) => [seg.id, seg.label]))}
                  />
                </>
              )}
            </div>
          )}

          <h2>Appareils découverts ({devices.length})</h2>
          <p className="muted" style={{ marginTop: -8 }}>
            Cliquez une ligne pour voir ses services et échanges en détail, ci-dessous. Survolez un
            point coloré pour voir le service concerné.
          </p>

          <div className="na-device-list-wrap">
            <table>
              <thead>
                <tr>
                  <th>MAC</th><th>Dernière IP</th><th>Nom d'hôte</th><th>Rôle</th>
                  <th>Vu la 1ère fois</th><th>Vu la dernière fois</th><th>{periodStart && periodEnd ? "Volume (période)" : "Volume"}</th><th>Services</th>
                </tr>
              </thead>
              <tbody>
                {devices.map((d) => (
                  <tr
                    key={d.id}
                    className={`na-device-row${activeDevice?.id === d.id ? " active" : ""}`}
                    onClick={() => handleSelectDevice(d)}
                  >
                    <td>{d.mac_address}</td>
                    <td>{d.ip_address || <span className="muted">—</span>}</td>
                    <td>
                      {d.hostname || <span className="muted">—</span>}
                      {d.hostname && classifications[d.hostname]?.category && (
                        <span
                          className="na-classification-badge"
                          title={classifications[d.hostname].reason}
                        >
                          {classifications[d.hostname].category}
                        </span>
                      )}
                    </td>
                    <td>{d.role_hint ? `${ROLE_ICONS[d.role_hint] || "🏷️"} ${d.role_hint}` : <span className="muted">—</span>}</td>
                    <td className="muted">{new Date(d.first_seen).toLocaleString("fr-FR")}</td>
                    <td className="muted">{new Date(d.last_seen).toLocaleString("fr-FR")}</td>
                    <td>{formatBytes(periodStart && periodEnd ? d.bytes_total_period : d.bytes_total)}</td>
                    <td>
                      <span className="na-service-dots">
                        {/* Filtrage "intelligent" (livraison #257, demandé explicitement --
                            capture d'écran montrant des CENTAINES de points sur une seule
                            ligne, illisible) : au-delà de MAX_VISIBLE_SERVICE_DOTS, les
                            services les moins significatifs (déjà triés par packet_count
                            DÉCROISSANT côté backend, voir store.list_services_by_segment)
                            sont résumés par un compteur "+N" plutôt qu'un point de plus --
                            les services les PLUS utilisés restent toujours visibles en
                            premier, jamais une troncature arbitraire (alphabétique/aléatoire)
                            qui masquerait le signal le plus utile. */}
                        {(allServices[d.id] || []).slice(0, MAX_VISIBLE_SERVICE_DOTS).map((s) => (
                          <span
                            key={s.id}
                            className={`na-service-dot ${s.protocol}`}
                            title={`${s.protocol.toUpperCase()} ${s.port} (${s.packet_count} paquet(s))`}
                          />
                        ))}
                        {(allServices[d.id] || []).length > MAX_VISIBLE_SERVICE_DOTS && (
                          <span
                            className="na-service-more"
                            title={`${(allServices[d.id] || []).length - MAX_VISIBLE_SERVICE_DOTS} service(s) supplémentaire(s), moins utilisé(s) -- cliquez la ligne pour le détail complet`}
                          >
                            +{(allServices[d.id] || []).length - MAX_VISIBLE_SERVICE_DOTS}
                          </span>
                        )}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {activeDevice && (
            <div className="na-footer-panel">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                <h3 style={{ margin: 0 }}>
                  {activeDevice.hostname || activeDevice.mac_address}
                  {activeDevice.hostname && <span className="muted"> ({activeDevice.mac_address})</span>}
                </h3>
                <button className="secondary" onClick={() => setActiveDevice(null)}>Fermer</button>
              </div>

              <div style={{ display: "flex", gap: 24, flexWrap: "wrap", marginTop: 8 }}>
                <div style={{ flex: "1 1 260px" }}>
                  <h4 style={{ marginBottom: 4 }}>Services observés ({activeDeviceServices ? activeDeviceServices.length : 0})</h4>
                  {activeDeviceServices === null ? (
                    <p className="muted">Chargement…</p>
                  ) : activeDeviceServices.length === 0 ? (
                    <p className="muted">Aucun service observé.</p>
                  ) : (
                    <div style={{ maxHeight: 220, overflowY: "auto" }}>
                      <table>
                        <thead><tr><th>Protocole</th><th>Port</th><th>Paquets</th></tr></thead>
                        <tbody>
                          {activeDeviceServices.map((s) => (
                            <tr key={s.id}><td>{s.protocol.toUpperCase()}</td><td>{s.port}</td><td>{s.packet_count}</td></tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>

                <div style={{ flex: "1 1 260px" }}>
                  <h4 style={{ marginBottom: 4 }}>Échanges (qui parle à qui)</h4>
                  {deviceLinks.length === 0 ? (
                    <p className="muted">Aucun échange observé.</p>
                  ) : (
                    <table>
                      <thead><tr><th>De</th><th>Vers</th><th>Volume</th></tr></thead>
                      <tbody>
                        {deviceLinks.map((l) => {
                          const from = macToDevice[l.device_a_id];
                          const to = macToDevice[l.device_b_id];
                          return (
                            <tr
                              key={l.id}
                              className={`na-link-row${activeLink?.id === l.id ? " active" : ""}`}
                              title="Cliquer pour voir l'évolution du volume de cette paire"
                              onClick={() => handleSelectLink(l)}
                            >
                              <td>{from ? (from.hostname || from.mac_address) : l.device_a_id}</td>
                              <td>{to ? (to.hostname || to.mac_address) : l.device_b_id}</td>
                              <td>{formatBytes(l.bytes_total)}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  )}
                  {activeLink && (
                    <div className="na-link-history">
                      <h4 style={{ marginBottom: 2 }}>
                        Volume de la paire dans le temps
                        <span className="muted">
                          {" "}— {(macToDevice[activeLink.device_a_id]?.hostname || macToDevice[activeLink.device_a_id]?.mac_address || activeLink.device_a_id)}
                          {" ↔ "}
                          {(macToDevice[activeLink.device_b_id]?.hostname || macToDevice[activeLink.device_b_id]?.mac_address || activeLink.device_b_id)}
                        </span>
                      </h4>
                      {activeLinkHistory === null ? (
                        <p className="muted">Chargement…</p>
                      ) : (
                        <HistoryBars rows={activeLinkHistory} label="Volume échangé entre les deux appareils, par intervalle entre relevés" />
                      )}
                    </div>
                  )}
                </div>

                <div style={{ flex: "1 1 260px" }}>
                  <h4 style={{ marginBottom: 4 }}>Présence dans le temps</h4>
                  <p className="muted" style={{ marginTop: -4, marginBottom: 6 }}>
                    Un point par relevé périodique (voir configuration) -- volume CUMULATIF à cet
                    instant, pas un delta.
                  </p>
                  {activeDeviceHistory === null ? (
                    <p className="muted">Chargement…</p>
                  ) : activeDeviceHistory.length === 0 ? (
                    <p className="muted">Aucun relevé encore enregistré pour cet appareil.</p>
                  ) : (
                    <>
                    <HistoryBars rows={activeDeviceHistory} label="Volume échangé par cet appareil, par intervalle entre relevés" />
                    <table>
                      <thead><tr><th>Relevé</th><th>IP</th><th>Volume cumulé</th></tr></thead>
                      <tbody>
                        {activeDeviceHistory.map((h, idx) => (
                          <tr key={idx}>
                            <td className="muted">{new Date(h.snapshot_at).toLocaleString("fr-FR")}</td>
                            <td>{h.ip_address || "—"}</td>
                            <td>{formatBytes(h.bytes_total)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    </>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
