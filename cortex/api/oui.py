# -*- coding: utf-8 -*-
"""Table OUI réduite (livraison #463) : préfixes MAC des constructeurs
courants du parc -> (constructeur, famille). Volontairement courte et
lisible ; un préfixe inconnu ne dit rien (principe oui-vendor, limite
connue). Sources : registre IEEE public, préfixes les plus répandus."""

OUI = {
    # équipements réseau
    "00:19:cb": ("Zyxel", "equipement-reseau"), "b8:ec:a3": ("Zyxel", "equipement-reseau"), "5c:e2:8c": ("Zyxel", "equipement-reseau"),
    "fc:f5:28": ("Zyxel", "equipement-reseau"), "00:1e:a6": ("Zyxel", "equipement-reseau"),
    "00:0c:42": ("MikroTik", "equipement-reseau"), "48:8f:5a": ("MikroTik", "equipement-reseau"), "dc:2c:6e": ("MikroTik", "equipement-reseau"), "b8:69:f4": ("MikroTik", "equipement-reseau"),
    "00:1a:a1": ("Cisco", "equipement-reseau"), "00:1b:0c": ("Cisco", "equipement-reseau"), "5c:5e:ab": ("Cisco", "equipement-reseau"), "00:25:45": ("Cisco", "equipement-reseau"),
    "24:a4:3c": ("Ubiquiti", "equipement-reseau"), "78:8a:20": ("Ubiquiti", "equipement-reseau"), "f0:9f:c2": ("Ubiquiti", "equipement-reseau"), "b4:fb:e4": ("Ubiquiti", "equipement-reseau"),
    "50:c7:bf": ("TP-Link", "equipement-reseau"), "a4:2b:b0": ("TP-Link", "equipement-reseau"), "ec:08:6b": ("TP-Link", "equipement-reseau"),
    "20:e5:2a": ("Netgear", "equipement-reseau"), "9c:3d:cf": ("Netgear", "equipement-reseau"),
    "00:1c:f0": ("D-Link", "equipement-reseau"), "1c:7e:e5": ("D-Link", "equipement-reseau"),
    "00:1f:45": ("Aruba/HPE", "equipement-reseau"), "24:de:c6": ("Aruba/HPE", "equipement-reseau"),
    "00:24:d4": ("Freebox", "equipement-reseau"), "14:0c:76": ("Freebox", "equipement-reseau"), "70:fc:8f": ("Freebox", "equipement-reseau"),
    "e4:9e:12": ("Livebox (Sagemcom)", "equipement-reseau"), "44:ce:7d": ("Livebox (Sagemcom)", "equipement-reseau"),
    "00:26:5a": ("Teltonika", "equipement-reseau"), "00:1e:42": ("Teltonika", "equipement-reseau"),
    # stockage
    "00:11:32": ("Synology", "stockage-nas"), "90:09:d0": ("Synology", "stockage-nas"),
    "24:5e:be": ("QNAP", "stockage-nas"), "00:08:9b": ("QNAP", "stockage-nas"),
    # imprimantes
    "00:80:77": ("Brother", "imprimante"), "30:05:5c": ("Brother", "imprimante"), "3c:2a:f4": ("Brother", "imprimante"),
    "00:00:48": ("Epson", "imprimante"), "64:eb:8c": ("Epson", "imprimante"),
    "00:1e:8f": ("Canon", "imprimante"), "18:0c:ac": ("Canon", "imprimante"), "f4:a9:97": ("Canon", "imprimante"),
    "00:00:aa": ("Xerox", "imprimante"), "9c:93:4e": ("Xerox", "imprimante"),
    "00:17:c8": ("Kyocera", "imprimante"), "00:c0:ee": ("Kyocera", "imprimante"),
    "00:26:73": ("Ricoh", "imprimante"), "00:00:74": ("Ricoh", "imprimante"),
    # virtualisation / cartes
    "00:50:56": ("VMware", "machine-virtuelle"), "00:0c:29": ("VMware", "machine-virtuelle"), "00:05:69": ("VMware", "machine-virtuelle"),
    "52:54:00": ("QEMU/KVM", "machine-virtuelle"), "00:16:3e": ("Xen", "machine-virtuelle"), "00:15:5d": ("Hyper-V", "machine-virtuelle"),
    "02:42:ac": ("Docker", "conteneur"),
    # petits ordinateurs / IoT
    "b8:27:eb": ("Raspberry Pi", "petit-ordinateur"), "dc:a6:32": ("Raspberry Pi", "petit-ordinateur"), "e4:5f:01": ("Raspberry Pi", "petit-ordinateur"), "d8:3a:dd": ("Raspberry Pi", "petit-ordinateur"),
    "24:0a:c4": ("Espressif (ESP)", "iot"), "a4:cf:12": ("Espressif (ESP)", "iot"), "30:ae:a4": ("Espressif (ESP)", "iot"),
    "00:1e:c0": ("Microchip", "iot"),
    # postes (généralistes : constructeur seulement, pas de rôle)
    "3c:22:fb": ("Apple", None), "a4:83:e7": ("Apple", None), "f0:18:98": ("Apple", None), "bc:d0:74": ("Apple", None), "00:11:22": ("Apple", None),
    "00:1a:a0": ("Dell", None), "18:66:da": ("Dell", None), "b0:83:fe": ("Dell", None),
    "00:1b:21": ("Intel", None), "3c:97:0e": ("Intel", None), "8c:16:45": ("Lenovo", None),
    "00:26:b9": ("Dell", None), "c8:1f:66": ("Dell", None), "d4:be:d9": ("Dell", None),
    "e8:80:88": ("HP", None), "3c:d9:2b": ("HP", None), "10:e7:c6": ("HP", None),
    "00:0d:3a": ("Microsoft", None), "28:18:78": ("Microsoft", None),
}


def vendor_of(mac):
    """-> (constructeur, famille) ou (None, None)."""
    if not mac:
        return None, None
    m = mac.lower().replace("-", ":")
    if m.startswith("02:42:ac"):
        return OUI["02:42:ac"]
    return OUI.get(m[:8], (None, None))
