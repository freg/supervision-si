import React from "react";
import { createRoot } from "react-dom/client";
import { AuthProvider } from "react-oidc-context";
import { oidcConfig } from "./authConfig.js";
import App from "./App.jsx";
import "./theme.css";
import "./hub.css";

createRoot(document.getElementById("root")).render(
  <AuthProvider {...oidcConfig}>
    <App />
  </AuthProvider>
);
