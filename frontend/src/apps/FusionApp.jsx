import { useEffect, useMemo, useRef, useState } from "react";
import { fetchIpamIpList, fetchZenossIpList } from "./fusionApi.js";
import {
  mergeIpSources, filterRows, severityClass, enrichWithGeolocation, extractPostalCodeFromRow,
  FUSION_COLUMNS, defaultColumnWidths, computeResizedWidth, toggleColumnVisibility, visibleColumns,
} from "./fusionLib.js";
import { fetchGeolocations, registerIpsForGeolocation, fetchCommuneCentroid, upsertGeolocation } from "./pixelGridApi.js";
import { classifyIp } from "../lib/ipClassify.js";

const SOURCE_LABELS = { ipam: "IPAM", zenoss: "Zenoss" };

export default function FusionApp({ onGoToMap }) {
  const [ipamEntries, setIpamEntries] = useState([]);
  const [zenossEntries, setZenossEntries] = useState([]);
  const [ipamError, setIpamError] = useState(null);
  const [zenossError, setZenossError] = useState(null);
  const [loaded, setLoaded] = useState(false);

  const [query, setQuery] = useState("");
  const [hostnameQuery, setHostnameQuery] = useState("");
  const [alertQuery, setAlertQuery] = useState("");
  const [correlatedOnly, setCorrelatedOnly] = useState(false);
  const [selectedRow, setSelectedRow] = useState(null);

  const [geolocations, setGeolocations] = useState([]);
  const [geoStatus, setGeoStatus] = useState(null); // null | "loading" | {ok, ...summary} | {ok:false, error}
  const [postalGeoStatus, setPostalGeoStatus] = useState(null);

  const [hiddenColumns, setHiddenColumns] = useState(() => new Set());
  const [columnWidths, setColumnWidths] = useState(defaultColumnWidths);
  const [columnsMenuOpen, setColumnsMenuOpen] = useState(false);
  const columnsMenuRef = useRef(null);

  useEffect(() => {
    Promise.all([fetchIpamIpList(), fetchZenossIpList()]).then(([ipam, zenoss]) => {
      setIpamEntries(ipam.entries);
      setIpamError(ipam.error);
      setZenossEntries(zenoss.entries);
      setZenossError(zenoss.error);
      setLoaded(true);
    });
    fetchGeolocations().then(setGeolocations);
  }, []);

  // Ferme le panneau "⚙ Colonnes" au clic en dehors — comportement
  // attendu d'un menu déroulant, évite qu'il reste ouvert en permanence.
  useEffect(() => {
    if (!columnsMenuOpen) return undefined;
    function handleClickOutside(e) {
      if (columnsMenuRef.current && !columnsMenuRef.current.contains(e.target)) {
        setColumnsMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [columnsMenuOpen]);

  const visible = useMemo(() => visibleColumns(hiddenColumns), [hiddenColumns]);

  /** Démarre un glisser de redimensionnement sur la poignée d'une
   * colonne — écouteurs posés/retirés pour CE geste précis via des
   * fermetures locales (pas de ref partagée à gérer) : chaque glisser
   * a ses propres onMove/onUp assortis, aucun risque de retirer le
   * mauvais écouteur si plusieurs re-rendus interviennent pendant le
   * geste. */
  function startColumnResize(key, e) {
    e.preventDefault();
    const startWidth = columnWidths[key] ?? 150;
    const startClientX = e.clientX;

    function onMove(moveEvent) {
      setColumnWidths((prev) => ({ ...prev, [key]: computeResizedWidth(startWidth, moveEvent.clientX - startClientX) }));
    }
    function onUp() {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    }
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  }

  const merged = useMemo(() => {
    const base = mergeIpSources(ipamEntries, zenossEntries);
    return enrichWithGeolocation(base, geolocations);
  }, [ipamEntries, zenossEntries, geolocations]);
  const filtered = useMemo(
    () => filterRows(merged, { query, correlatedOnly, hostnameQuery, alertQuery }),
    [merged, query, correlatedOnly, hostnameQuery, alertQuery]
  );

  const correlatedCount = useMemo(() => merged.filter((r) => r.sources.length > 1).length, [merged]);

  async function handleGeolocate() {
    setGeoStatus("loading");
    const ips = [...new Set(merged.map((r) => r.ip))];
    const result = await registerIpsForGeolocation(ips);
    if (result.ok) {
      setGeolocations(await fetchGeolocations());
      setGeoStatus({
        ok: true,
        publicResolved: result.publicResolved,
        privatePending: result.privatePending,
        publicPending: result.publicPending,
      });
    } else {
      setGeoStatus({ ok: false, error: result.error });
    }
    setTimeout(() => setGeoStatus(null), 8000);
  }

  /** Complément à handleGeolocate pour les lignes encore sans position
   * (souvent des IP privées, hors de portée du géo-IP) : extrait un
   * code postal du nom d'hôte, résout son centroïde de commune, et
   * enregistre directement — même principe "automatique en lot" déjà
   * en place pour handleGeolocate, pas une nouvelle philosophie. */
  async function handleGeocodeByPostalCode() {
    setPostalGeoStatus("loading");
    const candidates = merged.filter((r) => !r.position?.mapped && extractPostalCodeFromRow(r));
    let resolved = 0;
    let notFound = 0;
    for (const row of candidates) {
      const codePostal = extractPostalCodeFromRow(row);
      const { commune, error } = await fetchCommuneCentroid(codePostal);
      if (error || !commune) {
        notFound += 1;
        continue;
      }
      const ok = await upsertGeolocation(row.ip, commune.latitude, commune.longitude);
      if (ok) resolved += 1;
    }
    setGeolocations(await fetchGeolocations());
    setPostalGeoStatus({ ok: true, resolved, notFound, scanned: candidates.length });
    setTimeout(() => setPostalGeoStatus(null), 8000);
  }

  /** Rendu d'une cellule selon la clé de colonne — seule source de
   * vérité pour "quoi afficher dans cette colonne", partagée par
   * toutes les lignes ; ajouter/retirer une colonne ne se fait qu'ici
   * ET dans FUSION_COLUMNS (fusionLib.js), jamais dans le JSX du
   * tableau lui-même. */
  function renderCell(row, key) {
    switch (key) {
      case "ip":
        return row.ip;
      case "mac":
        return row.mac || "—";
      case "hostnames":
        return row.hostnames.join(", ") || "—";
      case "sources":
        return row.sources.map((s) => (
          <span key={s} className={`fusion-source-tag fusion-source-tag-${s}`}>
            {SOURCE_LABELS[s] || s}
          </span>
        ));
      case "subnet":
        return row.ipam?.subnet || "—";
      case "alerts":
        return row.zenoss ? (
          <span className={`fusion-severity ${severityClass(row.zenoss.maxSeverity)}`}>
            {row.zenoss.activeCount} · {row.zenoss.severityLabel}
          </span>
        ) : (
          "—"
        );
      case "position":
        return row.position?.mapped ? (
          <span className="fusion-geo-position mapped">
            <span title={`${row.position.latitude}, ${row.position.longitude}`}>
              📍 {row.position.latitude.toFixed(2)}, {row.position.longitude.toFixed(2)}
            </span>
            {onGoToMap && (
              <button
                className="fusion-map-btn"
                title="Centrer et zoomer sur la carte (onglet Supervision SI)"
                onClick={(e) => {
                  e.stopPropagation();
                  onGoToMap({ latitude: row.position.latitude, longitude: row.position.longitude, zoom: 15 });
                }}
              >
                🗺️
              </button>
            )}
          </span>
        ) : row.position ? (
          <span className="fusion-geo-position pending">⏳ en attente</span>
        ) : (
          <span className="fusion-geo-position unknown">
            {classifyIp(row.ip) === "private" && "IP privée"}
            {classifyIp(row.ip) === "public" && "IP publique"}
            {!["private", "public"].includes(classifyIp(row.ip)) && "—"}
          </span>
        );
      default:
        return null;
    }
  }

  return (
    <div className="fusion-shell">
      <div className="fusion-header">
        <div>
          <h2>Fusion IP/MAC</h2>
          <p className="fusion-subtitle">
            Corrélation par adresse IP entre les sources qui en connaissent — calculée dans le
            navigateur à partir des données déjà chargées, aucun service intermédiaire.
          </p>
        </div>
        <div className="fusion-source-status">
          <span className={`fusion-source-badge${ipamError ? " error" : ""}`}>
            IPAM {ipamError ? "⚠️" : `(${ipamEntries.length})`}
          </span>
          <span className={`fusion-source-badge${zenossError ? " error" : ""}`}>
            Zenoss {zenossError ? "⚠️" : `(${zenossEntries.length})`}
          </span>
        </div>
      </div>

      {ipamError && <p className="fusion-error">IPAM injoignable — {ipamError}</p>}
      {zenossError && <p className="fusion-error">Zenoss injoignable — {zenossError}</p>}

      {!loaded && <p className="fusion-empty">Chargement des deux sources…</p>}

      {loaded && (
        <>
          <div className="fusion-toolbar">
            <input
              className="fusion-search-input"
              placeholder="🔍 Filtrer (IP, MAC, nom d'hôte, description, subnet…)"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <input
              className="fusion-search-input fusion-search-input-narrow"
              placeholder="🔍 Nom/hôte…"
              value={hostnameQuery}
              onChange={(e) => setHostnameQuery(e.target.value)}
            />
            <input
              className="fusion-search-input fusion-search-input-narrow"
              placeholder="🔍 Alerte…"
              value={alertQuery}
              onChange={(e) => setAlertQuery(e.target.value)}
            />
            <label className="fusion-toggle">
              <input
                type="checkbox"
                checked={correlatedOnly}
                onChange={(e) => setCorrelatedOnly(e.target.checked)}
              />
              Vues par plusieurs sources seulement ({correlatedCount})
            </label>
            <span className="fusion-count">
              {filtered.length} / {merged.length} adresse{merged.length > 1 ? "s" : ""}
            </span>
            <button
              className="fusion-geo-btn"
              onClick={handleGeolocate}
              disabled={geoStatus === "loading" || merged.length === 0}
              title="IP privées (la plupart chez vous) : ajoutées en attente, à placer à la main dans l'onglet Géolocalisation. IP publiques : géolocalisées automatiquement via un service externe."
            >
              🌍 {geoStatus === "loading" ? "Géolocalisation…" : "Géolocaliser ces IP"}
            </button>
            {geoStatus?.ok && (
              <span className="fusion-geo-status ok">
                ✓ {geoStatus.publicResolved} résolue{geoStatus.publicResolved > 1 ? "s" : ""} · {geoStatus.privatePending + geoStatus.publicPending} en attente
              </span>
            )}
            {geoStatus?.ok === false && <span className="fusion-geo-status error">⚠️ {geoStatus.error}</span>}
            <button
              className="fusion-geo-btn"
              onClick={handleGeocodeByPostalCode}
              disabled={postalGeoStatus === "loading" || merged.length === 0}
              title="Cherche un code postal à 5 chiffres dans le nom d'hôte (ex. BIO17-17300-ISLANDE-RB3011) et résout le centroïde de la commune correspondante — pour les lignes encore sans position, IP privées incluses."
            >
              🏘️ {postalGeoStatus === "loading" ? "Géocodage…" : "Géocoder via code postal"}
            </button>
            {postalGeoStatus?.ok && (
              <span className="fusion-geo-status ok">
                ✓ {postalGeoStatus.resolved} résolue{postalGeoStatus.resolved > 1 ? "s" : ""}
                {postalGeoStatus.notFound > 0 && ` · ${postalGeoStatus.notFound} sans correspondance`}
                {postalGeoStatus.scanned === 0 && " · aucun nom d'hôte avec code postal exploitable"}
              </span>
            )}
            <div className="fusion-columns-menu-wrap" ref={columnsMenuRef}>
              <button className="fusion-geo-btn" onClick={() => setColumnsMenuOpen((v) => !v)}>
                ⚙ Colonnes
              </button>
              {columnsMenuOpen && (
                <div className="fusion-columns-menu">
                  {FUSION_COLUMNS.map((col) => (
                    <label key={col.key} className="fusion-columns-menu-item">
                      <input
                        type="checkbox"
                        checked={!hiddenColumns.has(col.key)}
                        onChange={() => setHiddenColumns((prev) => toggleColumnVisibility(prev, col.key))}
                      />
                      {col.label}
                    </label>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="fusion-columns">
            <div className="fusion-table-wrap">
              <table className="fusion-table" style={{ tableLayout: "fixed" }}>
                <colgroup>
                  {visible.map((col) => (
                    <col key={col.key} style={{ width: `${columnWidths[col.key] ?? col.defaultWidth}px` }} />
                  ))}
                </colgroup>
                <thead>
                  <tr>
                    {visible.map((col, i) => (
                      <th key={col.key} className={i === visible.length - 1 ? "fusion-col-sticky-right" : ""}>
                        {col.label}
                        <span
                          className="fusion-col-resize-handle"
                          onMouseDown={(e) => startColumnResize(col.key, e)}
                          title="Glisser pour redimensionner"
                        />
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((row) => (
                    <tr
                      key={row.ip}
                      className={row.ip === selectedRow?.ip ? "selected" : ""}
                      onClick={() => setSelectedRow(row)}
                    >
                      {visible.map((col, i) => (
                        <td key={col.key} className={i === visible.length - 1 ? "fusion-col-sticky-right" : ""}>
                          {renderCell(row, col.key)}
                        </td>
                      ))}
                    </tr>
                  ))}
                  {filtered.length === 0 && (
                    <tr>
                      <td colSpan={visible.length || 1} className="fusion-empty-row">
                        Aucune adresse ne correspond.
                      </td>
                    </tr>
                  )}
                  {visible.length === 0 && (
                    <tr>
                      <td className="fusion-empty-row">
                        Toutes les colonnes sont masquées — rouvrez-en via "⚙ Colonnes".
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            <aside className="fusion-detail">
              <h3>Détail</h3>
              {!selectedRow && <p className="fusion-empty">Cliquez une ligne pour voir le détail brut par source.</p>}
              {selectedRow && (
                <>
                  <div className="fusion-detail-ip">{selectedRow.ip}</div>
                  {selectedRow.ipam && (
                    <div className="fusion-detail-block">
                      <div className="fusion-detail-block-title">IPAM</div>
                      <pre className="fusion-detail-json">{JSON.stringify(selectedRow.ipam, null, 2)}</pre>
                    </div>
                  )}
                  {selectedRow.zenoss && (
                    <div className="fusion-detail-block">
                      <div className="fusion-detail-block-title">Zenoss</div>
                      <pre className="fusion-detail-json">{JSON.stringify(selectedRow.zenoss, null, 2)}</pre>
                    </div>
                  )}
                </>
              )}
            </aside>
          </div>
        </>
      )}
    </div>
  );
}
