"""Vectorise un plan photographié (nettoyé, redressé) en SVG par couches de couleur (potrace)."""
import cv2, numpy as np, subprocess, re, sys
src, dst = sys.argv[1], sys.argv[2]
im = cv2.imread(src); h,w = im.shape[:2]
hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV); H,S,V = cv2.split(hsv)
g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
bg = cv2.medianBlur(g, 51); norm = cv2.divide(g, bg, scale=255)   # fond de photo aplani
colored = (S>45)
layers = [
  ("black",  "#1f1f1f", 4, (norm<125) & ~colored),
  ("grey",   "#8c8c8c", 5, (norm>=125) & (norm<185) & ~colored),
  ("blue",   "#3b8ac4", 3, (H>=92)&(H<=132)&(S>38)&(V>80)),
  ("green",  "#3aa835", 4, (H>=38)&(H<=90)&(S>60)&(V>60)),
  ("yellow", "#e2c11e", 4, (H>=16)&(H<=38)&(S>70)&(V>110)&(V<208)),
  ("red",    "#d0302a", 4, (((H<=12)|(H>=170))&(S>80)&(V>60)))]
parts=[]
for name,color,t,m in layers:
    m = m.astype(np.uint8)*255
    cv2.imwrite(f'l_{name}.pbm', 255-m)
    subprocess.run(['potrace','-s','-t',str(t),'-a','1.0','-O','0.3','-o',f'l_{name}.svg',f'l_{name}.pbm'],check=True)
    svg=open(f'l_{name}.svg').read()
    gm=re.search(r'<g transform="([^"]+)"[^>]*>(.*?)</g>', svg, re.S)
    parts.append(f'<g id="{name}" transform="{gm.group(1)}" fill="{color}" stroke="none">{gm.group(2)}</g>')
svg=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}"><rect width="{w}" height="{h}" fill="#ffffff"/>'+"".join(parts)+'</svg>'
open(dst,'w').write(svg); print(dst, len(svg)//1024,'ko')
