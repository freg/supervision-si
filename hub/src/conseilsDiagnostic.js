// #935 : propositions et conseils sur les points critiques d'un poste, à partir du diagnostic poste-windows
// (évènements, plantages, disques/SMART, volumes, stabilité), de l'antivirus relevé et des tests de charge
// (dernier + historique, pour l'intermittence). Module pur, testé par hub/tests/conseilsDiagnostic.test.mjs.
// #938 : chaque conseil NOMME les éléments concernés (le disque visé par les évènements -- interne ou externe --, le
// pilote, la mise à jour en échec, les dates) et donne des ÉTAPES précises, commandes copiables à l'appui.
// Chaque conseil : { code, niveau: critique|alerte|info, titre, constat, action, elements: [texte], etapes: [{texte, commande?}] }.
// Classés critique > alerte > info.

const POIDS = { critique: 0, alerte: 1, info: 2 };
const sain = (s) => ["healthy", "ok", "normal", "online"].includes(String(s || "").toLowerCase());
const dateFr = (t) => { if (!t) return "?"; const d = new Date(t); return Number.isNaN(d.getTime()) ? String(t) : d.toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }); };
const go = (o) => (o == null ? "" : o >= 1e12 ? `${(o / 1e12).toFixed(1).replace(".", ",")} To` : `${Math.round(o / 1e9)} Go`);

/** Cherche dans les journaux regroupés une source/texte (insensible à la casse) ; renvoie l'entrée au plus fort nombre. */
function journal(evts, motif) {
  const re = new RegExp(motif, "i");
  const hits = (evts || []).filter((e) => re.test(`${e.source} ${e.id} ${e.exemple || ""}`));
  if (!hits.length) return null;
  return hits.reduce((a, b) => ((b.nombre || 0) > (a.nombre || 0) ? b : a));
}

/** Toutes les entrées de journal qui correspondent au motif, par nombre décroissant. */
function journaux(evts, motif) {
  const re = new RegExp(motif, "i");
  return (evts || []).filter((e) => re.test(`${e.source} ${e.id} ${e.exemple || ""}`)).sort((a, b) => (b.nombre || 0) - (a.nombre || 0));
}

/** Dates (les plus récentes d'abord, 3 max) des évènements critiques d'une catégorie. */
function dates(critiques, categorie) {
  return (critiques || []).filter((e) => e.categorie === categorie).map((e) => e.t).filter(Boolean).sort().reverse().slice(0, 3).map(dateFr);
}

/** Libellé d'un disque : « n°1 « Seagate Expansion » (USB, externe, E:) ». */
export function nomDisque(d) {
  if (!d) return "disque inconnu";
  const parts = [];
  if (d.bus) parts.push(d.bus);
  if (d.externe === true) parts.push("externe"); else if (d.externe === false) parts.push("interne");
  if (d.volumes?.length) parts.push(d.volumes.join(" "));
  if (d.octets) parts.push(go(d.octets));
  return `${d.numero != null ? `disque n°${d.numero} ` : ""}« ${d.modele || "modèle inconnu"} »${parts.length ? ` (${parts.join(", ")})` : ""}`;
}

/** Nom d'une carte / d'un pilote cité dans un message d'évènement (NDIS : « L'adaptateur réseau Killer(R) Wi-Fi 6E AX1675i ... »). */
export function extraireAdaptateur(texte) {
  const t = String(texte || "");
  let m = t.match(/(?:adaptateur r[ée]seau|network adapter|carte r[ée]seau|adapter)\s+[«"]?\s*([^«»"\n]{4,80}?)\s*[»"]?\s*(?:a\s|has\s|n'a\s|ne\s|was\s|is\s|failed|\.|,|:|$)/i);
  if (m) return m[1].trim();
  m = t.match(/\b((?:Killer|Intel|Realtek|Qualcomm|MediaTek|Broadcom)[^\n,.;:]{3,60}?(?:Wi-?Fi|Wireless|AX\d{3,4}|AC\d{3,4}|Ethernet)[^\n,.;:]{0,30})/i);
  return m ? m[1].trim() : null;
}

/** Titre et code d'erreur d'une mise à jour en échec (WindowsUpdateClient 20 : « ... error 0x80070103: Intel - ... »). */
export function extraireMiseAJour(texte) {
  const t = String(texte || "");
  const code = (t.match(/0x[0-9A-Fa-f]{8}/) || [])[0] || null;
  let titre = null;
  const m = t.match(/(?:error|erreur)\s+0x[0-9A-Fa-f]{8}\s*:\s*(.+?)\s*$/i) || t.match(/:\s*([^:\n]{8,160})\s*$/);
  if (m) titre = m[1].trim().replace(/[.\s]+$/, "");
  return { code, titre };
}

/**
 * Conseils à partir du détail d'un poste et de l'historique des tests de charge.
 * @param detail { poste, alertes, diagnostic, reinstallation, charge }
 * @param histo  [{at, data}] relevés poste-charge (le plus récent d'abord)
 */
export function conseils(detail, histo) {
  const d = (detail && detail.diagnostic) || {};
  const re = (detail && detail.reinstallation) || {};
  const poste = (detail && detail.poste) || {};
  const cat = d.categories || {};
  const out = [];
  const add = (code, niveau, titre, constat, action, elements = [], etapes = []) => out.push({ code, niveau, titre, constat, action, elements: elements.filter(Boolean), etapes });
  const E = (texte, commande) => (commande ? { texte, commande } : { texte });
  const constructeur = [poste.fabricant, poste.modele].filter(Boolean).join(" ");
  const biosTxt = poste.bios ? `BIOS actuel ${poste.bios}${poste.bios_date ? ` (${dateFr(poste.bios_date).slice(0, 10)})` : ""}` : null;

  // --- Antivirus ---
  const av = re.antivirus || [];
  if (av.length === 0 || !av.some((a) => a.actif)) {
    add("antivirus", "critique", "Aucun antivirus actif",
      av.length ? "Antivirus présent mais inactif." : "Aucun antivirus détecté ; Windows Defender semble désactivé.",
      "Réactiver Windows Defender (ou installer un antivirus) et vérifier qu'il n'a pas été désactivé par une stratégie ou un logiciel tiers.",
      av.map((a) => `${a.nom} : ${a.actif ? "actif" : "inactif"}${a.a_jour === false ? ", pas à jour" : ""}`),
      [E("Vérifier l'état réel de Defender (service, temps réel, signatures)", "Get-MpComputerStatus | Select-Object AMServiceEnabled, RealTimeProtectionEnabled, AntivirusEnabled, AntivirusSignatureLastUpdated"),
        E("Réactiver la protection en temps réel (PowerShell administrateur)", "Set-MpPreference -DisableRealtimeMonitoring $false"),
        E("Chercher une stratégie qui le désactive (clé DisableAntiSpyware / DisableRealtimeMonitoring)", "Get-ItemProperty 'HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows Defender' -ErrorAction SilentlyContinue ; Get-ItemProperty 'HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows Defender\\Real-Time Protection' -ErrorAction SilentlyContinue"),
        E("Si un antivirus tiers est installé : le désinstaller proprement ou le réactiver ; un seul moteur à la fois")]);
  } else if (av.some((a) => a.actif && a.a_jour === false)) {
    add("antivirus-maj", "alerte", "Antivirus pas à jour", "L'antivirus actif n'est pas à jour.", "Mettre à jour les signatures de l'antivirus.",
      av.filter((a) => a.actif).map((a) => a.nom), [E("Mettre à jour les signatures Defender", "Update-MpSignature")]);
  }

  // --- Disques (SMART, santé, température, usure) ---
  for (const dk of d.disques || []) {
    const nom = dk.modele || "disque";
    const el = [nomDisque(dk)];
    const cmdSmart = `Get-PhysicalDisk${dk.numero != null ? ` -DeviceNumber ${dk.numero}` : ""} | Get-StorageReliabilityCounter | Format-List Temperature, TemperatureMax, Wear, ReadErrorsTotal, ReadErrorsUncorrected, WriteErrorsTotal, PowerOnHours`;
    if (dk.sante && !sain(dk.sante)) add("disque-sante@" + nom, "critique", `Disque « ${nom} » en mauvais état`, `État SMART : ${dk.sante}.`, "Sauvegarder sans tarder et remplacer le disque.", el,
      [E("Sauvegarder immédiatement (fiche de l'agent › Sauvegardes : données, puis image)"), E("Relever les compteurs de fiabilité pour le dossier de remplacement", cmdSmart), E("Remplacer le disque ; réinstaller depuis l'image ou la liste de réinstallation du poste")]);
    const err = (dk.erreurs_lecture || 0) + (dk.erreurs_ecriture || 0);
    if (err > 0) add("disque-erreurs@" + nom, "alerte", `Erreurs d'E/S sur « ${nom} »`, `${err} erreur(s) de lecture/écriture relevée(s).`, "Vérifier le câble/port, lancer un test de charge disque et surveiller le SMART.", el,
      [E("Compteurs de fiabilité (erreurs non corrigées = disque à remplacer)", cmdSmart), E(dk.externe ? "Disque externe : changer de câble et de port USB (direct, sans concentrateur)" : "Disque interne : vérifier le câble SATA / le siège M.2, le micrologiciel du disque chez le constructeur"), E("Test de charge disque (onglet Tests de charge) puis comparer les compteurs")]);
    if (typeof dk.temperature === "number" && dk.temperature >= 70) add("disque-chaud@" + nom, "critique", `Disque « ${nom} » très chaud`, `${dk.temperature} °C${dk.temperature_max != null ? ` (max relevé ${dk.temperature_max} °C)` : ""}.`, "Vérifier la ventilation ; une surchauffe abrège fortement la vie du disque.", el,
      [E("Arrêter les charges lourdes, nettoyer grilles et ventilateurs (air comprimé, poste éteint)"), E("Surveiller la température après nettoyage", cmdSmart), E("Vérifier le plan d'alimentation (mode « performances » chauffe davantage)", "powercfg /getactivescheme"), E(constructeur ? `Vérifier le micrologiciel / la gestion thermique chez le constructeur (${constructeur})` : "Vérifier le micrologiciel du constructeur")]);
    else if (typeof dk.temperature === "number" && dk.temperature >= 55) add("disque-tiede@" + nom, "alerte", `Disque « ${nom} » chaud`, `${dk.temperature} °C${dk.temperature_max != null ? ` (max relevé ${dk.temperature_max} °C)` : ""}.`, "Vérifier la ventilation et l'empoussièrement.", el,
      [E("Nettoyer grilles et ventilateurs (air comprimé, poste éteint) ; ne pas poser le portable sur un tissu"), E("Relever la température à froid puis après 15 min de charge", cmdSmart), E("Si > 70 °C en charge : dissipateur SSD / pâte thermique, ou service constructeur")]);
    if (typeof dk.usure === "number" && dk.usure >= 80) add("disque-usure@" + nom, "alerte", `SSD « ${nom} » usé`, `Usure ${dk.usure} %.`, "Prévoir le remplacement du SSD.", el, [E("Sauvegarder (image) puis planifier le remplacement"), E("Suivre l'usure", cmdSmart)]);
  }

  // --- Volumes presque pleins ---
  for (const v of d.volumes || []) {
    if (v.octets && v.libre != null && v.libre / v.octets < 0.1) {
      const l = String(v.lettre || "C:").replace(/\\$/, "");
      add("volume-plein@" + v.lettre, "alerte", `Volume ${v.lettre} presque plein`, `${Math.round((100 * v.libre) / v.octets)} % libre (${go(v.libre)} sur ${go(v.octets)}).`, "Libérer de l'espace (un disque système saturé provoque lenteurs et plantages).",
        [`volume ${v.lettre}${v.disque != null ? ` (disque n°${v.disque})` : ""}`],
        [E("Nettoyage de disque (fichiers temporaires, anciennes mises à jour)", `cleanmgr /d ${l}`), E("Les 15 plus gros dossiers du volume", `Get-ChildItem ${l}\\ -Directory -Force -ErrorAction SilentlyContinue | ForEach-Object { [pscustomobject]@{ Dossier=$_.FullName; Go=[math]::Round((Get-ChildItem $_.FullName -Recurse -File -Force -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum/1GB,1) } } | Sort-Object Go -Descending | Select-Object -First 15`), E("Vider la corbeille, supprimer les anciennes versions de Windows (Windows.old) via Assistant Stockage")]);
    }
  }

  // --- Catégories d'évènements critiques ---
  if ((cat.ecran_bleu || 0) > 0 || (d.vidages || []).length) add("ecran-bleu", "critique", "Écrans bleus (BSOD)", `${cat.ecran_bleu || (d.vidages || []).length} sur la période.`, "Analyser le vidage mémoire (BlueScreenView / WinDbg) pour identifier le pilote fautif, puis le mettre à jour.",
    [...dates(d.critiques, "ecran_bleu").map((t) => `écran bleu le ${t}`), ...(d.vidages || []).slice(0, 3).map((v) => `vidage ${v.fichier} (${dateFr(v.t)})`)],
    [E("Lire les codes d'arrêt (BugCheck 1001)", "Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-WER-SystemErrorReporting'} -MaxEvents 10 | Format-List TimeCreated, Message"), E("Ouvrir les vidages C:\\Windows\\Minidump avec BlueScreenView (NirSoft) ou WinDbg : noter le pilote fautif"), E("Mettre à jour ce pilote depuis le constructeur ; si mémoire suspectée, test mémoire", "mdsched.exe")]);
  if ((cat.materiel || 0) > 0) add("whea", "critique", "Erreurs matérielles (WHEA)", `${cat.materiel} évènement(s) WHEA.`, "Signe d'un défaut matériel (CPU, mémoire, PCIe) : tester mémoire et disque, vérifier températures et alimentation.",
    dates(d.critiques, "materiel").map((t) => `WHEA le ${t}`),
    [E("Détail des erreurs WHEA (composant : processeur, mémoire, PCIe)", "Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-WHEA-Logger'} -MaxEvents 10 | Format-List TimeCreated, Id, Message"), E("Test mémoire complet au redémarrage", "mdsched.exe"), E("Si PCIe : retirer / réinsérer la carte ou le SSD visé ; vérifier l'alimentation et les températures")]);
  if ((cat.diag_memoire_erreur || 0) > 0) add("memoire-defaut", "critique", "Mémoire défectueuse", "Le diagnostic mémoire Windows a relevé des erreurs.", "Lancer un test mémoire complet (MemTest86) et remplacer la barrette fautive.",
    dates(d.critiques, "diag_memoire_erreur").map((t) => `diagnostic mémoire en erreur le ${t}`),
    [E("Résultat détaillé du diagnostic Windows", "Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-MemoryDiagnostics-Results'} -MaxEvents 5 | Format-List TimeCreated, Message"), E("MemTest86 depuis une clé USB, 4 passes, une barrette à la fois pour isoler la fautive"), E("Remplacer la barrette ; en attendant, retirer la fautive si le poste a deux barrettes")]);

  // --- Erreurs disque / contrôleur : NOMMER le disque visé (#938) ---
  if ((cat.disque || 0) > 0) {
    const grp = d.disques_evenements || [];
    const el = grp.map((g) => {
      const ids = (g.ids || []).map((kv) => (Array.isArray(kv) ? `${kv[0]} ×${kv[1]}` : String(kv))).join(", ");
      if (g.numero == null) return `${g.nombre} réinitialisation(s) de contrôleur sans disque cité (${ids})${g.dernier ? `, dernière le ${dateFr(g.dernier)}` : ""}`;
      const qui = g.resolu ? nomDisque(g) : `disque n°${g.numero} (plus présent : disque ou clé débranché depuis, ou agent à mettre à jour pour le nommer)`;
      return `${g.nombre} évènement(s) sur ${qui} : ${ids}${g.dernier ? `, dernier le ${dateFr(g.dernier)}` : ""}`;
    });
    const externes = grp.filter((g) => g.externe === true), internes = grp.filter((g) => g.externe === false), inconnus = grp.filter((g) => g.numero != null && !g.resolu);
    let action;
    if (grp.length && externes.length && !internes.length) action = `Seul un disque EXTERNE est visé (${externes.map((g) => `« ${g.modele} »`).join(", ")}) : le disque interne n'est pas en cause. Vérifier câble, port et alimentation du boîtier ; si c'est un VHDX ou une copie montée, le démonter après usage.`;
    else if (grp.length && internes.length && !externes.length) action = `Le disque INTERNE est visé (${internes.map((g) => `« ${g.modele} »`).join(", ")}) : sauvegarder, vérifier le système de fichiers et le micrologiciel, surveiller le SMART.`;
    else if (grp.length && internes.length && externes.length) action = "Interne ET externe sont visés : vérifier d'abord le contrôleur / l'alimentation (point commun), puis chaque disque.";
    else if (inconnus.length) action = "Le disque visé n'est plus présent (débranché depuis) : probablement un disque externe ou une clé ; rebrancher pour le confirmer, sinon ignorer.";
    else action = "Identifier le disque concerné (le relevé de l'agent 0.6.34+ le nomme) ; vérifier câble/port et boîtier ; corréler avec les tests de charge disque.";
    const etapes = [E("Lister les disques tels que Windows les numérote (n° = celui des évènements \\Device\\HarddiskN)", "Get-PhysicalDisk | Sort-Object { [int]$_.DeviceId } | Format-Table DeviceId, FriendlyName, BusType, MediaType, Size, HealthStatus, OperationalStatus"),
      E("Derniers évènements disque avec le disque cité", "Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='disk','stornvme','storahci'} -MaxEvents 20 | Format-List TimeCreated, ProviderName, Id, Message")];
    for (const g of externes) etapes.push(E(`Disque externe « ${g.modele }» : changer le câble et le port USB (port direct, pas de concentrateur) ; boîtier alimenté ? ; éjecter proprement avant de débrancher`), E(`Vérifier son système de fichiers${g.volumes?.length ? ` (${g.volumes.join(" ")})` : ""}`, g.volumes?.length ? `chkdsk ${g.volumes[0]} /scan` : "chkdsk <lettre:> /scan"));
    for (const g of internes) etapes.push(E(`Disque interne « ${g.modele} » : sauvegarder d'abord (fiche › Sauvegardes)`), E(`Vérifier le système de fichiers${g.volumes?.length ? ` (${g.volumes.join(" ")})` : ""} -- planifié au redémarrage si volume système`, g.volumes?.length ? `chkdsk ${g.volumes[0]} /scan` : "chkdsk C: /scan"), E("Compteurs de fiabilité du disque", `Get-PhysicalDisk -DeviceNumber ${g.numero} | Get-StorageReliabilityCounter | Format-List Temperature, ReadErrorsTotal, ReadErrorsUncorrected, WriteErrorsTotal`), E(`Micrologiciel du disque / du contrôleur chez le constructeur${constructeur ? ` (${constructeur})` : ""}`));
    if (grp.some((g) => g.numero == null)) etapes.push(E("Réinitialisations de contrôleur (storahci/stornvme 129) : pilote de stockage (Intel RST / NVMe) et BIOS à mettre à jour ; désactiver la mise en veille PCIe", "powercfg /setacvalueindex SCHEME_CURRENT 501a4d13-42af-4429-9fd1-a8218c268e20 ee12f906-d277-404b-b6da-e5fa1a576df5 0 ; powercfg /setactive SCHEME_CURRENT"));
    etapes.push(E("Corréler : lancer un test de charge disque sur le volume visé (onglet Tests de charge) et voir si des évènements disk apparaissent pendant le test"));
    add("disque-controleur", "alerte", "Erreurs disque / contrôleur", `${cat.disque} évènement(s) disque/contrôleur.`, action, el, etapes);
  }
  if ((cat.arret_brutal || 0) > 0) add("arret-brutal", "alerte", "Arrêts non propres", `${cat.arret_brutal} arrêt(s) brutal(aux) (Kernel-Power 41 / gel).`, "Surveiller température et alimentation ; relever l'état au prochain gel ; vérifier le pilote graphique et le BIOS.",
    [...dates(d.critiques, "arret_brutal").map((t) => `arrêt brutal le ${t}`), biosTxt],
    [E("Les arrêts brutaux et ce qui précède (Kernel-Power 41 : BugcheckCode 0 = coupure / gel sans écran bleu)", "Get-WinEvent -FilterHashtable @{LogName='System'; Id=41,6008,1001} -MaxEvents 15 | Format-List TimeCreated, ProviderName, Id, Message"),
      E("Rapport d'énergie et de veille (surchauffe, sortie de veille, batterie)", "powercfg /energy /output %TEMP%\\energy.html ; powercfg /sleepstudy /output %TEMP%\\sleep.html"),
      E("Températures au prochain gel : noter ce qui tournait (onglet Activité / Tests de charge) ; si le gel survient sous charge → thermique ou alimentation"),
      E("Pilote graphique : version et date ; réinstallation propre depuis le constructeur", "Get-CimInstance Win32_VideoController | Format-List Name, DriverVersion, DriverDate"),
      E(`BIOS / UEFI : comparer avec le constructeur${constructeur ? ` (${constructeur})` : ""} et mettre à jour`, "Get-CimInstance Win32_BIOS | Format-List SMBIOSBIOSVersion, ReleaseDate")]);

  // --- Stabilité ---
  const stab = (d.stabilite || [])[0];
  if (stab && typeof stab.indice === "number" && stab.indice < 4) add("stabilite", "alerte", "Indice de stabilité bas", `Indice Windows ${stab.indice.toFixed(1)} / 10${stab.t ? ` au ${dateFr(stab.t).slice(0, 10)}` : ""}.`, "Traiter en priorité les plantages et arrêts ci-dessus ; l'indice remonte quand ils cessent.",
    [], [E("Historique de fiabilité (chronologie des pannes avec détail)", "perfmon /rel"), E("Rien à corriger ici : c'est la conséquence des points ci-dessus")]);

  // --- Applications qui plantent souvent ---
  for (const p of d.plantages || []) {
    if ((p.plantages || 0) + (p.blocages || 0) >= 5) {
      const mod = (p.modules || []).join(", ");
      const el = [`${p.application}${mod ? ` -- module(s) : ${mod}` : ""}${p.dernier ? `, dernier le ${dateFr(p.dernier)}` : ""}`];
      const et = [E(`Détail des plantages de ${p.application} (module, décalage, chemin)`, `Get-WinEvent -FilterHashtable @{LogName='Application'; Id=1000,1002} -MaxEvents 200 | Where-Object { $_.Message -like '*${String(p.application).replace(/'/g, "''")}*' } | Select-Object -First 5 | Format-List TimeCreated, Message`)];
      let action;
      if (/ntshrui|FileExplorer/i.test(mod)) {
        action = "Lié aux partages réseau / à l'Explorateur : vérifier les lecteurs réseau et pilotes réseau.";
        et.push(E("Lecteurs réseau mappés : repérer ceux qui ne répondent plus (serveur disparu, déconnecté)", "net use ; Get-SmbMapping"),
          E("Supprimer les mappages morts (X: = lettre concernée) puis recréer ceux utiles", "net use X: /delete /y"),
          E("Raccourcis réseau cassés dans « Emplacements réseau »", `Get-ChildItem "$env:APPDATA\\Microsoft\\Windows\\Network Shortcuts"`),
          E("Si ça persiste : désactiver les extensions de shell tierces (ShellExView, NirSoft) puis relancer l'Explorateur"));
      } else if (/combase|DllHost/i.test(mod) || /DllHost/i.test(p.application)) {
        action = "Composant COM / aperçu de fichiers (DllHost) : réparer les fichiers système et vérifier les gestionnaires d'aperçu tiers.";
        et.push(E("Réparer les fichiers système", "sfc /scannow"), E("Réparer l'image Windows si sfc a trouvé des erreurs", "DISM /Online /Cleanup-Image /RestoreHealth"),
          E("Gestionnaires d'aperçu / miniatures tiers (lecteurs PDF, codecs, CAO) : mettre à jour ou désactiver"));
      } else if (/kernelbase/i.test(mod)) {
        action = "Réinstaller ou mettre à jour l'application concernée.";
        if (/SupportAssist/i.test(p.application)) et.push(E("Dell SupportAssist : désinstaller (Paramètres › Applications) puis réinstaller la dernière version depuis dell.com/support ; ou le laisser désinstallé s'il n'est pas utilisé"));
        else et.push(E("Réinstaller l'application depuis l'éditeur ; vérifier qu'elle est à jour", `winget list --name "${String(p.application).replace(/\.exe$/i, "")}"`));
      } else {
        action = "Mettre à jour ou réinstaller l'application ; vérifier le module en cause.";
        et.push(E("Mettre à jour l'application ; si le module est un pilote (nv*, ig*, atio*) → pilote graphique"));
      }
      add("plantage@" + p.application, "alerte", `« ${p.application} » plante souvent`, `${p.plantages || 0} plantage(s)${p.blocages ? `, ${p.blocages} blocage(s)` : ""}${mod ? `, module : ${mod}` : ""}.`, action, el, et);
    }
  }

  // --- Journaux : pilotes et BIOS ---
  const wifi = journaux(d.evenements, "NDIS|wi-?fi|wlan|Killer");
  if (wifi.length) {
    const carte = wifi.map((e) => extraireAdaptateur(e.exemple)).find(Boolean);
    add("wifi", "alerte", "Pilote Wi-Fi instable", `${wifi.reduce((n, e) => n + (e.nombre || 0), 0)} incident(s) réseau sans fil dans les journaux (${wifi.slice(0, 2).map((e) => `${e.source} ${e.id}`).join(", ")}).`, "Mettre à jour le pilote Wi-Fi (et l'utilitaire constructeur) ; désactiver l'économie d'énergie de la carte Wi-Fi.",
      [carte ? `carte : ${carte}` : null, ...wifi.slice(0, 2).map((e) => `${e.source} ${e.id} ×${e.nombre}${e.dernier ? `, dernier le ${dateFr(e.dernier)}` : ""}`)],
      [E("Carte et version du pilote installé", "Get-NetAdapter -Physical | Format-Table Name, InterfaceDescription, DriverVersion, DriverDate, Status"),
        E(`Télécharger le dernier pilote Wi-Fi${carte ? ` pour « ${carte} »` : ""} chez le constructeur${constructeur ? ` (${constructeur})` : ""} ou Intel ; désinstaller l'ancien (Gestionnaire de périphériques › Désinstaller en cochant « supprimer le pilote ») puis installer`),
        E("Désactiver l'économie d'énergie de la carte (sortie de veille = source des incidents)", "Get-NetAdapter -Physical | Where-Object InterfaceDescription -match 'Wi-?Fi|Wireless' | Set-NetAdapterPowerManagement -AllowComputerToTurnOffDevice Disabled"),
        E("Désinstaller l'utilitaire « Killer Intelligence Center / Killer Control » s'il est présent (source connue d'instabilité) ; garder le seul pilote")]);
  }
  const hal = journaux(d.evenements, "\\bHAL\\b|ACPI");
  if (hal.length) add("bios", "alerte", "Horloge/ACPI en échec (BIOS)", `${hal.reduce((n, e) => n + (e.nombre || 0), 0)} erreur(s) HAL/ACPI (${hal.slice(0, 2).map((e) => `${e.source} ${e.id}`).join(", ")}).`, "Mettre à jour le BIOS/UEFI du constructeur ; ces erreurs disparaissent en général après la mise à jour.",
    [biosTxt, constructeur ? `machine : ${constructeur}` : null, ...hal.slice(0, 2).map((e) => `${e.source} ${e.id} ×${e.nombre}`)],
    [E("Version et date du BIOS en place", "Get-CimInstance Win32_BIOS | Format-List SMBIOSBIOSVersion, ReleaseDate, Manufacturer"),
      E(`Comparer avec la dernière version chez le constructeur${constructeur ? ` (${constructeur})` : ""} ; mettre à jour sur secteur, batterie > 20 %, sans périphérique USB superflu`),
      E("Après mise à jour : vérifier que HAL 12/21 et ACPI ne reviennent plus", "Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-HAL','ACPI'} -MaxEvents 10 | Format-List TimeCreated, Id, Message")]);
  const wu = journaux(d.evenements, "WindowsUpdate|WU\\b");
  if (wu.length) {
    const majs = wu.map((e) => ({ ...extraireMiseAJour(e.exemple), n: e.nombre })).filter((m) => m.titre || m.code);
    add("maj-pilote", "alerte", "Mises à jour en échec", `${wu.reduce((n, e) => n + (e.nombre || 0), 0)} échec(s) d'installation de mises à jour (souvent des pilotes).`, "Installer manuellement le pilote concerné depuis le site du constructeur ; vérifier Windows Update.",
      majs.slice(0, 3).map((m) => `${m.titre || "mise à jour"}${m.code ? ` -- erreur ${m.code}` : ""} (×${m.n})`),
      [E("Liste des mises à jour en échec et leur code", "Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-WindowsUpdateClient'; Id=20} -MaxEvents 15 | Format-List TimeCreated, Message"),
        ...(majs.some((m) => /0x80070103/i.test(m.code || "")) ? [E("Erreur 0x80070103 = pilote déjà installé ou plus récent présent : masquer cette mise à jour (outil « wushowhide.diagcab » de Microsoft) ; pas d'action sur le poste")] : []),
        E("Installer le pilote manuellement depuis le constructeur, puis relancer la recherche", "UsoClient StartScan"),
        E("Si Windows Update boucle : réparer ses composants", "Dism /Online /Cleanup-Image /RestoreHealth ; sfc /scannow")]);
  }

  // --- Tests de charge : défaut et intermittence ---
  const runs = histo || [];
  const defauts = runs.filter((r) => String((r.data || {}).verdict || "").toLowerCase().startsWith("défaut reproduit"));
  const disqueKo = runs.filter((r) => ((r.data || {}).disque || {}).identique === false);
  const gels = runs.filter((r) => (((r.data || {}).processeur || {}).gel_max_s || 0) >= 10);
  if (disqueKo.length) add("charge-disque", "critique", "Défaut disque reproduit sous charge", "Au moins un test de charge a relu des données différentes de celles écrites.", "Suspecter disque, câble ou contrôleur : remplacer le câble/port, tester un autre disque, sauvegarder.",
    disqueKo.slice(0, 3).map((r) => `test du ${dateFr(r.at)}${r.data?.disque?.dossier ? ` sur ${r.data.disque.dossier}` : ""} : données relues différentes`),
    [E("Sauvegarder le poste avant toute autre chose (fiche › Sauvegardes)"), E("Vérifier le système de fichiers du volume testé", `chkdsk ${(disqueKo[0].data?.disque?.dossier || "C:").slice(0, 2)} /scan`), E("Relancer 3 tests disque de suite sur le même volume, puis sur un autre volume / disque : défaut qui suit le disque → disque ; qui suit le port → câble/contrôleur")]);
  if (gels.length) add("charge-gel", "critique", "Poste figé sous charge", "Le poste s'est figé pendant un test de charge (surveillance interrompue).", "Blocage système ou matériel sous charge : vérifier alimentation, température et disque.",
    gels.slice(0, 3).map((r) => `test du ${dateFr(r.at)} : gel ${r.data.processeur.gel_max_s} s`),
    [E("Relever les évènements système autour de l'heure du gel", "Get-WinEvent -FilterHashtable @{LogName='System'; Level=1,2} -MaxEvents 30 | Format-List TimeCreated, ProviderName, Id, Message"), E("Rejouer le test en surveillant les températures (onglet Tests de charge : courbe) ; gel reproductible à chaud → thermique / alimentation")]);
  if (runs.length >= 2 && defauts.length > 0 && defauts.length < runs.length) {
    add("charge-intermittent", "alerte", "Défaut intermittent", `Défaut reproduit sur ${defauts.length} test(s) de charge sur ${runs.length}.`, "Enchaîner plusieurs tests et comparer (onglet Tests de charge) ; un défaut qui va et vient oriente vers un câble/contrôleur ou un problème thermique.",
      [...defauts.slice(0, 3).map((r) => `défaut le ${dateFr(r.at)} : ${r.data?.verdict || ""}${r.data?.disque?.identique === false ? " (disque)" : ""}${(r.data?.processeur?.gel_max_s || 0) >= 10 ? " (gel)" : ""}`), `${runs.length - defauts.length} test(s) sans défaut`],
      [E("Enchaîner 3 tests identiques dans l'heure et comparer (Tests de charge › Historique › cocher 2 à 3 tests)"), E("Varier UN paramètre à la fois : volume testé (interne vs externe), poste sur secteur vs batterie, à froid vs après 30 min de charge"), E("Noter ce qui change entre un test en défaut et un test sain (heure, température, disque externe branché ou non)")]);
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

/** Texte complet copiable d'un conseil (titre, constat, éléments, étapes et commandes). */
export function texteConseil(c) {
  if (!c) return "";
  const l = [`${c.titre} [${c.niveau}]`, c.constat, `→ ${c.action}`];
  if (c.elements?.length) { l.push("", "Éléments concernés :"); for (const e of c.elements) l.push(`• ${e}`); }
  if (c.etapes?.length) { l.push("", "Procédure :"); c.etapes.forEach((e, i) => { l.push(`${i + 1}. ${e.texte}`); if (e.commande) l.push(`   ${e.commande}`); }); }
  return l.join("\n");
}

/** Toutes les commandes d'une liste de conseils, prêtes à coller dans PowerShell (lecture seule sauf mention). */
export function scriptConseils(liste) {
  const l = ["# Diagnostic -- commandes proposées (PowerShell administrateur). Lignes LECTURE SEULE sauf celles marquées [MODIFIE].", ""];
  for (const c of liste || []) {
    const cmds = (c.etapes || []).filter((e) => e.commande);
    if (!cmds.length) continue;
    l.push(`# --- ${c.titre}`);
    for (const e of cmds) l.push(`# ${/Set-|\/delete|setacvalue|setactive|sfc|DISM|Dism|Update-Mp|cleanmgr|chkdsk|UsoClient/.test(e.commande) ? "[MODIFIE] " : ""}${e.texte}`, e.commande, "");
  }
  return l.join("\n");
}
