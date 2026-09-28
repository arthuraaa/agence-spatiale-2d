# Publier Agence Spatiale 2D sur Google Play

La marche à suivre complète, dans l'ordre. Compte **au moins 3 semaines** : Google impose
14 jours de test fermé aux nouveaux comptes personnels.

Règles de Google Play (à revérifier au moment de publier, elles changent chaque année) :

- format **AAB** (Android App Bundle), pas APK ;
- viser **Android 16 (API 36)** pour une nouvelle appli (depuis le 31 août 2026) ;
- bibliothèques natives 64 bits **alignées sur 16 Ko** (NDK r28 ou plus) ;
- **politique de confidentialité** obligatoire, même sans collecte de données.

`buildozer.spec` est déjà réglé pour tout ça, et `outils/verifier_paquet.py` le contrôle.

---

## 1. Choisir l'identifiant définitif (5 min, AVANT tout envoi)

L'identifiant de l'appli (`package.domain` + `package.name` dans `buildozer.spec`,
aujourd'hui `org.agencespatiale.agencespatiale`) **ne pourra plus jamais changer** après le
premier envoi. Prends quelque chose qui est à toi, par exemple `io.github.TONPSEUDO.agencespatiale`
ou `fr.TONNOM.agencespatiale` (minuscules, chiffres, points).

À savoir : les APK de test déjà installés sur ton téléphone utilisent
`org.agencespatiale.agencespatiale` avec une clé de test. Si tu gardes cet identifiant, il
faudra désinstaller la version de test avant d'installer celle du Play Store.

## 2. Créer ta clé d'envoi (10 min, une seule fois)

Google signe l'appli finale avec sa propre clé (« signature d'application Play ») ; toi, tu
signes chaque envoi avec ta **clé d'envoi**. Il faut Java (JDK 17) pour l'outil `keytool`.

```
keytool -genkeypair -v -keystore cle-envoi-agence.jks -alias envoi -keyalg RSA -keysize 2048 -validity 10000
```

- Garde `cle-envoi-agence.jks` **hors du dépôt** (le `.gitignore` bloque les `.jks`), en
  deux exemplaires (clé USB + gestionnaire de mots de passe), avec son mot de passe.
- Si tu la perds, Google peut la remplacer (demande via la Play Console), mais c'est long.

## 3. Construire l'AAB signé

### Avec GitHub Actions (recommandé, rien à installer)

1. Mets le dossier dans un dépôt GitHub (privé ou public).
2. *Settings > Secrets and variables > Actions > New repository secret*, trois secrets :
   - `CLE_ENVOI_BASE64` : la clé encodée en base64. Sous Windows (PowerShell) :
     `[Convert]::ToBase64String([IO.File]::ReadAllBytes("cle-envoi-agence.jks")) | Set-Clipboard`
     puis colle ; sous Linux : `base64 -w0 cle-envoi-agence.jks`.
   - `CLE_ENVOI_ALIAS` : `envoi`
   - `CLE_ENVOI_MOT_DE_PASSE` : le mot de passe choisi.
3. *Actions > Android > Run workflow*, coche **publication**. (Ou pousse une étiquette :
   `git tag v1.6.0 && git push --tags`.)
4. À la fin (30 à 60 min la première fois), télécharge l'artefact **aab-google-play**.
   Le workflow a déjà passé `outils/verifier_paquet.py` dessus.

### Sur ta machine (Linux ou WSL2)

```
pip install -r requirements-build.txt
export P4A_RELEASE_KEYSTORE=~/cles/cle-envoi-agence.jks
export P4A_RELEASE_KEYSTORE_PASSWD='...'  P4A_RELEASE_KEYALIAS=envoi  P4A_RELEASE_KEYALIAS_PASSWD='...'
buildozer android release
python outils/verifier_paquet.py bin/*.aab
```

Contrôle facultatif de la version d'Android visée, avec bundletool
(<https://github.com/google/bundletool/releases>) :

```
java -jar bundletool.jar dump manifest --bundle bin/*.aab --xpath /manifest/uses-sdk/@android:targetSdkVersion
```

La réponse doit être `36` (ou plus).

## 4. Publier la politique de confidentialité (10 min)

1. Complète les « À COMPLÉTER » de `docs/politique-confidentialite.md`, puis régénère la page :
   demande à Claude Code « régénère docs/index.html depuis le Markdown », ou modifie
   `docs/index.html` à la main.
2. Dans le dépôt GitHub : *Settings > Pages*, source « Deploy from a branch », branche `main`,
   dossier `/docs`. L'adresse sera `https://TONPSEUDO.github.io/TONDEPOT/`.

## 5. Compte développeur Google Play (1 à quelques jours)

<https://play.google.com/console> : 25 $ une seule fois, vérification d'identité (pièce
d'identité). Choisis un compte **personnel**.

## 6. Créer l'application dans la Play Console

*Créer une application* : nom « Agence Spatiale 2D », langue par défaut **français**,
**Jeu**, **Gratuit**, accepte les déclarations.

### « Configurer votre application » : les réponses

| Rubrique | Réponse |
|---|---|
| Accès à l'application | Toutes les fonctionnalités sont disponibles sans restriction |
| Annonces | Non, l'appli ne contient pas d'annonces |
| Classification du contenu | Questionnaire IARC, catégorie « Jeu » : pas de violence envers des personnes (seulement des fusées qui explosent), ni sexe, ni langage grossier, ni drogue, ni jeu d'argent, ni échanges entre joueurs, ni partage de position : classement attendu PEGI 3 / Tout public |
| Public cible | **13 ans et plus** (le plus simple ; viser les enfants ajoute les exigences du programme « Familles ») |
| Sécurité des données | L'appli **ne collecte ni ne partage aucune donnée** (pas d'internet, sauvegarde locale uniquement) |
| Politique de confidentialité | l'adresse GitHub Pages de l'étape 4 |
| Appli gouvernementale, fonctionnalités financières, santé, actualités | Non / aucune |

### Fiche Play Store (tout est dans `store/`)

| Élément | Fichier |
|---|---|
| Nom, description courte, description complète | `store/fiche-fr.md` (+ traduction anglaise : `store/fiche-en.md`) |
| Icône 512 × 512 | `store/icone-512.png` |
| Image de présentation 1024 × 500 | `store/banniere-1024x500.png` |
| Captures d'écran téléphone (2 à 8) | `store/captures/*.png` (1920 × 1080) |
| Catégorie | Jeux > Simulation |
| E-mail de contact | le tien |

Pour refaire les visuels après un changement du jeu : `python outils/generer_visuels_store.py`.

## 7. Tests (au moins 14 jours)

1. **Test interne** (immédiat, jusqu'à 100 personnes) : *Tester > Tests internes*, crée une
   version, envoie l'AAB, ajoute ton adresse e-mail, installe depuis le lien. Vérifie : le
   jeu démarre, le son, la touche retour (menu pause), la sauvegarde après un redémarrage.
   Le **rapport de pré-lancement** (Tests > Rapport de pré-lancement) essaie l'appli sur de
   vrais appareils : regarde s'il signale un plantage.
2. **Test fermé** : obligatoire pour un compte personnel récent. *Tester > Tests fermés*,
   crée une liste d'au moins **12 testeurs** (adresses Gmail : famille, amis, collègues),
   envoie-leur le lien d'inscription. Il faut **12 testeurs inscrits sans interruption
   pendant 14 jours**. Demande-leur de vraiment jouer un peu, Google regarde aussi l'usage.
   Prévois-en 14 ou 15, au cas où certains se désinscrivent.
3. Après 14 jours : *Tableau de bord > Demander l'accès à la production*, réponds au
   questionnaire (comment s'est passé le test, ce que tu as corrigé).

## 8. Production

*Production > Créer une version*, envoie l'AAB (le même, ou un nouveau), notes de version
(dans `store/fiche-fr.md`), puis *Envoyer pour examen*. L'examen prend en général quelques
jours.

## 9. Mises à jour

```
python outils/nouvelle_version.py 1.6.1     # version + versionCode (+1), partout à la fois
git commit -am "Version 1.6.1" && git tag v1.6.1 && git push && git push --tags
```

GitHub Actions construit l'AAB signé ; envoie-le dans la Play Console (Production > Créer
une version). Chaque envoi doit avoir un versionCode plus grand que le précédent.

**Chaque année vers août**, Google relève la version d'Android minimale visée : passe
`android.api` à la valeur exigée dans `buildozer.spec` (et dans `tests/test_version.py`),
reconstruis, teste, publie.

## En cas de souci

- **La construction buildozer échoue** : lis la fin du journal dans GitHub Actions. Pistes
  dans `CLAUDE.md` (section « Construction Android »), par exemple essayer
  `p4a.branch = develop` dans `buildozer.spec`.
- **La Play Console refuse l'AAB** (16 Ko, version d'Android visée…) : `python
  outils/verifier_paquet.py bin/*.aab` dit ce qui cloche.
- **Tester vite une modification sur ton téléphone** sans attendre la construction :
  `outils/apk_rapide/` (APK de test seulement).
