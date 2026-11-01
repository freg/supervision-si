// #833 Bouton d'une commande d'agent : « en cours… » (désactivé) tant que la commande attend l'agent, et suivi de fin
// (bascule vers l'onglet du résultat ; échec : onglet Commandes).
import { useEffect, useRef } from "react";
import { commandeEnCours, finsCommandes, ONGLET_RESULTAT } from "./commandesLib.js";

const SUIVIES = new Set();
export const suivreCommande = (id) => { if (id) SUIVIES.add(id); };

export default function BoutonCommande({ cmds, agent, critere, className = "", disabled, onClick, children, title }) {
  const c = commandeEnCours(cmds, agent, critere);
  return <button type="button" className={`${className}${c ? " en-cours" : ""}`} disabled={disabled || !!c} onClick={onClick}
    title={c ? `commande ${c.id} : l'agent y travaille` : title}>{c ? "en cours…" : children}</button>;
}

export function useFinCommandes(cmds, setTab, setMsg, setErr) {
  const vus = useRef({});
  useEffect(() => {
    for (const c of finsCommandes(cmds, SUIVIES, vus.current)) {
      const quoi = [c.params?.action, c.params?.moteur, c.params?.nom || c.params?.instance || c.params?.profil].filter(Boolean).join(" ");
      if (c.status === "done" && !c.error) { setMsg(`✔ ${quoi} sur ${c.agent_id} : terminé`); setTab(ONGLET_RESULTAT[c.params?.action] || "commandes"); }
      else { setErr(`✗ ${quoi} sur ${c.agent_id} : ${c.error || "échec"} — sortie dans l'onglet Commandes`); setTab("commandes"); }
    }
  }, [cmds, setTab, setMsg, setErr]);
}
