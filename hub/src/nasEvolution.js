// #927 : potentiel d'évolution d'un NAS -- baies (occupées / libres), espace non alloué de la réserve, capacité utile
// selon le RAID, et conseils chiffrés pour agrandir les volumes (sans matériel, disques ajoutés, disques plus grands,
// unité d'extension). Module pur, testé par hub/tests/nasEvolution.test.mjs. Entrée : un NAS tel que relevé par la
// sonde nas-snmp ({systeme, disques, raid, reserves, volumes, baies?}).

const TO = 1e12;

/** Capacité lisible (unités décimales des fabricants de disques, virgule décimale). */
export const taille = (o) => (o == null || !isFinite(o) ? "—" : o >= TO ? `${(o / TO).toFixed(1).replace(".", ",")} To` : `${Math.round(o / 1e9)} Go`);

/** Nombre de baies déduit du nom QNAP (TS-883XU -> 8, TS-h1886XU -> 18, TS-453D -> 4) ; null si non reconnu. */
export function baiesDuModele(modele) {
  const m = String(modele || "").toUpperCase().match(/\b(?:TS|TVS|TDS|TES|ES|HS|TBS)-?H?(\d{3,4})/);
  if (!m) return null;
  const n = parseInt(m[1].length === 3 ? m[1][0] : m[1].slice(0, 2), 10);
  return n > 0 ? n : null;
}

/** Disque SSD (ou M.2) d'après son modèle. */
export const estSsd = (d) => /ssd|nvme|m\.2/i.test(String(d?.modele || ""));

/** Capacité utile d'un groupe RAID de `n` disques de capacité `c` (null si configuration impossible). */
export function utile(niveau, n, c) {
  const l = String(niveau || "").toLowerCase();
  if (!c || !n) return null;
  if (l === "5") return n >= 3 ? (n - 1) * c : null;
  if (l === "6") return n >= 4 ? (n - 2) * c : null;
  if (l === "1") return n === 2 ? c : null;
  if (l === "10") return n >= 4 && n % 2 === 0 ? (n / 2) * c : null;
  if (l === "0" || l === "single" || l === "jbod") return n * c;
  return null;
}

const SANS_REDONDANCE = ["single", "jbod", "0"];
const TAILLES = [16, 20, 24].map((x) => x * TO);   // capacités courantes des disques NAS 3,5"

/**
 * Potentiel d'évolution : { baies, source, libres:[n°], occupees:[{baie, type, modele}], reserve:{total, libre},
 * volumes:{nom: taille max atteignable}, conseils:[{cle, titre, detail, gain, ton}] }.
 */
export function evolution(nas) {
  const disques = nas?.disques || [];
  const baies = Number(nas?.baies) > 0 ? Number(nas.baies) : baiesDuModele(nas?.systeme?.modele);
  const source = Number(nas?.baies) > 0 ? "réglage" : baies ? "modèle" : null;
  const num = (d) => parseInt(d.emplacement, 10);
  const internes = disques.filter((d) => !baies || (num(d) >= 1 && num(d) <= baies));
  const prises = new Set(internes.map(num));
  const libres = baies ? Array.from({ length: baies }, (_, i) => i + 1).filter((b) => !prises.has(b)) : [];
  const occupees = internes.map((d) => ({ baie: num(d), type: estSsd(d) ? "SSD" : "HDD", modele: d.modele, octets: d.octets }))
    .sort((a, b) => a.baie - b.baie);

  const reserves = nas?.reserves || [];
  const total = reserves.reduce((s, r) => s + (Number(r.octets) || 0), 0);
  const libre = reserves.reduce((s, r) => s + (Number(r.libre_octets) || 0), 0);
  const volumes = {};
  for (const v of nas?.volumes || []) {
    // une seule réserve : tout volume peut grandir de l'espace qu'elle a de libre ; plusieurs : réserve du volume inconnue
    if (reserves.length === 1 && v.ko != null) volumes[v.nom] = v.ko * 1024 + libre;
  }

  const conseils = [];
  const ajoute = (cle, ton, titre, detail, gain = null) => conseils.push({ cle, ton, titre, detail, gain });

  // 1. Sans matériel : espace non alloué de la réserve
  if (reserves.length && libre > 0) {
    ajoute("reserve", "good", `Étendre un volume tout de suite, sans matériel : ${taille(libre)} libres dans la réserve`,
      "Stockage et clichés instantanés › choisir le volume › Gérer › Redimensionner. En ligne, sans arrêt. Garder 10 à 20 % "
      + "de la réserve libres pour les clichés instantanés.", libre);
  }
  const alloue = (nas?.volumes || []).reduce((s, v) => s + (Number(v.ko) || 0) * 1024, 0);
  if (total && alloue > total * 1.02) {
    ajoute("surallocation", "warn", `Volumes « légers » plus grands que la réserve (${taille(alloue)} promis pour ${taille(total)})`,
      "Les volumes à allocation dynamique peuvent promettre plus que la réserve n'a : surveiller la réserve, pas seulement les volumes.");
  }

  // 2. Groupe RAID des données : disques durs, capacité du plus petit
  const hdd = disques.filter((d) => !estSsd(d) && Number(d.octets) > 0);
  const c = hdd.length ? Math.min(...hdd.map((d) => Number(d.octets))) : null;
  const raid = (nas?.raid || []).find((r) => !SANS_REDONDANCE.includes(String(r.niveau || "").toLowerCase())) || null;
  const niveau = raid ? String(raid.niveau) : null;
  const n = hdd.length;
  const actuel = raid ? utile(niveau, n, c) : null;
  const libresHdd = libres.length;

  if (raid && c && libresHdd > 0) {
    const k = libresHdd;
    const cible = niveau === "1" ? "5" : niveau;                        // RAID 1 : migration en RAID 5 en ajoutant des disques
    const apres = utile(cible, n + k, c);
    if (apres && actuel != null) {
      const parDisque = utile(cible, n + 1, c) != null && utile(cible, n, c) != null ? utile(cible, n + 1, c) - utile(cible, n, c) : null;
      ajoute("ajout", "good", `Ajouter ${k} disque${k > 1 ? "s" : ""} de ${taille(c)} dans ${k > 1 ? "les baies libres" : "la baie libre"} (${libres.join(", ")})`,
        `RAID ${niveau}${cible !== niveau ? ` migré en RAID ${cible}` : ""} : ${taille(actuel)} utiles → ${taille(apres)}`
        + `${parDisque ? ` (${taille(parDisque)} de plus par disque)` : ""}. Gérer › Étendre le groupe RAID (en ligne, plusieurs heures à `
        + "quelques jours), puis la réserve et les volumes grandissent. Disques de même capacité : seule celle du plus petit compte.", apres - actuel);
    }
    if ((cible === "5") && n + k >= 6 && c >= 8 * TO) {
      const r6 = utile("6", n + k, c);
      ajoute("raid6", "warn", `À ${n + k} disques de ${taille(c)}, passer en RAID 6`,
        `RAID 6 tolère deux pannes (${taille(r6)} utiles sur ${n + k} disques). En RAID 5, la reconstruction d'un disque de `
        + `${taille(c)} dure environ un jour, pendant lequel une seconde panne ferait tout perdre.`, r6 != null && actuel != null ? r6 - actuel : null);
    }
  }

  // 3. Disques plus grands, sans baie supplémentaire
  if (raid && c && actuel != null) {
    for (const t of TAILLES.filter((x) => x > c * 1.2).slice(0, 2)) {
      const u = utile(niveau, n, t);
      if (u) ajoute(`remplacement-${t / TO}`, "neutral", `Remplacer les ${n} disques par des ${taille(t)}, un par un`,
        `${taille(actuel)} → ${taille(u)} utiles sans occuper de baie. Un disque à la fois, reconstruction entre chaque `
        + "(environ un jour par disque), puis Gérer › Étendre la capacité. Vérifier la liste de compatibilité QNAP du modèle.", u - actuel);
    }
  }

  // 4. SSD seul dans une baie 3,5"
  for (const d of occupees.filter((x) => x.type === "SSD")) {
    ajoute(`ssd-${d.baie}`, "warn", `SSD seul en baie ${d.baie} (${d.modele || "?"})`,
      "Sans redondance, et il occupe une baie 3,5\" : s'il sert de cache, une carte M.2 dans un emplacement PCIe libre le "
      + "remplace et libère la baie pour un disque de données ; s'il porte des données, les sauvegarder.");
  }

  // 5. Plus de baie libre / modèle inconnu
  if (baies && libres.length === 0) {
    ajoute("extension", "neutral", "Toutes les baies sont occupées",
      "Remplacer par des disques plus grands, ou ajouter une unité d'extension (boîtier de disques relié par une carte PCIe : "
      + "modèles compatibles dans la liste QNAP du NAS).");
  }
  if (!baies) {
    ajoute("baies-inconnues", "neutral", "Nombre de baies inconnu (modèle non reconnu)",
      "Préciser « baies » pour ce NAS dans /etc/si-agent/nas-snmp.json sur l'hôte de l'agent.");
  }
  return { baies, source, libres, occupees, reserve: { total, libre }, volumes, raid: niveau, utile: actuel, conseils };
}
