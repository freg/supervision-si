import React from "react";
import { createRoot } from "react-dom/client";
import { AuthProvider } from "react-oidc-context";
import { oidcConfig } from "./authConfig.js";
import App from "./App.jsx";
import "./theme.css";
import "./hub.css";
import { installActionFeedback } from "./actionFeedback.js";

installActionFeedback();

// #796 : application installable. Le service worker n'existe qu'en contexte sûr (https ou localhost) ;
// l'invite d'installation arrive tôt, elle est gardée pour le bouton « Installer » de l'écran Urgence.
if ("serviceWorker" in navigator && window.isSecureContext) {
  window.addEventListener("load", () => { navigator.serviceWorker.register("/sw.js").catch(() => {}); });
}
window.addEventListener("beforeinstallprompt", (e) => { e.preventDefault(); window.__hubInstallPrompt = e; window.dispatchEvent(new Event("hub-install-ready")); });   // #778 : bouton occupé pendant l'envoi, bandeau « fait » / « échec »

// #998 : une page d'un nœud IA (/ia/<nœud>/…) que la passerelle ne sert pas encore retombe sur le hub : dans le cadre
// de la tuile Hermes, le hub s'afficherait dans lui-même à l'infini. On affiche alors un message, jamais le hub.
const dansCadreIa = window.self !== window.top && window.location.pathname.startsWith("/ia/");
createRoot(document.getElementById("root")).render(
  dansCadreIa ? (
    <p style={{ padding: 16, color: "var(--danger)", fontFamily: "system-ui, sans-serif" }}>
      La passerelle ne sert pas encore {window.location.pathname} : nœud non déclaré dans la passerelle, ou job de la passerelle
      en échec (Tour de contrôle › Livraisons &amp; jobs).
    </p>
  ) : (
    <AuthProvider {...oidcConfig}>
      <App />
    </AuthProvider>
  )
);
