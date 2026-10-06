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

export function installLines({ base, agentId, site, pkg, caFp }) {
  const b = normalizeBase(base);
  const internal = isInternal(b);
  const out = { base: b, internal, download: "", install: "" };
  if (pkg && pkg.name) {
    const folder = pkg.name.replace(/\.tar\.gz$/, "");
    out.download = `curl -fsS${internal ? "k" : "L"} -o ${pkg.name} ${b}/package && echo '${pkg.sha256}  ${pkg.name}' | sha256sum -c && tar xzf ${pkg.name} && cd ${folder}`;
  }
  out.install = `./install.sh --agent ${agentId} --secret "$TOKEN" --central ${b} --site ${site || "default"}` + (internal && caFp ? ` --ca-fingerprint ${caFp}` : "");
  return out;
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
