// Lecture d'un message brut (RFC 5322 / MIME) pour la tuile « Serveur de
// messagerie » (#697) : en-têtes décodés (RFC 2047), arbre MIME, corps texte
// et HTML, pièces jointes, images inline (cid:). Pur, sans dépendance -- testé
// par tests/mailMime.test.mjs.
//
// Visualiseur HTML : `safeHtmlDocument` enveloppe le HTML du message dans une
// politique de sécurité qui interdit scripts, formulaires, cadres et TOUT
// chargement distant (images de pistage comprises) ; seules les images
// embarquées (cid: -> data:) s'affichent. À rendre dans
// <iframe sandbox="" srcDoc=…> (sandbox vide = ni script ni même origine).

const decoderFor = (charset) => {
  const cs = String(charset || "utf-8").trim().toLowerCase().replace(/^"|"$/g, "");
  try { return new TextDecoder(cs === "us-ascii" || cs === "ascii" ? "utf-8" : cs); } catch { return new TextDecoder("utf-8"); }
};

export function bytesFromBinaryString(s) {
  const out = new Uint8Array(s.length);
  for (let i = 0; i < s.length; i++) out[i] = s.charCodeAt(i) & 0xff;
  return out;
}

export function decodeBase64(text) {
  const clean = String(text || "").replace(/[^A-Za-z0-9+/=]/g, "");
  try { return bytesFromBinaryString(atob(clean.replace(/=+$/, "").padEnd(Math.ceil(clean.replace(/=+$/, "").length / 4) * 4, "="))); } catch { return new Uint8Array(0); }
}

export function decodeQuotedPrintable(text, { header = false } = {}) {
  let s = String(text || "");
  if (header) s = s.replace(/_/g, " ");
  else s = s.replace(/=\r?\n/g, "");
  const bytes = [];
  const enc = new TextEncoder();
  for (let i = 0; i < s.length; i++) {
    const c = s[i];
    if (c === "=" && /^[0-9A-Fa-f]{2}$/.test(s.slice(i + 1, i + 3))) { bytes.push(parseInt(s.slice(i + 1, i + 3), 16)); i += 2; }
    else { const code = s.charCodeAt(i); if (code < 128) bytes.push(code); else bytes.push(...enc.encode(c)); }
  }
  return new Uint8Array(bytes);
}

/** « =?utf-8?B?…?= » et « =?iso-8859-1?Q?…?= » -> texte ; les blancs entre deux mots encodés disparaissent. */
export function decodeWords(value) {
  return String(value || "")
    .replace(/(=\?[^?]+\?[BbQq]\?[^?]*\?=)\s+(?==\?[^?]+\?[BbQq]\?)/g, "$1")
    .replace(/=\?([^?*]+)(?:\*[^?]*)?\?([BbQq])\?([^?]*)\?=/g, (_, cs, enc, txt) => {
      const bytes = enc.toUpperCase() === "B" ? decodeBase64(txt) : decodeQuotedPrintable(txt, { header: true });
      return decoderFor(cs).decode(bytes);
    });
}

export function splitHeadBody(raw) {
  const s = String(raw || "");
  const m = /\r?\n\r?\n/.exec(s);
  return m ? [s.slice(0, m.index), s.slice(m.index + m[0].length)] : [s, ""];
}

/** En-têtes -> [{name, value}] (lignes repliées dépliées, valeurs décodées), dans l'ordre. */
export function parseHeaders(head) {
  const out = [];
  for (const line of String(head || "").split(/\r?\n/)) {
    if (/^[ \t]/.test(line) && out.length) out[out.length - 1].raw += " " + line.trim();
    else { const i = line.indexOf(":"); if (i > 0) out.push({ name: line.slice(0, i).trim(), raw: line.slice(i + 1).trim() }); }
  }
  return out.map((h) => ({ name: h.name, value: decodeWords(h.raw), raw: h.raw }));
}

export const header = (headers, name) => (headers.find((h) => h.name.toLowerCase() === name.toLowerCase()) || {}).value || "";

/** « text/html; charset="utf-8"; name*=… » -> {type, params}. */
export function parseParams(value) {
  const parts = String(value || "").split(/;(?=(?:[^"]*"[^"]*")*[^"]*$)/);
  const params = {};
  for (const p of parts.slice(1)) {
    const i = p.indexOf("=");
    if (i < 0) continue;
    let k = p.slice(0, i).trim().toLowerCase(); let v = p.slice(i + 1).trim().replace(/^"|"$/g, "");
    if (k.endsWith("*")) {                         // RFC 2231 : utf-8''nom%20encod%C3%A9
      k = k.replace(/\*\d*\*?$/, "");
      const m = /^([^']*)'[^']*'(.*)$/.exec(v);
      if (m) { try { v = decoderFor(m[1] || "utf-8").decode(decodeQuotedPrintable(m[2].replace(/%/g, "="))); } catch { /* tel quel */ } }
      params[k] = (params[k] || "") + v;
    } else params[k] = decodeWords(v);
  }
  return { type: (parts[0] || "").trim().toLowerCase(), params };
}

function bodyBytes(body, encoding) {
  const enc = String(encoding || "").toLowerCase().trim();
  if (enc === "base64") return decodeBase64(body);
  if (enc === "quoted-printable") return decodeQuotedPrintable(body);
  return null;                                     // 7bit / 8bit / binary : texte déjà lisible
}

/** Message brut -> arbre MIME {headers, type, params, disposition, filename, cid, text?, bytes?, parts[]}. */
export function parseMessage(raw, depth = 0) {
  const [head, body] = splitHeadBody(raw);
  const headers = parseHeaders(head);
  const ct = parseParams(header(headers, "Content-Type") || "text/plain; charset=us-ascii");
  const disp = parseParams(header(headers, "Content-Disposition"));
  const node = {
    headers, type: ct.type || "text/plain", params: ct.params, disposition: disp.type || "",
    filename: disp.params.filename || ct.params.name || "", cid: header(headers, "Content-ID").replace(/^<|>$/g, ""),
    encoding: header(headers, "Content-Transfer-Encoding").toLowerCase(), parts: [], size: body.length,
  };
  if (node.type.startsWith("multipart/") && ct.params.boundary && depth < 20) {
    const b = "--" + ct.params.boundary;
    const chunks = []; let cur = null;
    for (const line of body.split(/\r?\n/)) {
      const t = line.trimEnd();
      if (t === b + "--") { if (cur) chunks.push(cur); cur = null; break; }
      if (t === b) { if (cur) chunks.push(cur); cur = []; continue; }
      if (cur) cur.push(line);
    }
    if (cur) chunks.push(cur);                     // message tronqué : dernière partie gardée
    node.parts = chunks.map((c) => c.join("\n")).filter((c) => c.trim()).map((c) => parseMessage(c, depth + 1));
  } else if (node.type === "message/rfc822" && depth < 20) {
    node.parts = [parseMessage(body, depth + 1)];
  } else {
    const bytes = bodyBytes(body, node.encoding);
    if (node.type.startsWith("text/")) node.text = bytes ? decoderFor(ct.params.charset).decode(bytes) : body;
    else node.bytes = bytes || bytesFromBinaryString(body);
  }
  return node;
}

function walk(node, fn) { fn(node); node.parts.forEach((p) => walk(p, fn)); }

function toDataUrl(type, bytes) {
  let s = "";
  for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
  return `data:${type};base64,${btoa(s)}`;
}

/** Arbre -> {html, text, attachments:[{filename,type,size,cid,inline}], cidMap} ; l'HTML l'emporte sur le texte (alternative). */
export function extractBodies(tree) {
  let html = "", text = "";
  const attachments = [], cidMap = {};
  walk(tree, (n) => {
    if (n.parts.length) return;
    const isAttachment = n.disposition === "attachment" || (n.filename && n.disposition !== "inline" && !n.type.startsWith("text/"));
    if (!isAttachment && n.type === "text/html" && n.text !== undefined) html += n.text;
    else if (!isAttachment && n.type === "text/plain" && n.text !== undefined) text += (text ? "\n\n" : "") + n.text;
    else {
      const size = n.bytes ? n.bytes.length : (n.text || "").length;
      attachments.push({ filename: n.filename || "(sans nom)", type: n.type, size, cid: n.cid, inline: !!n.cid && n.type.startsWith("image/") });
      if (n.cid && n.bytes && n.type.startsWith("image/")) cidMap[n.cid] = toDataUrl(n.type, n.bytes);
    }
  });
  return { html, text, attachments, cidMap };
}

const escapeHtml = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

/** Document HTML autonome et inoffensif pour <iframe sandbox="" srcDoc>. */
export function safeHtmlDocument({ html, text, cidMap = {} }) {
  const body = html
    ? html.replace(/<meta[^>]+http-equiv\s*=\s*["']?refresh[^>]*>/gi, "").replace(/cid:([^"'\s)>]+)/gi, (m, id) => cidMap[id] || cidMap[decodeURIComponent(id)] || "about:blank")
    : `<pre style="white-space:pre-wrap;font:13px/1.45 ui-monospace,monospace">${escapeHtml(text || "")}</pre>`;
  const csp = "default-src 'none'; img-src data:; style-src 'unsafe-inline'; font-src data:; form-action 'none'; frame-src 'none'; base-uri 'none'";
  return `<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="${csp}"><base target="_blank"></head><body>${body}</body></html>`;
}

/** Résumé pour l'en-tête du visualiseur. */
export function summarize(raw) {
  const tree = parseMessage(raw);
  const h = (n) => header(tree.headers, n);
  const bodies = extractBodies(tree);
  const remote = (bodies.html.match(/\b(?:src|background)\s*=\s*["']?https?:/gi) || []).length;
  return { tree, from: h("From"), to: h("To"), cc: h("Cc"), subject: h("Subject"), date: h("Date"), messageId: h("Message-ID"),
    spam: h("X-Spam-Status") || h("X-Spam-Score") || h("X-Spam-Flag"), ...bodies, remoteImages: remote };
}
