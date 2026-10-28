// #680 : lignes d'installation d'un agent déclaré, régénérées pour l'adresse du hub choisie (LAN ou entrée extérieure).
// Adresse interne (IP, nom sans point, .local/.lan/.home/.internal) : certificat de la CA du projet -> curl -k
// (le SHA-256 fait foi) + --ca-fingerprint ; adresse publique : certificat public -> ni -k ni empreinte.
// Même règle que _pin_internal_ca côté si-agent-api.
export const HISTORY_KEY = "siAgent.hubAddresses";
export const HISTORY_MAX = 8;

export function normalizeBase(url) {
  let u = String(url || "").trim().replace(/\/+$/, "");
  if (!u) return "";
  if (!/^https?:\/\//i.test(u)) u = "https://" + u;
  if (!/\/api\/si-agent$/.test(u)) u = u.replace(/\/api\/si-agent\/.*$/, "") + (/\/api\/si-agent$/.test(u) ? "" : "/api/si-agent");
  return u;
}

export function isInternal(url) {
  const host = String(url || "").replace(/^https?:\/\//i, "").split("/")[0].split(":")[0].replace(/^\[|\]$/g, "");
  return /^\d{1,3}(\.\d{1,3}){3}$/.test(host) || !host.includes(".") || /\.(local|lan|home|internal)$/i.test(host);
}

export function caFingerprintOf(installCommand) {
  return ((String(installCommand || "").match(/--ca-fingerprint\s+(\S+)/) || [])[1]) || "";
}

/** Argument de shell : tel quel s'il est sûr, sinon entre apostrophes (#887 : site « bureau/optline service/téléport 2 »
 * collé tel quel cassait la commande en plusieurs arguments). */
export function shq(v) {
  const s = String(v ?? "");
  return /^[A-Za-z0-9._\/:@%+=,-]+$/.test(s) ? s : `'${s.replace(/'/g, `'\\''`)}'`;
}

export function installLines({ base, agentId, site, pkg, caFp }) {
  const b = normalizeBase(base);
  const internal = isInternal(b);
  const out = { base: b, internal, download: "", install: "" };
  if (pkg && pkg.name) {
    const folder = pkg.name.replace(/\.tar\.gz$/, "");
    out.download = `curl -fsS${internal ? "k" : "L"} -o ${pkg.name} ${b}/package && echo '${pkg.sha256}  ${pkg.name}' | sha256sum -c && tar xzf ${pkg.name} && cd ${folder}`;
  }
  if (pkg && pkg.name) {
    // #897 : même étape sous Windows 10 / 11 (PowerShell) : curl.exe et tar sont livrés avec Windows ; -k pour une
    // adresse interne (CA du projet) compensé, comme sous Linux, par le contrôle de l'empreinte SHA-256 de l'archive.
    const folder = pkg.name.replace(/\.tar\.gz$/, "");
    out.downloadWindows = `curl.exe -fsS${internal ? "k" : "L"} -o ${pkg.name} ${b}/package; `
      + `if ((Get-FileHash .\\${pkg.name} -Algorithm SHA256).Hash -ne '${String(pkg.sha256 || "").toUpperCase()}') { throw 'empreinte SHA-256 differente : archive alteree' }; `
      + `tar -xzf .\\${pkg.name}; cd .\\${folder}`;
  }
  out.install = `./install.sh --agent ${shq(agentId)} --secret "$TOKEN" --central ${b} --site ${shq(site || "default")}` + (internal && caFp ? ` --ca-fingerprint ${caFp}` : "");
  return out;
}

/** #864 : hôte trop ancien (Python < 3.7 : Debian 9 / Proxmox VE 5) -- Python 3.11 autonome dans /opt/pyagent (uv),
 * sans toucher au Python du système, puis la MÊME ligne d'installation avec --python (toutes les options gardées). */
export function oldHostLines(install) {
  const ligne = String(install || "").replace(/^sudo\s+/, "").replace(/^\.\/install\.sh\s*/, "");
  return [
    "uname -m; python3 --version",
    "curl -LsSf https://astral.sh/uv/install.sh | sh",
    "sudo UV_PYTHON_INSTALL_DIR=/opt/pyagent ~/.local/bin/uv python install 3.11",
    'PYAGENT="$(UV_PYTHON_INSTALL_DIR=/opt/pyagent ~/.local/bin/uv python find 3.11)"; echo "$PYAGENT"; "$PYAGENT" --version',
    `sudo ./install.sh --python "$PYAGENT" ${ligne}`.trim(),
    "systemctl status si-agent --no-pager | head -5",
  ];
}

export function pushHistory(list, url, max = HISTORY_MAX) {
  const u = normalizeBase(url);
  if (!u) return list || [];
  return [u, ...(list || []).filter((x) => x !== u)].slice(0, max);
}

export function loadHistory(storage) {
  try { const v = JSON.parse((storage || globalThis.localStorage).getItem(HISTORY_KEY) || "[]"); return Array.isArray(v) ? v.filter((x) => typeof x === "string") : []; } catch { return []; }
}
export function saveHistory(list, storage) {
  try { (storage || globalThis.localStorage).setItem(HISTORY_KEY, JSON.stringify(list || [])); } catch { /* stockage indisponible : rien */ }
}
