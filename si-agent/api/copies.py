# -*- coding: utf-8 -*-
"""#856 : Migration › « Copies et sauvegardes » -- état permanent et complet de TOUTES les copies des CT / VM et de
leur DISTANCE à la source. Assemblage PUR des relevés de la sonde copies-inventory (testé dans test_z_copies.py).

Copies reconnues, où qu'elles soient (nœuds Proxmox, serveurs du LAN, PBS, disque USB) : réplique pvesr, copie ZFS
(reçue ou clonée), instantané local (ne survit pas à la perte du nœud), archive vzdump, sauvegarde PBS, flux « zfs
send » en fichier, copie rsync (répertoire subvol-/vm-…-disk-…), CT restauré sous un autre numéro (9xxx, même nom).

Rattachement d'une copie à sa source, dans l'ordre : réplique (instantanés __replicate_ et cluster de l'hôte),
règles d'origine (préfixe de chemin -> nœud), nom du nœud écrit dans le chemin (ovh/pve2, data/ovh/pve3,
vzdump-lxc-101-pve3-…), invité du même numéro dans le cluster de l'hôte, numéro unique dans tout le parc.

DISTANCE à la source :
  - instantané commun (même nom côté source et côté copie) : octets écrits depuis = somme des « written » des
    instantanés postérieurs + « written » du jeu de données -> EXACT ;
  - sinon : majorant par les instantanés de la source postérieurs à la date de la copie (0 = rien n'a changé) ;
  - source arrêtée et rien écrit depuis son dernier instantané : figée depuis -> toute copie postérieure est à 0.
VOLUME : la copie correspond-elle en taille ? (ZFS ±3 % en logique, rsync ±15 %, archive compressée plausible).
Verdict par invité : ok (copie hors du nœud à distance 0, ou de moins de 26 h si l'invité tourne, volume cohérent),
attention, critique (aucune copie qui survive à la perte du nœud)."""
import re
import time

VMID = re.compile(r"(?:^|[/_.@-])(subvol|vm|basevol|base)-(\d+)-disk-(\d+)")
TOL = {"zfs": 0.03, "rsync": 0.15, "restaure": 0.05, "flux": 0.2, "pbs": 0.35}
JOUR = 26 * 3600
GO = 1024 ** 3


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def _noeud_regex(n):
    """« pve-2 » -> motif qui reconnaît pve2 / pve-2 / pve_2 comme MOT dans un chemin (pas pve20, pas pve-21)."""
    core = re.sub(r"[^a-z0-9]", "", n.lower())
    m = re.match(r"^([a-z]+)(\d+)$", core)
    pat = (re.escape(m.group(1)) + r"[-_]?" + m.group(2)) if m else re.escape(core)
    return re.compile(r"(?<![a-z0-9])" + pat + r"(?![0-9])")


def disk_tag(name):
    m = VMID.search("/" + (name or ""))
    return ("%s-%s-disk-%s" % m.groups(), int(m.group(2))) if m else (None, None)


def hotes(reports):
    """[(agent, hôte, at, data)] -> {nom: relevé le plus frais}."""
    out = {}
    for _a, _h, at, d in reports or []:
        for h in (d or {}).get("hosts") or []:
            if h.get("name") and (h["name"] not in out or str(at) > str(out[h["name"]].get("_at"))):
                out[h["name"]] = dict(h, _at=at)
    return out


def _snaps(zfs, dataset):
    return sorted([z for z in zfs if z.get("dataset") == dataset and z.get("snap")], key=lambda z: z.get("creation") or 0)


def delta_depuis(src, t=None, snap=None):
    """Octets écrits sur le disque source depuis l'instantané `snap` (exact) ou depuis la date t (majorant).
    -> (octets, exact ?) ; (None, False) si on ne sait pas."""
    snaps, ds = src["snaps"], src["ds"]
    if snap:
        i = next((k for k, s in enumerate(snaps) if s["snap"] == snap), None)
        if i is not None:
            return sum(s.get("written") or 0 for s in snaps[i + 1:]) + (ds.get("written") or 0), True
    if t is None or not snaps:
        return None, False
    prec = [s for s in snaps if (s.get("creation") or 0) <= t]
    if not prec:
        return None, False
    apres = [s for s in snaps if (s.get("creation") or 0) > t]
    return sum(s.get("written") or 0 for s in apres) + (ds.get("written") or 0), False


def _volume(kind, taille, ref, compresse=False):
    if not taille or not ref:
        return "inconnu", None
    r = taille / float(ref)
    if kind in ("vzdump",):
        if compresse:
            return ("plausible" if 0.03 <= r <= 1.25 else "écart"), r
        return ("ok" if 0.7 <= r <= 1.25 else "écart"), r
    tol = TOL.get(kind, 0.1)
    return ("ok" if abs(r - 1) <= tol else "écart"), r


def assemble(reports, regles=None, maintenant=None):
    now = maintenant or time.time()
    regles = regles or {}
    H = hotes(reports)
    origines = sorted(((_norm(k), v) for k, v in (regles.get("origines") or {}).items()), key=lambda x: -len(x[0]))
    dans = dict((h, x.get("dans")) for h, x in H.items() if x.get("dans"))
    dans.update(regles.get("dans") or {})
    sites = dict((h, x.get("site")) for h, x in H.items() if x.get("site"))
    sites.update(regles.get("sites") or {})

    # -- sources : invités des nœuds Proxmox et leurs disques ZFS
    sources, par_vmid, cluster_de = {}, {}, {}
    for hn, h in H.items():
        if not h.get("ok"):
            continue
        cl = h.get("cluster")
        for g in h.get("guests") or []:
            key = "%s/%s" % (hn, g["vmid"])
            disques = {}
            for z in h.get("zfs") or []:
                if z.get("snap") or z.get("type") not in ("filesystem", "volume"):
                    continue
                tag, vm = disk_tag(z["name"].split("/")[-1])
                if vm == g["vmid"] and not any(_norm(z["name"]).startswith(o) for o, _ in origines):
                    disques[tag] = {"tag": tag, "ds": z, "snaps": _snaps(h["zfs"], z["name"]), "pool": z["name"].split("/")[0]}
            sources[key] = {"key": key, "node": hn, "vmid": g["vmid"], "type": g["type"], "name": g.get("name") or "", "status": g["status"],
                            "cluster": cl, "disques": disques, "copies": []}
            par_vmid.setdefault(g["vmid"], []).append(key)
        if cl:
            cluster_de[hn] = cl
    noeuds = {n: _noeud_regex(n) for n in H}

    def origine(hn, chemin, vmid, cluster_vms=None):
        """-> (clé source, méthode) ou (None, raison)."""
        c = _norm(chemin)
        for o, n in origines:
            if c.startswith(o) or o in c:
                k = "%s/%s" % (n, vmid)
                return (k, "règle") if k in sources else (None, "règle vers %s : invité %s absent" % (n, vmid))
        low = str(chemin or "").lower()
        for n, rx in sorted(noeuds.items(), key=lambda x: -len(x[0])):
            if n != hn and rx.search(low):
                k = "%s/%s" % (n, vmid)
                if k in sources:
                    return k, "nom du nœud dans le chemin"
        for r in cluster_vms or []:
            if r.get("vmid") == vmid and "%s/%s" % (r.get("node"), vmid) in sources:
                return "%s/%s" % (r["node"], vmid), "même cluster"
        if len(par_vmid.get(vmid) or []) == 1:
            return par_vmid[vmid][0], "numéro unique dans le parc"
        return None, "numéro %s : %d sources possibles" % (vmid, len(par_vmid.get(vmid) or []))

    def survit(src, hn):
        return hn != src["node"] and dans.get(hn) != src["node"]

    def support(h, pool=None, chemin=None):
        if pool:
            p = next((x for x in h.get("pools") or [] if x.get("name") == pool), None)
            if p:
                f = []
                if p.get("health") and p["health"] != "ONLINE":
                    f.append("pool %s %s" % (pool, p["health"]))
                if p.get("redondance") == "non":
                    f.append("pool %s sans redondance" % pool)
                return {"type": "zfs", "fragile": "; ".join(f) or None}
        if chemin:
            sup = max(((k, v) for k, v in (h.get("supports") or {}).items() if chemin.startswith(k.rstrip("/") + "/") or chemin == k),
                      key=lambda kv: len(kv[0]), default=(None, None))[1]
            if sup:
                return {"type": sup.get("fs"), "fragile": "disque simple (%s %s)" % (sup.get("fs"), sup.get("device")) if sup.get("fs") != "zfs" else None}
        return {"type": None, "fragile": None}

    orphelines, vus_pbs = [], set()

    def ajouter(key, c, hn):
        src = sources[key]
        c["hote"] = hn
        c["survit"] = survit(src, hn)
        c["site"] = sites.get(hn)
        c["age_h"] = round((now - c["at"]) / 3600.0, 1) if c.get("at") else None
        src["copies"].append(c)

    for hn, h in H.items():
        if not h.get("ok"):
            continue
        zfs = h.get("zfs") or []
        cvms = h.get("cluster_vms") or []
        # a. jeux de données ZFS qui ne sont pas les disques d'un invité de cet hôte
        locaux = {d["ds"]["name"] for s in sources.values() if s["node"] == hn for d in s["disques"].values()}
        for z in zfs:
            if z.get("snap") or z.get("type") not in ("filesystem", "volume") or z["name"] in locaux:
                continue
            tag, vm = disk_tag(z["name"].split("/")[-1])
            if tag is None:
                continue
            snaps = _snaps(zfs, z["name"])
            repl = any(s["snap"].startswith("__replicate_%s-" % vm) for s in snaps)
            if repl:
                key, meth = origine(hn, "", vm, cvms)
                kind = "réplique"
            else:
                key, meth = origine(hn, z["name"], vm, cvms)
                kind = "zfs"
            if not key:
                orphelines.append({"hote": hn, "emplacement": z["name"], "type": kind, "vmid": vm, "raison": meth, "taille": z.get("lref")})
                continue
            d = sources[key]["disques"].get(tag)
            last = snaps[-1] if snaps else None
            at = (last or z).get("creation")
            communs = [s["snap"] for s in snaps if d and any(x["snap"] == s["snap"] for x in d["snaps"])]
            if d and communs:
                delta, exact = delta_depuis(d, snap=communs[-1])
                ref = next(x for x in d["snaps"] if x["snap"] == communs[-1]).get("lref")
                ref_copie = next(s for s in snaps if s["snap"] == communs[-1]).get("lref")
            else:
                delta, exact = delta_depuis(d, t=at) if d else (None, False)
                ref, ref_copie = (d["ds"].get("lref") if d else None), z.get("lref")
            vol, ratio = _volume("zfs", ref_copie, ref)
            ajouter(key, {"type": kind, "emplacement": z["name"], "disque": tag, "at": at, "taille": z.get("lref"), "volume": vol, "ratio": ratio,
                          "delta": delta, "exact": exact, "commun": communs[-1] if communs else None, "rattachement": meth,
                          "support": support(h, pool=z["name"].split("/")[0])}, hn)
        # b. instantanés locaux des disques des invités de cet hôte
        for s in sources.values():
            if s["node"] != hn:
                continue
            for d in s["disques"].values():
                autres = [x for x in d["snaps"] if not x["snap"].startswith("__replicate_")]
                if autres:
                    last = autres[-1]
                    delta, exact = delta_depuis(d, snap=last["snap"])
                    ajouter(s["key"], {"type": "instantané", "emplacement": "%s@%s" % (d["ds"]["name"], last["snap"]), "disque": d["tag"], "at": last.get("creation"),
                                       "taille": last.get("lref"), "volume": "ok", "ratio": 1.0, "delta": delta, "exact": exact, "nombre": len(autres),
                                       "rattachement": "disque de l'invité", "support": support(h, pool=d["pool"])}, hn)
        # c. archives vzdump
        for a in h.get("archives") or []:
            key, meth = origine(hn, a["path"], a["vmid"], cvms)
            if key and hn == sources[key]["node"] and meth == "numéro unique dans le parc":
                meth = "archive sur le nœud de l'invité"
            if not key:
                orphelines.append({"hote": hn, "emplacement": a["path"], "type": "vzdump", "vmid": a["vmid"], "raison": meth, "taille": a.get("size"), "at": a.get("at")})
                continue
            src = sources[key]
            tot = sum((d["ds"].get("lref") or 0) for d in src["disques"].values()) or None
            ds = [delta_depuis(d, t=a["at"]) for d in src["disques"].values()]
            delta = sum(x[0] for x in ds) if ds and all(x[0] is not None for x in ds) else None
            vol, ratio = _volume("vzdump", a.get("size"), tot, a.get("compresse"))
            ajouter(key, {"type": "vzdump", "emplacement": a["path"], "disque": "*", "at": a["at"], "taille": a.get("size"), "volume": vol, "ratio": ratio,
                          "delta": delta, "exact": False, "rattachement": meth, "support": support(h, chemin=a["path"])}, hn)
        # d. flux zfs send en fichiers
        for f in h.get("flux") or []:
            if f.get("vmid") is None:
                continue
            key, meth = origine(hn, f["path"], f["vmid"], cvms)
            if not key:
                orphelines.append({"hote": hn, "emplacement": f["path"], "type": "flux", "vmid": f["vmid"], "raison": meth, "taille": f.get("size"), "at": f.get("at")})
                continue
            d = sources[key]["disques"].get(f.get("disk"))
            delta, exact = delta_depuis(d, snap=f.get("snap"), t=f["at"]) if d else (None, False)
            ref = next((x.get("lref") for x in (d or {}).get("snaps", []) if x["snap"] == f.get("snap")), (d or {}).get("ds", {}).get("lref"))
            vol, ratio = _volume("flux", f.get("size"), ref)
            ajouter(key, {"type": "flux", "emplacement": f["path"], "disque": f.get("disk"), "at": f["at"], "taille": f.get("size"), "volume": vol, "ratio": ratio,
                          "delta": delta, "exact": exact, "commun": f.get("snap") if exact else None, "rattachement": meth, "support": support(h, chemin=f["path"])}, hn)
        # e. copies rsync
        for r in h.get("dirs") or []:
            key, meth = origine(hn, r["path"], r["vmid"], cvms)
            if not key:
                orphelines.append({"hote": hn, "emplacement": r["path"], "type": "rsync", "vmid": r["vmid"], "raison": meth, "taille": r.get("size"), "at": r.get("at")})
                continue
            d = sources[key]["disques"].get(r["disk"])
            delta, exact = delta_depuis(d, t=r["at"]) if d else (None, False)
            vol, ratio = _volume("rsync", r.get("size"), (d or {}).get("ds", {}).get("lref"))
            ajouter(key, {"type": "rsync", "emplacement": r["path"], "disque": r["disk"], "at": r["at"], "taille": r.get("size"), "volume": vol, "ratio": ratio,
                          "delta": delta, "exact": False, "rattachement": meth, "support": support(h, chemin=r["path"])}, hn)
        # f. sauvegardes PBS vues d'un nœud (pvesm list) ; une même sauvegarde vue de deux nœuds n'est comptée qu'une fois
        for b in h.get("pbs") or []:
            if b["volid"] in vus_pbs:
                continue
            vus_pbs.add(b["volid"])
            key, meth = origine(hn, "", b["vmid"], cvms)
            pbs_hote = b.get("storage")
            if not key:
                orphelines.append({"hote": pbs_hote or hn, "emplacement": b["volid"], "type": "pbs", "vmid": b["vmid"], "raison": meth, "taille": b.get("size"), "at": b.get("at")})
                continue
            src = sources[key]
            tot = sum((d["ds"].get("lref") or 0) for d in src["disques"].values()) or None
            ds = [delta_depuis(d, t=b["at"]) for d in src["disques"].values()]
            delta = sum(x[0] for x in ds) if ds and all(x[0] is not None for x in ds) else None
            vol, ratio = _volume("pbs", b.get("size"), tot)
            hp = pbs_hote if pbs_hote in H else hn
            ajouter(key, {"type": "pbs", "emplacement": b["volid"], "disque": "*", "at": b["at"], "taille": b.get("size"), "volume": vol, "ratio": ratio,
                          "delta": delta, "exact": False, "rattachement": meth, "support": support(H.get(hp, {}))}, hp)

    # g. CT / VM restaurés sous un autre numéro (9xxx, même nom)
    for key, s in list(sources.items()):
        if s["vmid"] < 9000 or not s["name"]:
            continue
        cands = [k for k, x in sources.items() if k != key and x["name"].lower() == s["name"].lower() and x["vmid"] < 9000]
        if len(cands) != 1:
            continue
        src = sources[cands[0]]
        s["copie_de"] = cands[0]
        tot = sum((d["ds"].get("lref") or 0) for d in src["disques"].values()) or None
        mine = sum((d["ds"].get("lref") or 0) for d in s["disques"].values()) or None
        at = max([x.get("creation") or 0 for d in s["disques"].values() for x in d["snaps"]] + [d["ds"].get("creation") or 0 for d in s["disques"].values()] or [0]) or None
        ds = [delta_depuis(d, t=at) for d in src["disques"].values()] if at else []
        delta = sum(x[0] for x in ds) if ds and all(x[0] is not None for x in ds) else None
        vol, ratio = _volume("restaure", mine, tot)
        hn = s["node"]
        pool = next((d["pool"] for d in s["disques"].values()), None)
        ajouter(cands[0], {"type": "restauré", "emplacement": "%s %s (%s)" % ("CT" if s["type"] == "lxc" else "VM", s["vmid"], s["name"]), "disque": "*",
                           "at": at, "taille": mine, "volume": vol, "ratio": ratio, "delta": delta, "exact": False, "rattachement": "même nom, numéro 9xxx",
                           "support": support(H[hn], pool=pool)}, hn)

    invites = []
    for key, s in sorted(sources.items(), key=lambda kv: (kv[1]["node"], kv[1]["vmid"])):
        tot = sum((d["ds"].get("lref") or 0) for d in s["disques"].values())
        fige = None
        if s["status"] != "running" and s["disques"] and all((d["ds"].get("written") or 0) == 0 and d["snaps"] for d in s["disques"].values()):
            fige = max(d["snaps"][-1].get("creation") or 0 for d in s["disques"].values())
        for c in s["copies"]:
            if fige and c.get("at") and c["at"] >= fige:
                c["delta"], c["exact"] = 0, True
            c["distance"] = _distance(c, s["status"])
        hors = [c for c in s["copies"] if c["survit"]]
        hors.sort(key=lambda c: (c["delta"] if c["delta"] is not None else 1e18, bool((c.get("support") or {}).get("fragile")),
                                 c["volume"] == "écart", -(c.get("at") or 0)))      # à distance égale : support solide, volume cohérent, plus récente
        best = hors[0] if hors else None
        raisons, verdict = [], "ok"
        if not best:
            verdict = "critique"
            raisons.append("aucune copie qui survive à la perte de %s" % s["node"])
        else:
            frais = best["delta"] == 0 or (s["status"] == "running" and best.get("age_h") is not None and best["age_h"] * 3600 <= JOUR)
            if not frais:
                verdict = "attention"
                raisons.append("meilleure copie hors du nœud : %s" % best["distance"])
            if best["volume"] == "écart":
                verdict = "attention"
                raisons.append("volume de la copie incohérent (%s)" % _pct(best.get("ratio")))
            if all((c.get("support") or {}).get("fragile") for c in hors):
                verdict = "attention" if verdict == "ok" else verdict
                raisons.append("toutes les copies hors du nœud sont sur un support fragile")
            if s["vmid"] >= 9000 and s.get("copie_de"):
                raisons.append("c'est elle-même une copie de %s" % s["copie_de"])
        if s.get("copie_de") and verdict == "critique":
            verdict, raisons = "info", ["copie restaurée de %s (pas une source)" % s["copie_de"]]
        invites.append({"key": key, "node": s["node"], "vmid": s["vmid"], "type": s["type"], "name": s["name"], "status": s["status"], "taille": tot or None,
                        "fige_depuis": fige, "disques": sorted(s["disques"]), "copies": sorted(s["copies"], key=lambda c: (not c["survit"], c["delta"] if c["delta"] is not None else 1e18)),
                        "meilleure": best, "verdict": verdict, "raisons": raisons, "copie_de": s.get("copie_de")})
    res = {"ok": 0, "attention": 0, "critique": 0, "info": 0}
    for i in invites:
        res[i["verdict"]] = res.get(i["verdict"], 0) + 1
    return {"at": now, "hotes": [{"name": n, "ok": h.get("ok"), "error": h.get("error"), "at": h.get("_at"), "site": sites.get(n), "dans": dans.get(n),
                                  "pools": h.get("pools") or [], "supports": h.get("supports") or {}} for n, h in sorted(H.items())],
            "invites": invites, "orphelines": orphelines, "resume": res}


def _pct(r):
    return "%d %%" % round(r * 100) if r is not None else "?"


def taille_lisible(o):
    if o is None:
        return "?"
    for u, f in (("To", 1024 ** 4), ("Go", GO), ("Mo", 1024 ** 2)):
        if o >= f:
            return "%.1f %s" % (o / float(f), u)
    return "%d o" % o


def _distance(c, status):
    if c.get("delta") == 0:
        return "0 (identique%s)" % ("" if c.get("exact") else ", source inchangée depuis")
    age = c.get("age_h")
    a = ("%d j" % (age // 24) if age is not None and age >= 48 else "%s h" % age) if age is not None else "date inconnue"
    if c.get("delta") is not None:
        return "%s%s modifiés · %s" % ("" if c.get("exact") else "≤ ", taille_lisible(c["delta"]), a)
    return "%s%s" % (a, " (invité en marche)" if status == "running" else "")
