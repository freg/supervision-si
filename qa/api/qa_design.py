"""Conformité visuelle et ergonomique (#721, item 116 tranches 1 et 2) -- logique PURE, testée sans navigateur.

  AUDIT_JS      : relevé brut dans la page (couleurs calculées, tailles, défilements, en-têtes de tableau, styles en dur) ;
  evaluate()    : règles de design du hub appliquées au relevé -> constats {rule, severity, message, sample} ;
  hub_tour_steps(): « tour du hub » -- une visite par vue (?view=…), attente, audit (capture à chaque visite).

Règles (note design PERMANENTE du 22 sept. 2026 + WCAG) : contraste des textes (4,5:1, 3:1 pour les grands textes),
la page ne défile pas (seuls les cadres et tbody défilent), pas de défilement horizontal, en-têtes de tableau fixes,
cibles cliquables d'au moins 24 px (WCAG 2.2), pas de couleur en dur dans les styles en ligne (variables de theme.css),
textes tronqués signalés. Gravités : erreur, avertissement, info."""
import re

AUDIT_JS = r"""() => {
  const vis = (e) => { const r = e.getBoundingClientRect(), s = getComputedStyle(e); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && s.opacity !== '0'; };
  const bg = (e) => { while (e) { const c = getComputedStyle(e).backgroundColor; if (c && c !== 'transparent' && !/rgba\([^)]*,\s*0\)$/.test(c)) return c; e = e.parentElement; } return 'rgb(255, 255, 255)'; };
  const name = (e) => e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') + (e.classList.length ? '.' + [...e.classList].slice(0, 2).join('.') : '');
  const texts = [];
  for (const e of document.querySelectorAll('body *')) {
    if (texts.length >= 400) break;
    if (!vis(e) || ![...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim())) continue;
    const s = getComputedStyle(e);
    texts.push({ el: name(e), text: e.textContent.trim().slice(0, 40), color: s.color, bg: bg(e), size: parseFloat(s.fontSize), weight: parseInt(s.fontWeight, 10) || 400 });
  }
  const targets = [...document.querySelectorAll('a[href],button,input:not([type=hidden]),select,[role=button]')].filter(vis).slice(0, 300)
    .map((e) => { const r = e.getBoundingClientRect(); return { el: name(e), text: (e.textContent || e.value || e.getAttribute('aria-label') || '').trim().slice(0, 30), w: Math.round(r.width), h: Math.round(r.height), inline: getComputedStyle(e).display === 'inline' }; });
  const truncated = [...document.querySelectorAll('body *')].filter((e) => vis(e) && e.scrollWidth > e.clientWidth + 1 && getComputedStyle(e).textOverflow === 'ellipsis').slice(0, 40)
    .map((e) => ({ el: name(e), text: e.textContent.trim().slice(0, 60) }));
  const tables = [...document.querySelectorAll('table')].filter(vis).slice(0, 40).map((t) => {
    const th = t.querySelector('thead th'); const s = th ? getComputedStyle(th) : null; let p = t.parentElement, scroller = null;
    while (p && p !== document.body) { const o = getComputedStyle(p).overflowY; if (o === 'auto' || o === 'scroll') { scroller = p; break; } p = p.parentElement; }
    return { el: name(t), rows: t.rows.length, has_thead: !!th, sticky: !!s && s.position === 'sticky', in_scroller: !!scroller, overflows: scroller ? scroller.scrollHeight > scroller.clientHeight + 1 : t.getBoundingClientRect().height > innerHeight };
  });
  const inline = [...document.querySelectorAll('[style]')].map((e) => ({ el: name(e), style: e.getAttribute('style') }))
    .filter((x) => /#[0-9a-f]{3,8}\b|rgba?\(/i.test(x.style) && !/var\(/.test(x.style)).slice(0, 40);
  const d = document.documentElement;
  return { url: location.href, title: document.title, theme: d.getAttribute('data-theme') || '', texts, targets, truncated, tables, inline,
           page: { scroll_h: Math.max(d.scrollHeight, document.body.scrollHeight), view_h: innerHeight, scroll_w: Math.max(d.scrollWidth, document.body.scrollWidth), view_w: innerWidth } };
}"""


def parse_rgb(s):
    """« rgb(1, 2, 3) » / « rgba(1, 2, 3, 0.5) » -> (r, g, b, a) ; None si illisible."""
    m = re.match(r"rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)(?:[,\s/]+([\d.]+%?))?\s*\)", str(s or ""))
    if not m:
        return None
    a = m.group(4)
    alpha = 1.0 if a is None else (float(a[:-1]) / 100 if a.endswith("%") else float(a))
    return float(m.group(1)), float(m.group(2)), float(m.group(3)), alpha


def _lum(rgb):
    def ch(c):
        c /= 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = rgb[:3]
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(fg, bg):
    """Rapport de contraste WCAG (1 à 21) ; la couleur du texte semi-transparente est composée sur le fond."""
    f, b = parse_rgb(fg), parse_rgb(bg)
    if not f or not b:
        return None
    if f[3] < 1:
        f = tuple(f[3] * f[i] + (1 - f[3]) * b[i] for i in range(3)) + (1.0,)
    l1, l2 = sorted((_lum(f), _lum(b)), reverse=True)
    return round((l1 + 0.05) / (l2 + 0.05), 2)


def evaluate(m):
    """Relevé AUDIT_JS -> constats (au plus un par règle et par couple de couleurs / élément, exemples bornés)."""
    out = []
    seen = set()
    for t in (m or {}).get("texts") or []:
        r = contrast(t.get("color"), t.get("bg"))
        if r is None:
            continue
        large = (t.get("size") or 0) >= 24 or ((t.get("size") or 0) >= 18.66 and (t.get("weight") or 400) >= 700)
        need = 3.0 if large else 4.5
        key = (t.get("color"), t.get("bg"), large)
        if r < need and key not in seen:
            seen.add(key)
            out.append({"rule": "contraste", "severity": "erreur" if r < 3 else "avertissement",
                        "message": "contraste %.2f:1 < %.1f:1 (%s sur %s)" % (r, need, t.get("color"), t.get("bg")),
                        "sample": "%s « %s »" % (t.get("el"), t.get("text"))})
    p = (m or {}).get("page") or {}
    if p.get("scroll_h") and p.get("view_h") and p["scroll_h"] > p["view_h"] * 1.02 + 4:
        out.append({"rule": "page-defile", "severity": "avertissement",
                    "message": "la page défile (%d px pour %d visibles) : seuls les cadres et les tbody doivent défiler" % (p["scroll_h"], p["view_h"]), "sample": ""})
    if p.get("scroll_w") and p.get("view_w") and p["scroll_w"] > p["view_w"] + 2:
        out.append({"rule": "defilement-horizontal", "severity": "erreur",
                    "message": "défilement horizontal de la page (%d px pour %d)" % (p["scroll_w"], p["view_w"]), "sample": ""})
    for t in (m or {}).get("tables") or []:
        if t.get("has_thead") and t.get("overflows") and not t.get("sticky"):
            out.append({"rule": "entete-fixe", "severity": "avertissement",
                        "message": "en-tête de tableau non fixe alors que le tableau défile (%d lignes)" % (t.get("rows") or 0), "sample": t.get("el")})
    small = [x for x in (m or {}).get("targets") or [] if not x.get("inline") and (x.get("w", 99) < 24 or x.get("h", 99) < 24)]
    if small:
        out.append({"rule": "cible-petite", "severity": "avertissement",
                    "message": "%d cible(s) cliquable(s) de moins de 24 px" % len(small),
                    "sample": ", ".join("%s « %s » %dx%d" % (x["el"], x.get("text") or "", x["w"], x["h"]) for x in small[:5])})
    inl = (m or {}).get("inline") or []
    if inl:
        out.append({"rule": "couleur-en-dur", "severity": "avertissement",
                    "message": "%d style(s) en ligne avec une couleur en dur (utiliser les variables de theme.css)" % len(inl),
                    "sample": " ; ".join("%s : %s" % (x["el"], x["style"][:60]) for x in inl[:3])})
    tr = (m or {}).get("truncated") or []
    if tr:
        out.append({"rule": "texte-tronque", "severity": "info", "message": "%d texte(s) tronqué(s) (…)" % len(tr),
                    "sample": " ; ".join("%s « %s »" % (x["el"], x["text"]) for x in tr[:3])})
    return out


def score(findings):
    """Note sur 100 : -15 par erreur, -5 par avertissement, -1 par info (plancher 0)."""
    w = {"erreur": 15, "avertissement": 5, "info": 1}
    return max(0, 100 - sum(w.get(f.get("severity"), 0) for f in findings or []))


def hub_tour_steps(views, wait_ms=1500, strict=False):
    """Tour du hub : pour chaque vue {view, label} -> aller à ?view=…, attendre, auditer (capture à chaque visite)."""
    steps = []
    for v in views or []:
        vid = str((v or {}).get("view") or "").strip()
        if not re.fullmatch(r"[a-z0-9-]{1,60}", vid):
            continue
        label = str(v.get("label") or vid)[:80]
        steps += [{"action": "goto", "selector": "", "value": "/?view=" + vid, "note": label},
                  {"action": "wait", "selector": "", "value": str(int(wait_ms)), "note": ""},
                  {"action": "audit", "selector": "", "value": "strict" if strict else "", "note": label}]
    return steps
