// #899 : accueil du hub pour une visite NON authentifiée (au lieu d'une erreur) : deux entrées.
// 1. Nouvel agent : nom du poste pré-configuré dans le hub ; si un administrateur a ouvert son installation (fiche de
//    l'agent › Installation), l'accueil remet l'archive, le fichier .cmd et les lignes d'installation -- sinon un refus.
// 2. Accès sécurisé : mire Keycloak du hub.
import { useState } from "react";

const estWindows = typeof navigator !== "undefined" && /Windows/i.test(navigator.userAgent || "");

export default function Accueil({ apiBase, onConnexion, erreur }) {
  const [nom, setNom] = useState("");
  const [res, setRes] = useState(null);
  const [occupe, setOccupe] = useState(false);
  const chercher = async (e) => {
    e?.preventDefault();
    if (!nom.trim()) return;
    setOccupe(true);
    try {
      const r = await fetch(`${apiBase}/accueil/agent?nom=${encodeURIComponent(nom.trim())}`, { credentials: "omit" });
      const d = await r.json().catch(() => ({}));
      setRes(r.ok ? { ok: true, d } : { ok: false, msg: d.error || `refus (${r.status})` });
    } catch (err) { setRes({ ok: false, msg: String(err) }); }
    setOccupe(false);
  };
  const d = res?.ok ? res.d : null;
  const lienCmd = d ? `${apiBase}/accueil/agent.cmd?nom=${encodeURIComponent(d.agent_id)}` : "";
  return (
    <div className="hub-shell hub-center">
      <div className="hub-card" style={{ maxWidth: 720, width: "100%" }}>
        <h1 style={{ marginTop: 0 }}>Hub SI</h1>
        {erreur && <p className="muted" style={{ fontSize: 12 }}>Connexion automatique impossible : {erreur}</p>}
        <div style={{ display: "grid", gap: 16, gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))" }}>
          <form onSubmit={chercher} className="hub-card" style={{ margin: 0 }}>
            <h3 style={{ marginTop: 0 }}>🖥️ Nouvel agent</h3>
            <p className="muted" style={{ fontSize: 13 }}>Installer l'agent de supervision sur ce poste : saisir le <b>nom prévu</b> par l'administrateur.</p>
            <input type="text" value={nom} onChange={(e) => setNom(e.target.value)} placeholder="nom du poste (ex. pc-paul)" autoComplete="off" style={{ width: "100%" }} />
            <button className="secondary" type="submit" disabled={occupe || !nom.trim()} style={{ marginTop: 8 }}>{occupe ? "…" : "Continuer"}</button>
          </form>
          <div className="hub-card" style={{ margin: 0 }}>
            <h3 style={{ marginTop: 0 }}>🔐 Accès sécurisé</h3>
            <p className="muted" style={{ fontSize: 13 }}>Hub de supervision : connexion par l'annuaire de l'entreprise.</p>
            <button className="primary" onClick={onConnexion}>Se connecter</button>
          </div>
        </div>
        {res && !res.ok && <p className="np-tone bad" style={{ marginTop: 12 }}>{res.msg}</p>}
        {d && (
          <div style={{ marginTop: 14 }}>
            <h3>Installation de l'agent « {d.agent_id} » (site {d.site})</h3>
            {estWindows ? (<>
              <ol style={{ lineHeight: 1.7 }}>
                {d.install_cmd_available ? (<>
                  <li>Télécharger <a href={lienCmd} download={`si-agent-install-${d.agent_id}.cmd`}>le fichier d'installation</a>.</li>
                  <li>Le <b>double-cliquer</b> dans Téléchargements : « Éditeur inconnu » › <b>Exécuter</b>, puis accepter l'élévation. Il télécharge l'agent, l'installe, affiche « OK » et s'efface.</li>
                </>) : (<>
                  <li>Télécharger <a href={`${apiBase}/package`} download>l'archive de l'agent</a>, clic droit › <b>Extraire tout</b>.</li>
                  <li>Terminal <b>administrateur</b> dans le dossier extrait : <pre className="np-secret">{d.install_command_windows}</pre></li>
                </>)}
              </ol>
              <details><summary>Autres systèmes</summary><pre className="np-secret">{`TOKEN='${d.secret}'`}</pre><pre className="np-secret">{d.install_command}</pre></details>
            </>) : (<>
              <p className="muted" style={{ fontSize: 13 }}>Linux : archive <a href={`${apiBase}/package`} download>à télécharger</a>, décompresser, puis dans son dossier (root) :</p>
              <pre className="np-secret">{`TOKEN='${d.secret}'`}</pre><pre className="np-secret">{d.install_command}</pre>
              {d.install_command_macos && <details><summary>macOS</summary><pre className="np-secret">{d.install_command_macos}</pre></details>}
              <details><summary>Windows</summary><p><a href={lienCmd} download={`si-agent-install-${d.agent_id}.cmd`}>fichier d'installation .cmd</a></p><pre className="np-secret">{d.install_command_windows}</pre></details>
            </>)}
            <p className="muted" style={{ fontSize: 12 }}>Ces éléments contiennent le secret de l'agent : ne pas les diffuser. L'accès se referme dès que l'agent a contacté le hub.</p>
          </div>
        )}
      </div>
    </div>
  );
}
