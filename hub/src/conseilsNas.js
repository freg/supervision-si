// #944 : propositions et conseils pour un NAS QNAP, à partir du relevé SNMP (disques, SMART, RAID, volumes, applications)
// et du relevé SSH nas-qnap (snapshots, Time Machine, partages, outils). Même forme que conseilsDiagnostic :
// { code, niveau: critique|alerte|info, titre, constat, action, elements: [texte], etapes: [{texte, commande?}] }.
// Les « commandes » sont ici des chemins dans l'interface QTS ou des commandes de LECTURE par SSH : rien ne modifie le NAS.
// Module pur, testé par hub/tests/conseilsNas.test.mjs.

const POIDS = { critique: 0, alerte: 1, info: 2 };
const ANS_H = 8766;
const to = (o) => (o == null ? "?" : o >= 1e12 ? `${(o / 1e12).toFixed(1).replace(".", ",")} To` : `${Math.round(o / 1e9)} Go`);
const koTo = (k) => (k == null ? "?" : to(k * 1024));
const pct = (v) => (v == null ? "?" : `${String(Math.round(v * 10) / 10).replace(".", ",")} %`);
const E = (texte, commande) => (commande ? { texte, commande } : { texte });
const estSsd = (d) => /ssd|nvme|m\.2/i.test(`${d.modele || ""} ${d.interface || ""}`);

/**
 * @param n   fiche SNMP (tuile NAS : disques, smart, raid, volumes, reserves, applications, systeme, name)
 * @param ssh fiche SSH nas-qnap (snapshots, timemachine, partages, partages_timemachine, volumes_sans_snapshot, outils, raid) ou null
 */
export function conseilsNas(n, ssh) {
  const out = [];
  const add = (code, niveau, titre, constat, action, elements = [], etapes = []) => out.push({ code, niveau, titre, constat, action, elements: elements.filter(Boolean), etapes });
  const nom = n?.name || "NAS";
  const disques = n?.disques || [];

  // --- Disques : SMART, âge, température ---
  for (const d of disques) {
    const who = `baie ${d.emplacement} : ${d.modele || "?"}${d.octets ? ` (${to(d.octets)})` : ""}`;
    const smart = Object.entries(d.smart || {}).filter(([, v]) => v > 0);
    const h = Number(d.heures) || 0;
    if (d.etat && !/good|ok|normal/i.test(String(d.etat))) add("disque-etat@" + d.emplacement, "critique", `Disque en baie ${d.emplacement} en défaut`, `État ${d.etat}.`, "Remplacer le disque sans attendre (RAID dégradé ou donnée perdue sinon).",
      [who], [E("QTS › Stockage et snapshots › Disques : état, SMART, remplacement à chaud"), E("Vérifier la redondance du groupe RAID avant de retirer le disque (RAID 5 : un seul disque à la fois)")]);
    else if (smart.length) add("disque-smart@" + d.emplacement, smart.some(([k]) => /illisibles|non corrig/.test(k)) ? "critique" : "alerte", `Disque en baie ${d.emplacement} : SMART dégradé`, `${smart.map(([k, v]) => `${v} ${k}`).join(", ")}.`,
      estSsd(d) ? "SSD avec secteurs réalloués : usure ou défaut naissant -- le remplacer avant qu'il ne tombe, d'autant plus s'il est seul (sans redondance)." : "Secteurs réalloués / en attente : disque à remplacer de façon planifiée ; en surveiller l'évolution (une hausse = remplacement immédiat).",
      [who, h ? `${h.toLocaleString("fr-FR")} h de fonctionnement (${(h / ANS_H).toFixed(1).replace(".", ",")} ans)` : null],
      [E("QTS › Stockage et snapshots › Disques › le disque › Informations sur le disque › SMART : relever les attributs 5, 187, 197, 198 et refaire un test SMART complet"), E("Prévoir le disque de remplacement (même capacité ou plus, liste de compatibilité QNAP du modèle)"), E("Si le disque porte un volume sans redondance (RAID simple) : sauvegarder ce volume d'abord")]);
    if (h >= 7 * ANS_H) add("disque-age@" + d.emplacement, "alerte", `Disque en baie ${d.emplacement} âgé`, `${h.toLocaleString("fr-FR")} h de fonctionnement (${(h / ANS_H).toFixed(1).replace(".", ",")} ans).`,
      "Au-delà de 5 à 7 ans, remplacer de façon planifiée, un disque à la fois (reconstruction du RAID entre chaque).", [who],
      [E("Commander les disques de remplacement (mêmes capacités ou plus ; même lot d'âge = même risque : les remplacer tous, un par un)"), E("QTS › Stockage et snapshots › Disques › Remplacer (à chaud) ; attendre la fin de la reconstruction avant le suivant"), E("Voir « Potentiel d'évolution » : c'est l'occasion d'augmenter la capacité")]);
    else if (h >= 5 * ANS_H) add("disque-age@" + d.emplacement, "info", `Disque en baie ${d.emplacement} : ${(h / ANS_H).toFixed(1).replace(".", ",")} ans`, "Fin de vie statistique qui approche.", "Prévoir le remplacement dans l'année.", [who], []);
    if (typeof d.temperature === "number" && d.temperature >= 50) add("disque-chaud@" + d.emplacement, "alerte", `Disque en baie ${d.emplacement} chaud`, `${d.temperature} °C.`, "Vérifier ventilateurs et filtres ; température ambiante du local.", [who], [E("QTS › Panneau de configuration › Système › Matériel › Ventilateur intelligent : mode et seuils")]);
  }

  // --- RAID sans redondance / dégradé ---
  for (const r of n?.raid || []) {
    const single = /single|simple|raid ?0|linear/i.test(String(r.niveau));
    const degrade = !/ready|ok|good|active/i.test(String(r.etat || "Ready"));
    if (degrade) add("raid-degrade@" + r.dev, "critique", `RAID ${r.dev} dégradé`, `${r.niveau} · ${r.etat}.`, "Identifier le disque manquant / en défaut et le remplacer ; ne rien redémarrer tant que la reconstruction n'est pas finie.", [`${r.dev} : ${r.niveau}, ${to(r.octets)}`],
      [E("QTS › Stockage et snapshots › Stockage › le groupe RAID : disque membre en défaut ?"), E("Si l'état reste dégradé après remplacement : reconstruire (Gérer › Reconstruire)")]);
    else if (single) {
      const ssdSeul = disques.find((d) => estSsd(d));
      add("raid-simple@" + r.dev, "alerte", `${r.dev} sans redondance`, `${r.niveau} (${to(r.octets)}).`,
        ssdSeul ? `Probablement le SSD seul (${ssdSeul.modele}) : s'il sert de cache, une panne ne perd rien mais stoppe l'accélération ; s'il porte un volume ou des données, elles sont sans filet.` : "Un disque seul : toute panne perd son contenu.",
        [`${r.dev} : ${r.niveau}, ${to(r.octets)}`, ssdSeul ? `SSD en baie ${ssdSeul.emplacement} : ${ssdSeul.modele}` : null],
        [E("QTS › Stockage et snapshots › Stockage : à quoi sert ce groupe (cache SSD, volume statique, volume de réserve) ?"), E("Vérifier par SSH (lecture) ce qui est monté dessus", "cat /proc/mdstat ; df -h | grep -i cache"), E("Si volume de données : le sauvegarder (HBS vers un autre volume / PBS) ou le migrer ; si cache : prévoir le remplacement du SSD quand le SMART bouge")]);
    }
  }

  // --- Volumes pleins ---
  for (const v of n?.volumes || []) {
    if (v.leger || typeof v.pct !== "number") continue;
    const tm = /time ?machine/i.test(v.nom || "");
    if (v.pct >= 90) add("volume-plein@" + v.nom, "critique", `Volume ${v.nom} presque plein`, `${pct(v.pct)} (${koTo(v.ko)}).`,
      tm ? "Volume Time Machine saturé : Time Machine supprime ses anciennes sauvegardes seul, mais un volume plein bloque les nouvelles -- agrandir le volume ou réduire le quota de la machine." : "Agrandir le volume (réserve libre) ou faire de la place ; au-delà de 95 % les snapshots échouent.",
      [`${v.nom} : ${pct(v.pct)} de ${koTo(v.ko)}`], [E("QTS › Stockage et snapshots › le volume › Gérer › Redimensionner (en ligne, si réserve libre)"), E("Plus gros dossiers par SSH (lecture)", `du -sh /share/*/ 2>/dev/null | sort -rh | head -15`), tm ? E("Sur le Mac : Préférences › Time Machine › Options : exclure Bibliothèque/Caches, machines virtuelles, dossiers de téléchargement") : E("Snapshots : vérifier la place réservée (Stockage et snapshots › Snapshots › Espace garanti)")]);
    else if (v.pct >= 80) add("volume-presque-plein@" + v.nom, "alerte", `Volume ${v.nom} à ${pct(v.pct)}`, `${koTo(v.ko)} ; il reste ${koTo(v.libre_ko)}.`, "Prévoir l'agrandissement (réserve) ou le ménage avant 90 %.", [`${v.nom} : ${pct(v.pct)}`], [E("QTS › Stockage et snapshots › le volume › Gérer › Redimensionner"), E("Plus gros dossiers (lecture)", "du -sh /share/*/ 2>/dev/null | sort -rh | head -15")]);
  }

  // --- Snapshots et Time Machine (SSH) ---
  if (ssh?.ok) {
    for (const vol of ssh.volumes_sans_snapshot || []) {
      add("snapshot-absent@" + vol, "alerte", `Pas de snapshot sur ${vol}`, "Aucun snapshot trouvé sur ce volume.", "Activer des snapshots planifiés (quotidiens, 7 à 14 conservés) : c'est la protection contre un effacement ou un rançongiciel côté postes.",
        [vol], [E("QTS › Stockage et snapshots › le volume › Snapshot › Gestionnaire de snapshots › Planification"), E("Réserver 10 à 20 % du volume à l'espace garanti des snapshots")]);
    }
    for (const s of ssh.snapshots || []) {
      if (s.nombre && s.dernier_age_h > 48) add("snapshot-vieux@" + s.volume, "alerte", `Snapshots de ${s.volume} en retard`, `${s.nombre} snapshot(s), dernier il y a ${Math.round(s.dernier_age_h)} h.`, "La planification s'est arrêtée (volume plein, espace garanti épuisé, tâche désactivée) : la relancer.", [`${s.volume} : ${s.noms?.slice(-1)[0] || ""}`],
        [E("QTS › Stockage et snapshots › Snapshot : état de la tâche et espace"), E("Liste par SSH (lecture)", `ls -1 ${s.dossier || "/share/CACHEDEV1_DATA/.snapshot"} | tail -5`)]);
    }
    for (const b of ssh.timemachine || []) {
      if (b.age_h > 24 * 7) add("timemachine-vieux@" + b.machine, "alerte", `Time Machine « ${b.machine} » ne sauvegarde plus`, `Dernière écriture il y a ${Math.round(b.age_h / 24)} j.`, "Le Mac n'atteint plus le NAS (Wi-Fi, mot de passe changé, volume plein) ou Time Machine est désactivé : vérifier sur le Mac.",
        [`${b.chemin}${b.ko ? ` (${koTo(b.ko)})` : ""}`], [E("Sur le Mac : Réglages › Général › Time Machine : dernière sauvegarde, erreur affichée"), E("Sur le NAS : Panneau de configuration › Services réseau et fichiers › Win/Mac/NFS › Time Machine : service actif, compte, quota")]);
    }
    if ((ssh.partages_timemachine || []).length && !(ssh.timemachine || []).length) add("timemachine-vide", "info", "Partage Time Machine sans sauvegarde", `Partage(s) déclaré(s) : ${ssh.partages_timemachine.join(", ")}.`, "Aucun Mac n'y a encore sauvegardé, ou les bundles sont ailleurs.", [], []);
  } else if (ssh === null || ssh === undefined) {
    add("ssh-absent", "info", "Snapshots et Time Machine non relevés", "Seul le SNMP est actif.", "Activer la sonde nas-qnap (SSH) sur l'agent du LAN pour voir snapshots, Time Machine, partages et connexions.", [], []);
  }

  // --- Applications à mettre à jour ---
  const maj = (n?.applications || []).filter((a) => a.mise_a_jour);
  if (maj.length) add("apps-maj", maj.some((a) => /plex|media|qdms|video/i.test(a.nom)) && maj.some((a) => a.actif) ? "alerte" : "info", `${maj.length} application(s) à mettre à jour`, maj.map((a) => `${a.nom} ${a.version} → ${a.disponible}${a.actif ? "" : " (inactive)"}`).join(", ") + ".",
    "Mettre à jour les applications actives exposées (serveurs média, partage) ; désinstaller celles qui ne servent pas.", maj.map((a) => `${a.nom} : ${a.version} → ${a.disponible}${a.actif ? "" : " (inactive : désinstaller ?)"}`),
    [E("QTS › App Center › Mises à jour : installer ; applications inactives inutiles → Supprimer"), E("Vérifier ensuite que le micrologiciel QTS est à jour (Panneau de configuration › Mise à jour du micrologiciel)")]);

  out.sort((a, b) => POIDS[a.niveau] - POIDS[b.niveau]);
  return out;
}

export function bilanNas(liste) {
  const b = { critique: 0, alerte: 0, info: 0 };
  for (const c of liste || []) b[c.niveau] = (b[c.niveau] || 0) + 1;
  return b;
}
