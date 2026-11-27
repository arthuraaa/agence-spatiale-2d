# -*- coding: utf-8 -*-
"""Version du jeu : la SEULE source. buildozer.spec la lit (version.regex) et le menu l'affiche.

Pour passer à la version suivante : python outils/nouvelle_version.py 1.6.1
(met aussi à jour VERSION_CODE et android.numeric_version dans buildozer.spec).
"""
__version__ = "1.9.7"
VERSION_CODE = 23      # entier qui doit augmenter à CHAQUE envoi sur Google Play
