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
