# -*- coding: utf-8 -*-
"""
Vérifie l'APK de test comme le ferait le téléphone :

    python outils/apk_rapide/verifier.py [APK]                      extraction seule
    python outils/apk_rapide/verifier.py [APK] --lancer --python310 CHEMIN

1) Extraction stricte de assets/private.tar, comme AssetExtract de python-for-android : un
   fichier dont le dossier n'a pas d'entrée dans l'archive fait échouer le démarrage.
2) Avec --lancer : lance le main.pyc extrait avec un Python 3.10 où pygame 2.1.0 est
   installé, en simulant les doigts (menu, hangar, décollage) et deux passages en arrière-plan.
"""
import argparse
import io
import os
import shutil
import subprocess
import sys
import tarfile
import zipfile

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.normpath(os.path.join(ICI, "..", ".."))


def extraire(apk, cible):
    tar = tarfile.open(fileobj=io.BytesIO(zipfile.ZipFile(apk).read("assets/private.tar")), mode="r:gz")
    shutil.rmtree(cible, ignore_errors=True)
    os.makedirs(cible)
    n = 0
    for e in tar:
        chemin = os.path.join(cible, e.name)
        if e.isdir():
            os.makedirs(chemin, exist_ok=True)
            continue
        if not os.path.isdir(os.path.dirname(chemin)):
            sys.exit("ÉCHEC, comme sur le téléphone : « could not open %s » (après %d fichiers)" % (e.name, n))
        open(chemin, "wb").write(tar.extractfile(e).read())
        n += 1
    print("extraction réussie : %d fichiers" % n)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("apk", nargs="?", default=os.path.join(RACINE, "bin", "agence-spatiale-2d-test.apk"))
    p.add_argument("--lancer", action="store_true")
    p.add_argument("--python310", default="python3.10")
    args = p.parse_args()
    cible = os.path.join(ICI, "cache", "extrait")
    extraire(args.apk, cible)
    if args.lancer:
        r = subprocess.run([args.python310, os.path.join(ICI, "simuler_lancement.py"), cible], timeout=900)
        sys.exit(r.returncode)


if __name__ == "__main__":
    main()
