// Tuile « htop » (#800) -- calculs purs (testés : tests/htopLib.test.mjs). Données : relais si-htop via si-agent-api /htop.
export const go = (n) => (n == null ? "—" : n >= 1e12 ? (n / 1e12).toFixed(2) + " To" : (n / 1e9).toFixed(1) + " Go");
export const num = (v, s = "") => (v == null ? "—" : `${Math.round(v * 10) / 10}${s}`);
export const pctOf = (a, b) => (a != null && b ? Math.round((1000 * a) / b) / 10 : null);

// Gravité d'une valeur face à un seuil : critique au-delà du seuil critique, attention au-delà du seuil, « proche » à 80 %
export function niveau(v, seuil, critique) {
  if (v == null || seuil == null) return { tone: "", label: "" };
  if (critique != null && v >= critique) return { tone: "critical", label: "critique" };
  if (v >= seuil) return { tone: "warning", label: "au seuil" };
  if (v >= 0.8 * seuil) return { tone: "near", label: "proche" };
  return { tone: "", label: "" };
}

// Gravité d'un hôte : la pire de ses mesures (muet = critique)
export function niveauHote(h, s = {}) {
  if (h.muet) return "critical";
  const t = [niveau(h.cpu, s.cpu, 98), niveau(h.memoire_pct, s.memoire, 97), niveau(h.swap_pct, s.swap, 90), niveau(h.iowait, s.iowait, 50),
    niveau(h.steal, s.steal, 40), niveau(h.charge_coeur, s.charge, 4)].map((x) => x.tone);
  return t.includes("critical") ? "critical" : t.includes("warning") ? "warning" : t.includes("near") ? "near" : "";
}

const VAL = { nom: (h) => h.nom, cpu: (h) => h.cpu, mem: (h) => h.memoire_pct, swap: (h) => h.swap_pct, iowait: (h) => h.iowait, steal: (h) => h.steal,
  charge: (h) => h.charge_coeur, disque: (h) => maxDisque(h), age: (h) => h.age_s };
export function maxDisque(h) {
  const v = [...(h.disques || []).map((d) => pctOf(d[2], d[1])), ...(h.pools || []).map((z) => pctOf(z[2], z[1]))].filter((x) => x != null);
  return v.length ? Math.max(...v) : null;
}
export function trier(hotes, col = "cpu", dir = -1) {
  const f = VAL[col] || VAL.cpu;
  return [...hotes].sort((a, b) => {
    const x = f(a), y = f(b);
    if (x == null && y == null) return 0;
    if (x == null) return 1;
    if (y == null) return -1;
    return typeof x === "string" ? dir * x.localeCompare(y) : dir * (x - y);
  });
}

// Invités rangés sous leur Proxmox (rapprochés par le nom déclaré dans /etc/pve) ; le reste à la fin
export function grouper(hotes, col, dir) {
  const t = trier(hotes, col, dir);
  const parent = {};
  for (const p of t.filter((h) => h.nature === "pve")) for (const g of p.invites || []) if (g[1]) parent[String(g[1]).toLowerCase()] = p.nom;
  const out = [];
  for (const p of t.filter((h) => h.nature === "pve")) {
    out.push({ ind: 0, h: p });
    for (const h of t) if (h.nature !== "pve" && parent[h.nom.toLowerCase()] === p.nom) out.push({ ind: 1, h });
  }
  return out.concat(t.filter((h) => h.nature !== "pve" && !parent[h.nom.toLowerCase()]).map((h) => ({ ind: 0, h })));
}

// Invités de tous les Proxmox : [{pve, vmid, nom, type, coeurs, mem, limite, pic_coeurs, pic_mem}]
export function invites(hotes) {
  const out = [];
  for (const p of hotes.filter((h) => h.nature === "pve")) {
    for (const g of p.invites || []) {
      const pic = (p.pics_invites || {})[String(g[0])] || [];
      out.push({ pve: p.nom, vmid: g[0], nom: g[1] || "", type: g[2], coeurs: g[4], mem: g[6] ?? g[5], limite: g[7] ?? null,
        pic_coeurs: pic[0] ?? g[4], pic_mem: pic[1] ?? g[6] ?? g[5] });
    }
  }
  return out;
}

// Projection : la cible reçoit les invités choisis -> CPU (pic et p95 sur 24 h), mémoire hors ARC au pic, mémoire allouée.
// Hypothèse : cœurs de même puissance sur les deux nœuds ; les invités déjà répliqués occupent déjà leur place disque.
export function projeter(hotes, cible, choix) {
  const c = hotes.find((h) => h.nom === cible);
  if (!c || !c.ncpu || !(c.memoire || [])[0]) return null;
  const sel = invites(hotes).filter((g) => g.pve !== cible && choix.some((x) => x.pve === g.pve && String(x.vmid) === String(g.vmid)));
  const pic = c.pic_24h || {};
  const total = c.memoire[0];
  const coeurs = sel.reduce((a, g) => a + (g.pic_coeurs || 0), 0);
  const mem = sel.reduce((a, g) => a + (g.pic_mem || 0), 0);
  const cpuPic0 = pic.cpu ?? c.cpu ?? 0, cpuP950 = pic.cpu_p95 ?? c.cpu ?? 0, memPic0 = pic.memoire ?? c.memoire_pct ?? 0;
  const alloue0 = (c.invites || []).reduce((a, g) => a + (g[7] || 0), 0);
  const alloue = alloue0 + sel.reduce((a, g) => a + (g.limite || 0), 0);
  const r = {
    invites: sel, coeurs: Math.round(coeurs * 100) / 100, mem,
    cpu_pic: [cpuPic0, Math.round((cpuPic0 + (100 * coeurs) / c.ncpu) * 10) / 10],
    cpu_p95: [cpuP950, Math.round((cpuP950 + (100 * coeurs) / c.ncpu) * 10) / 10],
    mem_pic: [memPic0, Math.round((memPic0 + (100 * mem) / total) * 10) / 10],
    alloue: [pctOf(alloue0, total), pctOf(alloue, total)], minutes: pic.minutes || 0,
  };
  const pire = Math.max(r.cpu_p95[1], r.mem_pic[1]);   // tient : p95 et mémoire < 80 %, pic < 90 % ; juste : < 90 / < 100
  r.verdict = pire < 80 && r.cpu_pic[1] < 90 ? "ok" : pire < 90 && r.cpu_pic[1] < 100 ? "juste" : "non";
  return r;
}

// Tracé d'une courbe (valeurs 0..max) dans une boîte w × h ; trous (null) coupent le tracé
export function sparkPath(values, w = 160, h = 32, max = 100) {
  const n = values.length;
  if (!n) return "";
  let d = "", haut = false;
  values.forEach((v, i) => {
    if (v == null) { haut = false; return; }
    const x = n === 1 ? w : (i * w) / (n - 1), y = h - (Math.min(max, Math.max(0, v)) * h) / max;
    d += `${haut ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)} `;
    haut = true;
  });
  return d.trim();
}
