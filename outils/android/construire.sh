#!/usr/bin/env bash
# Construit le jeu pour Android avec buildozer (Ubuntu, ou tout Linux).
#     bash outils/android/construire.sh debug      APK de TEST            -> bin/*.apk
#     bash outils/android/construire.sh deploy     APK de test, installé et lancé sur le
#                                                  téléphone branché en USB, avec son journal
#     bash outils/android/construire.sh release    AAB SIGNÉ, Google Play -> bin/*.aab
# La première fois, buildozer télécharge le SDK et le NDK Android et compile Python et SDL :
# compter 30 à 60 minutes. Ensuite, quelques minutes.
set -euo pipefail
cd "$(dirname "$0")/../.."
MODE="${1:-debug}"
if [ ! -x .venv-android/bin/buildozer ]; then
    echo "Lance d'abord (une seule fois) : bash outils/android/preparer.sh"
    exit 1
fi
# shellcheck disable=SC1091
source .venv-android/bin/activate

case "$MODE" in
debug)
    buildozer android debug
    PAQUET="$(ls -t bin/*.apk | head -1)"
    ;;
deploy)
    if command -v adb >/dev/null && ! adb devices | grep -qw device$; then
        echo "Aucun téléphone détecté en USB. Sur le téléphone :"
        echo "  1. Paramètres > À propos > appuie 7 fois sur « Numéro de build » (options développeur) ;"
        echo "  2. Options pour les développeurs > active « Débogage USB » ;"
        echo "  3. Branche-le, et accepte « Autoriser le débogage USB » qui s'affiche."
        echo "Vérifie avec : adb devices   (le téléphone doit apparaître avec « device »)"
        exit 1
    fi
    echo "== Construction, installation et lancement (Ctrl+C pour arrêter le journal)"
    buildozer android debug deploy run logcat     # journal filtré : python et SDL (buildozer.spec)
    exit 0
    ;;
release)
    CLE="${AGENCE_CLE:-$HOME/.agence-spatiale/cle-envoi.jks}"
    if [ ! -f "$CLE" ]; then
        echo "Clé d'envoi introuvable : $CLE"
        echo "Crée-la (une seule fois) : bash outils/android/creer_cle.sh"
        exit 1
    fi
    echo "== Tests d'abord : on ne publie pas un jeu qui ne passe pas ses tests"
    python tests/tout.py --rapide
    if [ -z "${P4A_RELEASE_KEYSTORE_PASSWD:-}" ]; then
        read -r -s -p "Mot de passe de la clé d'envoi : " P4A_RELEASE_KEYSTORE_PASSWD
        echo
    fi
    # Variables lues par buildozer / python-for-android pour signer l'AAB
    export P4A_RELEASE_KEYSTORE="$CLE"
    export P4A_RELEASE_KEYSTORE_PASSWD
    export P4A_RELEASE_KEYALIAS="${AGENCE_ALIAS:-envoi}"
    export P4A_RELEASE_KEYALIAS_PASSWD="${P4A_RELEASE_KEYALIAS_PASSWD:-$P4A_RELEASE_KEYSTORE_PASSWD}"
    buildozer android release
    PAQUET="$(ls -t bin/*.aab | head -1)"
    ;;
*)
    echo "Usage : bash outils/android/construire.sh debug|deploy|release"
    exit 1
    ;;
esac

echo
echo "== Contrôle du paquet pour Google Play"
python outils/verifier_paquet.py "$PAQUET" || true
echo
echo "Fichier produit : $PAQUET"
if [ "$MODE" = "debug" ]; then
    echo "Pour l'installer sur ton téléphone branché en USB : adb install -r \"$PAQUET\""
    echo "(ou directement : bash outils/android/construire.sh deploy)"
fi
if grep -qi microsoft /proc/version 2>/dev/null; then
    echo "Pour le voir dans l'explorateur Windows : explorer.exe bin"
fi
