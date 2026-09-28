# CLAUDE.md — Agence Spatiale 2D

Guide pour Claude Code. À lire avant toute modification.

## Le projet

Jeu de simulation spatiale 2D façon *Space Agency* / *KSP*, en Python + pygame, pour PC et
Android. Environ 9 000 lignes, tout en français. Objectif : **publication sur Google Play**
(marche à suivre : `PUBLICATION.md`). Le fonctionnement du jeu est décrit dans `README.md`.

## Façon de travailler (préférences d'Arthur)

- Réponds en **français**, en tutoyant, de façon concise.
- Code **simple, commenté, réutilisable**. Noms de modules, fonctions, variables et
  commentaires **en français**, comme l'existant.
- Après chaque modification : `python tests/tout.py --rapide` pendant le travail, puis
  `python tests/tout.py` (complet, environ 3 min) avant de conclure. Tout doit passer.
- Chaque bug corrigé s'accompagne d'un test qui l'aurait attrapé.
- Mets à jour `README.md`, et ce fichier si l'architecture ou les commandes changent.
- Jamais de clé de signature (`*.jks`) ni de mot de passe dans le dépôt.
- Ne casse pas les sauvegardes existantes (`jeu/sauvegarde.py`) : un nouveau champ se lit
  avec une valeur par défaut (`d.get("champ", défaut)`).
- Pour « voir » l'écran : capture sans fenêtre (`SDL_VIDEODRIVER=dummy`, puis
  `pygame.image.save`), comme dans `tests/captures.py` ou `outils/generer_visuels_store.py`.

## Commandes

| Quoi | Commande |
|---|---|
| Installer (PC) | `pip install -r requirements.txt` |
| Jouer au clavier et à la souris | `python main.py` |
| Interface du téléphone, à la souris | `python main.py --tactile` |
| … au format d'un téléphone 20:9 | `AGENCE_ECRAN=2400x1080 python main.py --tactile` |
| Tous les tests | `python tests/tout.py` (`--rapide` : sans les plus longs) |
| Un fichier de tests | `python tests/test_boosters.py` (ou `python tests/tout.py boost`) |
| APK de test et AAB signé | GitHub Actions : workflow `Android` (voir « Construction Android ») |
| APK de test en local (Linux/WSL2) | `buildozer android debug` → `bin/*.apk` |
| AAB signé en local | `buildozer android release` (variables `P4A_RELEASE_*`, voir PUBLICATION.md) |
| Vérifier un paquet pour Google Play | `python outils/verifier_paquet.py bin/*.aab` |
| Nouvelle version | `python outils/nouvelle_version.py 1.6.1` |
| Visuels de la fiche Play Store | `python outils/generer_visuels_store.py` |
| APK de test rapide, sans SDK | `python outils/apk_rapide/construire.py` (voir son LISEZMOI.md) |

## Architecture

```
main.py                 boucle principale, écrans, sauvegarde auto, écran d'erreur (erreur.txt)
jeu/version.py          LA version (__version__, VERSION_CODE), lue par buildozer.spec et le menu
jeu/constantes.py       réglages : tolérances, accélérations du temps, couleurs...
jeu/orbite.py           mécanique képlérienne 2D (autonome)
jeu/corps.py            planètes et lunes            jeu/pieces.py   pièces et modèles de fusées
jeu/vaisseau.py         pile de pièces, boosters, étages, Δv, ports, sections de réservoirs
jeu/trajectoire.py      prédiction (tronçons, sphères d'influence, rencontres)
jeu/manoeuvre.py        nœuds de manœuvre
jeu/univers.py          la simulation : physique, rails, SAS, étages, amarrage, atterrissage
jeu/pilote.py           aides au pilotage : orbite, manœuvres, transferts, retour, rendez-vous,
                        amarrage, atterrissage automatiques ; panneaux d'aide
jeu/missions.py         les 20 missions de la carrière
jeu/tutoriel.py         moteur des tutoriels ET des scénarios (bulle, étapes, crash → Réessayer)
jeu/scenarios.py        missions historiques (Spoutnik, Vostok, Apollo 11, Apollo 13)
jeu/triche.py           photos de la partie (retour 30 s), plein, mise en orbite
jeu/sons.py, musique.py sons et musique fabriqués par le code (aucun fichier audio)
jeu/reglages.py         réglages du joueur (reglages.json) : aides, son, triche, tutos faits
jeu/sauvegarde.py       sauvegarde JSON ; chemin_sauvegarde() = dossier où écrire
jeu/plateforme.py       PC ou Android (sur_android()), mode tactile, taille logique de l'écran
jeu/interface.py        texte, boutons, panneaux, formats     jeu/rendu.py   caméra et dessin
jeu/hud.py, hud_tactile.py   instruments (PC / tactile)       jeu/tactile.py  suivi des doigts
jeu/vol.py, hangar.py, menu.py   les écrans                   jeu/polices/   DejaVu + licence
tests/                  tests sans écran ; tests/tout.py les lance tous
outils/                 verifier_paquet.py, nouvelle_version.py, generer_visuels_store.py, apk_rapide/
store/                  fiche Play Store : textes FR/EN, icône, bannière, captures
docs/                   politique de confidentialité (GitHub Pages)
android/                attributs ajoutés au manifeste Android
buildozer.spec          construction Android      .github/workflows/  tests.yml, android.yml
```

## Contraintes Android (à respecter)

- Sur Android, le jeu tourne avec python-for-android : **Python 3.11** (3.10 pour l'APK
  rapide) et **pygame 2.1.x**. N'utilise rien de plus récent que Python 3.10 et pygame 2.1,
  et **aucune dépendance compilée** en plus (pas de numpy : les sons sont calculés en
  Python pur). `tests/test_attributs.py` vérifie que chaque `module.attribut` existe.
- Détecter Android : `plateforme.sur_android()`. (`plateforme.ANDROID` n'existe pas : ce
  bug a fait planter la version 1.3 dès le passage en arrière-plan.)
- N'écrire des fichiers que dans le dossier de `sauvegarde.chemin_sauvegarde()`
  (`ANDROID_PRIVATE` sur Android).
- Écran tactile : surface **logique de 540 px de haut**, largeur selon le téléphone (1200 en
  20:9, 960 en 16:9, 720 en 4:3), agrandie par SDL. Vérifie les nouveaux écrans en 20:9 et
  en 4:3 (`AGENCE_ECRAN=2400x1080` / `1440x1080`).
- Polices : toujours `interface.police()` (DejaVu embarquée), jamais la police système.
- La touche « retour » d'Android (`K_AC_BACK`) ouvre le menu pause ;
  `android/manifeste_application.xml` garde ce comportement en API 36.

## Construction Android (buildozer)

`buildozer.spec` est réglé pour Google Play : API 36, NDK r28c (bibliothèques alignées sur
16 Ko), AAB en publication, arm64-v8a + armeabi-v7a, version lue dans `jeu/version.py`,
versionCode = `android.numeric_version` (= `VERSION_CODE`, vérifié par `tests/test_version.py`).

**Important : cette construction n'a encore jamais été lancée** (elle a été préparée sans
accès au SDK Android). Première tâche : la faire passer dans GitHub Actions (workflow
`Android`), vérifier le paquet avec `outils/verifier_paquet.py`, puis l'essayer sur un vrai
téléphone. Pistes si elle échoue :

1. Lire la **fin** du journal : c'est en général une recette python-for-android qui échoue.
2. Essayer `p4a.branch = develop` dans `buildozer.spec` (la dernière version publiée de
   python-for-android peut être en retard sur le NDK r28c).
3. Recette `pygame` qui ne compile pas : chercher dans les issues de
   kivy/python-for-android ; en dernier recours, une recette locale (`p4a.local_recipes`).
4. Erreur Cython : essayer une autre version dans `requirements-build.txt`.
5. Cache abîmé : supprimer le cache dans l'onglet Actions (Caches).

Buildozer ne tourne pas sous Windows : utiliser WSL2 (Ubuntu) ou GitHub Actions.
L'**APK rapide** (`outils/apk_rapide/`) sert seulement aux tests : il réutilise le moteur
compilé d'un APK « donneur » (ancien, non aligné sur 16 Ko) et `verifier_paquet.py` le refuse.

## Tests

- `python tests/tout.py` : environ 20 fichiers, 3 minutes, sans écran ni son (SDL « dummy »).
- Les tutoriels (`test_tutoriel`) et les missions historiques (`test_scenarios`) sont
  **joués jusqu'au bout** par des joueurs scriptés : si tu touches à la physique, au SAS ou
  aux pilotes, relance-les.
- `Application(...)` relit `reglages.json` : un test qui a besoin des aides ou de la
  triche les impose **après** l'avoir créée (`reglages.AIDES = True`). `test_tactile` tape
  au hasard dans l'interface et nettoie derrière lui.

## Pièges connus (leçons apprises)

- SAS RÉTRO près du sol : se redresse vers la verticale (`univers._pro_retro_surface`),
  sinon le vaisseau tourbillonne ou se pose de travers (`test_atterrissage`).
- Sous parachute, le SAS STAB laisse la voile redresser la capsule (sinon elle se pose
  penchée et s'écrase).
- Textes des bulles : `[[avec les aides|sans les aides]]` et `{COMMANDE}` (clavier ou
  doigt), mis en forme par `tutoriel.formater`.
- Missions : suivre les **pièces de commande** (leur `proprietaire`), pas les noms des
  vaisseaux, qui changent à chaque amarrage et séparation.
- Tout nouvel état de la partie doit passer par `sauvegarde.univers_vers_dict` : sinon le
  « retour 30 s » de la triche (qui s'en sert) le perd.
- Sons : les canaux 0 à 9 sont réservés (boucles, puis musique : `sons.CANAUX_MUSIQUE`).
- APK rapide : dans `private.tar`, chaque dossier doit avoir sa propre entrée, avant ses
  fichiers (sinon l'appli se ferme au démarrage).

## À faire

- Faire passer la construction buildozer, puis tester sur un vrai téléphone (Android 16 si
  possible : touche retour, son, sauvegarde, arrière-plan).
- Écran « À propos / Licences » dans Options (LGPL de pygame, voir `LICENCES.md`).
- Tablettes : en API 36, Android ignore l'orientation imposée sur grand écran ; vérifier le
  jeu en portrait.
- Version anglaise du jeu (textes) pour la fiche Play internationale.
- Chaque année vers août : relever `android.api` (exigence Google Play) et
  `tests/test_version.py`.
