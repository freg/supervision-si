import test from "node:test";
import assert from "node:assert/strict";
import { niveauSignal, lignesRadar, ageBalayage, classeSignal, bande, libelleClient, ouEstBranche, tableBrassage, anomaliesBrassage, versFraction, texteReleve, syntheseCouverture, tailleReduite } from "../src/reperageLib.js";

const inv = { clients: [
  { mac: "aa:bb:cc:00:00:01", nom: "ecran-amphi", ip: "172.16.20.10", type: "filaire", commutateur: "GS-1", commutateur_id: "d1", port: 12, vlan: 20 },
  { mac: "aa:bb:cc:00:00:02", type: "filaire", commutateur: "GS-1", commutateur_id: "d1", port: 3, fabricant: "Zyxel" },
  { mac: "aa:bb:cc:00:00:03", nom: "Pixel", type: "wifi", borne: "Studio", ssid: "numeria", signal: -58, bande: "band5", canal: 44 },
], commutateurs: [{ id: "d1", nom: "GS-1", ports: { "12": ["aa:bb:cc:00:00:01"], "3": ["aa:bb:cc:00:00:02"] } }] };

test("classes et libellés", () => {
  assert.deepEqual([-50, -65, -75, -85, null, "x"].map(classeSignal), ["bon", "moyen", "faible", "mauvais", "inconnu", "inconnu"]);
  assert.equal(bande("band24"), "2,4 GHz"); assert.equal(bande("zz"), "zz");
  assert.equal(libelleClient(inv.clients[1]), "Zyxel"); assert.equal(libelleClient(null), "");
  assert.equal(ouEstBranche(inv.clients[0]), "GS-1 port 12 · VLAN 20");
  assert.equal(ouEstBranche(inv.clients[2]), "borne Studio · numeria · -58 dBm · 5 GHz");
  assert.equal(ouEstBranche({ type: "inconnu", vlan: 7 }), "VLAN 7 (port inconnu)");
});

test("table de brassage et anomalies", () => {
  const prises = [{ prise: "B-12", commutateur: "GS-1", port: 12, mac: "aa:bb:cc:00:00:09", equipement: "PC accueil" }, { prise: "B-13", commutateur: "GS-1", port: 12 }, { prise: "C-1", commutateur: "GS-2", port: 1 }];
  const t = tableBrassage(inv, prises);
  assert.equal(t.commutateurs[0].ports.map((p) => p.port).join(","), "3,12");
  assert.equal(t.commutateurs[0].ports[1].prises.length, 2); assert.equal(t.commutateurs[0].ports[1].clients[0].nom, "ecran-amphi");
  assert.deepEqual(t.orphelines.map((p) => p.prise), ["C-1"]);
  const a = anomaliesBrassage(t);
  assert.deepEqual(a.map((x) => x.genre), ["doublon", "equipement"]);
  assert.match(a[1].texte, /attendu PC accueil, vu ecran-amphi/);
  assert.deepEqual(tableBrassage(null, []), { commutateurs: [], orphelines: [] });
});

test("fraction, relevés, synthèse, photo", () => {
  assert.deepEqual(versFraction(150, 50, { left: 100, top: 0, width: 100, height: 100 }), { x: 0.5, y: 0.5 });
  assert.deepEqual(versFraction(999, -5, { left: 0, top: 0, width: 10, height: 10 }), { x: 1, y: 0 }); assert.equal(versFraction(1, 1, null), null);
  assert.equal(texteReleve({ borne: "Studio", rssi_mobile: -61, bande: "band5", canal: 44, note: "porte" }), "Studio · -61 dBm (téléphone) · 5 GHz · canal 44 — porte");
  assert.equal(texteReleve({ signal: -70 }), "borne ? · -70 dBm (vu par la borne)");
  const s = syntheseCouverture([{ borne: "A", signal: -55 }, { borne: "A", rssi_mobile: -75 }, { borne: "B", signal: -90 }, { signal: null }]);
  assert.equal(s.total, 4); assert.equal(s.faibles, 2); assert.equal(s.bornes[0].borne, "A"); assert.equal(s.bornes[0].median, -55);
  assert.deepEqual(tailleReduite(4000, 3000), { w: 1600, h: 1200 }); assert.deepEqual(tailleReduite(800, 600), { w: 800, h: 600 }); assert.deepEqual(tailleReduite(0, 0), { w: 0, h: 0 });
});

test("radar", () => {
  assert.equal(niveauSignal(-90), 0); assert.equal(niveauSignal(-40), 1); assert.equal(niveauSignal(-65), 0.5); assert.equal(niveauSignal(null), 0);
  const l = lignesRadar([{ bssid: "a", rssi: -70, bande: "band5", canal: 36, distance_m: 12.3 }, { bssid: "b", ssid: "GROUPE_I", rssi: -50, bande: "band24", distance_m: 2.5 }]);
  assert.equal(l[0].nom, "GROUPE_I");
  assert.equal(lignesRadar([{ bssid: "c", ssid: "X", rssi: -50, connecte: 1 }])[0].nom, "X ● connecté"); assert.equal(l[0].distance, "2,5 m"); assert.equal(l[1].distance, "12 m"); assert.equal(l[1].bande, "5 GHz"); assert.equal(l[1].classe, "moyen");
  assert.equal(ageBalayage(null), "jamais"); assert.equal(ageBalayage(1000, 1030), "il y a 30 s"); assert.equal(ageBalayage(1000, 1000 + 7200), "il y a 2 h");
});
