import useIpamStats from "../hooks/useIpamStats.js";

export default function IpamOverviewPanel() {
  const { stats, health, error } = useIpamStats(60000);

  if (health && health.status !== "ok") {
    return (
      <p className="synthesis-empty">
        ⚠️ Base IPAM {health.db === "non configuré" ? "non configurée" : "injoignable"}
        {health.error ? ` — ${health.error}` : ""} (voir ipam/README.md).
      </p>
    );
  }

  if (error) {
    return <p className="synthesis-empty">⚠️ {error}</p>;
  }

  if (!stats) {
    return <p className="synthesis-empty">Chargement…</p>;
  }

  return (
    <div className="ipam-overview">
      <div className="ipam-overview-row">
        <span className="ipam-overview-value">{stats.sectionCount}</span>
        <span className="ipam-overview-label">section{stats.sectionCount > 1 ? "s" : ""}</span>
      </div>
      <div className="ipam-overview-row">
        <span className="ipam-overview-value">{stats.subnetCount}</span>
        <span className="ipam-overview-label">subnet{stats.subnetCount > 1 ? "s" : ""}</span>
      </div>
      <div className="ipam-overview-states">
        <span className="ipam-overview-state ipam-overview-state-active" title="Actifs (en ligne)">
          🟢 {stats.activeCount}
        </span>
        <span className="ipam-overview-state ipam-overview-state-offline" title="Hors ligne">
          🔴 {stats.offlineCount}
        </span>
        <span className="ipam-overview-state ipam-overview-state-unmonitored" title="Non surveillés">
          ⚪ {stats.unmonitoredCount}
        </span>
      </div>
    </div>
  );
}
