"""Plan vectoriel depuis un PDF de DCE (livraison #569) -- garde l'architecture
(traits gris/noirs, textes noirs : noms de salles), écarte les symboles de
lots techniques (couleurs) et le cartouche (droite de la page), retire les
mots interdits (nom du client, du site…). Nécessite pymupdf.

Usage : python3 plan_from_pdf.py <plan.pdf> <plan.svg> [ratio_x_max=0.70] [mots,interdits]
Le SVG obtenu se dépose dans Nebula → Plan du site (jamais dans le dépôt :
c'est une donnée du site)."""
import sys, re, collections
import pymupdf

src, dst = sys.argv[1], sys.argv[2]
xmax_ratio = float(sys.argv[3]) if len(sys.argv) > 3 else 0.70
DROP_WORDS = [w for w in (sys.argv[4].split(",") if len(sys.argv) > 4 else []) if w]
d = pymupdf.open(src); p = d[0]; M = p.rotation_matrix
W, H = p.rect.width, p.rect.height
xmax = W * xmax_ratio

def T(pt):
    q = pymupdf.Point(pt) * M
    return q.x, q.y

def grey(c):
    return c is not None and abs(c[0]-c[1]) < 0.05 and abs(c[1]-c[2]) < 0.05

groups = collections.defaultdict(list)  # (stroke, fill, width) -> [d]
xs=[]; ys=[]
for it in p.get_drawings():
    c, f = it.get("color"), it.get("fill")
    if not (grey(c) or (c is None and grey(f))):
        continue
    if c is not None and c[0] < 0.05 and f is None and it.get("width", 0) > 1.5:
        pass  # traits noirs épais : bordures de cartouche, filtrés par la zone
    parts = []
    pts = []
    for item in it["items"]:
        k = item[0]
        if k == "l":
            a, b = T(item[1]), T(item[2]); parts.append("M%.1f %.1fL%.1f %.1f" % (a + b)); pts += [a, b]
        elif k == "c":
            a, b, c2, e = T(item[1]), T(item[2]), T(item[3]), T(item[4]); parts.append("M%.1f %.1fC%.1f %.1f %.1f %.1f %.1f %.1f" % (a + b + c2 + e)); pts += [a, e]
        elif k == "re":
            r = item[1]; q = [T((r.x0, r.y0)), T((r.x1, r.y0)), T((r.x1, r.y1)), T((r.x0, r.y1))]
            parts.append("M%.1f %.1fL%.1f %.1fL%.1f %.1fL%.1f %.1fZ" % tuple(v for pt in q for v in pt)); pts += q
        elif k == "qu":
            q = [T(item[1].ul), T(item[1].ur), T(item[1].lr), T(item[1].ll)]
            parts.append("M%.1f %.1fL%.1f %.1fL%.1f %.1fL%.1f %.1fZ" % tuple(v for pt in q for v in pt)); pts += q
    if not parts or not pts:
        continue
    if max(x for x, _ in pts) > xmax:  # cartouche / légende
        continue
    if it.get("closePath") and parts[-1][-1] != "Z":
        parts[-1] += "Z"
    key = (tuple(round(x, 2) for x in c) if c else None, tuple(round(x, 2) for x in f) if f else None, round(it.get("width") or 0.5, 2))
    groups[key].append("".join(parts))
    xs += [x for x, _ in pts]; ys += [y for _, y in pts]

texts = []
for b in p.get_text("dict")["blocks"]:
    for l in b.get("lines", []):
        for s in l["spans"]:
            t = s["text"].strip()
            if not t or s["color"] != 0 or s["size"] < 3.5:
                continue
            if re.fullmatch(r"[\d.,\s%°xX×/-]+", t):
                continue
            if any(k in t.lower() for k in DROP_WORDS):  # jamais de nom de client / de site dans le dépôt
                continue
            x, y = T((s["origin"][0], s["origin"][1]))
            if x > xmax:
                continue
            ang = l["dir"]
            texts.append((x, y, s["size"], t, ang))

pad = 20
x0, y0, x1, y1 = min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad
out = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="%.1f %.1f %.1f %.1f" width="%.0f" height="%.0f">' % (x0, y0, x1 - x0, y1 - y0, x1 - x0, y1 - y0),
       '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="#ffffff"/>' % (x0, y0, x1 - x0, y1 - y0)]
def hexc(c):
    return "#%02x%02x%02x" % tuple(int(round(v * 255)) for v in c)
for (c, f, w), ds in sorted(groups.items(), key=lambda kv: (kv[0][1] is None, kv[0][2])):
    stroke = hexc(c) if c else "none"
    if c and c[0] > 0.8:
        stroke = "#bdbdbd"
    elif c and c[0] > 0.3:
        stroke = "#6f6f6f"
    fill = hexc(f) if f else "none"
    if f and f[0] > 0.8:
        fill = "#e6e6e6"
    elif f:
        fill = "#8c8c8c"
    out.append('<path fill="%s" stroke="%s" stroke-width="%.2f" stroke-linecap="round" stroke-linejoin="round" d="%s"/>' % (fill, stroke, max(w, 0.4), "".join(ds)))
out.append('<g font-family="Arial, Helvetica, sans-serif" fill="#1f1f1f">')
for x, y, size, t, ang in texts:
    t = t.replace("&", "&amp;").replace("<", "&lt;")
    # direction du texte dans la page non tournée -> tournée de 270°
    dx, dy = ang
    rx, ry = dy, -dx  # direction transformée par la matrice de rotation (a=0,b=-1,c=1,d=0)
    import math
    deg = math.degrees(math.atan2(ry, rx))
    tr = ' transform="rotate(%.1f %.1f %.1f)"' % (deg, x, y) if abs(deg) > 0.5 else ""
    out.append('<text x="%.1f" y="%.1f" font-size="%.1f"%s>%s</text>' % (x, y, size, tr, t))
out.append("</g></svg>")
open(dst, "w").write("\n".join(out))
print("paths", sum(len(v) for v in groups.values()), "groups", len(groups), "texts", len(texts), "bbox", round(x0), round(y0), round(x1), round(y1), "ko", len("\n".join(out)) // 1024)

