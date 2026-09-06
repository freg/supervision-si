import React, { useEffect, useRef, useState } from "react";
import { getJson, postJson } from "../api.js";
import { fmtTs, ROLE_LABELS } from "../lib.js";

// Fil de discussion d'un ticket — sert de forum (questions du
// demandeur) et de chat demandeur <-> technicien. Rafraîchi toutes les
// 15 s tant que le fil est affiché (même esprit que le polling 10 s de
// l'app supervision). Pattern hasLoadedOnce : le contenu reste monté
// entre deux rechargements (pas de perte de défilement).
export default function TicketThread({ ticketId, me, actedBy }) {
  const [messages, setMessages] = useState([]);
  const [hasLoadedOnce, setHasLoadedOnce] = useState(false);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState(null);
  const [sending, setSending] = useState(false);
  const bottomRef = useRef(null);
  const lastCountRef = useRef(0);

  const load = async () => {
    const res = await getJson(`/tickets/${ticketId}/messages`);
    if (res.ok) {
      setMessages(res.data);
      setError(null);
    } else {
      setError(res.data.error || "fil illisible");
    }
    setHasLoadedOnce(true);
  };

  useEffect(() => {
    setHasLoadedOnce(false);
    setMessages([]);
    load();
    const interval = setInterval(load, 15000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ticketId]);

  useEffect(() => {
    // Défilement en bas uniquement quand un message ARRIVE (pas à
    // chaque polling sans changement).
    if (messages.length > lastCountRef.current && bottomRef.current) {
      bottomRef.current.scrollIntoView({ block: "nearest" });
    }
    lastCountRef.current = messages.length;
  }, [messages]);

  const send = async () => {
    const body = draft.trim();
    if (!body || sending) return;
    setSending(true);
    const res = await postJson(`/tickets/${ticketId}/messages`, {
      user_id: me.id,
      body,
      ...(actedBy ? { acted_by_user_id: actedBy.id } : {}),
    });
    setSending(false);
    if (res.ok) {
      setDraft("");
      await load();
    } else {
      setError(res.data.error || "envoi impossible");
    }
  };

  return (
    <div>
      <h3>💬 Fil de discussion</h3>
      {!hasLoadedOnce && <p className="muted">Chargement…</p>}
      {hasLoadedOnce && messages.length === 0 && (
        <p className="muted">Aucun message pour l'instant.</p>
      )}
      <div className="thread">
        {messages.map((m) => (
          <div key={m.id} className={`msg${m.user_id === me.id ? " mine" : ""}`}>
            <div className="msg-head">
              <strong>{m.author_name || m.author_login || "(inconnu)"}</strong>
              {m.author_role && (
                <span className="role-tag">
                  {ROLE_LABELS[m.author_role] || m.author_role}
                </span>
              )}
              {m.acted_by_user_id && (
                <span className="acted-by-tag" title="Saisi par le personnel pour le compte de cette personne">
                  ✍️ saisi par {m.acted_by_name || m.acted_by_login || "le personnel"}
                </span>
              )}
              <span>{fmtTs(m.created_ts)}</span>
            </div>
            <div className="msg-body">{m.body}</div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
      {error && <p className="error-text">{error}</p>}
      <div className="thread-input">
        <textarea
          placeholder="Votre message… (Entrée = envoyer, Maj+Entrée = retour à la ligne)"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
        />
        <button className="primary" onClick={send} disabled={sending || !draft.trim()}>
          Envoyer
        </button>
      </div>
    </div>
  );
}
