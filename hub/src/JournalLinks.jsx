// #768 : liens vers le journal d'un agent, à côté de chaque message d'erreur (règle : une erreur donne toujours le
// chemin vers son journal).
import { agentJournalLinks } from "./hubLinks.js";

export default function JournalLinks({ agentId, q = "", name }) {
  const l = agentJournalLinks(agentId, q);
  if (!l.length) return null;
  return <span className="journal-links" style={{ marginLeft: 6, whiteSpace: "nowrap" }}>
    {name ? `${name} : ` : ""}{l.map((x, i) => <span key={x.label}>{i ? " · " : "→ "}<a href={x.href}>{x.label}</a></span>)}</span>;
}
