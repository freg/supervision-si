# -*- coding: utf-8 -*-
"""Orchestration de conteneurs sur un hôte (livraison #832) -- commande `orchestration` du central (hub supervision) et
agent hubemu du hub maison. Deux moteurs, pilotés de la même façon par les hubs :

  - k3s (Kubernetes léger) : serveur ou nœud rejoignant un serveur ; Traefik et servicelb DÉSACTIVÉS (les hubs ont
    déjà leur Traefik sur 80/443) ; charges = Deployment + Service NodePort (30000-32767) ; quotas = ResourceQuota
    par espace de noms ;
  - Nomad (HashiCorp, l'alternative simple à Kubernetes) : serveur + client sur un nœud (pilote Docker), API HTTP sur
    127.0.0.1:4646 seulement (pas d'ACL : jamais exposée ; interface web par tunnel SSH) ; charges = job « service »
    avec port dynamique ; pas de quotas (Nomad Enterprise).

Actions : installer, rejoindre, etat, deployer, echelle, supprimer, quota, desinstaller. Chaque charge porte une
étiquette si-orchestration et, si une durée de vie est donnée, son expiration : l'action etat supprime les charges
expirées (TTL) et les liste dans « expirees ». Le jeton de jonction k3s n'est jamais renvoyé (lecture manuelle sur le
serveur : /var/lib/rancher/k3s/server/node-token).
Pur et testé : valider, manifeste_k3s, job_nomad, script, lire_etat, resumer_k3s, resumer_nomad, a_expirer."""
import json
import re
import shlex
import time

MOTEURS = ("k3s", "nomad")
ACTIONS = ("installer", "rejoindre", "etat", "deployer", "echelle", "supprimer", "quota", "desinstaller")
NOMAD_API = "http://127.0.0.1:4646"
_NOM = re.compile(r"^[a-z0-9]([a-z0-9-]{0,38}[a-z0-9])?$")
_IMAGE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/:@-]{0,200}$")
_URL = re.compile(r"^https://[A-Za-z0-9.-]{1,253}(:\d{1,5})?$")
_HOTE = re.compile(r"^[A-Za-z0-9.-]{1,253}$")
_JETON = re.compile(r"^[A-Za-z0-9:._-]{16,300}$")
KUBECTL = 'K="$(command -v kubectl || echo "k3s kubectl")"; export KUBECONFIG=/etc/rancher/k3s/k3s.yaml'


def _entier(v, mini, maxi, defaut=None):
    if v in (None, ""):
        return defaut
    try:
        n = int(v)
    except (TypeError, ValueError):
        return None
    return n if mini <= n <= maxi else None


def valider(params, maintenant=None):
    """params -> (v, None) ou (None, message)."""
    p = params or {}
    action = str(p.get("action") or "")
    if action not in ACTIONS:
        return None, "action : " + ", ".join(ACTIONS)
    moteur = str(p.get("moteur") or ("tous" if action == "etat" else ""))
    if moteur not in MOTEURS and not (action == "etat" and moteur == "tous"):
        return None, "moteur : k3s ou nomad"
    v = {"action": action, "moteur": moteur}
    if action in ("installer", "etat", "desinstaller"):
        return v, None
    if action == "rejoindre":
        if moteur == "k3s":
            if not _URL.match(str(p.get("serveur") or "")):
                return None, "serveur : https://<serveur k3s>:6443"
            if not _JETON.match(str(p.get("jeton") or "")):
                return None, "jeton : contenu de /var/lib/rancher/k3s/server/node-token sur le serveur (opération manuelle)"
            v.update(serveur=p["serveur"], jeton=p["jeton"])
        else:
            if not _HOTE.match(str(p.get("serveur") or "")):
                return None, "serveur : adresse du serveur Nomad (port 4647)"
            v["serveur"] = p["serveur"]
        return v, None
    espace = str(p.get("espace") or "si")
    if not _NOM.match(espace):
        return None, "espace : minuscules, chiffres, tirets"
    v["espace"] = espace
    if action == "quota":
        if moteur == "nomad":
            return None, "quotas : Nomad Enterprise uniquement (pas dans la version libre)"
        q = {k: _entier(p.get(k), 1, m) for k, m in (("cpu", 256000), ("memoire", 1048576), ("pods", 1000))}
        if None in q.values():
            return None, "quota : cpu (millicœurs), memoire (Mio), pods -- entiers"
        v.update(q)
        return v, None
    nom = str(p.get("nom") or "")
    if not _NOM.match(nom):
        return None, "nom : minuscules, chiffres, tirets (40 max)"
    v["nom"] = nom
    if action == "supprimer":
        return v, None
    rep = _entier(p.get("repliques"), 0, 50, 1)
    if rep is None:
        return None, "répliques : 0 à 50"
    v["repliques"] = rep
    if action == "echelle":
        return v, None
    image = str(p.get("image") or "")
    if not _IMAGE.match(image):
        return None, "image : nom d'image de conteneur (ex. nginx:1.27-alpine)"
    port = _entier(p.get("port"), 1, 65535)
    cpu = _entier(p.get("cpu"), 10, 64000, 250)
    mem = _entier(p.get("memoire"), 16, 262144, 256)
    ttl = _entier(p.get("ttl_h"), 1, 24 * 90)
    if (p.get("port") not in (None, "") and port is None) or cpu is None or mem is None or (p.get("ttl_h") not in (None, "") and ttl is None):
        return None, "port 1-65535, cpu 10-64000 (millicœurs), memoire 16-262144 (Mio), ttl_h 1-2160"
    v.update(image=image, port=port, cpu=cpu, memoire=mem, expire=int((maintenant or time.time()) + ttl * 3600) if ttl else None)
    return v, None


def manifeste_k3s(v):
    """Deployment (+ Service NodePort si port) en JSON pour kubectl apply."""
    lab = {"app": v["nom"], "si-orchestration": "1"}
    ann = {"si-orchestration/expire": str(v["expire"])} if v.get("expire") else {}
    cont = {"name": v["nom"], "image": v["image"],
            "resources": {"requests": {"cpu": "%dm" % v["cpu"], "memory": "%dMi" % v["memoire"]},
                          "limits": {"cpu": "%dm" % v["cpu"], "memory": "%dMi" % v["memoire"]}}}
    if v.get("port"):
        cont["ports"] = [{"containerPort": v["port"]}]
    items = [{"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": v["espace"]}},
             {"apiVersion": "apps/v1", "kind": "Deployment", "metadata": {"name": v["nom"], "namespace": v["espace"], "labels": lab, "annotations": ann},
              "spec": {"replicas": v["repliques"], "selector": {"matchLabels": {"app": v["nom"]}},
                       "template": {"metadata": {"labels": lab}, "spec": {"containers": [cont]}}}}]
    if v.get("port"):
        items.append({"apiVersion": "v1", "kind": "Service", "metadata": {"name": v["nom"], "namespace": v["espace"], "labels": lab},
                      "spec": {"type": "NodePort", "selector": {"app": v["nom"]}, "ports": [{"port": v["port"], "targetPort": v["port"]}]}})
    return {"apiVersion": "v1", "kind": "List", "items": items}


def job_nomad(v):
    """Job « service » Nomad (API JSON) : pilote Docker, port dynamique vers le port du conteneur."""
    meta = {"si_orchestration": "1", "si_espace": v["espace"]}
    if v.get("expire"):
        meta["si_expire"] = str(v["expire"])
    tache = {"Name": v["nom"], "Driver": "docker", "Config": {"image": v["image"]},
             "Resources": {"CPU": max(100, v["cpu"]), "MemoryMB": v["memoire"]}}   # Nomad : MHz (100 minimum)
    groupe = {"Name": v["nom"], "Count": v["repliques"], "Tasks": [tache]}
    if v.get("port"):
        groupe["Networks"] = [{"DynamicPorts": [{"Label": "app", "To": v["port"]}]}]
        tache["Config"]["ports"] = ["app"]
    return {"Job": {"ID": v["nom"], "Name": v["nom"], "Type": "service", "Datacenters": ["*"], "Meta": meta, "TaskGroups": [groupe]}}


def _attendre_k3s():
    return 'for i in $(seq 1 60); do $K get nodes 2>/dev/null | grep -q " Ready" && break; sleep 2; done; $K get nodes -o wide'


def script(v):
    a, m = v["action"], v["moteur"]
    q = shlex.quote
    if a == "etat":
        out = ["echo @@K3S", "if command -v k3s >/dev/null 2>&1; then %s; $K get nodes,deployments,services -A -l si-orchestration=1 -o json 2>/dev/null | head -c 2000000 || true; "
               "$K get nodes -o json 2>/dev/null | head -c 2000000 || true; fi" % KUBECTL] if m in ("k3s", "tous") else []
        if m in ("nomad", "tous"):
            out += ["echo @@NOMAD", "if command -v nomad >/dev/null 2>&1; then curl -sf %s/v1/nodes; echo; curl -sf '%s/v1/jobs?meta=true'; echo; fi" % (NOMAD_API, NOMAD_API)]
        return "\n".join(out) + "\nexit 0"
    if m == "k3s":
        if a == "installer":
            return ('set -e; if command -v k3s >/dev/null; then echo "k3s déjà installé : $(k3s --version | head -1)"; else\n'
                    'curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="server --disable traefik --disable servicelb --write-kubeconfig-mode 600" sh -; fi\n'
                    + KUBECTL + "\n" + _attendre_k3s() + '\necho "jeton de jonction (à lire sur place, jamais envoyé) : /var/lib/rancher/k3s/server/node-token"')
        if a == "rejoindre":
            return ('set -e; if command -v k3s >/dev/null; then echo "ERREUR k3s déjà installé sur ce nœud" >&2; exit 1; fi\n'
                    'curl -sfL https://get.k3s.io | K3S_URL=%s K3S_TOKEN=%s INSTALL_K3S_EXEC="agent" sh -\nsleep 5; systemctl is-active k3s-agent'
                    % (q(v["serveur"]), q(v["jeton"])))
        if a == "desinstaller":
            return '[ -x /usr/local/bin/k3s-uninstall.sh ] && /usr/local/bin/k3s-uninstall.sh || { [ -x /usr/local/bin/k3s-agent-uninstall.sh ] && /usr/local/bin/k3s-agent-uninstall.sh; } || echo "k3s absent"'
        pre = "set -e; " + KUBECTL + "\n"
        if a == "deployer":
            return pre + "printf '%%s' %s | $K apply -f -\n$K -n %s get deploy,svc -l app=%s -o wide" % (q(json.dumps(manifeste_k3s(v))), q(v["espace"]), q(v["nom"]))
        if a == "echelle":
            return pre + "$K -n %s scale deployment/%s --replicas=%d" % (q(v["espace"]), q(v["nom"]), v["repliques"])
        if a == "supprimer":
            return pre + "$K -n %s delete deployment,service -l app=%s,si-orchestration=1 --ignore-not-found" % (q(v["espace"]), q(v["nom"]))
        if a == "quota":
            rq = {"apiVersion": "v1", "kind": "List", "items": [
                {"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": v["espace"]}},
                {"apiVersion": "v1", "kind": "ResourceQuota", "metadata": {"name": "si-quota", "namespace": v["espace"]},
                 "spec": {"hard": {"requests.cpu": "%dm" % v["cpu"], "limits.cpu": "%dm" % v["cpu"], "requests.memory": "%dMi" % v["memoire"],
                                   "limits.memory": "%dMi" % v["memoire"], "pods": str(v["pods"])}}}]}
            return pre + "printf '%%s' %s | $K apply -f -\n$K -n %s describe resourcequota si-quota" % (q(json.dumps(rq)), q(v["espace"]))
    if m == "nomad":
        api = NOMAD_API
        if a in ("installer", "rejoindre"):
            conf = ('data_dir  = "/opt/nomad/data"\nbind_addr = "0.0.0.0"\naddresses { http = "127.0.0.1" }\n'
                    + ('server { enabled = true\n  bootstrap_expect = 1 }\n' if a == "installer" else "")
                    + 'client { enabled = true%s }\nplugin "docker" { config { allow_privileged = false } }\nui { enabled = true }\n'
                    % ('\n  servers = ["%s:4647"]' % v["serveur"] if a == "rejoindre" else ""))
            return ('set -e; command -v docker >/dev/null || { echo "ERREUR Docker requis (pilote des tâches Nomad)" >&2; exit 1; }\n'
                    'if ! command -v nomad >/dev/null; then\n'
                    '  export DEBIAN_FRONTEND=noninteractive; apt-get update -q; apt-get install -y -q gpg curl lsb-release >/dev/null\n'
                    '  curl -fsSL https://apt.releases.hashicorp.com/gpg | gpg --dearmor --yes -o /usr/share/keyrings/hashicorp-archive-keyring.gpg\n'
                    '  echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" > /etc/apt/sources.list.d/hashicorp.list\n'
                    '  apt-get update -q; apt-get install -y -q nomad\nfi\n'
                    'mkdir -p /etc/nomad.d /opt/nomad/data\nprintf \'%%s\' %s > /etc/nomad.d/nomad.hcl\n'
                    'systemctl enable nomad >/dev/null 2>&1; systemctl restart nomad\n'
                    'for i in $(seq 1 30); do curl -sf %s/v1/agent/health >/dev/null && break; sleep 2; done\n'
                    'nomad version; curl -sf %s/v1/nodes | head -c 600; echo\n'
                    'echo "interface web : ssh -L 4646:127.0.0.1:4646 <hôte> puis http://127.0.0.1:4646"' % (q(conf), api, api))
        if a == "desinstaller":
            return 'systemctl disable --now nomad 2>/dev/null; apt-get remove -y -q nomad 2>/dev/null || true; echo "Nomad retiré (données : /opt/nomad)"'
        if a == "deployer":
            return "set -e; printf '%%s' %s | curl -sf -X POST --data-binary @- %s/v1/jobs; echo" % (q(json.dumps(job_nomad(v))), api)
        if a == "echelle":
            return "set -e; printf '%%s' %s | curl -sf -X POST --data-binary @- %s/v1/job/%s/scale; echo" % (
                q(json.dumps({"Count": v["repliques"], "Target": {"Group": v["nom"]}, "Message": "hub"})), api, v["nom"])
        if a == "supprimer":
            return "set -e; curl -sf -X DELETE '%s/v1/job/%s?purge=true'; echo" % (api, v["nom"])
    raise ValueError("action non prise en charge")


def lire_etat(stdout):
    """Sortie de l'action etat -> {k3s: {installe, noeuds, charges}, nomad: {...}}."""
    out = {}
    bloc = None
    parts = {"K3S": [], "NOMAD": []}
    for l in (stdout or "").splitlines():
        if l.strip() in ("@@K3S", "@@NOMAD"):
            bloc = l.strip()[2:]
            continue
        if bloc:
            parts[bloc].append(l)
    if "@@K3S" in (stdout or ""):
        out["k3s"] = resumer_k3s(_jsons("\n".join(parts["K3S"])))
    if "@@NOMAD" in (stdout or ""):
        docs = _jsons("\n".join(parts["NOMAD"]))
        out["nomad"] = resumer_nomad(docs[0] if docs else None, docs[1] if len(docs) > 1 else None)
    return out


def _jsons(texte):
    """Documents JSON successifs (kubectl -o json, curl) -> liste."""
    dec, i, docs = json.JSONDecoder(), 0, []
    t = texte or ""
    while i < len(t):
        while i < len(t) and t[i] in " \r\n\t":
            i += 1
        if i >= len(t):
            break
        try:
            d, j = dec.raw_decode(t, i)
        except ValueError:
            nl = t.find("\n", i)
            if nl < 0:
                break
            i = nl + 1
            continue
        docs.append(d)
        i = j
    return docs


def resumer_k3s(docs):
    if not docs:
        return {"installe": False, "noeuds": [], "charges": []}
    items = [it for d in docs if isinstance(d, dict) for it in (d.get("items") or [])]
    noeuds, deps, svcs = {}, [], {}
    for it in items:
        k, md = it.get("kind"), it.get("metadata") or {}
        if k == "Node":
            st = it.get("status") or {}
            pret = any(c.get("type") == "Ready" and c.get("status") == "True" for c in st.get("conditions") or [])
            roles = sorted(x.split("/", 1)[1] for x in (md.get("labels") or {}) if x.startswith("node-role.kubernetes.io/"))
            noeuds[md.get("name")] = {"nom": md.get("name"), "pret": pret, "roles": roles or ["agent"], "version": (st.get("nodeInfo") or {}).get("kubeletVersion"),
                                      "cpu": (st.get("capacity") or {}).get("cpu"), "memoire": (st.get("capacity") or {}).get("memory")}
        elif k == "Deployment":
            deps.append(it)
        elif k == "Service":
            svcs[(md.get("namespace"), md.get("name"))] = it
    charges = []
    for it in deps:
        md, sp, st = it.get("metadata") or {}, it.get("spec") or {}, it.get("status") or {}
        cs = (((sp.get("template") or {}).get("spec") or {}).get("containers") or [{}])
        sv = svcs.get((md.get("namespace"), md.get("name"))) or {}
        np = [p.get("nodePort") for p in ((sv.get("spec") or {}).get("ports") or []) if p.get("nodePort")]
        exp = (md.get("annotations") or {}).get("si-orchestration/expire")
        charges.append({"moteur": "k3s", "nom": md.get("name"), "espace": md.get("namespace"), "image": cs[0].get("image"),
                        "voulu": sp.get("replicas", 0), "pret": st.get("readyReplicas", 0) or 0, "acces": np[0] if np else None,
                        "expire": int(exp) if exp and exp.isdigit() else None})
    return {"installe": True, "noeuds": sorted(noeuds.values(), key=lambda n: n["nom"] or ""), "charges": sorted(charges, key=lambda c: (c["espace"] or "", c["nom"] or ""))}


def resumer_nomad(noeuds, jobs):
    if noeuds is None and jobs is None:
        return {"installe": False, "noeuds": [], "charges": []}
    ns = [{"nom": n.get("Name"), "pret": n.get("Status") == "ready", "eligible": n.get("SchedulingEligibility") == "eligible",
           "version": n.get("Version"), "roles": ["client"]} for n in (noeuds or []) if isinstance(n, dict)]
    charges = []
    for j in jobs or []:
        if not isinstance(j, dict):
            continue
        meta = j.get("Meta") or {}
        som = ((j.get("JobSummary") or {}).get("Summary") or {})
        en_cours = sum((g or {}).get("Running", 0) for g in som.values())
        exp = meta.get("si_expire")
        charges.append({"moteur": "nomad", "nom": j.get("ID"), "espace": meta.get("si_espace") or j.get("Namespace"), "statut": j.get("Status"),
                        "pret": en_cours, "voulu": None, "suivi": meta.get("si_orchestration") == "1", "acces": None,
                        "expire": int(exp) if exp and str(exp).isdigit() else None})
    return {"installe": True, "noeuds": ns, "charges": sorted(charges, key=lambda c: c["nom"] or "")}


def a_expirer(etat, maintenant):
    """Charges suivies dont la durée de vie est dépassée -> [{moteur, nom, espace}]."""
    out = []
    for m in MOTEURS:
        for c in ((etat or {}).get(m) or {}).get("charges") or []:
            if c.get("expire") and c["expire"] <= maintenant and c.get("suivi", True):
                out.append({"moteur": m, "nom": c["nom"], "espace": c.get("espace") or "si"})
    return out


def masquer(params):
    p = dict(params or {})
    if p.get("jeton"):
        p["jeton"] = "(masqué)"
    return p


def run(cmd, params, maintenant=None):
    v, err = valider(params, maintenant)
    if err:
        return {"ok": False, "error": err}
    long = v["action"] in ("installer", "rejoindre", "desinstaller")
    r = cmd(["bash", "-c", script(v)], timeout=1800 if long else 300)
    rc = getattr(r, "returncode", -1)
    out, errt = (getattr(r, "stdout", "") or ""), (getattr(r, "stderr", "") or "")[-2000:]
    if rc != 0:
        msg = next((l for l in errt.splitlines()[::-1] if l.startswith("ERREUR")), None) or errt.strip()[-400:] or "code %s" % rc
        return {"ok": False, "error": msg, "result": {"stdout": out[-4000:], "stderr": errt}}
    res = {"stdout": out[-4000:], "action": v["action"], "moteur": v["moteur"]}
    if v["action"] == "etat":
        etat = lire_etat(out)
        res.pop("stdout")
        res["etat"] = etat
        exp = []
        for x in a_expirer(etat, maintenant or time.time()):           # TTL : la charge expirée est supprimée ici
            r2 = run(cmd, {"action": "supprimer", "moteur": x["moteur"], "nom": x["nom"], "espace": x["espace"]}, maintenant)
            exp.append(dict(x, ok=r2.get("ok"), error=r2.get("error")))
        res["expirees"] = exp
    return {"ok": True, "error": None, "result": res}
