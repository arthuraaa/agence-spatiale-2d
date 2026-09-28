# -*- coding: utf-8 -*-
"""
APK de TEST rapide, sans SDK Android : greffe le jeu sur le moteur python-for-android déjà
compilé d'un APK « donneur » (Python 3.10 + pygame 2.1.0, projet libre Car-Game-pygame).

    python outils/apk_rapide/construire.py [--python310 CHEMIN_VERS_PYTHON_3.10]

Pour essayer vite sur ton téléphone. PAS pour Google Play : le moteur du donneur vise une
ancienne version d'Android et ses bibliothèques ne sont pas alignées sur 16 Ko. Le vrai
paquet se construit avec buildozer (voir README.md et PUBLICATION.md).

Il faut : Java 17 ou plus, internet (au 1er lancement, environ 80 Mo téléchargés dans
outils/apk_rapide/cache/), pygame (pour les icônes), et un Python 3.10, car le bytecode doit
correspondre au Python du donneur : option --python310, sinon « py -3.10 » (Windows) ou
« python3.10 » (Linux, macOS).

Résultat : bin/agence-spatiale-2d-test.apk, signé avec la clé de TEST cle-test.jks.
"""
import argparse
import glob
import hashlib
import io
import os
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.normpath(os.path.join(ICI, "..", ".."))
CACHE = os.path.join(ICI, "cache")
DONNEUR_URL = ("https://github.com/wishrohitv/Car-Game-pygame/releases/download/v1/"
               "cargame-0.1-arm64-v8a_armeabi-v7a-debug.apk")
APKTOOL_URL = "https://github.com/iBotPeaches/Apktool/releases/download/v2.12.1/apktool_2.12.1.jar"
SIGNEUR_URL = "https://github.com/patrickfav/uber-apk-signer/releases/download/v1.3.0/uber-apk-signer-1.3.0.jar"
PAQUET = "org.agencespatiale.agencespatiale"          # l'identifiant des APK de test précédents
CLE, ALIAS, MOT_DE_PASSE = os.path.join(ICI, "cle-test.jks"), "agence", "agence2d"   # clé de TEST
SORTIE = os.path.join(RACINE, "bin", "agence-spatiale-2d-test.apk")


def etape(texte):
    print("-> " + texte, flush=True)


def telecharger(url, nom):
    chemin = os.path.join(CACHE, nom)
    if not os.path.exists(chemin):
        etape("téléchargement de %s" % nom)
        with urllib.request.urlopen(url) as r, open(chemin + ".part", "wb") as f:
            shutil.copyfileobj(r, f)
        os.replace(chemin + ".part", chemin)
    return chemin


def trouver_python310(option):
    essais = [[option]] if option else []
    if sys.version_info[:2] == (3, 10):
        essais.append([sys.executable])
    essais += [["py", "-3.10"], ["python3.10"]]
    for commande in essais:
        try:
            r = subprocess.run(commande + ["-c", "import sys; print(sys.version_info[:2])"],
                               capture_output=True, text=True)
        except OSError:
            continue
        if r.returncode == 0 and "(3, 10)" in r.stdout:
            return commande
    sys.exit("Python 3.10 introuvable : installe-le, ou donne son chemin avec --python310")


def version():
    texte = open(os.path.join(RACINE, "jeu", "version.py"), encoding="utf-8").read()
    return (re.search(r'__version__ = "([^"]+)"', texte).group(1),
            int(re.search(r"VERSION_CODE = (\d+)", texte).group(1)))


def main():
    parser = argparse.ArgumentParser(description="APK de test rapide (pas pour Google Play)")
    parser.add_argument("--python310", help="chemin d'un Python 3.10")
    args = parser.parse_args()
    import pygame                                           # pour redimensionner l'icône
    os.makedirs(CACHE, exist_ok=True)
    py310 = trouver_python310(args.python310)
    donneur = telecharger(DONNEUR_URL, "donneur.apk")
    apktool = telecharger(APKTOOL_URL, "apktool.jar")
    signeur = telecharger(SIGNEUR_URL, "uber-apk-signer.jar")
    nom_version, code_version = version()

    etape("décompilation du donneur")
    dec = os.path.join(CACHE, "dec")
    shutil.rmtree(dec, ignore_errors=True)
    subprocess.run(["java", "-jar", apktool, "d", "-q", "-f", donneur, "-o", dec], check=True)

    etape("contenu de l'application (jeu %s, bytecode Python 3.10)" % nom_version)
    stage = os.path.join(CACHE, "stage")
    shutil.rmtree(stage, ignore_errors=True)
    os.makedirs(stage)
    shutil.copy(os.path.join(RACINE, "main.py"), stage)
    shutil.copytree(os.path.join(RACINE, "jeu"), os.path.join(stage, "jeu"),
                    ignore=shutil.ignore_patterns("__pycache__"))
    with tarfile.open(fileobj=io.BytesIO(zipfile.ZipFile(donneur).read("assets/private.tar"))) as t:
        membre = next(m for m in t.getmembers() if m.name.endswith("sitecustomize.pyc"))
        open(os.path.join(stage, "sitecustomize.pyc"), "wb").write(t.extractfile(membre).read())
    with open(os.path.join(stage, "p4a_env_vars.txt"), "w") as f:
        f.write("P4A_IS_WINDOWED=False\nKIVY_ORIENTATION=LandscapeLeft LandscapeRight\n"
                "P4A_NUMERIC_VERSION=None\nP4A_MINSDK=21\n")
    subprocess.run(py310 + ["-c", "import py_compile; py_compile.compile('main.py', cfile='main.pyc', doraise=True)"],
                   cwd=stage, check=True)
    # « unchecked-hash » : le cache sert tel quel même si l'extraction change les dates des fichiers
    subprocess.run(py310 + ["-m", "compileall", "-q", "--invalidation-mode", "unchecked-hash", "jeu"],
                   cwd=stage, check=True)
    tampon = io.BytesIO()
    with tarfile.open(fileobj=tampon, mode="w:gz", format=tarfile.USTAR_FORMAT, compresslevel=9) as tar:
        # Le lanceur Java de python-for-android ne crée PAS les dossiers parents d'un fichier :
        # chaque dossier a sa propre entrée, placée avant les fichiers qu'il contient.
        for racine, dossiers, fichiers in os.walk(stage):
            dossiers.sort()
            for nom in sorted(fichiers) + dossiers:
                chemin = os.path.join(racine, nom)
                tar.add(chemin, arcname=os.path.relpath(chemin, stage).replace(os.sep, "/"), recursive=False)
    donnees = tampon.getvalue()
    open(os.path.join(dec, "assets", "private.tar"), "wb").write(donnees)

    etape("manifeste, nom, version %s (versionCode %d), icônes" % (nom_version, code_version))
    def remplacer(chemin, *paires):
        chemin = os.path.join(dec, chemin)
        texte = open(chemin, encoding="utf-8").read()
        for motif, valeur in paires:
            texte = re.sub(motif, valeur, texte)
        open(chemin, "w", encoding="utf-8").write(texte)
    remplacer("AndroidManifest.xml", (r'package="[^"]+"', 'package="%s"' % PAQUET),
              (r'android:screenOrientation="[^"]+"', 'android:screenOrientation="sensorLandscape"'))
    remplacer(os.path.join("res", "values", "strings.xml"), (r">Car game<", ">Agence Spatiale 2D<"),
              (r">#000000<", ">#080C18<"),
              (r'(<string name="private_version">)[^<]*(<)', r"\g<1>%s\g<2>" % hashlib.sha1(donnees).hexdigest()))
    remplacer("apktool.yml", (r"versionCode: .*", "versionCode: %d" % code_version),
              (r"versionName: .*", "versionName: '%s'" % nom_version))
    icone = pygame.image.load(os.path.join(RACINE, "icone.png"))
    for chemin in glob.glob(os.path.join(dec, "res", "mipmap*", "*.png")) + \
            glob.glob(os.path.join(dec, "res", "drawable-*", "ic_launcher.png")):
        pygame.image.save(pygame.transform.smoothscale(icone, pygame.image.load(chemin).get_size()), chemin)
    presplash = os.path.join(RACINE, "presplash.png")
    if os.path.exists(presplash):
        pygame.image.save(pygame.image.load(presplash), os.path.join(dec, "res", "drawable", "presplash.jpg"))

    etape("reconstruction, alignement, signature (clé de TEST)")
    brut = os.path.join(CACHE, "brut.apk")
    subprocess.run(["java", "-jar", apktool, "b", "-q", dec, "-o", brut], check=True)
    signe = os.path.join(CACHE, "signe")
    shutil.rmtree(signe, ignore_errors=True)
    subprocess.run(["java", "-jar", signeur, "-a", brut, "-o", signe, "--ks", CLE, "--ksAlias", ALIAS,
                    "--ksPass", MOT_DE_PASSE, "--ksKeyPass", MOT_DE_PASSE], check=True,
                   stdout=subprocess.DEVNULL)
    os.makedirs(os.path.dirname(SORTIE), exist_ok=True)
    shutil.copy(glob.glob(os.path.join(signe, "*.apk"))[0], SORTIE)
    print("APK de test prêt : %s (%.1f Mo)" % (os.path.relpath(SORTIE, RACINE), os.path.getsize(SORTIE) / 1e6))


if __name__ == "__main__":
    main()
