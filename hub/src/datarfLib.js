// Tuile « Data RF » (#806) -- calculs purs (testés : tests/datarfLib.test.mjs). Données : si-agent-api /datarf.
export const BANDES = [{ nom: "2,4 GHz", de: 2400, a: 2500, canaux: [1, 6, 11, 13] }, { nom: "5 GHz", de: 5150, a: 5730, canaux: [36, 52, 100, 116, 132] }];
export const freqCanal = (c) => (c <= 14 ? 2407 + 5 * c : 5000 + 5 * c);

// Spectre [[MHz, moy, max]] -> tracés d'une bande dans une boîte w × h, échelle dB [bas, haut]
export function traces(spectre, bande, w = 600, h = 120, bas = -90, haut = -30) {
  const pts = (spectre || []).filter((p) => p[0] >= bande.de && p[0] <= bande.a);
  const x = (f) => (((f - bande.de) * w) / (bande.a - bande.de)).toFixed(1);
  const y = (db) => (h - ((Math.min(haut, Math.max(bas, db)) - bas) * h) / (haut - bas)).toFixed(1);
  const trace = (i) => pts.filter((p) => p[i] != null).map((p, k) => `${k ? "L" : "M"}${x(p[0])},${y(p[i])}`).join(" ");
  return { moy: trace(1), max: trace(2), n: pts.length, x, y };
}

// Croisement par canal : occupation au spectre (rf-spectrum) et trafic Wi-Fi (wifi-monitor) -> soupçon de brouillage non Wi-Fi
export function croiser(rf, wm) {
  const out = new Map();
  for (const c of rf?.canaux || []) out.set(c.canal, { canal: c.canal, freq: c.freq ?? freqCanal(c.canal), spectre_pct: c.occupation_pct, moy_db: c.moy_db, max_db: c.max_db });
  for (const c of wm?.canaux || []) {
    const e = out.get(c.canal) || { canal: c.canal, freq: c.freq ?? freqCanal(c.canal) };
    out.set(c.canal, { ...e, wifi_pct: c.occupation_pct ?? c.occupation_estimee_pct ?? null, wifi_estime: c.occupation_pct == null, trames_s: c.par_s, retry_pct: c.retry_pct, deauth: c.deauth, signal_max: c.signal_max });
  }
  return [...out.values()].sort((a, b) => a.canal - b.canal).map((e) => {
    const s = e.spectre_pct, w = e.wifi_pct;
    // sans écoute Wi-Fi sur ce canal, on ne conclut pas
    const lecture = s == null || w == null ? "" : s >= 30 && w < s / 2 ? "non-wifi" : s >= 30 ? "wifi" : "";
    return { ...e, lecture };
  });
}

export const LECTURE = { "non-wifi": "occupé sans trafic Wi-Fi à la hauteur : brouillage ou émetteur non Wi-Fi probable", wifi: "occupé par du Wi-Fi" };

// Bornes vues par l'écoute, signal le plus fort d'abord
export function bornes(wm) {
  return [...(wm?.bornes || [])].sort((a, b) => (b.signal_max ?? -200) - (a.signal_max ?? -200));
}

// Âge d'une mesure ISO (s) par rapport à maintenant (ms)
export function age(iso, maintenant = Date.now()) {
  const t = Date.parse(iso || "");
  return Number.isFinite(t) ? Math.max(0, Math.round((maintenant - t) / 1000)) : null;
}
export const fmtAge = (s) => (s == null ? "—" : s < 120 ? `${s} s` : s < 7200 ? `${Math.round(s / 60)} min` : `${Math.round(s / 3600)} h`);

// #807 : configuration radio d'une sonde -----------------------------------------------------------------------------
export const ROLES = [["client", "client (connexion aux SSID testés)"], ["moniteur", "moniteur (écoute passive)"], ["inactive", "inactive"]];

// Rôle proposé pour une interface jamais réglée : déjà en moniteur -> moniteur, sinon client
export const roleDefaut = (i) => (i?.type === "monitor" ? "moniteur" : "client");

// Configuration de départ : interfaces relues sur la sonde + réglage mémorisé au hub (rôles, SSID, accès du coffre)
export function configInitiale(etat, memo) {
  const inter = {};
  for (const i of etat?.interfaces || []) inter[i.nom] = memo?.interfaces?.[i.nom] || etat?.reglage?.interfaces?.[i.nom] || roleDefaut(i);
  for (const [n, r] of Object.entries(memo?.interfaces || {})) if (!(n in inter)) inter[n] = r;
  const ssids = (memo?.ssids || etat?.reglage?.ssids || []).map((s) => ({ ssid: s.ssid, acces: s.acces || "", actif: s.actif !== false, iface: s.iface || "" }));
  return { interfaces: inter, ssids };
}

// Vérifications avant envoi -> liste de messages (vide = envoyable)
export function verifierConfig(cfg) {
  const err = [], vus = new Set();
  for (const s of cfg?.ssids || []) {
    const n = (s.ssid || "").trim();
    if (!n) { err.push("un SSID est vide"); continue; }
    if (new TextEncoder().encode(n).length > 32) err.push(`SSID trop long : ${n}`);
    if (vus.has(n)) err.push(`SSID en double : ${n}`);
    vus.add(n);
    if (s.iface && cfg.interfaces?.[s.iface] !== "client") err.push(`« ${n} » demande ${s.iface}, qui n'est pas en rôle client`);
  }
  if ((cfg?.ssids || []).some((s) => s.actif) && !Object.values(cfg?.interfaces || {}).includes("client")) err.push("aucune interface en rôle client pour tester les SSID actifs");
  return err;
}

// Commande du central (directe ou relayée par le collecteur) -> {etat: attente|ok|ko, texte, charge}
export function suiviCommande(c) {
  if (!c) return { etat: "attente", texte: "envoi…", charge: null };
  if (c.status === "pending") return { etat: "attente", texte: "en attente de l'agent", charge: null };
  const r = c.result || {}, x = r.result || {};
  const charge = x.resultat !== undefined ? x.resultat : x;
  if (c.status === "done") return { etat: "ok", texte: "fait", charge };
  return { etat: "ko", texte: r.error || x.error || "échec", charge };
}

// #811 : état du réseau de sondes -----------------------------------------------------------------------------------
// Une case = {niveau: ok|attention|critique|absent, texte, action?} ; l'action dit quoi faire (et où) quand ça ne va pas.
const NIV = { ok: 0, absent: 0, attention: 1, critique: 2 };
const pire = (cases) => cases.reduce((a, c) => (NIV[c.niveau] > NIV[a.niveau] ? c : a), { niveau: "ok" });

export function caseActivite(s) {
  const a = s.age_s ?? age(s.recu);
  if (a == null) return { niveau: "critique", texte: "jamais vue", action: "Enrôler la sonde au collecteur du site (netprobe/rpi/README.md § 6)" };
  if (a <= 300) return { niveau: "ok", texte: `vue il y a ${fmtAge(a)}` };
  if (a <= 1800) return { niveau: "attention", texte: `muette depuis ${fmtAge(a)}`, action: "Relevés en retard : vérifier l'alimentation (hub USB alimenté) et le réseau de la sonde" };
  return { niveau: "critique", texte: `muette depuis ${fmtAge(a)}`, action: "Sonde arrêtée ou hors réseau : alimentation, câble / SSID d'administration, service si-agent de la sonde" };
}

export function caseRf(s) {
  const r = s.rf_spectrum;
  if (!r) return { niveau: "absent", texte: "pas de HackRF" };
  if (r.present === false) return { niveau: "critique", texte: "HackRF non détecté", action: "Sur la PortaPack : menu Mayhem › HackRF ; vérifier le câble USB et l'alimentation (hub alimenté)" };
  if (r.error) return { niveau: "attention", texte: r.error.slice(0, 80), action: "Débrancher / rebrancher le HackRF ; si « délai dépassé », réduire les balayages (--balayages 5)" };
  const occ = (r.canaux || []).filter((c) => c.occupation_pct >= 60);
  if (occ.length) return { niveau: "attention", texte: `${occ.length} canal(aux) occupé(s) au spectre`, action: "Voir le croisement spectre / Wi-Fi par canal (brouillage non Wi-Fi ?)" };
  return { niveau: "ok", texte: `${(r.canaux || []).length} canaux balayés` };
}

export function caseWifi(s) {
  const out = [];
  const m = s.wifi_monitor;
  if (m) {
    if (m.error) out.push({ niveau: "attention", texte: `écoute : ${m.error.slice(0, 60)}`, action: "Réduire la durée d'écoute par canal ou le nombre de canaux (fiche de la sonde)" });
    else if (!m.iface) out.push({ niveau: "critique", texte: "carte d'écoute absente", action: "Brancher la carte Alfa (hub USB alimenté) ; vérifier lsusb (0e8d:7612)" });
    else if (!(m.canaux || []).length) {
      const r = (m.refus || [])[0] || "";
      out.push({ niveau: "critique", texte: "écoute sans canal", action: /rf-?kill/i.test(r) ? "Radio bloquée : sudo rfkill unblock all (corrigé d'office par l'agent 0.5.92)"
        : /busy/i.test(r) ? "Carte occupée : la mettre en rôle « moniteur » dans Configuration radio (NetworkManager la relâche)" : `Cause : ${r || "inconnue"} — Configuration radio, rôle moniteur` });
    } else out.push({ niveau: "ok", texte: `${(m.canaux || []).length} canaux · ${(m.bornes || []).length} bornes` });
  }
  const p = s.wifi_probe;
  if (p) {
    if (p.link?.connected) out.push({ niveau: p.summary?.state === "critical" ? "critique" : p.summary?.state === "warning" ? "attention" : "ok",
      texte: `client ${p.link.ssid || ""} ${p.link.signal_dbm ?? ""} dBm`.trim(), action: p.summary?.state && p.summary.state !== "ok" ? "Voir les constats du lien client (signal, gigue, pertes)" : undefined });
    else out.push({ niveau: "attention", texte: "client non associé", action: "Configuration radio : interface client + SSID à tester (clé dans le coffre)" });
  }
  if (!out.length) return { niveau: "absent", texte: "pas de sonde Wi-Fi" };
  const w = pire(out);
  return { ...w, texte: out.map((c) => c.texte).join(" · "), action: w.action };
}

export function caseLan(s) {
  const p = s.path_probe;
  if (!p) return { niveau: "absent", texte: "pas de mesure de chemin" };
  if (p.error) return { niveau: "attention", texte: p.error.slice(0, 80), action: "Vérifier l'adresse IP et la passerelle de la sonde" };
  const st = p.summary?.state;
  const n = (p.paths || []).length;
  if (st === "critical") return { niveau: "critique", texte: `chemin en échec (${n} interface(s))`, action: "Bail DHCP, DNS ou HTTP en échec : voir les constats de la sonde" };
  if (st === "warning") return { niveau: "attention", texte: `chemin dégradé (${n} interface(s))`, action: "Latence ou résolution lente : voir les constats de la sonde" };
  return { niveau: "ok", texte: `chemin correct (${n} interface(s))` };
}

// Tableau : une ligne par sonde, colonnes Activité / RF / Wi-Fi / LAN, niveau global, constats de la sonde
export function etatSondes(sondes, constats = []) {
  return (sondes || []).map((s) => {
    const cols = { activite: caseActivite(s), rf: caseRf(s), wifi: caseWifi(s), lan: caseLan(s) };
    const c = (constats || []).filter((x) => String(x.message || "").startsWith(`${s.sonde} :`));
    return { sonde: s.sonde, via: s.via, ip: s.ip, ...cols, global: pire(Object.values(cols)).niveau, constats: c.length };
  }).sort((a, b) => NIV[b.global] - NIV[a.global] || a.sonde.localeCompare(b.sonde));
}
export const SYMBOLE = { ok: "✔", attention: "⚠", critique: "⛔", absent: "—" };
