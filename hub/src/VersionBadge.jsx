// Pastille de version du hub (bas droite) avec contrôle régulier (livraison #700) :
// compare la livraison COMPILÉE dans la page (VERSION.json) au code présent sur
// le central (git HEAD) et à origin. Rien n'est forcé : un indicateur et un
// bouton qui ouvre la tour de contrôle (mise à jour ou reconstruction).
// Contrôle réservé à qui a accès à la tour (services-api) ; sinon, le numéro seul.
import { useCallback, useEffect, useState } from "react";
import { fetchGit } from "./servicesClient.js";
import { versionStatus } from "./towerLib.js";

const FIRST_CHECK_MS = 15 * 1000;
const EVERY_MS = 15 * 60 * 1000;

export default function VersionBadge({ info, apiBase, token, enabled, onOpenTower }) {
  const [g, setG] = useState(null);
  const [checkedAt, setCheckedAt] = useState(null);
  const [busy, setBusy] = useState(false);
  const check = useCallback(async () => {
    if (!enabled || !apiBase || !token) return;
    setBusy(true);
    const r = await fetchGit(apiBase, token, true);
    setBusy(false); setG(r); setCheckedAt(new Date());
  }, [enabled, apiBase, token]);
  useEffect(() => {
    if (!enabled) return undefined;
    const first = setTimeout(check, FIRST_CHECK_MS);
    const every = setInterval(check, EVERY_MS);
    const onVisible = () => { if (document.visibilityState === "visible" && checkedAt && Date.now() - checkedAt.getTime() > EVERY_MS) check(); };
    document.addEventListener("visibilitychange", onVisible);
    return () => { clearTimeout(first); clearInterval(every); document.removeEventListener("visibilitychange", onVisible); };
  }, [enabled, check, checkedAt]);

  const st = enabled && g ? versionStatus(info.delivery_number, g) : null;
  const title = `hash contenu : ${info.content_hash} · hash git : ${info.git_hash} · dernière vérification : ${info.last_checked_at}`
    + (st ? `\n${st.text}${checkedAt ? ` (contrôlé à ${checkedAt.toLocaleTimeString("fr-FR")})` : ""} · clic : contrôler maintenant` : "");
  return (
    <span className="version-badge-wrap">
      <span className={`version-badge${st ? ` version-${st.state}` : ""}`} title={title} onClick={enabled ? check : undefined} style={enabled ? { cursor: "pointer" } : undefined}>
        {busy ? "⏳ " : st?.state === "ok" ? "● " : ""}#{info.delivery_number || "?"}
      </span>
      {st && (st.state === "update" || st.state === "rebuild") && (
        <button type="button" className="version-action" title={`${st.text} — ouvrir la tour de contrôle`} onClick={onOpenTower}>
          {st.state === "update" ? "⬆️" : "🔨"} #{st.target || "?"}
        </button>
      )}
    </span>
  );
}
