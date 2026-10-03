// #670 : bandeau des rappels d'agenda (VALARM) -- interrogé toutes les minutes, un rappel échu = ligne cliquable ; « ✕ » l'écarte
// pour cette occurrence ; notification du navigateur si elle a été autorisée (demandée au premier clic sur le bandeau).
import { useCallback, useEffect, useRef, useState } from "react";
import { listReminders } from "./groupwareClient.js";
import { dueReminders, reminderKey, reminderText } from "./groupwareLib.js";

const REFRESH_MS = 60000;

export default function GroupwareReminders({ base, login, groups, onOpen }) {
  const [list, setList] = useState([]);
  const [dismissed, setDismissed] = useState(() => new Set());
  const notified = useRef(new Set());

  const groupsKey = (groups || []).join(",");   // le tableau est recréé à chaque rendu du parent : on dépend de son contenu
  const load = useCallback(async () => {
    if (!base || !login) return;
    const r = await listReminders(base, login, groupsKey ? groupsKey.split(",") : [], 1440);
    if (!r || r.error) return;
    setList(r.reminders || []);
  }, [base, login, groupsKey]);
  useEffect(() => { load(); const id = setInterval(load, REFRESH_MS); return () => clearInterval(id); }, [load]);

  const due = dueReminders(list, dismissed);
  useEffect(() => {
    if (typeof Notification === "undefined" || Notification.permission !== "granted") return;
    for (const r of due) { const k = reminderKey(r); if (!notified.current.has(k)) { notified.current.add(k); try { new Notification("Rappel d'agenda", { body: reminderText(r) }); } catch { /* bloqué */ } } }
  }, [due]);
  if (!due.length) return null;

  const askPermission = () => { if (typeof Notification !== "undefined" && Notification.permission === "default") Notification.requestPermission(); };
  return (
    <div className="sa-banner warn gw-reminders" role="status" onClick={askPermission}>
      <span className="sa-banner-head">⏰ {due.length === 1 ? "Rappel d'agenda" : `${due.length} rappels d'agenda`}</span>
      <ul className="sa-banner-items">
        {due.slice(0, 4).map((r) => (
          <li key={reminderKey(r)}>
            <a href="#" onClick={(e) => { e.preventDefault(); onOpen && onOpen(r); }}>{reminderText(r)}</a>
            <button type="button" className="secondary pv-mini" title="Écarter ce rappel" onClick={(e) => { e.stopPropagation(); setDismissed(new Set([...dismissed, reminderKey(r)])); }}>✕</button>
          </li>
        ))}
      </ul>
    </div>
  );
}
