// Fiches du campus (livraison #566) -- logique PURE testée : regroupement
// par lab, filtre « début de mot d'abord », résumé.
import { rankFilter } from "./textFilter.js";

export const ASSET_LABELS = { kind: "Type", designation: "Désignation", model: "Modèle", serial: "N° de série", mac: "MAC", ip: "IP", account: "Compte", klass: "Classe", subclass: "Sous-classe", location: "Localisation", storage: "Stockage", profile: "Profil", commissioned: "Mise en service", comment: "Commentaire" };
export const SERVICE_LABELS = { course: "Parcours", name: "Atelier", apk: "Livraison APK", hardware: "Matériel", site: "Site / plateforme" };

export function cardText(item) {
  return [item.name, item.kind, item.course, item.designation, item.model, item.serial, item.mac, item.ip, item.lab, item.location, item.hardware, item.site, ...Object.values(item.fields || {})].filter(Boolean).join(" ");
}

/** Groupes [{lab, items}] filtrés, labs triés, « (sans lab) » en dernier. */
export function groupByLab(items, query, labFilter = "") {
  const kept = rankFilter(items.filter((i) => !labFilter || (i.lab || "") === labFilter), query, cardText);
  const groups = new Map();
  for (const it of kept) { const k = (it.lab || "").trim() || "(sans lab)"; if (!groups.has(k)) groups.set(k, []); groups.get(k).push(it); }
  return [...groups.entries()].map(([lab, items]) => ({ lab, items })).sort((a, b) => (a.lab === "(sans lab)") - (b.lab === "(sans lab)") || a.lab.localeCompare(b.lab, "fr"));
}

export function labs(items) {
  return [...new Set(items.map((i) => (i.lab || "").trim()).filter(Boolean))].sort((a, b) => a.localeCompare(b, "fr"));
}

/** Résumé des matériels : total, rapprochés Nebula, en ligne, par type. */
export function assetSummary(items) {
  const byKind = new Map();
  let matched = 0, online = 0;
  for (const i of items) {
    byKind.set(i.kind || "?", (byKind.get(i.kind || "?") || 0) + 1);
    if (i.nebula) { matched++; if (i.nebula.status === "online") online++; }
  }
  return { total: items.length, matched, online, byKind: [...byKind.entries()].sort((a, b) => b[1] - a[1]) };
}

// ---------------------------------------------------------------- #567
/** Rapproche les hôtes de la sonde windows-probe des fiches matériel (MAC, sinon nom NetBIOS = nom de fiche). */
export function matchWindowsHosts(hosts, assets) {
  const byMac = new Map(), byName = new Map(), byIp = new Map();
  for (const a of assets || []) {
    for (const m of a.macs || []) byMac.set(m.toLowerCase(), a);
    if (a.name) byName.set(a.name.trim().toLowerCase().replace(/\s+/g, "-"), a);
    if (a.ip) byIp.set(String(a.ip).trim(), a);
  }
  return (hosts || []).map((h) => {
    const mac = (h.mac || "").toLowerCase().replace(/-/g, ":");
    const nm = (h.name || "").trim().toLowerCase();
    const asset = (mac && byMac.get(mac)) || (h.ip && byIp.get(h.ip)) || (nm && (byName.get(nm) || byName.get(nm.replace(/-/g, " ")))) || null;
    return { ...h, asset };
  });
}

/** Liens d'accès pour un hôte : [{kind, label, href?, copy?, download?}]. */
export function accessLinks(h) {
  const p = h.ports || {};
  const out = [];
  if (p.rdp) out.push({ kind: "rdp", label: "RDP", download: { name: `${h.name || h.ip}.rdp`, text: `full address:s:${h.ip}\r\nprompt for credentials:i:1\r\nauthentication level:i:2\r\n` }, href: `rdp://full%20address=s:${h.ip}` });
  if (p.anydesk) out.push({ kind: "anydesk", label: "AnyDesk", href: `anydesk:${h.ip}` });
  if (p.smb) out.push({ kind: "smb", label: "Partage", href: `smb://${h.ip}`, copy: `\\\\${h.ip}` });
  if (p.vnc) out.push({ kind: "vnc", label: "VNC", href: `vnc://${h.ip}` });
  if (p.ssh) out.push({ kind: "ssh", label: "SSH", href: `ssh://${h.ip}` });
  if (p.winrm || p.winrm_tls) out.push({ kind: "winrm", label: "WinRM", copy: `Enter-PSSession -ComputerName ${h.ip}` });
  if (p.https || p.http) out.push({ kind: "web", label: "Web", href: `${p.https ? "https" : "http"}://${h.ip}/` });
  return out;
}

/** Fiches -> CSV (BOM, point-virgule) pour l'import du hub (#571). */
export function recordsToCsv(records, columns) {
  const esc = (v) => { v = v == null ? "" : String(v); return /[";\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v; };
  return "\ufeff" + [columns.map(esc).join(";"), ...records.map((r) => columns.map((c) => esc(r[c])).join(";"))].join("\r\n");
}
