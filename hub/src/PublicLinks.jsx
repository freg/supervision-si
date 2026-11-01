// Pages ouvertes sans connexion (livraison #505) -- liste à plat sur
// l'accueil du hub, volontairement PAS des tuiles : ces adresses sont
// faites pour être transmises (mail, affiche, favori des demandeurs),
// il faut donc les LIRE et les COPIER, pas seulement les ouvrir.
// Logique dans publicLinks.js (testée) ; ici uniquement le rendu et le
// retour « Copié » du presse-papier. Aucune icône, aucune couleur en
// dur (variables de shared/theme.css seulement).
import { useEffect, useState } from "react";
import { displayUrl } from "./publicLinks.js";

async function copyText(text) {
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    /* repli ci-dessous */
  }
  try {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(ta);
    return ok;
  } catch {
    return false;
  }
}

export default function PublicLinks({ links }) {
  const [copied, setCopied] = useState(null);
  useEffect(() => {
    if (!copied) return undefined;
    const t = setTimeout(() => setCopied(null), 2000);
    return () => clearTimeout(t);
  }, [copied]);
  if (!links || links.length === 0) return null;
  return (
    <section className="hub-public-links" aria-labelledby="hub-public-links-title">
      <h3 id="hub-public-links-title" className="hub-frame-title">Pages ouvertes — sans connexion</h3>
      <p className="muted hub-public-links-lead">Adresses à transmettre aux personnes qui ne se connectent pas au hub (même serveur, aucune identification demandée).</p>
      <table className="hub-public-links-table">
        <tbody>
          {links.map((l) => (
            <tr key={l.id}>
              <th scope="row">{l.name}</th>
              <td className="muted">{l.description}</td>
              <td><code title={l.url}>{displayUrl(l.url)}</code></td>
              <td className="hub-public-links-actions">
                <a href={l.url} target="_blank" rel="noopener noreferrer">Ouvrir</a>
                <button type="button" onClick={async () => setCopied((await copyText(l.url)) ? l.id : `err:${l.id}`)}>
                  {copied === l.id ? "Copié" : copied === `err:${l.id}` ? "Échec" : "Copier"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
