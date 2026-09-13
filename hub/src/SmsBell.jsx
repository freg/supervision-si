import React, { useCallback, useEffect, useRef, useState } from "react";
import { fetchNotifications, ackNotifications } from "./imapConnectorsClient.js";
import { relativeTime, notifTitle, notifExcerpt, bellTone } from "./smsBell.js";

// Cloche SMS du hub (livraison #490) — demandé explicitement :
// « brancher les SMS entrants des passerelles sur une notification
// temps réel du hub (cloche + compteur non lus) ». Badge dans la
// zone status-badges (à côté de l'horloge et du n° de livraison) :
// compteur de SMS non lus, panneau au clic (expéditeur, extrait,
// temps relatif), accusé de réception par message ou en bloc, lien
// vers la tuile Connecteurs IMAP. L'état « lu » est côté serveur
// (ack_at en base) : partagé entre navigateurs du LAN.
//
// JAMAIS bloquant : API injoignable = cloche discrète avec un title
// d'explication, le reste du hub n'en sait rien. Sondage 30 s —
// « temps réel » à l'échelle d'une passerelle SMS.

const REFRESH_MS = 30000;

export default function SmsBell({ apiBase, onOpen }) {
  const [unread, setUnread] = useState(0);
  const [items, setItems] = useState([]);
  const [failed, setFailed] = useState(false);
  const [open, setOpen] = useState(false);
  const panelRef = useRef(null);

  const load = useCallback(async () => {
    const data = await fetchNotifications(apiBase, ["sms"]);
    if (data?.error) { setFailed(true); return; }
    setFailed(false);
    setUnread(data.unread || 0);
    setItems(Array.isArray(data.items) ? data.items : []);
  }, [apiBase]);

  useEffect(() => { load(); const id = setInterval(load, REFRESH_MS); return () => clearInterval(id); }, [load]);

  // Refermer le panneau en cliquant ailleurs.
  useEffect(() => {
    if (!open) return undefined;
    const onDocClick = (e) => { if (panelRef.current && !panelRef.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [open]);

  const ackOne = async (id) => {
    const r = await ackNotifications(apiBase, { ids: [id] });
    if (!r?.error) {
      setItems((prev) => prev.filter((it) => it.id !== id));
      setUnread((n) => Math.max(0, n - 1));
    }
  };

  const ackAll = async () => {
    const r = await ackNotifications(apiBase, { all: true, targets: ["sms"] });
    if (!r?.error) { setItems([]); setUnread(0); }
  };

  const tone = bellTone(unread, failed);
  const title = failed
    ? "SMS entrants : connecteurs IMAP injoignables"
    : unread > 0
      ? `${unread} SMS non lu${unread > 1 ? "s" : ""} — cliquer pour voir`
      : "SMS entrants — aucun non lu";

  return (
    <div className="sms-bell" ref={panelRef}>
      <button
        type="button"
        className={`sms-bell-badge ${tone}`}
        title={title}
        onClick={() => { setOpen((o) => !o); if (!open) load(); }}
      >
        🔔{unread > 0 && <span className="sms-bell-count">{unread > 99 ? "99+" : unread}</span>}
      </button>
      {open && (
        <div className="sms-bell-panel">
          <div className="sms-bell-head">
            <strong>SMS entrants</strong>
            {items.length > 0 && (
              <button type="button" className="sms-bell-ack-all" onClick={ackAll}>
                Tout marquer lu
              </button>
            )}
          </div>
          {failed && <div className="muted sms-bell-empty">Connecteurs IMAP injoignables — nouvelle tentative dans 30 s.</div>}
          {!failed && items.length === 0 && <div className="muted sms-bell-empty">Aucun SMS non lu.</div>}
          <ul className="sms-bell-list">
            {items.map((it) => (
              <li key={it.id}>
                <button type="button" className="sms-bell-item" title="Marquer lu" onClick={() => ackOne(it.id)}>
                  <span className="sms-bell-item-head">
                    <strong>{notifTitle(it)}</strong>
                    <span className="muted">{relativeTime(it.date || it.fetched_at)}</span>
                  </span>
                  <span className="sms-bell-item-text">{notifExcerpt(it)}</span>
                  <span className="muted sms-bell-item-conn">{it.connector_name}</span>
                </button>
              </li>
            ))}
          </ul>
          <div className="sms-bell-foot">
            <button type="button" className="sms-bell-open" onClick={() => { setOpen(false); onOpen?.(); }}>
              Ouvrir Connecteurs IMAP
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
