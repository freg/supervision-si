// #935 : propositions et conseils sur les points critiques d'un poste, à partir du diagnostic poste-windows
// (évènements, plantages, disques/SMART, volumes, stabilité), de l'antivirus relevé et des tests de charge
// (dernier + historique, pour l'intermittence). Module pur, testé par hub/tests/conseilsDiagnostic.test.mjs.
// Chaque conseil : { code, niveau: critique|alerte|info, titre, constat, action }. Classés critique > alerte > info.

const POIDS = { critique: 0, alerte: 1, info: 2 };
const sain = (s) => ["healthy", "ok", "normal", "online"].includes(String(s || "").toLowerCase());

/** Cherche dans les journaux regroupés une source/texte (insensible à la casse) ; renvoie l'entrée au plus fort nombre. */
function journal(evts, motif) {
  const re = new RegExp(motif, "i");
  const hits = (evts || []).filter((e) => re.test(`${e.source} ${e.id} ${e.exemple || ""}`));
  if (!hits.length) return null;
  return hits.reduce((a, b) => ((b.nombre || 0) > (a.nombre || 0) ? b : a));
}

/**
 * Conseils à partir du détail d'un poste et de l'historique des tests de charge.
 * @param detail { poste, alertes, diagnostic, reinstallation, charge }
 * @param histo  [{at, data}] relevés poste-charge (le plus récent d'abord)
 */
export function conseils(detail, histo) {
  const d = (detail && detail.diagnostic) || {};
  const re = (detail && detail.reinstallation) || {};
  const cat = d.categories || {};
  const out = [];
  const add = (code, niveau, titre, constat, action) => out.push({ code, niveau, titre, constat, action });

  // --- Antivirus ---
  const av = re.antivirus || [];
  if (av.length === 0 || !av.some((a) => a.actif)) {
    add("antivirus", "critique", "Aucun antivirus actif",
      av.length ? "Antivirus présent mais inactif." : "Aucun antivirus détecté ; Windows Defender semble désactivé.",
      "Réactiver Windows Defender (ou installer un antivirus) et vérifier qu'il n'a pas été désactivé par une stratégie ou un logiciel tiers.");
  } else if (av.some((a) => a.actif && a.a_jour === false)) {
    add("antivirus-maj", "alerte", "Antivirus pas à jour", "L'antivirus actif n'est pas à jour.", "Mettre à jour les signatures de l'antivirus.");
  }

  // --- Disques (SMART, santé, température, usure) ---
  for (const dk of d.disques || []) {
    const nom = dk.modele || "disque";
    if (dk.sante && !sain(dk.sante)) add("disque-sante@" + nom, "critique", `Disque « ${nom} » en mauvais état`, `État SMART : ${dk.sante}.`, "Sauvegarder sans tarder et remplacer le disque.");
    const err = (dk.erreurs_lecture || 0) + (dk.erreurs_ecriture || 0);
    if (err > 0) add("disque-erreurs@" + nom, "alerte", `Erreurs d'E/S sur « ${nom} »`, `${err} erreur(s) de lecture/écriture relevée(s).`, "Vérifier le câble/port, lancer un test de charge disque et surveiller le SMART.");
    if (typeof dk.temperature === "number" && dk.temperature >= 70) add("disque-chaud@" + nom, "critique", `Disque « ${nom} » très chaud`, `${dk.temperature} °C.`, "Vérifier la ventilation ; une surchauffe abrège fortement la vie du disque.");
    else if (typeof dk.temperature === "number" && dk.temperature >= 55) add("disque-tiede@" + nom, "alerte", `Disque « ${nom} » chaud`, `${dk.temperature} °C.`, "Vérifier la ventilation et l'empoussièrement.");
    if (typeof dk.usure === "number" && dk.usure >= 80) add("disque-usure@" + nom, "alerte", `SSD « ${nom} » usé`, `Usure ${dk.usure} %.`, "Prévoir le remplacement du SSD.");
  }

  // --- Volumes presque pleins ---
  for (const v of d.volumes || []) {
    if (v.octets && v.libre != null && v.libre / v.octets < 0.1) add("volume-plein@" + v.lettre, "alerte", `Volume ${v.lettre} presque plein`, `${Math.round((100 * v.libre) / v.octets)} % libre.`, "Libérer de l'espace (un disque système saturé provoque lenteurs et plantages).");
  }

  // --- Catégories d'évènements critiques ---
  if ((cat.ecran_bleu || 0) > 0 || (d.vidages || []).length) add("ecran-bleu", "critique", "Écrans bleus (BSOD)", `${cat.ecran_bleu || (d.vidages || []).length} sur la période.`, "Analyser le vidage mémoire (BlueScreenView / WinDbg) pour identifier le pilote fautif, puis le mettre à jour.");
  if ((cat.materiel || 0) > 0) add("whea", "critique", "Erreurs matérielles (WHEA)", `${cat.materiel} évènement(s) WHEA.`, "Signe d'un défaut matériel (CPU, mémoire, PCIe) : tester mémoire et disque, vérifier températures et alimentation.");
  if ((cat.diag_memoire_erreur || 0) > 0) add("memoire-defaut", "critique", "Mémoire défectueuse", "Le diagnostic mémoire Windows a relevé des erreurs.", "Lancer un test mémoire complet (MemTest86) et remplacer la barrette fautive.");
  if ((cat.disque || 0) > 0) add("disque-controleur", "alerte", "Erreurs disque / contrôleur", `${cat.disque} évènement(s) disque/contrôleur.`, "Identifier le disque concerné (interne vs externe) ; vérifier câble/port et boîtier ; corréler avec les tests de charge disque.");
  if ((cat.arret_brutal || 0) > 0) add("arret-brutal", "alerte", "Arrêts non propres", `${cat.arret_brutal} arrêt(s) brutal(aux) (Kernel-Power 41 / gel).`, "Surveiller température et alimentation ; relever l'état au prochain gel ; vérifier le pilote graphique et le BIOS.");

  // --- Stabilité ---
  const stab = (d.stabilite || [])[0];
  if (stab && typeof stab.indice === "number" && stab.indice < 4) add("stabilite", "alerte", "Indice de stabilité bas", `Indice Windows ${stab.indice.toFixed(1)} / 10.`, "Traiter en priorité les plantages et arrêts ci-dessus ; l'indice remonte quand ils cessent.");

  // --- Applications qui plantent souvent ---
  for (const p of d.plantages || []) {
    if ((p.plantages || 0) + (p.blocages || 0) >= 5) {
      const mod = (p.modules || []).join(", ");
      const action = /ntshrui/i.test(mod) ? "Lié aux partages réseau / à l'Explorateur : vérifier les lecteurs réseau et pilotes réseau."
        : /kernelbase/i.test(mod) ? "Réinstaller ou mettre à jour l'application concernée." : "Mettre à jour ou réinstaller l'application ; vérifier le module en cause.";
      add("plantage@" + p.application, "alerte", `« ${p.application} » plante souvent`, `${p.plantages || 0} plantage(s)${mod ? `, module : ${mod}` : ""}.`, action);
    }
  }

  // --- Journaux : pilotes et BIOS ---
  if (journal(d.evenements, "NDIS|wi-?fi|wlan|Killer")) add("wifi", "alerte", "Pilote Wi-Fi instable", "Nombreux incidents réseau sans fil dans les journaux (sortie de veille).", "Mettre à jour le pilote Wi-Fi (et l'utilitaire constructeur) ; désactiver l'économie d'énergie de la carte Wi-Fi.");
  if (journal(d.evenements, "\\bHAL\\b|ACPI")) add("bios", "alerte", "Horloge/ACPI en échec (BIOS)", "Erreurs HAL/ACPI répétées dans les journaux.", "Mettre à jour le BIOS/UEFI du constructeur ; ces erreurs disparaissent en général après la mise à jour.");
  if (journal(d.evenements, "WindowsUpdate|WU\\b")) add("maj-pilote", "alerte", "Mises à jour en échec", "Des mises à jour (souvent de pilotes) échouent de façon répétée.", "Installer manuellement le pilote concerné depuis le site du constructeur ; vérifier Windows Update.");

  // --- Tests de charge : défaut et intermittence ---
  const runs = histo || [];
  const defauts = runs.filter((r) => String((r.data || {}).verdict || "").toLowerCase().startsWith("défaut reproduit"));
  const disqueKo = runs.some((r) => ((r.data || {}).disque || {}).identique === false);
  const gel = runs.some((r) => (((r.data || {}).processeur || {}).gel_max_s || 0) >= 10);
  if (disqueKo) add("charge-disque", "critique", "Défaut disque reproduit sous charge", "Au moins un test de charge a relu des données différentes de celles écrites.", "Suspecter disque, câble ou contrôleur : remplacer le câble/port, tester un autre disque, sauvegarder.");
  if (gel) add("charge-gel", "critique", "Poste figé sous charge", "Le poste s'est figé pendant un test de charge (surveillance interrompue).", "Blocage système ou matériel sous charge : vérifier alimentation, température et disque.");
  if (runs.length >= 2 && defauts.length > 0 && defauts.length < runs.length) {
    add("charge-intermittent", "alerte", "Défaut intermittent", `Défaut reproduit sur ${defauts.length} test(s) de charge sur ${runs.length}.`, "Enchaîner plusieurs tests et comparer (onglet Tests de charge) ; un défaut qui va et vient oriente vers un câble/contrôleur ou un problème thermique.");
  }

  out.sort((a, b) => POIDS[a.niveau] - POIDS[b.niveau]);
  return out;
}

/** Compteurs par niveau, pour un en-tête. */
export function bilan(liste) {
  const b = { critique: 0, alerte: 0, info: 0 };
  for (const c of liste || []) b[c.niveau] = (b[c.niveau] || 0) + 1;
  return b;
}
