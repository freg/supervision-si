// « Mises à jour » du pied de page (#816) : tentatives de la tour de contrôle en ÉCHEC (mise à jour git, livraison,
// reconstruction…) tant qu'elles ne sont pas résolues -- par une réussite ultérieure du même genre ou à la main
// (« Résolu »). Résolues, elles quittent la liste et sont archivées (services-api data/jobs-archive) pour retraitement
// et apprentissage. Journal dépliable.
import { useCallback, useEffect, useState } from "react";
import { fetchJobFailures, resolveJobFailure } from "./servicesClient.js";

const quand = (t) => (t ? new Date(t * 1000).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" }) : "?");

export default function HubUpdateFailures({ apiBase, token, enabled, onCount }) {
  const [d, setD] = useState(null);
  const charger = useCallback(() => {
    if (!enabled || !apiBase || !token) return;
    fetchJobFailures(apiBase, token).then((r) => { if (!r?.error) { setD(r); onCount?.((r.echecs || []).length); } });
  }, [apiBase, token, enabled, onCount]);
  useEffect(() => { charger(); const t = setInterval(charger, 300000); return () => clearInterval(t); }, [charger]);
  if (!enabled || !d || !(d.echecs || []).length) return d?.archives ? <div className="hub-update-row hub-update-archives">{d.archives} échec(s) résolu(s) archivé(s) pour retraitement</div> : null;
  const resoudre = async (e) => {
    const note = window.prompt(`Marquer « ${e.label} » comme résolu ? Note (facultative) :`, "");
    if (note === null) return;
    await resolveJobFailure(apiBase, token, e.id, note);
    charger();
  };
  return (
    <div className="hub-update-failures">
      {d.echecs.map((e) => (
        <details key={e.id} className="hub-update-row hub-update-failure">
          <summary>
            <span className="hub-update-n">✗</span>
            <span className="hub-update-date">{quand(e.at)}</span>
            <span className="hub-update-title">{e.label} <span className="infra-muted">· {e.kind} · {e.user || "?"} · {e.status === "lost" ? "runner perdu" : `code ${e.rc}`}</span></span>
            <button type="button" className="secondary hub-update-link" onClick={(ev) => { ev.preventDefault(); resoudre(e); }} title="l'échec quitte la liste et est archivé">Résolu</button>
          </summary>
          <pre className="hub-update-log">{(e.log || []).join("\n") || "journal vide"}</pre>
        </details>
      ))}
      {d.archives > 0 && <div className="hub-update-row hub-update-archives">{d.archives} échec(s) résolu(s) archivé(s) pour retraitement</div>}
    </div>
  );
}
