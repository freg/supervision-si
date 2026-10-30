// #937 : tuile « Sauvegardes » -- module pur (tons, textes, tri, filtres, export) ; testé par tests/sauvegardesLib.test.mjs.

/** Ton CSS (np-tone) d'un état d'aperçu. */
export function ton(etat) {
  return { ok: "good", attention: "warn", critique: "bad", erreur: "bad", jamais: "warn", "non relevé": "neutral", info: "neutral" }[etat] || "neutral";
}

/** Urgence du mini bouton de détail (BoutonDetail) selon l'état. */
export function urgence(etat) {
  return etat === "critique" || etat === "erreur" ? "critique" : etat === "attention" || etat === "jamais" ? "alerte" : "info";
}

/** Libellé lisible d'un état. */
export function libelle(etat) {
  return { ok: "à jour", attention: "à surveiller", critique: "critique", erreur: "injoignable / en erreur", jamais: "jamais sauvegardé", "non relevé": "non relevé" }[etat] || etat || "—";
}

const UN = (v, d = 1) => (v == null ? "—" : Number(v).toFixed(d).replace(".", ","));

/** Octets -> Go / To (virgule française). */
export function to(o) {
  if (o == null) return "—";
  if (o >= 1e12) return `${UN(o / 1e12)} To`;
  if (o >= 1e9) return `${UN(o / 1e9)} Go`;
  if (o >= 1e6) return `${UN(o / 1e6, 0)} Mo`;
  return `${Math.round(o / 1e3)} ko`;
}

/** Âge en jours -> « il y a 3 j » / « aujourd'hui ». */
export function ageTexte(j) {
  if (j == null) return "jamais";
  if (j < 1) return "aujourd'hui";
  if (j < 2) return "hier";
  return `il y a ${Math.round(j)} j`;
}

/** Texte complet (copiable) d'une ligne de poste : raison, destinations, PBS -- pour le mini bouton de détail. */
export function detailPoste(p) {
  if (!p) return "";
  const l = [`${p.hostname} (${p.agent_id}) : ${libelle(p.etat)}`];
  if (p.raison) l.push(`• ${p.raison}`);
  if (p.at) l.push(`• dernière sauvegarde de conf : ${p.at} (${ageTexte(p.age_j)})`);
  if (p.archive) l.push(`• archive : ${p.archive}${p.octets != null ? ` (${to(p.octets)})` : ""} -- ${p.confs} conf(s), ${p.montages} montage(s)`);
  if (p.destinations_ok?.length) l.push(`• destinations écrites : ${p.destinations_ok.join(", ")}`);
  if (p.destinations_ko?.length) l.push(`• destinations en échec : ${p.destinations_ko.join(", ")}`);
  if (p.pbs) l.push(p.pbs.ok ? `• PBS : poussée OK (${p.pbs.snapshot || "instantané"})` : `• PBS : poussée en échec -- ${p.pbs.erreur || "?"}`);
  else l.push("• PBS : jamais poussé vers pbs10");
  return l.join("\n");
}

/** Filtre des postes : « tous » | « a-traiter » (critique, jamais, attention) | « ok ». */
export function filtrerPostes(postes, filtre) {
  const l = postes || [];
  if (filtre === "a-traiter") return l.filter((p) => p.etat !== "ok");
  if (filtre === "ok") return l.filter((p) => p.etat === "ok");
  return l;
}

/** Récapitulatif host/VM : une ligne par hôte de secours { hote, copies, echecs, absentes, libre, plus_vieille_h, etat }. */
export function etatHote(h) {
  if (!h) return "non relevé";
  if (h.erreur) return "erreur";
  if (h.echecs > 0 || h.absentes > 0) return "critique";
  if (h.plus_vieille_h != null && h.plus_vieille_h > 48) return "attention";
  return "ok";
}

/** #939 : état d'un hôte BackupPC (sonde backuppc) : jamais / critique (> 7 j ou échec sans réussite récente) / attention / ok. */
export function etatBackuppcHote(h) {
  if (!h) return "non relevé";
  if (h.age_h == null) return "jamais";
  if (h.age_h > 7 * 24) return "critique";
  if (h.age_h > 48 || h.erreur) return "attention";
  return "ok";
}

/** #939 : texte copiable d'un hôte BackupPC. */
export function detailBackuppc(h) {
  if (!h) return "";
  const j = (t) => (t ? new Date(t * 1000).toLocaleString("fr-FR") : "—");
  const l = [`${h.host} : ${libelle(etatBackuppcHote(h))}`, `• état : ${h.etat}${h.raison ? ` (${h.raison})` : ""}${h.en_cours ? " -- sauvegarde EN COURS" : ""}`];
  if (h.erreur) l.push(`• dernière erreur : ${h.erreur}`);
  l.push(`• dernière réussie : ${j(h.derniere_bonne)}${h.age_h != null ? ` (${ageTexte(h.age_h / 24)})` : ""}`, `• dernière pleine : ${j(h.derniere_pleine)} · dernière incrémentale : ${j(h.derniere_incr)}`,
    `• ${h.sauvegardes ?? 0} sauvegarde(s) conservée(s) dont ${h.pleines ?? 0} pleine(s)${h.taille ? ` · dernière : ${to(h.taille)}` : ""}${h.xfer_errs ? ` · ${h.xfer_errs} erreur(s) de transfert` : ""}`);
  if (h.user) l.push(`• utilisateur BackupPC : ${h.user}`);
  return l.join("\n");
}

/** #939 : conseil pour une erreur BackupPC connue (texte + commandes à lancer sur le serveur BackupPC, lecture seule). */
export function conseilBackuppc(erreur, host) {
  const e = String(erreur || "");
  if (/no files dumped/i.test(e)) return { texte: `« ${e} » : le transfert a réussi à se connecter mais n'a rien ramené -- partage/chemin absent sur l'hôte, droits de l'utilisateur de sauvegarde, ou rsync/tar qui échoue côté hôte. Vérifier le XferLOG puis le chemin sur l'hôte.`,
    commandes: [`sudo -u backuppc /usr/share/backuppc/bin/BackupPC_zcat $(ls -t /var/lib/backuppc/pc/${host}/XferLOG.*.z | head -1) | tail -40`, `grep -E 'RsyncShareName|TarShareName|XferMethod|ClientNameAlias' /etc/backuppc/${host}.pl`] };
  if (/no ping/i.test(e)) return { texte: "injoignable au moment de la sauvegarde (hôte éteint, nom DNS, pare-feu ICMP) : vérifier la résolution et le ping depuis le serveur BackupPC.", commandes: [`ping -c 3 ${host}`, `grep -E 'PingCmd|ClientNameAlias|BackupsDisable' /etc/backuppc/${host}.pl /etc/backuppc/config.pl`] };
  if (/permission denied|auth|ssh/i.test(e)) return { texte: "accès refusé : clé SSH du serveur BackupPC non acceptée par l'hôte, ou compte verrouillé.", commandes: [`sudo -u backuppc ssh -o BatchMode=yes root@${host} echo ok`] };
  if (/disk too full|disk full/i.test(e)) return { texte: "pool plein : BackupPC refuse de sauvegarder au-delà de DfMaxUsagePct -- libérer le pool (anciennes sauvegardes, hôtes retirés) ou agrandir le disque.", commandes: ["df -h /var/lib/backuppc", "grep -E 'DfMaxUsagePct|FullKeepCnt|IncrKeepCnt' /etc/backuppc/config.pl"] };
  if (!e) return null;
  return { texte: "voir le XferLOG et le journal de l'hôte sur le serveur BackupPC.", commandes: [`ls -t /var/lib/backuppc/pc/${host}/ | head`, `sudo -u backuppc /usr/share/backuppc/bin/BackupPC_zcat $(ls -t /var/lib/backuppc/pc/${host}/XferLOG.*.z | head -1) | tail -40`] };
}

/** #939 : état d'un NAS depuis l'aperçu (SNMP + SSH). */
export function detailNas(n) {
  if (!n) return "";
  const l = [`${n.nom} : ${libelle(n.etat)}`];
  for (const v of n.volumes || []) l.push(`• volume ${v.nom} : ${v.pct != null ? `${String(v.pct).replace(".", ",")} %` : "?"}`);
  if (n.ssh?.ok === false) l.push(`• SSH : ${n.ssh.erreur}`);
  for (const s of n.snapshots || []) l.push(`• snapshots ${s.volume} : ${s.nombre}${s.dernier_age_h != null ? `, dernier il y a ${Math.round(s.dernier_age_h)} h` : ""}`);
  for (const t of n.timemachine || []) l.push(`• Time Machine « ${t.machine} » : dernière écriture il y a ${Math.round(t.age_h)} h${t.ko ? ` (${to(t.ko * 1024)})` : ""}`);
  for (const r of n.ssh?.raid || []) l.push(`• ${r.dev} ${r.niveau} : ${r.degrade ? "DÉGRADÉ" : "ok"} ${r.etat || ""}`);
  for (const a of n.ssh?.alertes || []) l.push(`• ${a}`);
  return l.join("\n");
}

/** Points à traiter en premier (vue d'ensemble) : liste ordonnée de { etat, texte, lien? }. */
export function points(ap) {
  if (!ap) return [];
  const out = [];
  for (const p of ap.postes || []) {
    if (p.etat === "critique") out.push({ etat: "critique", texte: `${p.hostname} : ${p.raison}`, onglet: "postes" });
  }
  for (const b of ap.pbs || []) {
    if (b.etat === "erreur") out.push({ etat: "critique", texte: `PBS ${b.serveur} : ${b.erreur}`, onglet: "pbs" });
    for (const a of b.alertes || []) out.push({ etat: b.etat === "critique" ? "critique" : "attention", texte: `PBS ${b.serveur} : ${a}`, onglet: "pbs" });
  }
  for (const h of ap.copies?.hotes || []) {
    const e = etatHote(h);
    if (e !== "ok") out.push({ etat: e === "erreur" ? "critique" : e, texte: `copies ${h.hote} : ${h.erreur || `${h.echecs} échec(s), ${h.absentes} absente(s)`}`, onglet: "copies" });
  }
  if (ap.copies?.invites?.critique) out.push({ etat: "critique", texte: `${ap.copies.invites.critique} VM/CT sans copie fraîche`, onglet: "copies" });
  for (const n of ap.nas || []) {
    if (n.etat !== "ok") out.push({ etat: n.etat === "erreur" ? "critique" : n.etat, texte: `NAS ${n.nom} : ${n.erreur || (n.ssh?.alertes || [])[0] || "volume presque plein"}`, onglet: "nas" });
  }
  for (const b of ap.backuppc?.serveurs || []) {       // #939
    if (b.erreur) out.push({ etat: "critique", texte: `BackupPC ${b.serveur} : ${b.erreur}`, onglet: "backuppc" });
    for (const e of b.echecs_detail || []) out.push({ etat: e.age_h == null || e.age_h > 7 * 24 ? "critique" : "attention", texte: `BackupPC ${e.host} : ${e.erreur || "échec"}`, onglet: "backuppc" });
    if (b.pool_pct >= 85) out.push({ etat: b.pool_pct >= 95 ? "critique" : "attention", texte: `BackupPC ${b.serveur} : pool à ${String(b.pool_pct).replace(".", ",")} %`, onglet: "backuppc" });
  }
  for (const p of ap.postes || []) {
    if (p.etat === "jamais") out.push({ etat: "attention", texte: `${p.hostname} : jamais sauvegardé`, onglet: "postes" });
    else if (p.etat === "attention") out.push({ etat: "attention", texte: `${p.hostname} : ${p.raison}`, onglet: "postes" });
  }
  const rang = { critique: 0, attention: 1 };
  return out.sort((a, b) => (rang[a.etat] ?? 2) - (rang[b.etat] ?? 2));
}

/** Export CSV (séparateur ; pour Excel français) des postes. */
export function csvPostes(postes) {
  const esc = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  const lignes = [["poste", "agent", "etat", "derniere_sauvegarde", "age_j", "archive", "octets", "confs", "montages", "destinations_ok", "destinations_ko", "pbs"].join(";")];
  for (const p of postes || []) {
    lignes.push([p.hostname, p.agent_id, p.etat, p.at || "", p.age_j != null ? String(p.age_j).replace(".", ",") : "", p.archive || "", p.octets ?? "", p.confs, p.montages,
      (p.destinations_ok || []).join(","), (p.destinations_ko || []).join(","), p.pbs ? (p.pbs.ok ? "ok" : "échec") : "jamais"].map(esc).join(";"));
  }
  return lignes.join("\r\n");
}

export const ONGLETS = [["ensemble", "Vue d'ensemble"], ["postes", "Postes"], ["pbs", "PBS (pbs10)"], ["copies", "Copies host / VM"], ["backuppc", "BackupPC"], ["nas", "NAS QNAP"]];
