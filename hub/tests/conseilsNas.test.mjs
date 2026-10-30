// #944 : conseils NAS (SNMP + SSH), calqués sur nas-grpi-1 (anonymisé).
import { test } from "node:test";
import assert from "node:assert/strict";
import { conseilsNas, bilanNas } from "../src/conseilsNas.js";

const N = {
  name: "nas-1", systeme: { modele: "TS-883XU-RP" },
  disques: [{ emplacement: 1, modele: "Seagate ST12000 (SATA)", octets: 12e12, etat: "Good", temperature: 36, heures: 67696, smart: {} },
    { emplacement: 3, modele: "Seagate ST12000 (SATA)", octets: 12e12, etat: "Good", temperature: 39, heures: 20671, smart: {} },
    { emplacement: 8, modele: "Samsung SSD 860 QVO 1TB (SATA)", octets: 1e12, etat: "Good", temperature: 35, heures: 67691, smart: { "secteurs réalloués": 1 } }],
  raid: [{ dev: "/dev/md1", niveau: "5", etat: "Ready", octets: 24e12 }, { dev: "/dev/md2", niveau: "Single", etat: "Ready", octets: 891e9 }],
  volumes: [{ nom: "Volume-1", pct: 84.8, ko: 8.7e9, libre_ko: 1.3e9 }, { nom: "TimeMachineLaurence", pct: 89.7, ko: 852e6, libre_ko: 88e6 }, { nom: "Backup", pct: 1.6, ko: 2.1e9 }, { nom: "TMP_Vol", pct: 0.5, leger: true }],
  applications: [{ nom: "PlexMediaServer", version: "1.30.0", disponible: "1.42.2", mise_a_jour: true, actif: true }, { nom: "VideoStationPro", version: "5.8.4", disponible: "5.8.8", mise_a_jour: true, actif: false }, { nom: "ClamAV", mise_a_jour: false }],
};
const SSH = { ok: true, volumes_sans_snapshot: ["CACHEDEV2_DATA"], snapshots: [{ volume: "CACHEDEV1_DATA", nombre: 3, dernier_age_h: 60, dossier: "/share/CACHEDEV1_DATA/.snapshot", noms: ["GMT-2026.10.28-01.00.00"] }],
  timemachine: [{ machine: "mac-laurence", age_h: 5, chemin: "/share/TM/mac-laurence.sparsebundle", ko: 7e8 }, { machine: "mac-serge", age_h: 400, chemin: "/share/TM/mac-serge.sparsebundle" }], partages_timemachine: ["TimeMachineSerge"] };

test("conseils NAS : disques âgés, SSD seul avec SMART, volumes, snapshots, Time Machine, applications", () => {
  const c = conseilsNas(N, SSH);
  const codes = c.map((x) => x.code);
  assert.ok(codes.includes("disque-age@1") && !codes.includes("disque-age@3"), "7,7 ans oui, 2,4 ans non");
  const ssd = c.find((x) => x.code === "disque-smart@8");
  assert.equal(ssd.niveau, "alerte"); assert.match(ssd.action, /SSD avec secteurs réalloués/); assert.ok(ssd.elements[1].includes("7,7 ans"));
  const md2 = c.find((x) => x.code === "raid-simple@/dev/md2");
  assert.match(md2.action, /Probablement le SSD seul \(Samsung SSD 860 QVO 1TB/); assert.ok(md2.etapes.some((e) => /cat \/proc\/mdstat/.test(e.commande || "")));
  assert.equal(c.find((x) => x.code === "volume-presque-plein@TimeMachineLaurence").niveau, "alerte");
  const tm = conseilsNas({ volumes: [{ nom: "TimeMachineX", pct: 92, ko: 1e9, libre_ko: 1e8 }] }, null).find((x) => x.code === "volume-plein@TimeMachineX");
  assert.equal(tm.niveau, "critique"); assert.match(tm.action, /Time Machine saturé/);
  assert.equal(c.find((x) => x.code === "volume-presque-plein@Volume-1").niveau, "alerte");
  assert.ok(!codes.some((k) => k.endsWith("@TMP_Vol")) && !codes.some((k) => k.endsWith("@Backup")));
  assert.ok(codes.includes("snapshot-absent@CACHEDEV2_DATA") && codes.includes("snapshot-vieux@CACHEDEV1_DATA"));
  assert.ok(codes.includes("timemachine-vieux@mac-serge") && !codes.includes("timemachine-vieux@mac-laurence"));
  const apps = c.find((x) => x.code === "apps-maj");
  assert.equal(apps.niveau, "alerte"); assert.ok(apps.elements.some((e) => /VideoStationPro.*inactive : désinstaller/.test(e)));
  assert.equal(c[0].niveau, "alerte", "rien de critique sur ce relevé : alertes d'abord");
  const b = bilanNas(c);
  assert.ok(b.critique === 0 && b.alerte >= 6);
});

test("conseils NAS : sans SSH, sans problème", () => {
  const c = conseilsNas(N, null);
  assert.ok(c.some((x) => x.code === "ssh-absent") && !c.some((x) => x.code.startsWith("snapshot")));
  const sain = conseilsNas({ name: "x", disques: [{ emplacement: 1, etat: "Good", heures: 1000, smart: {} }], raid: [{ dev: "md1", niveau: "5", etat: "Ready" }], volumes: [{ nom: "V", pct: 40 }], applications: [] }, { ok: true, volumes_sans_snapshot: [], snapshots: [{ volume: "V", nombre: 5, dernier_age_h: 10 }], timemachine: [], partages_timemachine: [] });
  assert.deepEqual(sain, []);
  const deg = conseilsNas({ disques: [], raid: [{ dev: "md1", niveau: "5", etat: "Degraded" }], volumes: [] }, null);
  assert.equal(deg[0].code, "raid-degrade@md1");
});
