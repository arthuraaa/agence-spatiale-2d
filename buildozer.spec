# Construction Android avec buildozer (python-for-android) : APK de test et AAB pour Google Play.
#
#   buildozer android debug      -> bin/*.apk  (à installer sur ton téléphone pour tester)
#   buildozer android release    -> bin/*.aab  (signé avec ta clé d'envoi : voir PUBLICATION.md)
#
# buildozer tourne sous Linux (Ubuntu) :
#     bash outils/android/construire.sh debug     (ou release)   -- voir README.md

[app]
title = Agence Spatiale 2D

# Identifiant de l'appli sur Google Play = package.domain + "." + package.name.
# IL NE POURRA PLUS JAMAIS CHANGER après le premier envoi : choisis-le avant (PUBLICATION.md).
package.name = agencespatiale
package.domain = org.agencespatiale

source.dir = .
source.include_exts = py,ttf,png,txt
source.exclude_dirs = tests, outils, store, docs, android, bin, .buildozer, .venv-android, .git, __pycache__, cache_sons, cache_musique
source.exclude_patterns = sauvegarde.json, reglages.json, erreur.txt, presplash.png

# La version (le nom affiché) est lue dans jeu/version.py, la seule source.
version.regex = __version__ = ['"](.*)['"]
version.filename = %(source.dir)s/jeu/version.py

requirements = python3,pygame
icon.filename = %(source.dir)s/icone.png
presplash.filename = %(source.dir)s/presplash.png
android.presplash_color = #080C18
orientation = landscape, landscape-reverse
fullscreen = 1

# --- Android et Google Play ---------------------------------------------------------------
# Google Play exige de viser Android 16 (API 36) pour une nouvelle appli (depuis le 31/08/2026).
# Chaque année vers août, Google relève ce minimum : il faudra passer à l'API suivante.
android.api = 36
android.minapi = 24
android.ndk_api = 24
# NDK r28 : les bibliothèques natives sont alignées sur 16 Ko (exigé par Google Play).
android.ndk = 28c
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
# versionCode : doit augmenter à chaque envoi. Géré avec jeu/version.py par outils/nouvelle_version.py
android.numeric_version = 15
android.release_artifact = aab
android.debug_artifact = apk
# L'écran ne s'éteint pas pendant qu'on joue (les longues accélérations du temps).
android.wakelock = True
android.allow_backup = True
# Attributs ajoutés à <application> : garder la touche « retour » d'Android (voir le fichier).
android.extra_manifest_application_arguments = ./android/manifeste_application.xml
android.logcat_filters = *:S python:D SDL:D
p4a.bootstrap = sdl2
# Recettes locales : épingle Python 3.11 (la recette pygame de p4a, figée sur 2.1.0,
# ne compile pas contre le Python 3.14 des recettes officielles) — voir
# outils/android/recettes_locales/LISEZMOI.md ; la recette pygame locale (2.1.3)
# ajoute simd_blitters_sse2.c au Setup Android (sinon crash au démarrage sur ARM64)
p4a.local_recipes = outils/android/recettes_locales
# Si une recette refuse de compiler avec le NDK r28c, essayer la branche de développement :
# p4a.branch = develop

[buildozer]
log_level = 2
warn_on_root = 1
