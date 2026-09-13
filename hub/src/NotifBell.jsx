import React, { useCallback, useEffect, useRef, useState } from "react";
import { fetchNotifications, ackNotifications } from "./imapConnectorsClient.js";
import { relativeTime, smsTitle, notifExcerpt, zenossTitle, zenossExcerpt, zenossLineTone, bellTone } from "./notifBell.js";

// Cloche de notifications du hub (livraison #490, généralisée #491)
// — demandé explicitement : « brancher les SMS entrants des
// passerelles sur une notification temps réel du hub (cloche +
// compteur non lus) », puis « étendre la cloche aux alertes Zenoss
// (badge rouge cette fois, avec bascule directe vers la vue
// pixelgrid) ».
//
// Badge dans la zone status-badges : compteur total de non lus,
// ROUGE s'il y a des alertes supervision (Zenoss) non lues, ambre
// s'il ne reste que des SMS. Panneau au clic : deux sections
// (alertes supervision avec ton par sévérité + bascule vers la
// supervision SI dont la mosaïque pixel-grid affiche l'état ; SMS
// entrants), accusé de réception par message ou par section. L'état
// « lu » est côté serveur (ack_at en base) : partagé entre
// navigateurs du LAN.
//
// JAMAIS bloquant : API injoignable = cloche discrète avec un title
// d'explication. Sondage 30 s — « temps réel » à l'échelle d'une
// passerelle SMS ou d'une alerte remontée par e-mail.

const REFRESH_MS = 30000;
const LINE_ICON = { bad: "⛔", warn: "⚠", ok: "✔", neutral: "•" };

function NotifSection({ title, items, toneOf, titleOf, excerptOf, onAck, onAckAll, action }) {
  return (
    <div className="notif-bell-section">
      <div className="notif-bell-head">
        <strong>{title}</strong>
        {items.length > 0 && (
          <button type="button" className="notif-bell-ack-all" onClick={onAckAll}>
            Tout marquer lu
          </button>
        )}
      </div>
      {items.length === 0 && <div className="muted notif-bell-empty">Rien en attente.</div>}
      <ul className="notif-bell-list">
        {items.map((it) => {
          const tone = toneOf(it);
          return (
            <li key={it.id}>
              <button type="button" className={`notif-bell-item ${tone}`} title="Marquer lu" onClick={() => onAck(it.id)}>
                <span className="notif-bell-item-head">
                  <strong>{LINE_ICON[tone]} {titleOf(it)}</strong>
                  <span className="muted">{relativeTime(it.date || it.fetched_at)}</span>
                </span>
                <span className="notif-bell-item-text">{excerptOf(it)}</span>
                <span className="muted notif-bell-item-conn">{it.connector_name}</span>
              </button>
            </li>
          );
        })}
      </ul>
      {action}
    </div>
  );
}

export default function NotifBell({ apiBase, onOpenConnectors, onOpenSupervision }) {
  const [sms, setSms] = useState({ unread: 0, items: [] });
  const [zenoss, setZenoss] = useState({ unread: 0, items: [] });
  const [failed, setFailed] = useState(false);
  const [open, setOpen] = useState(false);
  const panelRef = useRef(null);

  const load = useCallback(async () => {
    const [s, z] = await Promise.all([
      fetchNotifications(apiBase, ["sms"]),
      fetchNotifications(apiBase, ["zenoss"]),
    ]);
    if (s?.error && z?.error) { setFailed(true); return; }
    setFailed(false);
    if (!s?.error) setSms({ unread: s.unread || 0, items: Array.isArray(s.items) ? s.items : [] });
    if (!z?.error) setZenoss({ unread: z.unread || 0, items: Array.isArray(z.items) ? z.items : [] });
  }, [apiBase]);

  useEffect(() => { load(); const id = setInterval(load, REFRESH_MS); return () => clearInterval(id); }, [load]);

  // Refermer le panneau en cliquant ailleurs.
  useEffect(() => {
    if (!open) return undefined;
    const onDocClick = (e) => { if (panelRef.current && !panelRef.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [open]);

  const ackOne = async (section, id) => {
    const r = await ackNotifications(apiBase, { ids: [id] });
    if (r?.error) return;
    const set = section === "sms" ? setSms : setZenoss;
    set((prev) => ({ unread: Math.max(0, prev.unread - 1), items: prev.items.filter((it) => it.id !== id) }));
  };

  const ackAll = async (section) => {
    const r = await ackNotifications(apiBase, { all: true, targets: [section] });
    if (r?.error) return;
    const set = section === "sms" ? setSms : setZenoss;
    set({ unread: 0, items: [] });
  };

  const total = sms.unread + zenoss.unread;
  const tone = bellTone({ smsUnread: sms.unread, zenossUnread: zenoss.unread, failed });
  const title = failed
    ? "Notifications : connecteurs IMAP injoignables"
    : total > 0
      ? `${zenoss.unread} alerte${zenoss.unread > 1 ? "s" : ""} supervision · ${sms.unread} SMS — cliquer pour voir`
      : "Notifications — rien en attente";

  return (
    <div className="notif-bell" ref={panelRef}>
      <button
        type="button"
        className={`notif-bell-badge ${tone}`}
        title={title}
        onClick={() => { setOpen((o) => !o); if (!open) load(); }}
      >
        🔔{total > 0 && <span className={`notif-bell-count ${tone}`}>{total > 99 ? "99+" : total}</span>}
      </button>
      {open && (
        <div className="notif-bell-panel">
          {failed && <div className="muted notif-bell-empty">Connecteurs IMAP injoignables — nouvelle tentative dans 30 s.</div>}
          <NotifSection
            title="Alertes supervision"
            items={zenoss.items}
            toneOf={zenossLineTone}
            titleOf={zenossTitle}
            excerptOf={zenossExcerpt}
            onAck={(id) => ackOne("zenoss", id)}
            onAckAll={() => ackAll("zenoss")}
            action={onOpenSupervision && (
              <div className="notif-bell-foot">
                <button type="button" className="notif-bell-open" onClick={() => { setOpen(false); onOpenSupervision(); }}>
                  Ouvrir la supervision SI
                </button>
              </div>
            )}
          />
          <NotifSection
            title="SMS entrants"
            items={sms.items}
            toneOf={() => "neutral"}
            titleOf={smsTitle}
            excerptOf={notifExcerpt}
            onAck={(id) => ackOne("sms", id)}
            onAckAll={() => ackAll("sms")}
            action={onOpenConnectors && (
              <div className="notif-bell-foot">
                <button type="button" className="notif-bell-open" onClick={() => { setOpen(false); onOpenConnectors(); }}>
                  Ouvrir Connecteurs IMAP
                </button>
              </div>
            )}
          />
        </div>
      )}
    </div>
  );
}
