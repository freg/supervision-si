// #840 Tuile « Boîtes aux lettres » : agents si-mailbox des sessions utilisateur (écran local, requêtes, automates
// dossier -> IA -> actions). Le hub ne voit que ceux en mode « relié », et seulement un résumé sans contenu ; en mode
// « discret » (défaut) l'agent n'a aucune liaison avec le hub.
import { useCallback, useEffect, useState } from "react";
import { fetchMailbox } from "./siAgentClient.js";
import { hubLink } from "./hubLinks.js";

const quand = (t) => (t ? new Date(t * 1000).toLocaleString("fr-FR") : "—");

export default function MailboxView({ onBack, siAgentApiBase }) {
  const [d, setD] = useState(null);
  const [err, setErr] = useState("");
  const charger = useCallback(async () => { const r = await fetchMailbox(siAgentApiBase); if (r?.error) setErr(r.error); else { setD(r); setErr(""); } }, [siAgentApiBase]);
  useEffect(() => { charger(); const t = setInterval(charger, 60000); return () => clearInterval(t); }, [charger]);
  return (
    <div className="infra-root veille">
      <div className="infra-top"><button className="secondary" onClick={onBack}>◀ Retour</button><h2>Boîtes aux lettres — agents si-mailbox</h2></div>
      {err && <p className="infra-error">{err}</p>}
      <div className="infra-page infra-scroll">
        <div className="infra-card">
          <b>Installer dans une session</b> (pas de lien : opération manuelle, sur le poste, sans root) :
          <code> cd supervision-si/mailbox && sh installer.sh</code> puis ouvrir l'adresse affichée (écran local 127.0.0.1:8095 avec jeton).
          <p className="infra-muted">Mode <b>discret</b> par défaut : aucune liaison avec le hub. Mode <b>relié</b> (réglage dans l'écran local) : un résumé sans contenu
            est remonté par la sonde « mailbox » de l'agent du poste — <a href={hubLink("si-agent", {})}>Agents hôtes › l'agent › Sondes</a>.</p>
        </div>
        <div className="infra-table-wrap"><table className="infra-table">
          <thead><tr><th>Poste</th><th>Session</th><th>Comptes</th><th>Automates</th><th>Traités 24 h</th><th>Erreurs 24 h</th><th>Dernier résumé</th><th>Dernières actions</th></tr></thead>
          <tbody>{(d?.postes || []).map((p) => (
            <tr key={`${p.agent_id}-${p.session}`}><td><a href={hubLink("si-agent", { agent: p.agent_id })}>{p.agent_id}</a></td><td>{p.session}</td><td>{p.comptes}</td>
              <td>{(p.automates || []).map((a) => <div key={a.nom}>{a.nom} <span className={`np-tone ${a.mode === "actif" ? "good" : "neutral"}`}>{a.mode}{a.actif === false ? " · suspendu" : ""}</span></div>)}</td>
              <td>{p.traites_24h}</td><td className={p.erreurs_24h ? "infra-error" : ""}>{p.erreurs_24h}</td>
              <td className={p.ancien ? "infra-error" : "infra-muted"}>{quand(p.ts)}</td>
              <td className="infra-muted">{(p.derniers || []).slice(-5).reverse().map((x, i) => <div key={i}>{quand(x.ts)} · {x.automate || ""} {x.action} : {x.resultat}{x.essai ? " (essai)" : ""}{x.sujet ? ` — ${x.sujet}` : ""}</div>)}</td></tr>))}
            {d && !d.postes.length && <tr><td colSpan={8} className="infra-muted">Aucun agent si-mailbox relié (les agents discrets restent invisibles, c'est voulu).</td></tr>}</tbody></table></div>
      </div>
    </div>
  );
}
