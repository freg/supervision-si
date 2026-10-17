// Tuile « Proxys d'entrée » (livraison #776) -- logique PURE, testée sous Node (hub/tests/edgePairLib.test.mjs).
// Données : si-agent-api GET /edge (proxys, routes, contrôle DNS, problèmes et solutions).

export const DNS_STATE = {
  ok: ["DNS conforme", "ok"], a_configurer: ["DNS à configurer", "critical"], propagation: ["propagation en cours", "warning"],
  erreur: ["contrôle DNS impossible", "warning"],
};
export const dnsLabel = (d) => (d ? (DNS_STATE[d.state] || [d.state])[0] : "pas encore contrôlé");
export const dnsTone = (d) => (d ? (DNS_STATE[d.state] || ["", ""])[1] : "");

/** Alertes à montrer en tête : DNS à configurer / en erreur, puis problèmes des proxys. */
export function alerts(view) {
  const a = [];
  (view?.routes || []).forEach((r) => {
    if (r.dns && (r.dns.state === "a_configurer" || r.dns.state === "erreur")) a.push({ kind: "dns", route: r, level: DNS_STATE[r.dns.state][1], title: `${r.name} : ${dnsLabel(r.dns)}`, data: r.dns.data });
  });
  (view?.proxies || []).forEach((p) => (p.problems || []).forEach((pb) => a.push({ kind: "proxy", proxy: p, level: "critical", title: pb.title, problem: pb })));
  return a;
}

export function routeLabel(r) {
  return r.mode === "sni" ? `${r.name} (HTTPS 443, HTTP 80)` : `port ${r.front_port}${r.name ? ` (${r.name})` : ""}`;
}

/** Joignabilité du serveur interne actif vue de chaque proxy -> "ok" | "partiel" | "ko" | "inconnu". */
export function reachState(r) {
  const v = Object.values(r?.reach || {});
  if (!v.length || v.every((x) => x === undefined)) return "inconnu";
  const ok = v.filter((x) => x != null).length;
  return ok === v.length ? "ok" : ok ? "partiel" : "ko";
}

/** Les deux proxys sur deux nœuds différents ? */
export function independent(proxies) {
  const n = (proxies || []).map((p) => p.node).filter(Boolean);
  return (proxies || []).length === 2 && (n.length < 2 || n[0] !== n[1]);
}

export const emptyRoute = () => ({ id: "", mode: "sni", name: "", backend: "", candidates: "", front_port: "", send_proxy: false, enabled: true, notes: "" });
export const routeToForm = (r) => ({ ...emptyRoute(), ...r, candidates: (r.candidates || []).filter((c) => c !== r.backend).join(", ") });
export function formToRoute(f) {
  const r = { ...f, candidates: String(f.candidates || "").split(/[\s,;]+/).filter(Boolean) };
  if (r.mode === "tcp") r.front_port = Number(f.front_port) || null; else delete r.front_port;
  return r;
}
