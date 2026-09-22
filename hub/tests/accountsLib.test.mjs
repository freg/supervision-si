// Comptes et groupes (livraison #557).
import test from "node:test";
import assert from "node:assert/strict";
import { filterUsers, validateNewUser, membersByGroup, groupDiff } from "../src/accountsLib.js";

const U = [{ username: "bob", first_name: "Bob", email: "bob@exemple.fr", groups: ["site-alpha"] }, { username: "alice", last_name: "Martin", groups: ["administrateurs", "site-alpha"] }, { username: "carol", groups: [] }];

test("filterUsers : recherche large, filtre de groupe, tri", () => {
  assert.deepEqual(filterUsers(U, "").map((u) => u.username), ["alice", "bob", "carol"]);
  assert.deepEqual(filterUsers(U, "martin").map((u) => u.username), ["alice"]);
  assert.deepEqual(filterUsers(U, "", "site-alpha").map((u) => u.username), ["alice", "bob"]);
  assert.deepEqual(filterUsers(U, "exemple", "site-alpha").map((u) => u.username), ["bob"]);
});

test("validateNewUser", () => {
  assert.deepEqual(validateNewUser({ username: "dave", password: "Passe-123" }, true), []);
  assert.ok(validateNewUser({ username: "d" }, true).some((e) => e.includes("identifiant")));
  assert.ok(validateNewUser({ username: "dave", email: "x" }, true).some((e) => e.includes("e-mail")));
  assert.ok(validateNewUser({ username: "dave" }, true).some((e) => e.includes("invitation")));
  assert.ok(validateNewUser({ username: "dave", password: "Passe-123" }, false).some((e) => e.includes("lecture seule")));
  assert.deepEqual(validateNewUser({ username: "dave", password: "Passe-123", allowKeycloakOnly: true }, false), []);
});

test("membersByGroup et groupDiff", () => {
  assert.deepEqual(membersByGroup(U), { "site-alpha": 2, administrateurs: 1 });
  assert.deepEqual(groupDiff(["a", "b"], ["b", "c"]), { added: ["c"], removed: ["a"] });
});
