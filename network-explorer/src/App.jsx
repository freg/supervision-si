import { useState } from "react";
import NetworkAgentView from "./NetworkAgentView.jsx";
import NetmapOrchestratorView from "./NetmapOrchestratorView.jsx";

const NETWORK_AGENT_API_BASE_URL = import.meta.env.VITE_NETWORK_AGENT_API_BASE_URL || "";
const NETMAP_ORCHESTRATOR_API_BASE_URL = import.meta.env.VITE_NETMAP_ORCHESTRATOR_API_BASE_URL || "";
const CLASSIFIER_API_BASE_URL = import.meta.env.VITE_CLASSIFIER_API_BASE_URL || "";

// Livraison #393 -- pas de navigation hub (onBack est un no-op, ces
// vues n'ont nulle part où "retourner" ici), juste un bandeau
// d'onglets minimal entre les deux tuiles réseau.
export default function App() {
  const [tab, setTab] = useState("network-agent");
  const noop = () => {};

  return (
    <div>
      <div style={{ display: "flex", gap: 8, padding: "8px 16px", borderBottom: "1px solid var(--border)" }}>
        <button className={tab === "network-agent" ? "" : "secondary"} onClick={() => setTab("network-agent")}>
          🌐 Agent réseau
        </button>
        <button className={tab === "orchestrator" ? "" : "secondary"} onClick={() => setTab("orchestrator")}>
          🧭 Orchestrateur réseau
        </button>
      </div>

      {tab === "network-agent" ? (
        <NetworkAgentView
          onBack={noop}
          networkAgentApiBase={NETWORK_AGENT_API_BASE_URL}
          classifierApiBase={CLASSIFIER_API_BASE_URL}
        />
      ) : (
        <NetmapOrchestratorView
          onBack={noop}
          netmapOrchestratorApiBase={NETMAP_ORCHESTRATOR_API_BASE_URL}
        />
      )}
    </div>
  );
}
