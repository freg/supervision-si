"""Différences visuelles entre deux captures (#727, item 116 tranche 3) -- PIL seulement, sans navigateur.

compare(ref, new, out) : part des pixels changés (au-delà d'un seuil par canal, pour ignorer l'anticrénelage), boîte
englobante des changements, image de différence (la nouvelle capture, assombrie, changements en surimpression). Tailles
différentes : comparaison sur la zone commune, signalée. Les zones vivantes (horloges, compteurs) se masquent à la
capture (sélecteurs CSS du scénario -> masque Playwright), pas ici."""
from PIL import Image, ImageChops

THRESHOLD = 24          # écart minimal par canal (0-255) compté comme changement
SIGNIFICANT = 0.005     # au-delà de 0,5 % de pixels changés : écart signalé


def compare(ref_path, new_path, out_path=None, threshold=THRESHOLD):
    a, b = Image.open(ref_path).convert("RGB"), Image.open(new_path).convert("RGB")
    size_changed = a.size != b.size
    w, h = min(a.width, b.width), min(a.height, b.height)
    a, b2 = a.crop((0, 0, w, h)), b.crop((0, 0, w, h))
    diff = ImageChops.difference(a, b2).convert("L").point(lambda v: 255 if v >= threshold else 0)
    hist = diff.histogram()
    changed = hist[255]
    total = w * h or 1
    bbox = diff.getbbox()
    if out_path:
        base = Image.blend(b2, Image.new("RGB", b2.size, (0, 0, 0)), 0.55)
        red = Image.new("RGB", b2.size, (230, 30, 30))
        Image.composite(red, base, diff).save(out_path)
    ratio = changed / total
    return {"ratio": round(ratio, 5), "changed_px": changed, "total_px": total, "bbox": list(bbox) if bbox else None,
            "size_changed": size_changed, "significant": ratio >= SIGNIFICANT or size_changed}


def pairs(ref_results, new_results):
    """Étapes comparables : même rang (hors connexion), capture des deux côtés -> [(index, action, ref_shot, new_shot)]."""
    ref = {r["index"]: r for r in ref_results or [] if not r.get("login") and r.get("shot")}
    return [(r["index"], r["action"], ref[r["index"]]["shot"], r["shot"]) for r in new_results or []
            if not r.get("login") and r.get("shot") and r["index"] in ref]
