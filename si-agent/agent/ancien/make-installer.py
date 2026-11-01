#!/usr/bin/env python3
"""#867 : génère install-ancien.sh en y embarquant le relevé de la sonde `systemes` (une seule source de vérité)."""
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, "..", "plugins", "systemes"))
import systemes  # noqa: E402


def generer():
    with open(os.path.join(ICI, "install-ancien.sh.in"), encoding="utf-8") as f:
        g = f.read()
    inv = systemes.INVENTAIRE_SH.strip("\n")
    assert "SI_INVENTAIRE_FIN" not in inv and g.count("@@INVENTAIRE@@") == 1
    return g.replace("@@INVENTAIRE@@", inv)


if __name__ == "__main__":
    dest = os.path.join(ICI, "install-ancien.sh")
    with open(dest, "w", encoding="utf-8") as f:
        f.write(generer())
    os.chmod(dest, 0o755)
    print(dest)
