// Écran « Urgence » (livraison #796) : la page d'accueil de l'application installée sur téléphone.
// - état en un coup d'œil (alertes critiques / avertissements des agents sur 24 h, regroupées), rafraîchi chaque minute ;
// - accès rapides (SMS, événements, tour de contrôle, migration, journal, PRA) ;
// - contacts d'urgence gardés sur l'appareil (jamais envoyés au serveur), liens tel: ;
// - alertes poussées : abonnement de l'appareil à notify-api (Web Push VAPID), essai, désabonnement ;
// - instantané gardé sur l'appareil pour la page hors ligne (offline.html).
// Logique pure : urgenceLib.js.
import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchEvents } from "./siAgentClient.js";
import { fetchPushKey, subscribePush, unsubscribePush, testPush, fetchPushSubs, deletePushSub } from "./notifyClient.js";
import { hubLink } from "./hubLinks.js";
import HubIcon from "./HubIcon.jsx";
import { QUICK_LINKS, SEV_LABEL, SNAPSHOT_KEY, CONTACTS_KEY, sinceIso, summarize, groupEvents, urlBase64ToUint8Array, pushSupport, deviceLabel, normContacts, telHref, makeSnapshot, ago } from "./urgenceLib.js";

const store = {
  get(k, d) { try { return JSON.parse(localStorage.getItem(k) || "null") ?? d; } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* stockage indisponible */ } },
};

function envSupport() {
  const nav = typeof navigator !== "undefined" ? navigator : {};
  return pushSupport({
    isSecureContext: typeof window !== "undefined" && window.isSecureContext,
    serviceWorker: "serviceWorker" in nav, PushManager: typeof window !== "undefined" && "PushManager" in window,
    Notification: typeof Notification !== "undefined", permission: typeof Notification !== "undefined" ? Notification.permission : "default",
    ios: /iPhone|iPad/.test(nav.userAgent || ""),
  });
}

function PushPanel({ notifyApiBase: api, accessToken: token }) {
  const [sub, setSub] = useState(null);
  const [sev, setSev] = useState("critical");
  const [label, setLabel] = useState(() => deviceLabel(typeof navigator !== "undefined" ? navigator.userAgent : ""));
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  const [subs, setSubs] = useState(null);
  const support = envSupport();

  const refresh = useCallback(async () => {
    if (support.ok) {
      try { const reg = await navigator.serviceWorker.ready; setSub(await reg.pushManager.getSubscription()); } catch { setSub(null); }
    }
    if (api && token) { const r = await fetchPushSubs(api, token); setSubs(r.error ? { error: r.error } : r); }
  }, [api, token, support.ok]);
  useEffect(() => { refresh(); }, [refresh]);

  const run = async (fn) => { setBusy(true); setMsg(null); try { await fn(); } catch (e) { setMsg({ ok: false, text: e.message || String(e) }); } setBusy(false); refresh(); };

  const activer = () => run(async () => {
    if ((await Notification.requestPermission()) !== "granted") throw new Error("notifications non autorisées sur cet appareil");
    const k = await fetchPushKey(api);
    if (!k.publicKey) throw new Error(`clé du serveur indisponible : ${k.error || "réponse vide"}`);
    const reg = await navigator.serviceWorker.ready;
    let s = await reg.pushManager.getSubscription();
    if (!s) s = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: urlBase64ToUint8Array(k.publicKey) });
    const r = await subscribePush(api, token, s.toJSON(), label, sev);
    if (r.error) throw new Error(r.error);
    setMsg({ ok: true, text: `appareil abonné (alertes ${SEV_LABEL[r.min_severity] || r.min_severity} et plus)` });
  });
  const essayer = () => run(async () => {
    const r = await testPush(api, token, sub.endpoint);
    if (r.error) throw new Error(r.error);
    setMsg({ ok: true, text: r.message || "envoyé" });
  });
  const couper = () => run(async () => {
    const r = await unsubscribePush(api, token, sub.endpoint);
    await sub.unsubscribe().catch(() => {});
    if (r.error) throw new Error(r.error);
    setMsg({ ok: true, text: "cet appareil ne reçoit plus les alertes" });
  });
  const retirer = (id) => run(async () => { const r = await deletePushSub(api, token, id); if (r.error) throw new Error(r.error); });

  if (!api) return <p className="infra-muted">notify-api non configuré : alertes poussées indisponibles.</p>;
  const list = subs?.subscriptions || [];
  return (
    <div className="infra-card urg-push">
      <b>Alertes poussées sur cet appareil</b>
      {!support.ok ? <p className="infra-muted">{support.reason}</p> : sub ? (
        <div className="urg-row">
          <span className="urg-ok">✔ activées</span>
          <button disabled={busy} onClick={essayer}>Envoyer un essai</button>
          <button disabled={busy} className="secondary" onClick={couper}>Désactiver</button>
        </div>
      ) : (
        <div className="urg-row">
          <label>Nom de l'appareil <input value={label} onChange={(e) => setLabel(e.target.value)} maxLength={80} /></label>
          <label>Recevoir <select value={sev} onChange={(e) => setSev(e.target.value)}>
            <option value="critical">les critiques</option><option value="warning">critiques et avertissements</option><option value="info">tout</option>
          </select></label>
          <button disabled={busy} onClick={activer}>Activer</button>
        </div>
      )}
      {msg && <p className={msg.ok ? "infra-muted" : "infra-error"}>{msg.text}</p>}
      {subs?.error && <p className="infra-error">liste des appareils : {subs.error}</p>}
      {list.length > 0 && (
        <details>
          <summary>{list.length} appareil(s) abonné(s){subs.queue ? ` · ${JSON.stringify(subs.queue)}` : ""}</summary>
          {list.map((s) => (
            <div key={s.id} className="urg-sub">
              <span><b>{s.label || `#${s.id}`}</b> <span className="infra-muted">{s.username} · {SEV_LABEL[s.min_severity] || s.min_severity} et plus
                {s.last_ok ? ` · dernier envoi ${new Date(s.last_ok * 1000).toLocaleString("fr-FR")}` : ""}</span>
                {s.last_error && <span className="infra-error"> · {s.last_error}</span>}</span>
              <button className="secondary" disabled={busy} onClick={() => retirer(s.id)}>Retirer</button>
            </div>
          ))}
        </details>
      )}
    </div>
  );
}

function Contacts() {
  const [list, setList] = useState(() => normContacts(store.get(CONTACTS_KEY, [])));
  const [edit, setEdit] = useState(false);
  const [f, setF] = useState({ name: "", role: "", phone: "" });
  const save = (l) => { const n = normContacts(l); setList(n); store.set(CONTACTS_KEY, n); };
  return (
    <div className="infra-card">
      <b>Contacts d'urgence</b> <button className="secondary" onClick={() => setEdit(!edit)}>{edit ? "Terminé" : "Modifier"}</button>
      <div className="infra-muted">Gardés sur cet appareil seulement, disponibles hors ligne.</div>
      {list.length === 0 && !edit && <p className="infra-muted">Aucun contact : « Modifier » pour en ajouter.</p>}
      {list.map((c, i) => (
        <div key={i} className="urg-contact">
          <span><b>{c.name}</b> <span className="infra-muted">{c.role}</span></span>
          {telHref(c.phone) ? <a className="urg-tel" href={telHref(c.phone)}>📞 {c.phone}</a> : <span>{c.phone}</span>}
          {edit && <button className="secondary" onClick={() => save(list.filter((_, j) => j !== i))}>✕</button>}
        </div>
      ))}
      {edit && (
        <form className="urg-row" onSubmit={(e) => { e.preventDefault(); save([...list, f]); setF({ name: "", role: "", phone: "" }); }}>
          <input placeholder="Nom" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} required />
          <input placeholder="Rôle (astreinte, fournisseur…)" value={f.role} onChange={(e) => setF({ ...f, role: e.target.value })} />
          <input placeholder="Téléphone" type="tel" value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} />
          <button type="submit">Ajouter</button>
        </form>
      )}
    </div>
  );
}

export default function UrgenceView({ onBack, siAgentApiBase, notifyApiBase, accessToken }) {
  const [events, setEvents] = useState(null);
  const [err, setErr] = useState(null);
  const [at, setAt] = useState(null);
  const [showInfo, setShowInfo] = useState(false);
  const [install, setInstall] = useState(() => (typeof window !== "undefined" ? window.__hubInstallPrompt || null : null));
  const [, tick] = useState(0);

  const load = useCallback(async () => {
    if (!siAgentApiBase) return;
    try {
      const ev = await fetchEvents(siAgentApiBase, { minSeverity: "warning", since: sinceIso(24), limit: 300 });
      setEvents(ev); setErr(null); setAt(new Date().toISOString());
      store.set(SNAPSHOT_KEY, makeSnapshot(ev));
    } catch (e) { setErr(e.message || String(e)); }
  }, [siAgentApiBase]);
  useEffect(() => { load(); const t = setInterval(load, 60000); const u = setInterval(() => tick((x) => x + 1), 30000); return () => { clearInterval(t); clearInterval(u); }; }, [load]);
  useEffect(() => {
    const f = () => setInstall(window.__hubInstallPrompt || null);
    window.addEventListener("hub-install-ready", f);
    return () => window.removeEventListener("hub-install-ready", f);
  }, []);

  const snap = useMemo(() => (events ? null : store.get(SNAPSHOT_KEY, null)), [events]);
  const shown = events || snap?.events || [];
  const sum = summarize(shown);
  const groups = groupEvents(shown).filter((g) => showInfo || g.severity !== "info");
  const standalone = typeof window !== "undefined" && window.matchMedia?.("(display-mode: standalone)").matches;

  const installer = async () => {
    if (!install) return;
    install.prompt();
    try { await install.userChoice; } catch { /* sans importance */ }
    window.__hubInstallPrompt = null; setInstall(null);
  };

  return (
    <div className="infra-root urg-root">
      <div className="infra-top">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h2>Urgence</h2>
        <button className="secondary" onClick={load}>↻ Actualiser</button>
        {install && !standalone && <button onClick={installer}>📲 Installer l'application</button>}
        <span className="infra-muted">{at ? `relevé ${ago(at)}` : snap ? `hors connexion : dernier relevé ${ago(snap.at)}` : ""}</span>
      </div>
      {err && <p className="infra-error">alertes indisponibles : {err}</p>}

      <div className={`urg-state urg-${sum.level}`}>
        <div className="urg-big">{sum.level === "critique" ? "🔴" : sum.level === "alerte" ? "🟠" : "🟢"} {sum.level === "ok" ? "Rien à signaler sur 24 h" : `${sum.critical} critique(s) · ${sum.warning} avertissement(s)`}</div>
        {sum.hosts.length > 0 && <div className="infra-muted">hôtes touchés : {sum.hosts.join(", ")}</div>}
      </div>

      <nav className="urg-links">
        {QUICK_LINKS.map((l) => <a key={l.view + (l.params?.tab || "")} className="urg-link" href={hubLink(l.view, l.params)}><HubIcon icon={l.icon} size={24} />{l.label}</a>)}
      </nav>

      <section>
        <h3>Alertes des dernières 24 h <label className="infra-muted"><input type="checkbox" checked={showInfo} onChange={(e) => setShowInfo(e.target.checked)} /> infos</label></h3>
        {events === null && !snap && !err && <p className="infra-muted">chargement…</p>}
        {groups.length === 0 && (events || snap) && <p className="infra-muted">aucune alerte</p>}
        {groups.slice(0, 60).map((g) => (
          <div key={g.id} className={`urg-ev urg-ev-${g.severity}`}>
            <div><b>{g.agent_id || g.source}</b> {g.message}{g.count > 1 && <span className="urg-count">×{g.count}</span>}</div>
            <div className="infra-muted">{SEV_LABEL[g.severity] || g.severity} · {g.kind} · {ago(g.last)}{g.count > 1 ? ` (depuis ${ago(g.first)})` : ""}
              {g.agent_id && <> · <a href={hubLink("si-agent", { tab: "events", agent: g.agent_id })}>événements</a></>}</div>
          </div>
        ))}
      </section>

      <PushPanel notifyApiBase={notifyApiBase} accessToken={accessToken} />
      <Contacts />
      {!standalone && <p className="infra-muted">Sur téléphone : ouvrir le hub par son adresse https publique puis « Installer l'application » (Android) ou Partager › « Sur l'écran d'accueil » (iPhone). L'icône ouvre directement cet écran.</p>}
    </div>
  );
}
