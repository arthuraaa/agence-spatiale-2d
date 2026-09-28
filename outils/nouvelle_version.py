# -*- coding: utf-8 -*-
"""
Passe à une nouvelle version :  python outils/nouvelle_version.py 1.6.1

Met à jour, ensemble :
  - jeu/version.py      : __version__ (le nom affiché) et VERSION_CODE (+1) ;
  - buildozer.spec      : android.numeric_version (= VERSION_CODE, le « versionCode » d'Android).
Google Play refuse un envoi dont le versionCode n'est pas plus grand que le précédent.
"""
import os
import re
import sys

RACINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def lire(chemin):
    with open(os.path.join(RACINE, chemin), encoding="utf-8") as f:
        return f.read()


def ecrire(chemin, texte):
    with open(os.path.join(RACINE, chemin), "w", encoding="utf-8") as f:
        f.write(texte)


def main():
    if len(sys.argv) != 2 or not re.fullmatch(r"\d+\.\d+(\.\d+)?", sys.argv[1]):
        print(__doc__)
        sys.exit(2)
    nom = sys.argv[1]
    v = lire("jeu/version.py")
    code = int(re.search(r"VERSION_CODE = (\d+)", v).group(1)) + 1
    v = re.sub(r'__version__ = "[^"]*"', '__version__ = "%s"' % nom, v)
    v = re.sub(r"VERSION_CODE = \d+", "VERSION_CODE = %d" % code, v)
    ecrire("jeu/version.py", v)
    b = lire("buildozer.spec")
    b, n = re.subn(r"(?m)^android\.numeric_version = \d+", "android.numeric_version = %d" % code, b)
    if n != 1:
        sys.exit("android.numeric_version introuvable dans buildozer.spec")
    ecrire("buildozer.spec", b)
    print("Version %s (versionCode %d). Pense à l'étiquette Git : v%s" % (nom, code, nom))


if __name__ == "__main__":
    main()
