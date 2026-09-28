# Licences

## Le jeu

Code et graphismes d'Agence Spatiale 2D : © 2026 Arthur. **À COMPLÉTER** : choisis une
licence si tu veux partager le code (par exemple MIT), sinon « tous droits réservés ».

## Composants libres embarqués dans l'application Android

| Composant | Licence | Rôle |
|---|---|---|
| Python | PSF License | langage du jeu |
| pygame | LGPL 2.1 | affichage, son, tactile (utilisé sans modification) |
| SDL2, SDL2_mixer, SDL2_ttf, SDL2_image | zlib | couche système sous pygame |
| python-for-android (via buildozer) | MIT | empaquetage Android |
| Polices DejaVu | licence libre Bitstream Vera / domaine public (`jeu/polices/LICENCE-DejaVu.txt`) | textes du jeu |

La LGPL de pygame demande d'indiquer qu'il est utilisé et où trouver son code source
(<https://github.com/pygame/pygame>). Recommandé avant publication : un petit écran
« À propos / Licences » dans le menu Options qui reprend ce tableau.

## Outil de test (hors application publiée)

`outils/apk_rapide/` réutilise l'APK de démonstration libre « Car-Game-pygame »
(<https://github.com/wishrohitv/Car-Game-pygame>) uniquement pour son moteur
python-for-android déjà compilé, afin de fabriquer des APK de **test**. Ces APK ne sont pas
destinés à Google Play.
