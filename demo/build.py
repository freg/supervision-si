# -*- coding: utf-8 -*-
"""Diaporama HTML autonome (images incluses, thème sombre, flèches / lecture automatique / plein écran) et présentation
.pptx (16:9, une capture par diapositive, légende et notes) à partir du manifeste d'une visite (livraison #982).

  python3 build.py <dossier de la visite>     (refait les deux fichiers sans repasser dans le hub)
"""
import base64
import html as H
import json
import os
import sys


def _manifeste(dossier):
    with open(os.path.join(dossier, "manifeste.json"), encoding="utf-8") as fh:
        return json.load(fh)


def diaporama(dossier, m):
    diapos = ['<section class="titre"><h1>%s</h1><p>%s</p><p class="m">%s%s · %s</p></section>' % (
        H.escape(m["titre"]), H.escape(m.get("sous_titre") or ""), H.escape(m.get("public") or ""),
        (" · livraison #%s" % H.escape(str(m["livraison"]))) if m.get("livraison") else "", H.escape(m["date"]))]
    for i, e in enumerate(m["etapes"], 1):
        with open(os.path.join(dossier, e["image"]), "rb") as fh:
            b64 = base64.b64encode(fh.read()).decode("ascii")
        diapos.append('<section><h2><span>%d/%d</span> %s</h2><img alt="%s" src="data:image/png;base64,%s"><p>%s</p></section>' % (
            i, len(m["etapes"]), H.escape(e["titre"]), H.escape(e["titre"]), b64, H.escape(e.get("legende") or "")))
    page = """<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>%(titre)s</title><style>
:root{--bg:#14171c;--panel:#1f242c;--text:#e8eaed;--muted:#9aa3ad;--accent:#4aa3df}
html,body{margin:0;height:100%%;background:var(--bg);color:var(--text);font-family:system-ui,-apple-system,"Segoe UI",sans-serif}
section{display:none;height:100vh;box-sizing:border-box;padding:2vh 3vw 9vh;flex-direction:column;align-items:center;justify-content:center;gap:1.2vh}
section.on{display:flex}
section.titre h1{font-size:4.2vw;margin:0;text-align:center}section.titre p{font-size:1.8vw;color:var(--muted);margin:0;text-align:center}
section.titre .m{font-size:1.2vw}
h2{margin:0;font-size:1.9vw;align-self:flex-start}h2 span{color:var(--accent);font-weight:400;margin-right:.6em}
img{max-width:100%%;max-height:72vh;border-radius:8px;box-shadow:0 8px 30px #000a;background:var(--panel)}
section p{margin:0;font-size:1.25vw;max-width:80vw;text-align:center;color:var(--text)}
nav{position:fixed;bottom:2vh;left:0;right:0;display:flex;gap:10px;justify-content:center;align-items:center}
nav button{background:var(--panel);color:var(--text);border:1px solid #333;border-radius:6px;padding:6px 14px;font-size:15px;cursor:pointer}
#barre{position:fixed;top:0;left:0;height:3px;background:var(--accent);transition:width .3s}
@media (max-width:700px){h2{font-size:18px}section p{font-size:14px}section.titre h1{font-size:28px}section.titre p{font-size:16px}}
</style></head><body><div id="barre"></div>%(diapos)s
<nav><button id="prec" aria-label="précédente">◀</button><span id="num"></span><button id="suiv" aria-label="suivante">▶</button>
<button id="auto">▶ lecture</button><button id="plein">⛶</button></nav>
<script>
const S=[...document.querySelectorAll("section")];let i=0,t=null;
function va(n){i=Math.max(0,Math.min(S.length-1,n));S.forEach((s,k)=>s.classList.toggle("on",k===i));
document.getElementById("num").textContent=(i+1)+" / "+S.length;document.getElementById("barre").style.width=(100*(i+1)/S.length)+"%%";}
document.getElementById("prec").onclick=()=>va(i-1);document.getElementById("suiv").onclick=()=>va(i+1);
document.getElementById("auto").onclick=(e)=>{if(t){clearInterval(t);t=null;e.target.textContent="▶ lecture";}else{t=setInterval(()=>va(i+1<S.length?i+1:0),6000);e.target.textContent="⏸ pause";}};
document.getElementById("plein").onclick=()=>document.fullscreenElement?document.exitFullscreen():document.documentElement.requestFullscreen();
document.addEventListener("keydown",(e)=>{if(["ArrowRight","PageDown"," "].includes(e.key))va(i+1);if(["ArrowLeft","PageUp"].includes(e.key))va(i-1);if(e.key==="Home")va(0);if(e.key==="End")va(S.length-1);});
let x0=null;document.addEventListener("touchstart",(e)=>{x0=e.touches[0].clientX});document.addEventListener("touchend",(e)=>{if(x0===null)return;const d=e.changedTouches[0].clientX-x0;if(Math.abs(d)>50)va(i+(d<0?1:-1));x0=null;});
va(0);
</script></body></html>""" % {"titre": H.escape(m["titre"]), "diapos": "\n".join(diapos)}
    chemin = os.path.join(dossier, "diaporama.html")
    with open(chemin, "w", encoding="utf-8") as fh:
        fh.write(page)
    return chemin


def presentation(dossier, m):
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.util import Emu, Inches, Pt
    from PIL import Image

    FOND, TEXTE, DISCRET, ACCENT = RGBColor(0x14, 0x17, 0x1C), RGBColor(0xE8, 0xEA, 0xED), RGBColor(0x9A, 0xA3, 0xAD), RGBColor(0x4A, 0xA3, 0xDF)
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    vide = prs.slide_layouts[6]

    def fond(s):
        f = s.background.fill
        f.solid()
        f.fore_color.rgb = FOND

    def texte(s, x, y, w, h, t, taille, couleur, gras=False, centre=False):
        from pptx.enum.text import PP_ALIGN
        tb = s.shapes.add_textbox(x, y, w, h)
        tf = tb.text_frame
        tf.word_wrap = True
        para = tf.paragraphs[0]
        para.text = t
        para.font.size, para.font.color.rgb, para.font.bold, para.font.name = Pt(taille), couleur, gras, "Calibri"
        if centre:
            para.alignment = PP_ALIGN.CENTER
        return tb

    s = prs.slides.add_slide(vide)
    fond(s)
    texte(s, Inches(0.8), Inches(2.4), Inches(11.7), Inches(1.4), m["titre"], 40, TEXTE, True, True)
    if m.get("sous_titre"):
        texte(s, Inches(0.8), Inches(3.8), Inches(11.7), Inches(0.8), m["sous_titre"], 22, DISCRET, False, True)
    pied = " · ".join(x for x in (m.get("public"), ("livraison #%s" % m["livraison"]) if m.get("livraison") else "", m["date"]) if x)
    texte(s, Inches(0.8), Inches(5.0), Inches(11.7), Inches(0.6), pied, 16, DISCRET, False, True)

    n = len(m["etapes"])
    for i, e in enumerate(m["etapes"], 1):
        s = prs.slides.add_slide(vide)
        fond(s)
        texte(s, Inches(0.5), Inches(0.25), Inches(12.3), Inches(0.7), "%d/%d   %s" % (i, n, e["titre"]), 24, TEXTE, True)
        img = os.path.join(dossier, e["image"])
        with Image.open(img) as im:
            w, h = im.size
        zone_w, zone_h, haut = Inches(12.3), Inches(5.3), Inches(1.05)
        k = min(zone_w / w, zone_h / h)
        pw, ph = int(w * k), int(h * k)
        s.shapes.add_picture(img, Emu(int((prs.slide_width - pw) / 2)), Emu(int(haut)), Emu(pw), Emu(ph))
        if e.get("legende"):
            texte(s, Inches(0.5), Emu(int(haut) + ph + Inches(0.1)), Inches(12.3), Inches(0.9), e["legende"], 15, TEXTE, False, True)
        s.notes_slide.notes_text_frame.text = e.get("legende") or e["titre"]
    chemin = os.path.join(dossier, "%s.pptx" % m["id"])
    prs.save(chemin)
    return chemin


def construire(dossier):
    m = _manifeste(dossier)
    return diaporama(dossier, m), presentation(dossier, m)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    print("\n".join(construire(sys.argv[1])))
