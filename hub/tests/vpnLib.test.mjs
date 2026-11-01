import test from "node:test";
import assert from "node:assert/strict";
import { operateur, stabilite } from "../src/vpnLib.js";

test("#888 : opérateur et type d'accès d'après le nom inverse", () => {
  assert.deepEqual(operateur("customer.exemple1.isp.starlink.com", "198.51.100.7"), { operateur: "Starlink", acces: "satellite" });
  assert.deepEqual(operateur("92-0-0-1.mobile.fr.orangecustomers.net"), { operateur: "Orange", acces: "mobile" });
  assert.deepEqual(operateur("lfbn-poi-1-2-3.w1-2.abo.wanadoo.fr"), { operateur: "Orange", acces: "fixe" });
  assert.deepEqual(operateur("vps-1.inconnu.example.net"), { operateur: "example.net", acces: "" });
  assert.deepEqual(operateur("", "198.51.100.7"), { operateur: "", acces: "" });
  assert.deepEqual(operateur("198.51.100.7", "198.51.100.7"), { operateur: "", acces: "" });
});

test("#888 : stabilité -- sessions courtes et reconnexions rapprochées", () => {
  const s = [
    { nom: "alice", debut: "2026-10-28T09:11:20", fin: "2026-10-28T10:18:57", duree_s: 4057, nom_origine: "c.isp.starlink.com" },
    { nom: "alice", debut: "2026-10-28T10:19:01", fin: "2026-10-28T10:19:44", duree_s: 43, nom_origine: "c.isp.starlink.com" },
    { nom: "alice", debut: "2026-10-28T14:00:00", fin: null, duree_s: 60, en_cours: true, nom_origine: "c.isp.starlink.com" },
    { nom: "bob", debut: "2026-10-27T15:10:48", fin: "2026-10-27T15:13:52", duree_s: 600, nom_origine: "x.mobile.fr.orangecustomers.net" },
  ];
  const [a, b] = stabilite(s);
  assert.equal(a.nom, "alice");
  assert.equal(a.sessions, 3);
  assert.equal(a.courtes, 1);           // 43 s ; la session en cours n'est pas « courte »
  assert.equal(a.reconnexions, 1);      // 4 s après la fin de la précédente
  assert.deepEqual(a.operateurs, ["Starlink (satellite)"]);
  assert.equal(b.reconnexions + b.courtes, 0);
});
