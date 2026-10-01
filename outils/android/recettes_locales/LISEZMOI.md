# Recettes locales python-for-android

Ces recettes remplacent celles de python-for-android (p4a) pendant la construction
(`p4a.local_recipes` dans `buildozer.spec`).

## Pourquoi ?

p4a (branches master et develop, en 2026) compile **Python 3.14.2**, mais sa recette
**pygame** est figée sur pygame **2.1.0**, qui ne compile ni contre Python 3.12 et
suivants, ni contre Python 3.11 (échec : `longintrepr.h file not found` en
compilant `src_c/_sdl2/sdl2.c`). Le jeu, lui, vise Python 3.11 + pygame 2.1.x
(voir CLAUDE.md).

## Quoi ?

- `python3/` et `hostpython3/` : copies des recettes officielles de p4a (master),
  avec la seule ligne `version = '3.11.9'` modifiée. `hostpython3` doit toujours
  avoir exactement la même version que `python3` (vérifié dans sa méthode `download`).
- `pygame/` : copie de la recette officielle avec deux différences — version
  **2.1.3** au lieu de 2.1.0 (première version dont les fichiers C pré-générés
  compilent contre Python 3.11 ; en 2.1.0, `src_c/_sdl2/sdl2.c` inclut
  `longintrepr.h`, retiré des en-têtes publics en 3.11), et archive prise sur
  **PyPI** (avec les .c pré-générés) plutôt que le dépôt GitHub (qui repart des
  .pyx et les régénère avec le vieux Cython de p4a). En plus, le gabarit
  `Setup.Android.SDL2.in` est complété : pygame 2.1.3 a introduit les blits SIMD
  (`alphablit_alpha_sse2_*`) dont `alphablit.c` dépend, mais le Setup Android
  n'ajoute pas `simd_blitters_sse2.c` au module `surface` — sans lui, l'APK se
  ferme au démarrage (« dlopen failed: cannot locate symbol
  alphablit_alpha_sse2_argb_surf_alpha » ; le fichier compile en NEON sur ARM
  grâce à `sse2neon.h`).
- Les patchs nécessaires pour 3.11 sont copiés à côté (tous testés avec
  `patch --dry-run` sur les sources CPython 3.11.9) :
  - `python3/patches/pyconfig_detection.patch`, `reproducible-buildinfo.diff`
    (appliqués toujours),
  - `python3/patches/cpython-311-ctypes-find-library.patch` (3.11 et plus),
  - `python3/patches/py3.8.1_fix_cortex_a8.patch` (si `lld` est installé),
  - `hostpython3/fix_ensurepip.patch` (appliqué toujours).

## Mise à jour

Si une version future de p4a recompile pygame contre un Python récent, on pourra
supprimer ce dossier et retirer `p4a.local_recipes` de `buildozer.spec`. Pour
changer de version de Python : modifier `version` dans les deux `__init__.py`,
garder les deux identiques, et revérifier les patchs avec `patch --dry-run`.
