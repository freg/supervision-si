import { initialState, onClick, onStatusUpdate, colorFor } from "./launcher-state.js";

const CGI_URL = "cgi-bin/launcher.cgi";
const POLL_INTERVAL_MS = 5000;

// service -> état (voir launcher-state.js) -- toute la LOGIQUE de
// transition vit dans ce module séparé, ici on ne fait que
// l'appliquer et rafraîchir le DOM en conséquence.
const states = {};

async function callCgi(params) {
  const url = `${CGI_URL}?${new URLSearchParams(params)}`;
  try {
    const res = await fetch(url);
    return await res.json();
  } catch {
    // Réseau indisponible, CGI injoignable -- jamais bloquant, la
    // prochaine boucle de sondage réessaiera simplement.
    return { error: "réseau indisponible" };
  }
}

function render(service) {
  const light = document.getElementById(`light-${service}`);
  if (!light) return;
  const color = colorFor(states[service]);
  light.className = `light light-${color}`;
  light.setAttribute(
    "title",
    states[service].pending
      ? `${service} — ${states[service].pending === "starting" ? "démarrage" : "arrêt"} en cours…`
      : `${service} — ${states[service].status}`
  );
}

async function pollStatus(service) {
  const data = await callCgi({ service, action: "status" });
  if (data.status) {
    states[service] = onStatusUpdate(states[service], data.status, Date.now());
    render(service);
  }
}

async function handleLightClick(service) {
  const { state, action } = onClick(states[service], Date.now());
  states[service] = state;
  render(service);
  if (!action) return; // clic ignoré (déjà en transition, ou statut encore inconnu)
  await callCgi({ service, action });
  // Première vérification peu après l'action déclenchée -- la boucle
  // de sondage régulière (voir init()) prend ensuite le relais.
  setTimeout(() => pollStatus(service), 1500);
}

function buildGrid(services) {
  const grid = document.getElementById("grid");
  grid.innerHTML = "";
  for (const service of services) {
    states[service] = initialState();
    const tile = document.createElement("div");
    tile.className = "tile";
    tile.innerHTML = `
      <button class="light light-gray" id="light-${service}" title="${service} — chargement…"></button>
      <div class="name">${service}</div>
    `;
    tile.querySelector(".light").addEventListener("click", () => handleLightClick(service));
    grid.appendChild(tile);
  }
}

async function pollAll(services) {
  await Promise.all(services.map((s) => pollStatus(s)));
}

async function init() {
  const listData = await callCgi({ action: "list" });
  const services = listData.services || [];
  if (services.length === 0) {
    document.getElementById("grid").innerHTML =
      '<p class="muted">Aucun service trouvé — le CGI est-il joignable ? (voir la console réseau du navigateur)</p>';
    return;
  }
  buildGrid(services);
  await pollAll(services);
  setInterval(() => pollAll(services), POLL_INTERVAL_MS);
}

init();
