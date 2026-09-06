import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App.jsx";
import "./theme.css";
import "./hub.css";

// Livraison #393, demandé explicitement : "un docker front qui se
// branche sur le/les dockers api" -- SANS Keycloak ni passerelle,
// contrairement au hub principal (voir NetworkAgentView.jsx et
// NetmapOrchestratorView.jsx, réutilisés TELS QUELS -- copiés depuis
// hub/src au moment du build, jamais forkés, voir Dockerfile).
// Aucun <AuthProvider> ici -- ce module n'authentifie personne, se
// fie uniquement à l'accès réseau direct (LAN) aux API concernées.
ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
