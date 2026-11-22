# -*- coding: utf-8 -*-
"""
Vérifie un APK ou un AAB avant de l'envoyer sur Google Play.

    python outils/verifier_paquet.py bin/agencespatiale-1.6.0-arm64-v8a_armeabi-v7a-release.aab

Contrôles (code de sortie 1 si l'un d'eux bloque la publication) :
  - chaque bibliothèque native 64 bits (arm64-v8a, x86_64) a ses segments alignés sur 16 Ko :
    Google Play le refuse sinon (appareils à pages mémoire de 16 Ko, Android 15 et plus) ;
  - l'architecture arm64-v8a est présente (Google Play exige le 64 bits) ;
  - version d'Android visée (targetSdkVersion) au moins égale à CIBLE_MIN, si l'outil aapt2
    du SDK Android est trouvé (APK seulement ; pour un AAB, voir PUBLICATION.md).
"""
import glob
import os
import re
import struct
import subprocess
import sys
import zipfile

PAGE = 16384              # 16 Ko
CIBLE_MIN = 36            # Google Play, nouvelles applis, depuis le 31 août 2026
ABI_64 = ("arm64-v8a", "x86_64")


def alignement_elf(donnees):
    """Plus petit alignement des segments chargés (PT_LOAD) d'un fichier ELF, ou None."""
    if donnees[:4] != b"\x7fELF":
        return None
    fin = "<" if donnees[5] == 1 else ">"
    if donnees[4] == 2:                                    # ELF 64 bits
        phoff = struct.unpack_from(fin + "Q", donnees, 0x20)[0]
        taille, nombre = struct.unpack_from(fin + "HH", donnees, 0x36)
        champ, format_ = 0x30, "Q"
    else:                                                  # ELF 32 bits
        phoff = struct.unpack_from(fin + "I", donnees, 0x1C)[0]
        taille, nombre = struct.unpack_from(fin + "HH", donnees, 0x2A)
        champ, format_ = 0x1C, "I"
    aligns = []
    for i in range(nombre):
        debut = phoff + i * taille
        if struct.unpack_from(fin + "I", donnees, debut)[0] == 1:          # PT_LOAD
            aligns.append(struct.unpack_from(fin + format_, donnees, debut + champ)[0])
    return min(aligns) if aligns else None


def decalage_donnees(fichier, info):
    """Position des données d'un fichier non compressé dans le zip (en-tête local compris)."""
    fichier.seek(info.header_offset)
    entete = fichier.read(30)
    nom, extra = struct.unpack_from("<HH", entete, 26)
    return info.header_offset + 30 + nom + extra


def cle_version_buildtools(chemin):
    """« 36.0.0 » après « 9.0.0 » : tri numérique du dossier build-tools, pas alphabétique."""
    try:
        return tuple(int(x) for x in os.path.basename(os.path.dirname(chemin)).split("."))
    except ValueError:
        return (0,)


def trouver_aapt2():
    candidats = []
    for base in (os.environ.get("ANDROID_HOME"), os.environ.get("ANDROID_SDK_ROOT"),
                 os.path.expanduser("~/.buildozer/android/platform/android-sdk")):
        if base:
            candidats += glob.glob(os.path.join(base, "build-tools", "*", "aapt2"))
    return max(candidats, key=cle_version_buildtools) if candidats else None


def verifier(chemin):
    problemes, notes = [], []
    aab = chemin.endswith(".aab")
    with zipfile.ZipFile(chemin) as z, open(chemin, "rb") as brut:
        libs = [i for i in z.infolist() if i.filename.endswith(".so") and "/lib/" in "/" + i.filename]
        abis = sorted({i.filename.split("/")[-2] for i in libs})
        print("%s : %d bibliothèques natives, architectures : %s" % (
            os.path.basename(chemin), len(libs), ", ".join(abis) or "aucune"))
        if libs and "arm64-v8a" not in abis:
            problemes.append("pas de version arm64-v8a (64 bits obligatoire sur Google Play)")
        mal = []
        for info in libs:
            abi = info.filename.split("/")[-2]
            if not aab and info.compress_type != zipfile.ZIP_STORED:
                notes.append("%s compressée dans l'APK (Google Play attend une bibliothèque "
                             "stockée, extractNativeLibs=false)" % info.filename)
            if abi not in ABI_64:
                continue
            align = alignement_elf(z.read(info))
            if align is not None and align < PAGE:
                mal.append("%s (segments alignés sur %d octets)" % (info.filename, align))
            if not aab and info.compress_type == zipfile.ZIP_STORED and decalage_donnees(brut, info) % PAGE:
                mal.append("%s (non compressée mais mal placée dans le zip : zipalign -P 16)" % info.filename)
        if mal:
            problemes.append("%d bibliothèque(s) 64 bits non alignée(s) sur 16 Ko, par exemple :\n      %s"
                             % (len(mal), "\n      ".join(mal[:5])))
        elif libs:
            notes.append("bibliothèques 64 bits alignées sur 16 Ko")
    if not aab:
        aapt2 = trouver_aapt2()
        if aapt2:
            sortie = subprocess.run([aapt2, "dump", "badging", chemin], capture_output=True, text=True).stdout
            cible = re.search(r"targetSdkVersion:'(\d+)'", sortie)
            code = re.search(r"versionCode='(\d+)'", sortie)
            if cible:
                notes.append("vise Android API %s, versionCode %s" % (cible.group(1), code.group(1) if code else "?"))
                if int(cible.group(1)) < CIBLE_MIN:
                    problemes.append("vise l'API %s : Google Play exige au moins %d" % (cible.group(1), CIBLE_MIN))
        else:
            notes.append("aapt2 introuvable : version d'Android visée non vérifiée")
    else:
        notes.append("AAB : version visée à contrôler avec bundletool (voir PUBLICATION.md)")
    for n in notes:
        print("  ok   " + n)
    for p in problemes:
        print("  NON  " + p)
    return not problemes


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    bons = [verifier(c) for c in sys.argv[1:]]
    print("=> prêt pour Google Play" if all(bons) else "=> À CORRIGER avant Google Play")
    sys.exit(0 if all(bons) else 1)


if __name__ == "__main__":
    main()
