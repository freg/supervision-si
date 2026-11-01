// Tests #697 : lecture MIME du visualiseur (tuile Serveur de messagerie).
import { test } from "node:test";
import assert from "node:assert/strict";
import { decodeWords, parseHeaders, parseParams, parseMessage, extractBodies, safeHtmlDocument, summarize, decodeQuotedPrintable } from "../src/mailMime.js";

const b64 = (s) => Buffer.from(s, "utf-8").toString("base64");

const RAW = [
  "Return-Path: <alice@exemple.org>",
  "From: =?utf-8?B?" + b64("Alice Élodie") + "?= <alice@exemple.org>",
  "To: bob@exemple.fr",
  "Subject: =?iso-8859-1?Q?Facture_de_d=E9cembre?=",
  "  =?utf-8?Q?_n=C2=B012?=",
  "Date: Wed, 07 Oct 2026 10:00:00 +0200",
  "Message-ID: <m1@exemple.org>",
  "X-Spam-Status: No, score=-1.2",
  "MIME-Version: 1.0",
  'Content-Type: multipart/mixed; boundary="EXT"',
  "",
  "Préambule ignoré",
  "--EXT",
  'Content-Type: multipart/related; boundary="REL"',
  "",
  "--REL",
  'Content-Type: multipart/alternative; boundary="ALT"',
  "",
  "--ALT",
  "Content-Type: text/plain; charset=utf-8",
  "Content-Transfer-Encoding: quoted-printable",
  "",
  "Bonjour, voici la facture de d=C3=A9cembre. Ligne coup=",
  "=C3=A9e.",
  "--ALT",
  "Content-Type: text/html; charset=utf-8",
  "Content-Transfer-Encoding: base64",
  "",
  b64('<p>Bonjour <b>Bob</b></p><img src="cid:logo@x"><img src="https://pistage.example/p.gif"><script>alert(1)</script><meta http-equiv="refresh" content="0;url=https://x.example">'),
  "--ALT--",
  "--REL",
  "Content-Type: image/png",
  "Content-Transfer-Encoding: base64",
  "Content-ID: <logo@x>",
  "",
  "iVBORw0KGgo=",
  "--REL--",
  "--EXT",
  "Content-Type: application/pdf; name*=utf-8''facture%20d%C3%A9cembre.pdf",
  "Content-Disposition: attachment",
  "Content-Transfer-Encoding: base64",
  "",
  b64("%PDF-1.4 faux"),
  "--EXT--",
  "épilogue",
].join("\r\n");

test("mots encodés RFC 2047 (B, Q, jeux de caractères, blancs entre mots)", () => {
  assert.equal(decodeWords("=?utf-8?B?" + b64("Élodie") + "?="), "Élodie");
  assert.equal(decodeWords("=?iso-8859-1?Q?d=E9cembre?= =?utf-8?Q?_n=C2=B012?="), "décembre n°12");
  assert.equal(decodeWords("sans encodage"), "sans encodage");
  assert.equal(new TextDecoder().decode(decodeQuotedPrintable("caf=C3=A9=\r\n!")), "café!");
});

test("en-têtes repliés et paramètres (RFC 2231)", () => {
  const h = parseHeaders("Subject: un\r\n  deux\r\nX-A: b");
  assert.deepEqual(h.map((x) => [x.name, x.value]), [["Subject", "un deux"], ["X-A", "b"]]);
  const p = parseParams("application/pdf; name*=utf-8''facture%20d%C3%A9cembre.pdf; x=\"a;b\"");
  assert.equal(p.type, "application/pdf"); assert.equal(p.params.name, "facture décembre.pdf"); assert.equal(p.params.x, "a;b");
});

test("arbre MIME, corps, pièces jointes, images inline", () => {
  const s = summarize(RAW);
  assert.equal(s.from, "Alice Élodie <alice@exemple.org>");
  assert.equal(s.subject, "Facture de décembre n°12");
  assert.equal(s.spam, "No, score=-1.2");
  assert.equal(s.tree.parts.length, 2);
  assert.match(s.text, /facture de décembre\. Ligne coupée\./);
  assert.match(s.html, /<b>Bob<\/b>/);
  assert.deepEqual(s.attachments.map((a) => [a.filename, a.type, a.inline]), [["(sans nom)", "image/png", true], ["facture décembre.pdf", "application/pdf", false]]);
  assert.ok(s.cidMap["logo@x"].startsWith("data:image/png;base64,"));
  assert.equal(s.remoteImages, 1);
});

test("document HTML inoffensif : CSP stricte, cid -> data:, rafraîchissement retiré", () => {
  const s = summarize(RAW);
  const doc = safeHtmlDocument(s);
  assert.match(doc, /Content-Security-Policy" content="default-src 'none'; img-src data:/);
  assert.ok(doc.includes('src="data:image/png;base64,'));
  assert.ok(!/http-equiv="refresh"/i.test(doc.replace(/Content-Security-Policy/, "")));
  const plain = safeHtmlDocument({ html: "", text: "<b>pas du HTML</b>" });
  assert.ok(plain.includes("&lt;b&gt;pas du HTML&lt;/b&gt;"));
});

test("message simple, tronqué ou malformé : jamais d'exception", () => {
  const simple = parseMessage("Subject: x\n\ncorps");
  assert.equal(simple.text, "corps");
  const cut = parseMessage('Content-Type: multipart/mixed; boundary="B"\n\n--B\nContent-Type: text/plain\n\ndébut seulement');
  assert.equal(cut.parts.length, 1); assert.equal(cut.parts[0].text, "début seulement");
  assert.doesNotThrow(() => summarize(""));
  assert.doesNotThrow(() => summarize("Content-Type: text/plain; charset=inconnu-42\nContent-Transfer-Encoding: base64\n\n@@@"));
  assert.equal(extractBodies(parseMessage("Content-Type: image/gif\n\nGIF89a")).attachments[0].type, "image/gif");
});
