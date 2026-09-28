#!/usr/bin/env bash
# Crée TA clé d'envoi pour Google Play. UNE SEULE FOIS : garde-la toute la vie de l'appli.
#     bash outils/android/creer_cle.sh
# Elle est rangée HORS du projet (~/.agence-spatiale/cle-envoi.jks) : elle ne finit jamais
# dans une archive ni dans git. keytool demande un mot de passe et ton nom.
set -euo pipefail
DOSSIER="$HOME/.agence-spatiale"
CLE="$DOSSIER/cle-envoi.jks"
if [ -f "$CLE" ]; then
    echo "Une clé existe déjà : $CLE"
    echo "Ne la remplace surtout pas : Google n'accepte que les envois signés avec elle."
    exit 1
fi
mkdir -p "$DOSSIER"
chmod 700 "$DOSSIER"
OPTIONS=()
if [ -n "${AGENCE_MDP:-}" ]; then          # (sans questions, pour les tests automatiques)
    OPTIONS=(-storepass "$AGENCE_MDP" -keypass "$AGENCE_MDP" -dname "${AGENCE_DNAME:-CN=Agence Spatiale 2D}")
fi
keytool -genkeypair -v -keystore "$CLE" -alias envoi -keyalg RSA -keysize 2048 -validity 10000 "${OPTIONS[@]}"
chmod 600 "$CLE"
echo
echo "Clé créée : $CLE (alias : envoi)"
echo "SAUVEGARDE-LA MAINTENANT hors de ce PC, avec son mot de passe : clé USB, gestionnaire"
echo "de mots de passe... Si tu la perds, Google peut la remplacer, mais c'est long."
if grep -qi microsoft /proc/version 2>/dev/null; then
    echo "Pour la copier depuis Windows : explorer.exe \"$DOSSIER\""
fi
