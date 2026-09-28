#!/usr/bin/env bash
# Prépare Ubuntu (ou une autre distribution Linux, ou WSL2) pour construire le jeu Android.
# À lancer UNE fois :
#     bash outils/android/preparer.sh
# Installe les outils système (Java 17, compilateurs, adb pour le téléphone en USB) puis, dans
# le dossier .venv-android, buildozer et pygame (pour lancer les tests avant de construire).
set -euo pipefail
cd "$(dirname "$0")/../.."

# Sous WSL2, le projet doit être dans Ubuntu (~), pas sur le disque Windows (/mnt/c/...) :
# la construction y serait des dizaines de fois plus lente, et échoue souvent.
if grep -qi microsoft /proc/version 2>/dev/null && [[ "$PWD" == /mnt/* ]]; then
    echo "Le projet est sur le disque Windows ($PWD)."
    echo "Copie-le d'abord dans Ubuntu, puis relance ce script depuis la copie :"
    echo "    cp -r \"$PWD\" ~/ && cd ~/$(basename "$PWD") && bash outils/android/preparer.sh"
    exit 1
fi

SUDO=""
[ "$(id -u)" -ne 0 ] && SUDO="sudo"          # (déjà root : pas besoin de sudo)
echo "== Outils système (mot de passe Ubuntu demandé)"
# (si un dépôt ajouté à la main ne répond pas, on continue avec ceux d'Ubuntu)
$SUDO apt-get update || echo "Avertissement : un dépôt n'a pas répondu, on continue."
$SUDO apt-get install -y git zip unzip openjdk-17-jdk python3-venv python3-pip \
    autoconf automake libtool pkg-config zlib1g-dev libncurses-dev cmake libffi-dev libssl-dev lld \
    adb android-sdk-platform-tools-common        # adb + règles USB pour reconnaître le téléphone

echo "== buildozer et pygame dans .venv-android"
python3 -m venv .venv-android
.venv-android/bin/pip install --upgrade pip
.venv-android/bin/pip install -r requirements-build.txt -r requirements.txt

# Les règles USB d'Android donnent accès au téléphone aux membres du groupe plugdev
if ! id -nG | grep -qw plugdev; then
    $SUDO usermod -aG plugdev "$(id -un)" || true
    echo "(Tu viens d'être ajouté au groupe plugdev : déconnecte-toi puis reconnecte-toi une fois"
    echo " pour que adb voie ton téléphone.)"
fi

echo
echo "Prêt ! Ensuite :"
echo "    bash outils/android/construire.sh debug      (APK de test, 30 à 60 min la 1re fois)"
echo "    bash outils/android/construire.sh deploy     (installe et lance sur le téléphone en USB)"
