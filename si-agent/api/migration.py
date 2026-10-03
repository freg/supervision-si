# -*- coding: utf-8 -*-
"""#658 (item 112) : migration d'un serveur / service vers la virtualisation -- générateur de plan (pur). Deux méthodes :
  image    : image brute À CHAUD du serveur (image_host : Disk2vhd sous Windows, dd | zstd sous Linux), transférée au central,
             importée dans une VM créée réseau coupé sur le nœud Proxmox choisi ;
  rebuild  : reconstruction par rôle -- conteneur (ou VM) créé depuis un modèle, rôle réinstallé (portage-kit, playbook),
             données synchronisées (datasync #652), puis bascule.
Dans les deux cas : des ÉTAPES DE TRANSITION (checkpoint = le plan s'arrête et attend « Reprendre » depuis le hub : vérifications
à la main, période d'observation) et un RETOUR EN ARRIÈRE (rollback_steps : rôle rendu au serveur d'origine, VM coupée du
réseau puis arrêtée ; le serveur physique n'est jamais détruit, la VM seulement sur demande explicite `purge_on_rollback`).
Le plan produit est un plan PRA ordinaire (kind = migration) : simulable, exécutable pas à pas, rejouable."""
import re

METHODS = ("image", "rebuild")
_AGENT = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def build(body):
    """-> (plan, erreur). plan = {name, kind, notes, steps, rollback_steps, auto_rollback}."""
    b = body or {}
    method = str(b.get("method") or "image")
    if method not in METHODS: return None, "method : image ou rebuild"
    src, pve = str(b.get("source_agent_id") or "").strip(), str(b.get("pve_agent_id") or "").strip()
    if not _AGENT.match(src): return None, "source_agent_id (agent du serveur à migrer) requis"
    if not _AGENT.match(pve): return None, "pve_agent_id (agent du nœud Proxmox cible) requis"
    try: vmid = int(b.get("vmid"))
    except (TypeError, ValueError): return None, "vmid entier requis"
    if vmid < 100: return None, "vmid ≥ 100"
    name = re.sub(r"[^A-Za-z0-9.-]", "-", str(b.get("name") or src))[:63].strip("-") or "migration"
    storage = str(b.get("storage") or "").strip()
    if not storage: return None, "storage (stockage Proxmox cible) requis"
    bridge = str(b.get("bridge") or "vmbr0"); memory = int(b.get("memory") or 4096); cores = int(b.get("cores") or 2)
    os_ = str(b.get("os") or "linux")
    if os_ not in ("linux", "windows"): return None, "os : linux ou windows"
    ostype = str(b.get("ostype") or ("win11" if os_ == "windows" else "l26"))
    role_id = b.get("role_id"); role_from, role_to = b.get("role_from"), b.get("role_to")
    if role_id not in (None, ""):
        try: role_id, role_from, role_to = int(role_id), int(role_from if role_from not in (None, "") else 0), int(role_to if role_to not in (None, "") else 1)
        except (TypeError, ValueError): return None, "role_id, role_from, role_to entiers"
    else: role_id = None
    kind = "lxc" if (method == "rebuild" and str(b.get("target_kind") or "lxc") == "lxc") else "qemu"
    steps, rb = [], []
    # --- phase 1 : préparation
    steps.append(dict(agent_id="central", action="checkpoint", label="Transition 1 -- préparer %s : prévenir, geler les écritures applicatives (services en lecture seule ou arrêtés), vérifier l'espace du stockage %s ; puis Reprendre" % (src, storage)))
    if method == "image":
        target = str(b.get("image_target") or "").strip()
        if not target: return None, "image_target (dossier / partage où le serveur écrit son image) requis pour la méthode image"
        steps.append(dict(agent_id=src, action="image_host", params=dict(target=target, transfer=True, delete_after=bool(b.get("delete_image_after", True)), name=name), label="image à chaud de %s -> %s, transférée au central" % (src, target), wait_s=0))
        create = dict(name=name, bridge=bridge, memory=memory, cores=cores, storage=storage, ostype=ostype, link_down=1)
        steps.append(dict(agent_id=pve, vmid=vmid, kind="qemu", action="create", params=create, label="VM %d « %s » créée sur %s, réseau coupé" % (vmid, name, pve)))
        steps.append(dict(agent_id=pve, vmid=vmid, kind="qemu", action="import_disk", params=dict(source="{{image}}", storage=storage, attach="sata0" if os_ == "windows" else "scsi0", boot=True, format=str(b.get("format") or "") or None), label="image importée dans la VM %d (stockage %s) et rattachée" % (vmid, storage)))
    else:
        if kind == "lxc":
            template = str(b.get("template") or "").strip()
            if not template: return None, "template (ex. local:vztmpl/debian-12-standard_12.7-1_amd64.tar.zst) requis pour un conteneur"
            create = dict(name=name, bridge=bridge, memory=memory, cores=cores, storage=storage, template=template, rootfs_gb=int(b.get("rootfs_gb") or 8), ip=str(b.get("ip") or "dhcp"), gateway=b.get("gateway"), link_down=0)
        else:
            create = dict(name=name, bridge=bridge, memory=memory, cores=cores, storage=storage, ostype=ostype, link_down=0)
        steps.append(dict(agent_id=pve, vmid=vmid, kind=kind, action="create", params=create, label="%s %d « %s » créé(e) sur %s depuis %s" % ("conteneur" if kind == "lxc" else "VM", vmid, name, pve, create.get("template") or "zéro")))
        steps.append(dict(agent_id=pve, vmid=vmid, kind=kind, action="start", params={}, label="démarrage de %d" % vmid))
        steps.append(dict(agent_id="central", action="checkpoint", label="Transition 2 -- reconstruire le rôle dans %d : installer l'application (portage-kit / playbook), poser l'agent si-agent, synchroniser les données (datasync : connecteur %s -> central -> %d), tester ; puis Reprendre" % (vmid, src, vmid)))
    # --- phase 2 : vérification hors réseau (méthode image) puis mise en réseau
    if method == "image":
        steps.append(dict(agent_id=pve, vmid=vmid, kind="qemu", action="start", params={}, label="premier démarrage de la VM %d, réseau COUPÉ" % vmid, wait_s=30))
        steps.append(dict(agent_id="central", action="checkpoint", label="Transition 2 -- console Proxmox de la VM %d : démarrage, fsck/pilotes (Windows : VirtIO puis passer le disque en scsi), IP/nom inchangés ; puis Reprendre = mise en réseau" % vmid))
        steps.append(dict(agent_id=pve, vmid=vmid, kind="qemu", action="set", params=dict(options={"net0": "virtio,bridge=%s" % bridge}), label="VM %d mise en réseau (%s)" % (vmid, bridge)))
    # --- phase 3 : bascule et observation
    if role_id is not None:
        steps.append(dict(agent_id="central", action="role_switch", role_id=role_id, to=role_to, label="bascule du rôle vers %d (candidat %d)" % (vmid, role_to)))
    else:
        steps.append(dict(agent_id="central", action="checkpoint", label="Transition 3 -- basculer le service vers %d (DNS / NAT / VIP à la main, ou déclarer un rôle #654) ; puis Reprendre" % vmid))
    steps.append(dict(agent_id="central", action="checkpoint", label="Transition 4 -- période d'observation : le service répond depuis %d ? Reprendre = finaliser (arrêt de %s) ; Abandonner = retour en arrière" % (vmid, src)))
    steps.append(dict(agent_id=src, action="host_shutdown", params={}, label="arrêt du serveur physique %s (il reste intact : retour possible en le rallumant)" % src))
    # --- retour en arrière : rôle rendu, VM coupée du réseau puis arrêtée, serveur à rallumer
    if role_id is not None: rb.append(dict(agent_id="central", action="role_switch", role_id=role_id, to=role_from, label="rôle rendu à %s (candidat %d)" % (src, role_from)))
    if method == "image" or kind == "qemu":
        rb.append(dict(agent_id=pve, vmid=vmid, kind=kind, action="set", params=dict(options={"net0": "virtio,bridge=%s,link_down=1" % bridge}), label="VM %d coupée du réseau" % vmid))
    rb.append(dict(agent_id=pve, vmid=vmid, kind=kind, action="shutdown", params={}, label="arrêt de %d" % vmid))
    rb.append(dict(agent_id="central", action="checkpoint", label="Retour -- rallumer %s si éteint (WoL / iDRAC / sur place), rétablir DNS / NAT à la main si pas de rôle ; Reprendre quand il répond" % src))
    if b.get("purge_on_rollback"): rb.append(dict(agent_id=pve, vmid=vmid, kind=kind, action="destroy", params=dict(confirm=str(vmid)), label="VM %d détruite (purge demandée)" % vmid))
    notes = "Migration %s -> %s (vmid %d, %s). Méthode : %s. Rejouable : relancer le plan reprend chaque étape ; retour en arrière = exécution du retour." % (src, pve, vmid, storage, "image brute à chaud" if method == "image" else "reconstruction par rôle")
    return dict(name=str(b.get("plan_name") or "Migration %s" % name)[:120], kind="migration", notes=notes, steps=steps, rollback_steps=rb, auto_rollback=bool(b.get("auto_rollback"))), None
