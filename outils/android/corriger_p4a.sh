#!/usr/bin/env bash
# Contourne le bug kivy/python-for-android#2905 (toujours ouvert en 2026) :
# l'option android.extra_manifest_application_arguments du buildozer.spec est
# insérée dans le AndroidManifest.xml généré avec des guillemets échappés
# (« "android:attribut=\"valeur\" " ») et Gradle refuse ce XML.
#
# On corrige la copie de python-for-android qu'utilise buildozer
# (~/.buildozer/android/platform/python-for-android) pour décoder la valeur
# avant le rendu du manifeste. À lancer avant chaque construction ; le script
# est sans effet si la correction est déjà en place.
#
#     bash outils/android/corriger_p4a.sh
set -euo pipefail

P4A="${P4A_DIR:-$HOME/.buildozer/android/platform/python-for-android}"

# buildozer installe p4a ici ; s'il n'y est pas encore, on le clone comme lui.
if [ ! -d "$P4A" ]; then
    echo "== Clone de python-for-android dans $P4A"
    git clone --depth 1 -b master --single-branch \
        https://github.com/kivy/python-for-android.git "$P4A"
fi

FICHIER="$P4A/pythonforandroid/bootstraps/common/build/build.py"
if [ ! -f "$FICHIER" ]; then
    echo "Fichier introuvable : $FICHIER" >&2
    exit 1
fi

python3 - "$FICHIER" <<'EOF'
import sys
from pathlib import Path

fichier = Path(sys.argv[1])
texte = fichier.read_text()
if "#2905" in texte:
    print("Contournement du bug #2905 déjà en place.")
else:
    marque = "    render_args = {"
    if marque not in texte:
        sys.exit("Structure de build.py inattendue, rien corrigé : " + str(fichier))
    # La première occurrence rend le AndroidManifest.xml (la seconde rend
    # strings.xml). On insère juste avant : si la valeur arrive échappée
    # (« "attr=\"valeur\" " »), on retire les guillemets d'extrémité puis les
    # antislashs ; une valeur saine reste inchangée.
    contournement = '''    # Contournement du bug kivy/python-for-android#2905 : buildozer transmet
    # la valeur échappée ; on la décode avant le rendu du manifeste.
    _extra = args.extra_manifest_application_arguments
    if _extra.startswith('"') and _extra.endswith('"'):
        args.extra_manifest_application_arguments = _extra[1:-1].replace('\\\\\\"', '"')

'''
    fichier.write_text(texte.replace(marque, contournement + marque, 1))
    print("Contournement du bug #2905 installé :", fichier)
    # Les dists déjà générées contiennent un manifeste rendu avec l'ancien
    # gabarit : p4a ne les re-rend pas, il faut les supprimer.
    import glob
    import shutil
    for dist in glob.glob(str(fichier.parents[5] / "build-*" / "dists")):
        print("Dist obsolète supprimée :", dist)
        shutil.rmtree(dist, ignore_errors=True)
EOF

# Vérification rapide : la correction doit décoder l'exemple du bug.
python3 - <<'EOF'
_extra = '"android:attribut=\\"valeur\\" "'
if _extra.startswith('"') and _extra.endswith('"'):
    decode = _extra[1:-1].replace('\\"', '"')
assert decode == 'android:attribut="valeur" ', decode
print("Auto-test du décodage : OK")
EOF
