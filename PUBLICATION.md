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
premier envoi. Prends quelque chose qui est à toi, par exemple `fr.TONPSEUDO.agencespatiale`
(minuscules, chiffres, points ; pas besoin de posséder le nom de domaine).

À savoir : les APK de test déjà installés sur ton téléphone utilisent
`org.agencespatiale.agencespatiale` avec une clé de test. Si tu gardes cet identifiant, il
faudra désinstaller la version de test avant d'installer celle du Play Store.

## 2. Préparer Ubuntu sous Windows (WSL2) (30 min, une seule fois)

buildozer, l'outil qui fabrique l'appli Android, ne tourne que sous Linux. Sous Windows, on
utilise WSL2 : un vrai Ubuntu dans Windows, fourni par Microsoft.

1. **Une seule fois**, installe Ubuntu dans Windows : dans PowerShell en administrateur,
   `wsl --install -d Ubuntu-24.04`, redémarre, puis crée ton utilisateur Ubuntu.
2. Dans Ubuntu, copie le projet dans ton dossier Linux (sur le disque Windows, `/mnt/c/...`,
   la construction serait des dizaines de fois plus lente) :
   `cp -r /mnt/c/Users/TOI/chemin/agence-spatiale-2d ~/ && cd ~/agence-spatiale-2d`
3. `bash outils/android/preparer.sh` : une seule fois (Java, compilateurs, buildozer).

## 3. Créer ta clé d'envoi (5 min, une seule fois)

Google signe l'appli finale avec sa propre clé (« signature d'application Play ») ; toi, tu
signes chaque envoi avec ta **clé d'envoi**. Dans Ubuntu :

```
bash outils/android/creer_cle.sh
```

keytool demande un mot de passe, puis ton nom. La clé est rangée **hors du projet**, dans
`~/.agence-spatiale/cle-envoi.jks` (alias `envoi`) : elle ne finit jamais dans une archive.

- **Sauvegarde-la tout de suite** en deux exemplaires (clé USB + gestionnaire de mots de
  passe), avec son mot de passe. `explorer.exe ~/.agence-spatiale` l'ouvre dans Windows.
- Si tu la perds, Google peut la remplacer (demande via la Play Console), mais c'est long.

## 4. Construire l'AAB signé

```
bash outils/android/construire.sh release
```

Le script lance d'abord les tests, demande le mot de passe de la clé, construit l'AAB
(30 à 60 min la première fois, puis quelques minutes), puis le contrôle avec
`outils/verifier_paquet.py` (alignement 16 Ko, 64 bits). Le fichier est dans `bin/`
(`explorer.exe bin` pour le retrouver dans Windows et l'envoyer dans la Play Console).

Contrôle facultatif de la version d'Android visée, avec bundletool (un simple fichier
`bundletool.jar` à télécharger, <https://github.com/google/bundletool/releases>) :

```
java -jar bundletool.jar dump manifest --bundle bin/*.aab --xpath /manifest/uses-sdk/@android:targetSdkVersion
```

La réponse doit être `36` (ou plus).

## 5. Mettre en ligne la politique de confidentialité (10 min)

Google demande une adresse web publique, même si le jeu ne collecte rien. Le plus simple,
gratuit et avec le même compte Google que la Play Console : **Google Sites**.

1. Complète les « À COMPLÉTER » de `docs/politique-confidentialite.md` (ton e-mail).
2. Sur <https://sites.google.com> : *Nouveau site* (vide), titre « Agence Spatiale 2D –
   Confidentialité », colle le texte, puis *Publier*. Note l'adresse (du genre
   `https://sites.google.com/view/agence-spatiale-2d`).

(`docs/index.html` est aussi une page toute prête, si tu préfères un autre hébergement.)

## 6. Compte développeur Google Play (1 à quelques jours)

<https://play.google.com/console> : 25 $ une seule fois, vérification d'identité (pièce
d'identité). Choisis un compte **personnel**.

## 7. Créer l'application dans la Play Console

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
| Politique de confidentialité | l'adresse Google Sites de l'étape 5 |
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

## 8. Tests (au moins 14 jours)

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

## 9. Production

*Production > Créer une version*, envoie l'AAB (le même, ou un nouveau), notes de version
(dans `store/fiche-fr.md`), puis *Envoyer pour examen*. L'examen prend en général quelques
jours.

## 10. Mises à jour

```
python outils/nouvelle_version.py 1.6.1     # version + versionCode (+1), partout à la fois
git commit -am "Version 1.6.1"             # l'historique, en local
bash outils/android/construire.sh release  # l'AAB signé, dans bin/
```

Envoie l'AAB dans la Play Console (Production > Créer une version). Chaque envoi doit avoir
un versionCode plus grand que le précédent.

**Chaque année vers août**, Google relève la version d'Android minimale visée : passe
`android.api` à la valeur exigée dans `buildozer.spec` (et dans `tests/test_version.py`),
reconstruis, teste, publie.

## En cas de souci

- **La construction buildozer échoue** : lis la fin du journal dans le terminal (ou demande
  à Claude Code, lancé dans Ubuntu, de relancer la construction et de corriger). Pistes
  dans `CLAUDE.md` (section « Construction Android »), par exemple essayer
  `p4a.branch = develop` dans `buildozer.spec`.
- **La Play Console refuse l'AAB** (16 Ko, version d'Android visée…) : `python
  outils/verifier_paquet.py bin/*.aab` dit ce qui cloche.
- **Tester vite une modification sur ton téléphone** sans attendre la construction :
  `outils/apk_rapide/` (APK de test seulement).
