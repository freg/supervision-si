# -*- coding: utf-8 -*-
"""Règles NAT (livraison #587) -- validation PURE des règles que le hub
accepte de créer ou modifier : traduction d'adresse ip:port -> ip:port
(dst-nat), src-nat / masquerade, avec des valeurs strictement contrôlées
(pas d'injection dans la ligne de commande, pas de champ exotique).
Commun aux transports REST et SSH."""
import ipaddress
import re

CHAINS = ("dstnat", "srcnat")
ACTIONS = ("dst-nat", "src-nat", "masquerade", "netmap", "redirect", "accept")
PROTOCOLS = ("tcp", "udp", "icmp", "")
FIELDS = ("chain", "action", "protocol", "dst-address", "dst-port", "to-addresses", "to-ports", "src-address", "src-port",
          "in-interface", "out-interface", "in-interface-list", "out-interface-list", "comment", "disabled", "dst-address-list", "src-address-list")
IFACE_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
COMMENT_RE = re.compile(r"^[^\"\n\r;]{0,120}$")


def _ip_or_net(v):
    try:
        if "/" in v:
            ipaddress.ip_network(v, strict=False)
        elif "-" in v:
            a, b = v.split("-", 1)
            ipaddress.ip_address(a)
            ipaddress.ip_address(b)
        else:
            ipaddress.ip_address(v)
        return True
    except ValueError:
        return False


def _ports(v):
    """« 8080 », « 8000-8010 », « 80,443 » (max 8 éléments)."""
    parts = v.split(",")
    if not 1 <= len(parts) <= 8:
        return False
    for p in parts:
        m = re.match(r"^(\d{1,5})(?:-(\d{1,5}))?$", p)
        if not m:
            return False
        a, b = int(m.group(1)), int(m.group(2) or m.group(1))
        if not (1 <= a <= 65535 and a <= b <= 65535):
            return False
    return True


def validate(rule, partial=False):
    """-> (champs normalisés, erreurs). partial=True : modification (les
    champs obligatoires peuvent manquer)."""
    rule = rule or {}
    out, errors = {}, []
    for k in rule:
        if k not in FIELDS:
            errors.append("champ « %s » non géré" % k)
    def val(k):
        v = rule.get(k)
        return v.strip() if isinstance(v, str) else v
    chain, action = val("chain"), val("action")
    if not partial or chain is not None:
        if chain not in CHAINS:
            errors.append("chain : dstnat ou srcnat")
        else:
            out["chain"] = chain
    if not partial or action is not None:
        if action not in ACTIONS:
            errors.append("action : %s" % " / ".join(ACTIONS))
        else:
            out["action"] = action
    proto = val("protocol")
    if proto is not None:
        if proto not in PROTOCOLS:
            errors.append("protocol : tcp, udp ou icmp")
        elif proto:
            out["protocol"] = proto
    for k in ("dst-address", "to-addresses", "src-address"):
        v = val(k)
        if v:
            if not _ip_or_net(v):
                errors.append("%s : adresse IP, réseau ou plage attendu" % k)
            else:
                out[k] = v
    for k in ("dst-port", "to-ports", "src-port"):
        v = val(k)
        if v not in (None, ""):
            v = str(v)
            if not _ports(v):
                errors.append("%s : port, plage 8000-8010 ou liste 80,443" % k)
            else:
                out[k] = v
    for k in ("in-interface", "out-interface", "in-interface-list", "out-interface-list", "dst-address-list", "src-address-list"):
        v = val(k)
        if v:
            if not IFACE_RE.match(v):
                errors.append("%s : nom invalide" % k)
            else:
                out[k] = v
    c = val("comment")
    if c is not None:
        if not COMMENT_RE.match(str(c)):
            errors.append("comment : 120 caractères max, sans guillemet ni point-virgule")
        else:
            out["comment"] = str(c)
    d = val("disabled")
    if d is not None:
        out["disabled"] = "true" if str(d).lower() in ("true", "yes", "1") else "false"
    # cohérence : dst-nat exige une cible ; une règle dst-nat sur un port exige un protocole
    eff = dict(rule)
    eff.update(out)
    if not partial:
        if action in ("dst-nat", "src-nat", "netmap") and not out.get("to-addresses"):
            errors.append("%s : to-addresses obligatoire" % action)
        if (out.get("dst-port") or out.get("to-ports") or out.get("src-port")) and not out.get("protocol"):
            errors.append("un port exige protocol tcp ou udp")
        if action in ("dst-nat", "redirect") and chain == "srcnat":
            errors.append("dst-nat / redirect vont dans la chaîne dstnat")
        if action in ("src-nat", "masquerade") and chain == "dstnat":
            errors.append("src-nat / masquerade vont dans la chaîne srcnat")
    return out, errors


def describe(rule):
    """Résumé lisible d'une règle (REST ou SSH) : « tcp 203.0.113.5:8443 → 192.0.2.10:443 »."""
    r = rule or {}
    proto = r.get("protocol") or "*"
    src = ":".join(x for x in (r.get("dst-address") or "*", r.get("dst-port") or "") if x)
    if r.get("action") in ("dst-nat", "netmap"):
        dst = ":".join(x for x in (r.get("to-addresses") or "", r.get("to-ports") or "") if x)
        return "%s %s → %s" % (proto, src, dst)
    if r.get("action") == "redirect":
        return "%s %s → routeur:%s" % (proto, src, r.get("to-ports") or "?")
    if r.get("action") in ("src-nat", "masquerade"):
        return "%s %s sortant%s%s" % (r.get("action"), r.get("src-address") or "*", " par " + r["out-interface"] if r.get("out-interface") else "",
                                        " → " + r["to-addresses"] if r.get("to-addresses") else "")
    return "%s %s %s" % (r.get("chain") or "?", r.get("action") or "?", src)
