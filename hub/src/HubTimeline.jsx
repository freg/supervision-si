import { useEffect, useState } from "react";
import {
  TIMELINE_GRANULARITIES, HUB_EVENT_CATEGORY_META,
  granularityWindowSeconds, granularityBucketSeconds, groupEventsByBucket,
} from "./hubTimelineLib.js";
import { fetchHubEvents } from "./settingsClient.js";

const nowTs = () => Math.floor(Date.now() / 1000);

const GRANULARITY_LABELS = {
  heure: "Heure",
  "demi-jour": "Demi-journée",
  jour: "Journée",
  semaine: "Semaine",
  mois: "Mois",
};

/**
 * Timeline verticale du hub -- backlog, étape 3 (livraison #120).
 * Ancrée à droite en mode onglets (voir TabShell.jsx, rendue dans
 * `.hub-tabshell-body` à côté de `.hub-tab-content`). Fenêtre
 * glissante paramétrable (granularité = quelle durée en arrière,
 * "demi-jour" par défaut, demandé explicitement) -- voir
 * hubTimelineLib.js pour la logique pure (fenêtre/regroupement),
 * testée séparément.
 *
 * Regroupe les événements par petit créneau ("bucket") pour éviter
 * une liste illisible en cas de rafale -- un marqueur par catégorie
 * PRÉSENTE dans le créneau, avec un compteur si plusieurs événements
 * du même type y tombent (demandé explicitement). Rafraîchie
 * périodiquement (60s), même esprit que le rafraîchissement léger
 * déjà utilisé ailleurs dans le projet (TechnicienView.jsx, "now").
 *
 * Personnelle par construction (voir hub/README.md) -- affiche
 * uniquement les événements du `login` transmis, jamais un journal
 * partagé.
 */
export default function HubTimeline({ login, prefsApiBase }) {
  const [granularity, setGranularity] = useState("demi-jour");
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [now, setNow] = useState(nowTs);

  useEffect(() => {
    const id = setInterval(() => setNow(nowTs()), 60000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (!login) return;
    let cancelled = false;
    setLoading(true);
    const since = now - granularityWindowSeconds(granularity);
    fetchHubEvents(prefsApiBase, login, since).then((evts) => {
      if (cancelled) return;
      setEvents(evts);
      setLoading(false);
    });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [login, prefsApiBase, granularity, now]);

  const buckets = groupEventsByBucket(events, granularityBucketSeconds(granularity));

  return (
    <aside className="hub-timeline">
      <div className="hub-timeline-header">
        <h3>🕒 Timeline</h3>
        <select
          value={granularity}
          onChange={(e) => setGranularity(e.target.value)}
          title="Fenêtre glissante -- combien de temps en arrière"
        >
          {TIMELINE_GRANULARITIES.map((g) => (
            <option key={g} value={g}>{GRANULARITY_LABELS[g]}</option>
          ))}
        </select>
      </div>

      <div className="hub-timeline-body">
        {loading && <p className="muted hub-timeline-empty">Chargement…</p>}
        {!loading && buckets.length === 0 && (
          <p className="muted hub-timeline-empty">Aucun événement sur cette fenêtre.</p>
        )}
        {!loading && buckets.map((b) => (
          <div key={b.bucketTs} className="hub-timeline-bucket">
            <div className="hub-timeline-bucket-time">
              {new Date(b.bucketTs * 1000).toLocaleString("fr-FR", {
                day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit",
              })}
            </div>
            <div className="hub-timeline-bucket-markers">
              {b.categories.map(({ category, count, events: catEvents }) => {
                const meta = HUB_EVENT_CATEGORY_META[category] || { icon: "•", label: category };
                const title = [
                  meta.label,
                  ...catEvents.map((e) => e.label).filter(Boolean),
                ].join(" — ");
                return (
                  <span
                    key={category}
                    className={`hub-timeline-marker hub-timeline-marker-${category}`}
                    title={title}
                  >
                    <span className="hub-timeline-marker-icon">{meta.icon}</span>
                    {count > 1 && <span className="hub-timeline-marker-count">{count}</span>}
                  </span>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </aside>
  );
}
