# -*- coding: utf-8 -*-
"""Sonde « emulation » (#831) : hôte d'émulation -- architecture, KVM, Docker, QEMU système, Java / SDK Android,
images Raspberry préparées, instances (registre /var/lib/si-emulation + état Docker). Lecture seule.
Pur et testé : capacites, instances."""
import glob
import json
import os
import platform
import shutil
import subprocess
import sys

RACINE = "/var/lib/si-emulation"
SDK = "/opt/android-sdk"


def _run(argv, timeout=20):
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout
    except (OSError, subprocess.TimeoutExpired):
        return -1, ""


def capacites(which=shutil.which, exists=os.path.exists, run=_run):
    rc, imgs = run(["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"]) if which("docker") else (-1, "")
    systeme = sorted(glob.glob(os.path.join(SDK, "system-images", "android-*", "google_apis", "*")))
    return {"arch": platform.machine(), "kvm": exists("/dev/kvm"), "docker": bool(which("docker")),
            "qemu_arm": bool(which("qemu-system-arm")), "qemu_aarch64": bool(which("qemu-system-aarch64")), "qemu_img": bool(which("qemu-img")),
            "java": bool(which("java")), "sdk_android": exists(os.path.join(SDK, "cmdline-tools", "latest", "bin", "sdkmanager")),
            "images_android": ["%s/%s" % (p.split(os.sep)[-3], p.split(os.sep)[-1]) for p in systeme],
            "images_raspberry": sorted(l for l in (imgs or "").split() if l.startswith("rpios-lite:")),
            "boot_raspberry": sorted(os.path.basename(p) for p in glob.glob(os.path.join(RACINE, "images", "boot-*")))}


def instances(registres, docker_ps):
    """registres : [dict] (instance.json) ; docker_ps : [dict] (docker ps --format json) -> état réconcilié."""
    dk = {d.get("Names"): d for d in docker_ps}
    out = []
    for d in registres:
        d = dict(d)
        if d.get("mode") == "conteneur":
            x = dk.get(d.get("id")) or {}
            d["etat"] = "en_marche" if x.get("State") == "running" else ("arrete" if x else "absent")
            d["docker"] = x.get("Status")
        else:
            pidf = os.path.join(RACINE, "instances", d.get("id") or "", "qemu.pid" if d.get("mode") == "systeme" else "pid")
            try:
                pid = int(open(pidf).read().strip())
                os.kill(pid, 0)
                d["etat"] = "en_marche"
            except (OSError, ValueError):
                d["etat"] = "arrete" if d.get("etat") != "demarre" else "arrete"
        out.append(d)
    return sorted(out, key=lambda x: x.get("id") or "")


def collecter():
    reg = []
    for f in glob.glob(os.path.join(RACINE, "instances", "*", "instance.json")):
        try:
            reg.append(json.load(open(f)))
        except (OSError, ValueError):
            continue
    ps = []
    if shutil.which("docker"):
        _rc, out = _run(["docker", "ps", "-a", "--filter", "label=si-emulation=1", "--format", "{{json .}}"])
        for l in out.splitlines():
            try:
                ps.append(json.loads(l))
            except ValueError:
                pass
    cap = capacites()
    alerts = []
    if not cap["docker"]:
        alerts.append({"code": "emulation-sans-docker", "severity": "info", "message": "Docker absent : pas d'émulation Raspberry en conteneur"})
    return {"capacites": cap, "instances": instances(reg, ps), "alerts": alerts}


if __name__ == "__main__":
    print(json.dumps(collecter(), ensure_ascii=False))
