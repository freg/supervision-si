// Repérage physique sur site (livraison #949) -- logique PURE, testée (hub/tests/reperageLib.test.mjs).
// Priorités de l'intervention : 1. prise → équipement → port ; 2. brassage ; 3. position (plan, photo) ; 4. couverture Wi-Fi.
export const ONGLETS = [
  { id: "prise", label: "1 · Prise / équipement", icon: "🔌" },
  { id: "brassage", label: "2 · Brassage", icon: "🧵" },
  { id: "position", label: "3 · Position", icon: "📍" },
  { id: "wifi", label: "4 · Couverture Wi-Fi", icon: "📶" },
];
export const MAC_KEY = "hub.reperage.mac";       // MAC Wi-Fi du téléphone (gardée sur l'appareil)
export const SITE_KEY = "hub.reperage.site";

/** « bon / moyen / faible / mauvais / inconnu » → variable de couleur du thème. */
export const CLASSE_COULEUR = { bon: "var(--ok)", moyen: "var(--accent)", faible: "var(--warning)", mauvais: "var(--danger)", inconnu: "var(--muted)" };

export function classeSignal(s) {
  if (s == null || s === "" || Number.isNaN(Number(s))) return "inconnu";
  const v = Number(s);
  return v >= -60 ? "bon" : v >= -70 ? "moyen" : v >= -80 ? "faible" : "mauvais";
}

/** Bande Nebula → libellé. */
export function bande(b) {
  return { band24: "2,4 GHz", band5: "5 GHz", band6: "6 GHz" }[b] || b || "";
}

/** Libellé court d'un client (nom > IP > fabricant > MAC). */
export function libelleClient(c) {
  if (!c) return "";
  return c.nom || c.ip || c.fabricant || c.mac || "?";
}

/** Où est branché un client, en une ligne : « GS2220-50HP-1 port 12 · VLAN 20 » ou « borne Studio · Campus_Numeria · -58 dBm ». */
export function ouEstBranche(c) {
  if (!c) return "";
  if (c.type === "filaire") return `${c.commutateur || c.commutateur_id || "commutateur ?"} port ${c.port ?? "?"}${c.vlan ? ` · VLAN ${c.vlan}` : ""}`;
  if (c.type === "wifi") return `borne ${c.borne || c.borne_id || "?"}${c.ssid ? ` · ${c.ssid}` : ""}${c.signal != null ? ` · ${c.signal} dBm` : ""}${c.bande ? ` · ${bande(c.bande)}` : ""}`;
  return c.vlan ? `VLAN ${c.vlan} (port inconnu)` : "connexion inconnue";
}

/** Vue « brassage » : pour chaque commutateur, ports triés avec client(s) et prise(s) déclarée(s). */
export function tableBrassage(inventaire, prises) {
  const parMac = new Map((inventaire?.clients || []).map((c) => [c.mac, c]));
  const prisesParPort = new Map();
  for (const p of prises || []) {
    if (p.commutateur && p.port != null) {
      const k = `${p.commutateur}#${p.port}`;
      prisesParPort.set(k, [...(prisesParPort.get(k) || []), p]);
    }
  }
  const out = [];
  for (const sw of inventaire?.commutateurs || []) {
    const ports = Object.entries(sw.ports || {}).map(([num, macs]) => ({
      port: Number.isNaN(Number(num)) ? num : Number(num),
      clients: macs.map((m) => parMac.get(m)).filter(Boolean),
      prises: prisesParPort.get(`${sw.nom}#${num}`) || [],
    }));
    ports.sort((a, b) => (typeof a.port === "number" && typeof b.port === "number" ? a.port - b.port : String(a.port).localeCompare(String(b.port))));
    out.push({ id: sw.id, nom: sw.nom, ports });
  }
  // prises déclarées sur un commutateur sans client vu (port vide ou commutateur inconnu de Nebula)
  const orphelines = (prises || []).filter((p) => p.commutateur && p.port != null && !out.some((s) => s.nom === p.commutateur && s.ports.some((x) => String(x.port) === String(p.port))));
  return { commutateurs: out, orphelines };
}

/** Anomalies de brassage : prise déclarée sur un port où Nebula voit un autre équipement que celui attendu, ou deux prises sur le même port. */
export function anomaliesBrassage(table) {
  const out = [];
  for (const sw of table.commutateurs) {
    for (const p of sw.ports) {
      if (p.prises.length > 1) out.push({ genre: "doublon", texte: `${sw.nom} port ${p.port} : ${p.prises.length} prises déclarées (${p.prises.map((x) => x.prise).join(", ")})` });
      for (const pr of p.prises) {
        if (pr.mac && p.clients.length && !p.clients.some((c) => c.mac === pr.mac)) {
          out.push({ genre: "equipement", texte: `prise ${pr.prise} (${sw.nom} port ${p.port}) : attendu ${pr.equipement || pr.mac}, vu ${p.clients.map(libelleClient).join(", ")}` });
        }
      }
    }
  }
  return out;
}

/** Coordonnées écran → fraction bornée (même logique que le plan Nebula). */
export function versFraction(px, py, box) {
  if (!box || !box.width || !box.height) return null;
  return { x: Math.min(1, Math.max(0, (px - box.left) / box.width)), y: Math.min(1, Math.max(0, (py - box.top) / box.height)) };
}

/** Texte de synthèse d'un relevé de couverture. */
export function texteReleve(r) {
  const s = r.rssi_mobile != null ? `${r.rssi_mobile} dBm (téléphone)` : r.signal != null ? `${r.signal} dBm (vu par la borne)` : "signal inconnu";
  return `${r.borne || "borne ?"} · ${s}${r.bande ? ` · ${bande(r.bande)}` : ""}${r.canal ? ` · canal ${r.canal}` : ""}${r.note ? ` — ${r.note}` : ""}`;
}

/** Résumé de couverture : par borne, nombre de relevés et signal médian ; part de relevés faibles / mauvais. */
export function syntheseCouverture(releves) {
  const parBorne = new Map();
  let faibles = 0;
  for (const r of releves || []) {
    const v = r.rssi_mobile != null ? r.rssi_mobile : r.signal;
    const k = r.borne || "?";
    const e = parBorne.get(k) || { borne: k, n: 0, valeurs: [] };
    e.n += 1;
    if (v != null) e.valeurs.push(Number(v));
    parBorne.set(k, e);
    if (["faible", "mauvais"].includes(classeSignal(v))) faibles += 1;
  }
  const bornes = [...parBorne.values()].map((e) => {
    const v = e.valeurs.slice().sort((a, b) => a - b);
    return { borne: e.borne, n: e.n, median: v.length ? v[Math.floor(v.length / 2)] : null };
  }).sort((a, b) => b.n - a.n);
  return { bornes, total: (releves || []).length, faibles };
}

/** Réduction d'une photo côté téléphone : dimensions cibles (plus grand côté ≤ max). */
export function tailleReduite(w, h, max = 1600) {
  if (!w || !h) return { w: 0, h: 0 };
  const k = Math.min(1, max / Math.max(w, h));
  return { w: Math.round(w * k), h: Math.round(h * k) };
}

/** Radar : barre de signal 0..1 à partir d'un RSSI (-90 → 0, -40 → 1). */
export function niveauSignal(rssi) {
  if (rssi == null || Number.isNaN(Number(rssi))) return 0;
  return Math.min(1, Math.max(0, (Number(rssi) + 90) / 50));
}

/** Lignes du dernier balayage → affichage : plus forte d'abord, SSID ou BSSID, distance arrondie. */
export function lignesRadar(bornes) {
  return (bornes || []).slice().sort((a, b) => b.rssi - a.rssi).map((b) => ({
    cle: b.bssid, nom: (b.ssid || b.bssid) + (b.connecte ? " ● connecté" : ""), bssid: b.bssid, rssi: b.rssi, niveau: niveauSignal(b.rssi), classe: classeSignal(b.rssi),
    bande: bande(b.bande), canal: b.canal, distance: b.distance_m != null ? (b.distance_m < 10 ? `${String(b.distance_m).replace(".", ",")} m` : `${Math.round(b.distance_m)} m`) : "—",
  }));
}

/** Âge d'un balayage en secondes, lisible. */
export function ageBalayage(at, maintenant) {
  if (!at) return "jamais";
  const s = Math.max(0, Math.round((maintenant || Date.now() / 1000) - at));
  return s < 60 ? `il y a ${s} s` : s < 3600 ? `il y a ${Math.round(s / 60)} min` : `il y a ${Math.round(s / 3600)} h`;
}
