// #903 : tuile « Messages » -- blog interne du hub. Déposer un mot pour tout le monde ou pour soi seul, permanent ou
// à durée de vie automatique (effacé seul à l'échéance), et le supprimer. Format « commande » : bloc copiable d'un clic,
// pour se passer une ligne d'un poste à l'autre sans la recopier à vue.
import { useCallback, useEffect, useState } from "react";
import { fetchMessages, postMessage, deleteMessage } from "./messagesClient.js";

const DUREES = [["permanent", "permanent"], ["1h", "1 heure"], ["1j", "1 jour"], ["1s", "1 semaine"]];
const quand = (t) => new Date(t * 1000).toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
const reste = (expire) => {
  if (!expire) return "permanent";
  const s = expire - Date.now() / 1000;
  if (s <= 0) return "expiré";
  if (s < 3600) return `expire dans ${Math.round(s / 60)} min`;
  if (s < 86400) return `expire dans ${Math.round(s / 3600)} h`;
  return `expire dans ${Math.round(s / 86400)} j`;
};

export default function MessagesView({ onBack }) {
  const [d, setD] = useState(null);
  const [corps, setCorps] = useState("");
  const [titre, setTitre] = useState("");
  const [portee, setPortee] = useState("tous");
  const [format, setFormat] = useState("texte");
  const [duree, setDuree] = useState("permanent");
  const [err, setErr] = useState(null);
  const [copie, setCopie] = useState(null);
  const charger = useCallback(() => fetchMessages().then(setD).catch((e) => setErr(String(e.message || e))), []);
  useEffect(() => { charger(); const t = setInterval(charger, 30000); return () => clearInterval(t); }, [charger]);
  const envoyer = async (e) => {
    e.preventDefault();
    if (!corps.trim()) return;
    setErr(null);
    try {
      await postMessage({ corps, titre, portee, format, duree_s: duree });
      setCorps(""); setTitre("");
      charger();
    } catch (ex) { setErr(String(ex.message || ex)); }
  };
  const retirer = async (id) => { if (window.confirm("Supprimer ce message ?")) { try { await deleteMessage(id); charger(); } catch (ex) { setErr(String(ex.message || ex)); } } };
  const copier = (id, texte) => { navigator.clipboard?.writeText(texte); setCopie(id); setTimeout(() => setCopie(null), 1500); };
  return (
    <div className="infra-page">
      <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
        {onBack && <button type="button" className="secondary" onClick={onBack}>◀ Retour</button>}
        <h2 style={{ margin: 0 }}>Messages</h2>
        <span className="infra-muted">un mot pour tout le monde ou pour soi ; permanent ou à durée de vie ; effaçable</span>
      </div>
      <form onSubmit={envoyer} className="infra-card" style={{ margin: "12px 0" }}>
        <input type="text" value={titre} onChange={(e) => setTitre(e.target.value)} placeholder="titre (facultatif)" style={{ width: "100%", marginBottom: 6 }} />
        <textarea value={corps} onChange={(e) => setCorps(e.target.value)} placeholder="votre message… (ou une commande à récupérer sur un autre poste)" rows={format === "commande" ? 4 : 3}
          style={{ width: "100%", fontFamily: format === "commande" ? "monospace" : "inherit" }} />
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center", marginTop: 6 }}>
          <label>Pour <select value={portee} onChange={(e) => setPortee(e.target.value)}><option value="tous">tout le monde</option><option value="moi">moi seul</option></select></label>
          <label>Type <select value={format} onChange={(e) => setFormat(e.target.value)}><option value="texte">texte</option><option value="commande">commande (copiable)</option></select></label>
          <label>Durée <select value={duree} onChange={(e) => setDuree(e.target.value)}>{DUREES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
          <button className="primary" type="submit" disabled={!corps.trim()}>Publier</button>
        </div>
      </form>
      {err && <div className="np-tone bad">{err}</div>}
      {d === null ? <p className="infra-muted">lecture…</p> : d.messages.length === 0 ? <p className="infra-muted">Aucun message.</p> : (
        d.messages.map((m) => (
          <section key={m.id} className="infra-card" style={{ margin: "8px 0" }}>
            <div style={{ display: "flex", gap: 8, alignItems: "baseline", flexWrap: "wrap" }}>
              {m.titre && <b>{m.titre}</b>}
              <span className="infra-muted" style={{ fontSize: 12 }}>
                {m.auteur_nom} · {quand(m.cree)} · {m.portee === "moi" ? "pour moi seul" : "pour tous"} · {reste(m.expire)}
              </span>
              <span style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
                {m.format === "commande" && <button className="secondary" onClick={() => copier(m.id, m.corps)}>{copie === m.id ? "copié ✓" : "copier"}</button>}
                {(m.auteur === d.moi || d.admin) && <button className="secondary" onClick={() => retirer(m.id)}>supprimer</button>}
              </span>
            </div>
            {m.format === "commande"
              ? <pre className="np-secret" style={{ margin: "6px 0 0", whiteSpace: "pre-wrap", wordBreak: "break-all" }}>{m.corps}</pre>
              : <div style={{ marginTop: 4, whiteSpace: "pre-wrap" }}>{m.corps}</div>}
          </section>
        ))
      )}
    </div>
  );
}
