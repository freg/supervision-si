// #935 : conseils de diagnostic d'un poste.
import { test } from "node:test";
import assert from "node:assert/strict";
import { conseils, bilan } from "../src/conseilsDiagnostic.js";

// Détail calqué sur pc-paul (anonymisé) : Defender off, erreurs disque/contrôleur, arrêts brutaux, Explorer/ntshrui,
// Wi-Fi Killer, HAL/ACPI, stabilité basse, disque interne sain à 60 °C.
const DETAIL = {
  reinstallation: { antivirus: [{ nom: "Windows Defender", actif: false, a_jour: true }] },
  diagnostic: {
    categories: { disque: 4, arret_brutal: 4 },
    disques: [{ modele: "NVMe interne", sante: "Healthy", temperature: 60, usure: 0 }],
    volumes: [{ lettre: "C:", octets: 1000e9, libre: 585e9, sante: "Healthy" }],
    stabilite: [{ indice: 3.0 }],
    plantages: [{ application: "Explorer.EXE", plantages: 5, blocages: 1, modules: ["ntshrui.dll"] }],
    evenements: [
      { journal: "System", source: "Microsoft-Windows-NDIS", id: 10317, niveau: 1, nombre: 23, exemple: "Wi-Fi Direct adapter failed" },
      { journal: "System", source: "Microsoft-Windows-HAL", id: 21, niveau: 2, nombre: 50, exemple: "horloge ACPI" },
      { journal: "System", source: "Microsoft-Windows-WindowsUpdateClient", id: 20, niveau: 2, nombre: 72, exemple: "Realtek MTD Driver" },
    ],
  },
};
const HISTO = [
  { at: "2026-10-30T11:39:00Z", data: { verdict: "aucun défaut reproduit", disque: { identique: true }, processeur: { gel_max_s: 2.8 } } },
  { at: "2026-10-30T09:00:00Z", data: { verdict: "défaut reproduit", disque: { identique: false }, processeur: { gel_max_s: 0 } } },
];

test("conseils pc-paul : couverture et classement", () => {
  const c = conseils(DETAIL, HISTO);
  const codes = c.map((x) => x.code);
  assert.ok(codes.includes("antivirus"));
  assert.ok(codes.includes("disque-controleur"));
  assert.ok(codes.includes("arret-brutal"));
  assert.ok(codes.includes("stabilite"));
  assert.ok(codes.some((k) => k.startsWith("plantage@Explorer")));
  assert.ok(codes.includes("wifi"));
  assert.ok(codes.includes("bios"));
  assert.ok(codes.includes("maj-pilote"));
  assert.ok(codes.includes("charge-disque"), "défaut disque reproduit dans l'historique");
  assert.ok(codes.includes("charge-intermittent"), "reproduit 1 test sur 2");
  // classement : les critiques d'abord
  assert.equal(c[0].niveau, "critique");
  const b = bilan(c);
  assert.ok(b.critique >= 2 && b.alerte >= 4);
  // antivirus : action concrète
  assert.match(c.find((x) => x.code === "antivirus").action, /Defender/);
});

test("disque sain, antivirus actif : peu ou pas de critiques", () => {
  const c = conseils({ reinstallation: { antivirus: [{ actif: true, a_jour: true }] },
    diagnostic: { categories: {}, disques: [{ modele: "SSD", sante: "Healthy", temperature: 40 }], volumes: [], stabilite: [{ indice: 9 }] } }, []);
  assert.equal(c.filter((x) => x.niveau === "critique").length, 0);
});

test("défauts non intermittents (tous KO) : pas de conseil intermittent", () => {
  const h = [{ data: { verdict: "défaut reproduit", disque: { identique: false } } },
    { data: { verdict: "défaut reproduit", disque: { identique: false } } }];
  const c = conseils({ diagnostic: {} }, h);
  assert.ok(c.some((x) => x.code === "charge-disque"));
  assert.ok(!c.some((x) => x.code === "charge-intermittent"));
});

test("disque chaud et volume plein", () => {
  const c = conseils({ diagnostic: { categories: {}, disques: [{ modele: "D", sante: "Healthy", temperature: 72 }],
    volumes: [{ lettre: "C:", octets: 1000, libre: 50 }] } }, []);
  assert.ok(c.some((x) => x.code.startsWith("disque-chaud") && x.niveau === "critique"));
  assert.ok(c.some((x) => x.code.startsWith("volume-plein") && x.niveau === "alerte"));
});

// #938 : les conseils nomment les éléments et donnent des étapes / commandes précises.
import { nomDisque, extraireAdaptateur, extraireMiseAJour, texteConseil, scriptConseils } from "../src/conseilsDiagnostic.js";

const DETAIL938 = {
  poste: { fabricant: "Dell Inc.", modele: "XPS 15 9530", bios: "1.12.0", bios_date: "2025-06-01T00:00:00Z" },
  reinstallation: { antivirus: [{ nom: "Windows Defender", actif: true, a_jour: true }] },
  diagnostic: {
    categories: { disque: 4, arret_brutal: 2 },
    disques: [{ numero: 0, modele: "NVMe PC801 NVMe SK hynix 1TB", bus: "NVMe", externe: false, volumes: ["C:"], sante: "Healthy", temperature: 60, temperature_max: 71, octets: 1024e9 },
      { numero: 1, modele: "Seagate Expansion", bus: "USB", externe: true, volumes: ["E:"], sante: "Healthy" }],
    disques_evenements: [{ numero: 1, nombre: 3, ids: [["disk 153", 2], ["disk 51", 1]], dernier: "2026-10-24T10:01:00Z", modele: "Seagate Expansion", bus: "USB", externe: true, volumes: ["E:"], resolu: true },
      { numero: null, nombre: 1, ids: [["stornvme 129", 1]], dernier: "2026-10-25T11:00:00Z", modele: null, bus: null, externe: null, volumes: [], resolu: true }],
    critiques: [{ t: "2026-10-20T08:00:00Z", categorie: "arret_brutal" }, { t: "2026-10-22T09:00:00Z", categorie: "arret_brutal" }],
    volumes: [], stabilite: [{ indice: 7 }],
    plantages: [{ application: "Explorer.EXE", plantages: 5, blocages: 0, modules: ["ntshrui.dll", "combase.dll"], dernier: "2026-10-28T10:00:00Z" },
      { application: "SupportAssistInstaller.exe", plantages: 5, blocages: 0, modules: ["KERNELBASE.dll"] }],
    evenements: [
      { source: "Microsoft-Windows-NDIS", id: 10317, niveau: 1, nombre: 23, dernier: "2026-10-29T06:00:00Z", exemple: "L'adaptateur réseau Killer(R) Wi-Fi 6E AX1675i 160MHz Wireless Network Adapter (211NGW) a été réinitialisé." },
      { source: "Microsoft-Windows-WindowsUpdateClient", id: 20, niveau: 2, nombre: 72, exemple: "Échec de l'installation : Windows n'a pas pu installer la mise à jour suivante avec l'erreur 0x80070103: Realtek Semiconductor Corp. - MEDIA - 6.0.9780.1" },
    ],
  },
};

test("#938 nomDisque, adaptateur, mise à jour", () => {
  assert.equal(nomDisque(DETAIL938.diagnostic.disques[1]), "disque n°1 « Seagate Expansion » (USB, externe, E:)");
  assert.match(nomDisque(DETAIL938.diagnostic.disques[0]), /interne, C:, 1,0 To/);
  assert.equal(nomDisque(null), "disque inconnu");
  assert.equal(extraireAdaptateur(DETAIL938.diagnostic.evenements[0].exemple), "Killer(R) Wi-Fi 6E AX1675i 160MHz Wireless Network Adapter (211NGW)");
  assert.match(extraireAdaptateur("Network adapter Intel(R) Wi-Fi 6 AX201 160MHz has failed") || "", /Intel\(R\) Wi-Fi 6 AX201/);
  assert.equal(extraireAdaptateur("rien ici"), null);
  const m = extraireMiseAJour(DETAIL938.diagnostic.evenements[1].exemple);
  assert.equal(m.code, "0x80070103");
  assert.equal(m.titre, "Realtek Semiconductor Corp. - MEDIA - 6.0.9780.1");
});

test("#938 erreurs disque : le disque EXTERNE est nommé, le disque interne est disculpé, commandes ciblées", () => {
  const c = conseils(DETAIL938, []);
  const dc = c.find((x) => x.code === "disque-controleur");
  assert.match(dc.action, /Seul un disque EXTERNE est visé \(« Seagate Expansion »\)/);
  assert.match(dc.action, /le disque interne n'est pas en cause/);
  assert.ok(dc.elements.some((e) => /3 évènement\(s\) sur disque n°1 « Seagate Expansion » \(USB, externe, E:\) : disk 153 ×2, disk 51 ×1/.test(e)), dc.elements.join(" | "));
  assert.ok(dc.elements.some((e) => /1 réinitialisation\(s\) de contrôleur sans disque cité \(stornvme 129 ×1\)/.test(e)));
  assert.ok(dc.etapes.some((e) => e.commande === "chkdsk E: /scan"));
  assert.ok(dc.etapes.some((e) => /Get-PhysicalDisk \| Sort-Object/.test(e.commande || "")));
  assert.ok(dc.etapes.some((e) => /stornvme 129/.test(e.texte) && /powercfg/.test(e.commande)));
  assert.ok(!dc.etapes.some((e) => /Disque interne/.test(e.texte)), "pas d'étape sur le disque interne quand il n'est pas visé");
  // disque interne visé
  const d2 = JSON.parse(JSON.stringify(DETAIL938));
  d2.diagnostic.disques_evenements = [{ numero: 0, nombre: 4, ids: [["disk 11", 4]], modele: "NVMe PC801 NVMe SK hynix 1TB", bus: "NVMe", externe: false, volumes: ["C:"], resolu: true }];
  const dc2 = conseils(d2, []).find((x) => x.code === "disque-controleur");
  assert.match(dc2.action, /Le disque INTERNE est visé/);
  assert.ok(dc2.etapes.some((e) => e.commande === "chkdsk C: /scan") && dc2.etapes.some((e) => /-DeviceNumber 0/.test(e.commande || "")));
  // disque cité mais disparu
  d2.diagnostic.disques_evenements = [{ numero: 3, nombre: 2, ids: [["disk 7", 2]], resolu: false, externe: null, volumes: [] }];
  const dc3 = conseils(d2, []).find((x) => x.code === "disque-controleur");
  assert.match(dc3.action, /n'est plus présent/);
  assert.ok(dc3.elements[0].includes("disque n°3 (plus présent"));
  // ancien agent (pas de disques_evenements) : repli explicite
  d2.diagnostic.disques_evenements = undefined;
  assert.match(conseils(d2, []).find((x) => x.code === "disque-controleur").action, /agent 0\.6\.34\+ le nomme/);
});

test("#938 éléments nommés : dates d'arrêts, BIOS, carte Wi-Fi, mise à jour en échec, modules des plantages", () => {
  const c = conseils(DETAIL938, []);
  const ab = c.find((x) => x.code === "arret-brutal");
  assert.equal(ab.elements.filter((e) => e.startsWith("arrêt brutal le")).length, 2);
  assert.ok(ab.elements.some((e) => /BIOS actuel 1\.12\.0/.test(e)));
  assert.ok(ab.etapes.some((e) => /Win32_BIOS/.test(e.commande || "")) && ab.etapes.some((e) => /Dell Inc\. XPS 15 9530/.test(e.texte)));
  const w = c.find((x) => x.code === "wifi");
  assert.equal(w.elements[0], "carte : Killer(R) Wi-Fi 6E AX1675i 160MHz Wireless Network Adapter (211NGW)");
  assert.match(w.constat, /23 incident\(s\)/);
  assert.ok(w.etapes.some((e) => /Set-NetAdapterPowerManagement/.test(e.commande || "")));
  const mj = c.find((x) => x.code === "maj-pilote");
  assert.equal(mj.elements[0], "Realtek Semiconductor Corp. - MEDIA - 6.0.9780.1 -- erreur 0x80070103 (×72)");
  assert.ok(mj.etapes.some((e) => /0x80070103 = pilote déjà installé/.test(e.texte)));
  const ex = c.find((x) => x.code === "plantage@Explorer.EXE");
  assert.ok(ex.etapes.some((e) => /net use ; Get-SmbMapping/.test(e.commande || "")));
  assert.match(ex.elements[0], /ntshrui\.dll, combase\.dll, dernier le/);
  const sa = c.find((x) => x.code === "plantage@SupportAssistInstaller.exe");
  assert.ok(sa.etapes.some((e) => /Dell SupportAssist/.test(e.texte)));
  const dt = c.find((x) => x.code.startsWith("disque-tiede"));
  assert.match(dt.constat, /60 °C \(max relevé 71 °C\)/);
  assert.ok(dt.etapes.some((e) => /-DeviceNumber 0/.test(e.commande || "")));
  assert.ok(!c.some((x) => x.code === "bios"), "pas d'évènement HAL/ACPI ici");
});

test("#938 texte copiable et script des commandes", () => {
  const c = conseils(DETAIL938, []);
  const t = texteConseil(c.find((x) => x.code === "disque-controleur"));
  assert.match(t, /Éléments concernés :\n• 3 évènement/);
  assert.match(t, /Procédure :\n1\. Lister les disques/);
  assert.match(t, /\n   chkdsk E: \/scan/);
  assert.equal(texteConseil(null), "");
  const s = scriptConseils(c);
  assert.match(s, /^# Diagnostic -- commandes proposées/);
  assert.match(s, /# \[MODIFIE\] .*\nchkdsk E: \/scan/);
  assert.match(s, /# Lister les disques[^\n]*\nGet-PhysicalDisk/);
  assert.ok(!/undefined/.test(s));
});
