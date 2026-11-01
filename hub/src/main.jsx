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

createRoot(document.getElementById("root")).render(
  <AuthProvider {...oidcConfig}>
    <App />
  </AuthProvider>
);
