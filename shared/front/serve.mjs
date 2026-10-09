// #737 : serveur statique commun des fronts pré-compilés (repris du hub, #681), avec chemin de base (FRONT_BASE,
// ex. /tickets/) : /tickets/assets/x -> dist/assets/x. Sans dépendance.
// - index.html (et toute route inconnue sans extension = SPA) : « pas de cache », le navigateur revalide à chaque
//   chargement -> une mise à jour du hub est vue immédiatement, plus de copie périmée (page blanche du 2026-10-06) ;
// - /assets/* (noms à empreinte, changent à chaque build) : cache d'un an, immuable ;
// - jamais de compression ici : le frontal public réécrit l'origine interne dans les corps (substitution), ce qu'il
//   ne peut pas faire sur un contenu compressé -- la passerelle nginx compresse si besoin.
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const TYPES = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".mjs": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8", ".json": "application/json; charset=utf-8", ".svg": "image/svg+xml", ".png": "image/png",
  ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".ico": "image/x-icon", ".webp": "image/webp",
  ".woff": "font/woff", ".woff2": "font/woff2", ".ttf": "font/ttf", ".map": "application/json; charset=utf-8", ".txt": "text/plain; charset=utf-8" };

export const NO_CACHE = "no-cache, no-store, must-revalidate";
export const IMMUTABLE = "public, max-age=31536000, immutable";

// Chemin d'URL -> {file, cache} sous root, ou null (traversée refusée). Route sans extension inconnue -> index.html.
export function resolve(root, urlPath, exists = fs.existsSync) {
  let p;
  try { p = decodeURIComponent(String(urlPath || "/").split("?")[0]); } catch { return null; }
  if (p.includes("\0")) return null;
  const abs = path.resolve(root, "." + path.posix.normalize("/" + p));
  if (abs !== path.resolve(root) && !abs.startsWith(path.resolve(root) + path.sep)) return null;
  const isFile = (f) => { try { return exists(f) && fs.statSync(f).isFile(); } catch { return exists(f) && path.extname(f) !== ""; } };
  if (p !== "/" && isFile(abs)) return { file: abs, cache: p.startsWith("/assets/") ? IMMUTABLE : NO_CACHE };
  if (path.extname(p) && p !== "/") return { file: null, cache: NO_CACHE };              // fichier absent -> 404
  return { file: path.join(root, "index.html"), cache: NO_CACHE };                          // SPA
}

/** Retire le chemin de base (« /tickets/ ») d'une URL ; hors base : inchangée. */
export function stripBase(url, base = "/") {
  const b = "/" + String(base || "/").replace(/^\/+|\/+$/g, "");
  if (b === "/") return url;
  const u = String(url || "/");
  if (u === b || u.startsWith(b + "?")) return "/" + u.slice(b.length);
  if (u.startsWith(b + "/")) return u.slice(b.length);
  return u;
}

export function createServer(root, base = "/") {
  return http.createServer((req, res) => {
    if (req.method !== "GET" && req.method !== "HEAD") { res.writeHead(405, { Allow: "GET, HEAD" }); return res.end(); }
    const r = resolve(root, stripBase(req.url, base));
    if (!r) { res.writeHead(400); return res.end("chemin invalide\n"); }
    if (!r.file) { res.writeHead(404, { "Cache-Control": NO_CACHE, "Content-Type": "text/plain; charset=utf-8" }); return res.end("introuvable\n"); }
    fs.stat(r.file, (err, st) => {
      if (err) { res.writeHead(404, { "Cache-Control": NO_CACHE }); return res.end(); }
      res.writeHead(200, { "Content-Type": TYPES[path.extname(r.file).toLowerCase()] || "application/octet-stream",
        "Content-Length": st.size, "Cache-Control": r.cache, "X-Content-Type-Options": "nosniff" });
      if (req.method === "HEAD") return res.end();
      fs.createReadStream(r.file).pipe(res);
    });
  });
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const root = path.resolve(process.env.FRONT_DIST || "dist");
  const port = Number(process.env.PORT || 5173);
  const base = process.env.FRONT_BASE || "/";
  createServer(root, base).listen(port, "0.0.0.0", () => console.log(`front compilé servi depuis ${root} sous ${base} sur :${port}`));
}
