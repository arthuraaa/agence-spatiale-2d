# Agence Spatiale 2D

Simulation spatiale 2D façon *Space Agency*, en Python + pygame : on assemble une fusée
par étages, on décolle, on se met en orbite, on s'amarre à une station, on va se poser
sur la Lune ou sur Mars. La mécanique orbitale est réaliste (orbites képlériennes,
sphères d'influence, atmosphères, rotation des planètes) mais l'univers est 100 fois
plus petit que le vrai pour que tout aille vite.

## Démarrage rapide (PC)

```
pip install -r requirements.txt     # pygame, rien d'autre
python main.py                      # clavier + souris
python main.py --tactile            # l'interface du téléphone, à la souris
python tests/tout.py                # tous les tests (environ 3 min, sans fenêtre)
```

Python 3.10 ou plus, pygame 2. La partie est sauvegardée dans `sauvegarde.json`, à côté de
`main.py`. Pour travailler sur le projet avec Claude Code, ouvre ce dossier : `CLAUDE.md`
contient tout ce qu'il faut savoir (commandes, architecture, contraintes Android).

## Sur Android

Le même code tourne sur téléphone et tablette. Sur Android, le jeu passe tout seul en
**mode tactile** : commandes à l'écran au lieu du clavier, et affichage en paysage à une
résolution de 540 pixels de haut, agrandie pour remplir l'écran (sinon le texte ferait
à peine un millimètre). Sur PC, `python main.py --tactile` permet d'essayer ce mode à
la souris.

### Essayer tout de suite : Pydroid 3 (sans APK)

1. Installe **Pydroid 3** depuis le Play Store, puis, dans son menu, *Pip* → installe `pygame`.
2. Copie le dossier du jeu (décompressé) sur le téléphone, par exemple dans *Documents*.
3. Dans Pydroid, ouvre `main.py` et appuie sur ▶.

### Construire l'APK (test) et l'AAB (Google Play)

La construction Android utilise **buildozer** (python-for-android), réglé dans
`buildozer.spec` pour Google Play : Android 16 (API 36), bibliothèques alignées sur 16 Ko
(NDK r28c), format AAB pour la publication. La version se règle à un seul endroit,
`jeu/version.py` (`python outils/nouvelle_version.py 1.6.1` la fait avancer partout).

Tout se fait **sur ton PC**, sous Linux ou sous Windows avec **WSL2** (Ubuntu dans Windows),
car buildozer ne tourne pas directement sous Windows :

1. **Une seule fois**, installe Ubuntu dans Windows : dans PowerShell en administrateur,
   `wsl --install -d Ubuntu-24.04`, redémarre, puis crée ton utilisateur Ubuntu.
2. Dans Ubuntu, copie le projet dans ton dossier Linux (sur le disque Windows, `/mnt/c/...`,
   la construction serait des dizaines de fois plus lente) :
   `cp -r /mnt/c/Users/TOI/chemin/agence-spatiale-2d ~/ && cd ~/agence-spatiale-2d`
3. `bash outils/android/preparer.sh` : une seule fois (Java, compilateurs, buildozer).
4. `bash outils/android/construire.sh debug` : l'**APK de test**, dans `bin/` (30 à 60 min la
   première fois, le temps de télécharger le SDK et de compiler Python ; quelques minutes
   ensuite). `explorer.exe bin` ouvre le dossier dans Windows : envoie l'APK sur ton
   téléphone et installe-le.
5. `bash outils/android/construire.sh release` : l'**AAB signé** pour Google Play, avec ta clé
   d'envoi (`bash outils/android/creer_cle.sh`, une seule fois) : voir `PUBLICATION.md`.

Garde **une seule copie** du projet, celle d'Ubuntu (`~/agence-spatiale-2d`), et travaille
dedans, Claude Code compris : lancé dans Ubuntu, il fait lui-même les constructions et corrige
ce qui coince. Depuis Windows, cette copie se voit dans l'explorateur, sous « Linux ».
- **APK de test rapide, sans SDK Android** (une minute, pour essayer une modification sur
  ton téléphone) : `python outils/apk_rapide/construire.py`. Il réutilise un moteur déjà
  compilé : **jamais pour Google Play** (voir `outils/apk_rapide/LISEZMOI.md`).

`python outils/verifier_paquet.py bin/*.aab` contrôle un paquet avant de l'envoyer sur
Google Play (alignement 16 Ko, 64 bits, version d'Android visée).

Sur Android, python-for-android fournit pygame 2.1 : le jeu n'utilise rien de plus récent,
ni aucune bibliothèque compilée en plus. Les polices DejaVu sont livrées dans
`jeu/polices/` car la police par défaut de pygame n'a pas les caractères comme « → » ou « Δ ».

### Publier sur Google Play

Tout est prêt : textes de la fiche en français et en anglais, icône, bannière et captures
dans `store/`, politique de confidentialité dans `docs/`. La marche à suivre complète
(compte, clé d'envoi, formulaires de la Play Console, test fermé de 14 jours, mises à jour)
est dans **`PUBLICATION.md`**.

### Commandes tactiles

| Commande | Geste |
|---|---|
| gaz | poser le doigt sur la manette de gauche et glisser (en bas = coupé) |
| tourner | maintenir ⟲ ou ⟳ (en bas à droite) |
| étage, parachute, désamarrer, récupérer | boutons de la colonne de droite |
| SAS | boutons du bas (STAB, PRO, RÉTRO, RAD+, RAD−, CIBLE, ANTI, MAN) |
| RCS | bouton RCS, puis maintenir ▲ ▼ ◀ ▶ |
| temps | ◀ et ▶ en haut ; taper au centre remet à x1 |
| zoom | pincer à deux doigts |
| cibler, centrer, contrôler | taper sur une planète ou un vaisseau |
| déplacer la vue | glisser un doigt dans le vide |
| revenir au vaisseau | ◎ : la vue revient sur la fusée et rezoome dessus |
| nœud de manœuvre | taper sur l'orbite, glisser une poignée, ou la taper (±1 m/s) |
| pilote automatique | bouton « Pilote » en haut à droite (si les aides sont activées) |
| menu, missions, aide, sauvegarde | ☰ en haut à droite, ou le bouton « retour » d'Android |

On peut utiliser plusieurs doigts à la fois (les gaz d'une main, la rotation de l'autre).
La partie est sauvegardée quand l'appli passe en arrière-plan, et toutes les minutes.

## Tutoriels

Le bouton **Tutoriels** du menu propose huit courts scénarios, chacun sur une mécanique :
construire une fusée, premier décollage, étages et boosters, se mettre en orbite, les
manœuvres, s'amarrer à la station, se poser sur la Lune, rentrer sur Terre. Chaque scénario
démarre dans la bonne situation (sur le pas de tir, en orbite, près de la station, autour
de la Lune...). Une bulle explique simplement quoi faire et fait clignoter le bouton
concerné ; l'étape suivante arrive toute seule dès que c'est fait. Les tutoriels terminés
sont cochés. Ils se jouent à part : ta vraie partie n'est jamais touchée.
Si la fusée s'écrase, la bulle le dit, donne un conseil propre au tuto et propose
**Réessayer** ; le bouton **Recommencer** relance le tuto à tout moment (panne sèche...).
Si une étape a été sautée, la bulle rappelle ce qui manque (par exemple la capsule,
la tête de la fusée, avant de pouvoir lancer).

## Scénarios

Le bouton **Scénarios** du menu propose de rejouer de grandes missions, avec moins d'aide
que les tutoriels : chaque objectif dit quoi faire, à toi de trouver comment.

- **Spoutnik 1 (1957)** : mettre le premier satellite en orbite.
- **Vostok 1 (1961)** : le tour de la Terre de Gagarine, puis le retour en parachute. Sa fusée
  a des boosters latéraux, comme la vraie.
- **Apollo 11 (1969)** : Columbia et Eagle tournent autour de la Lune, amarrés. Sépare Eagle,
  pose-le, largue son étage de descente pour redécoller, rejoins Columbia, puis rentre sur
  Terre (l'aide « Retour vers la Terre » calcule la poussée pour quitter la Lune).
- **Apollo 13 (1970)** : le module de service a explosé ; le moteur d'Aquarius, le module
  lunaire, doit ramener l'équipage.

Comme les tutoriels, les scénarios se jouent à part (ta carrière n'est pas touchée), proposent
« Réessayer » après un crash, et sont cochés une fois réussis.

## Sons

Tous les sons sont fabriqués par le code (bruit filtré, sinus, enveloppes) : aucun fichier
audio. Boucles : moteur (plus sourd dans le vide), vent dans l'atmosphère, souffle du RCS,
et une nappe d'ambiance. Bruitages : séparation d'étage, explosion, amarrage, parachute,
atterrissage, alertes, mission réussie, clic des boutons. Au premier lancement, les sons
sont préparés une fois (quelques secondes sur téléphone) puis gardés dans `cache_sons/`.
Une **musique d'ambiance** est composée en direct par le jeu (nappes, basse et cloches sur une
gamme où rien ne sonne faux) : calme au menu, entraînante au décollage, rêveuse en orbite,
mystérieuse autour de la Lune et des planètes. Elle ne se répète jamais tout à fait.
Le réglage **Son : tout / sans musique / effets seuls / coupé** est dans le menu Options.

## Options et triche

Le menu **Options** réunit le son, les aides au pilotage et la triche. Depuis le menu
principal, on y choisit aussi si la triche est autorisée en vol. En vol (☰ ou Échap, puis
Options ; raccourci : **appui long sur l'horloge**, ou `F12` sur PC), la colonne TRICHE propose :
revenir 30 s en arrière (le jeu photographie la partie toutes les 5 s), faire le plein,
carburant infini, vaisseau indestructible, mise en orbite immédiate et, en carrière,
+50 000 de fonds ou toutes les pièces débloquées. Les options restent dans la sauvegarde.

## Déroulement

- **Menu** : *Nouvelle carrière* (budget de 25 000, pièces à débloquer grâce aux missions)
  ou *Bac à sable* (tout est débloqué, pas d'argent).
- **Hangar** : clique sur les pièces à gauche pour les empiler **du nez vers le moteur**.
  Un clic sur une pièce de la fusée la sélectionne (`Suppr` la retire, `↑ ↓` la déplace,
  une nouvelle pièce s'insère juste en dessous). À droite : masse, prix, Δv et poussée/poids
  (TWR) de chaque étage. Le bouton *Modèles* propose 6 fusées prêtes à voler.
- **Vol** : une seule vue, du vaisseau au système solaire entier, avec la molette.
  Clique sur une planète ou un vaisseau pour le **cibler**, y **centrer la vue** ou en
  **prendre le contrôle**.

### Règles d'assemblage

- Le moteur actif est celui tout en bas de la pile. Il vide les réservoirs placés au-dessus
  de lui, jusqu'au premier découpleur (ou port d'amarrage).
- `ESPACE` sépare la fusée au découpleur le plus bas : un découpleur = un étage.
- Un port d'amarrage s'oriente tout seul. Deux ports collés l'un à l'autre forment une
  jonction qu'on défait avec `U` (c'est comme ça qu'on livre un module à la station).
- La capsule a un parachute et des propulseurs RCS intégrés. Pour rentrer sur Terre,
  largue tout sauf la capsule avant d'ouvrir le parachute (sinon c'est trop lourd).
- **Boosters latéraux** : sélectionne une pièce de la fusée (un réservoir), puis ajoute un
  *Découpleur radial* : une paire de boosters symétriques s'y accroche. Remplis-les ensuite
  (réservoirs, moteur en bas, coiffe en haut) : ce que tu ajoutes va dans le booster
  sélectionné. Le bas des boosters est aligné sur le bas de leur pièce porteuse.
  Les boosters accrochés à l'étage du bas s'allument avec le moteur central, chacun avec son
  propre carburant, et `ESPACE` les largue en premier. Le modèle **Hercule** en montre un exemple.

## Commandes (clavier AZERTY)

| Pilotage | |
|---|---|
| `←` `→` ou `Q` `D` | tourner |
| `↑` `↓` ou `Z` `S` | gaz + / − |
| `W` / `X` | plein gaz / couper les gaz |
| `ESPACE` | séparer l'étage |
| `T` | SAS marche / arrêt |
| `1` … `8` (sans Maj) | SAS : stabiliser, prograde, rétrograde, radial +, radial −, vers la cible, dos à la cible, manœuvre |
| `R` puis `I` `K` `J` `L` | RCS : translation avant / arrière / gauche / droite (amarrage) |
| `P` | parachute (moins de 250 m/s) |
| `U` | désamarrer |
| `V` | référence de vitesse : surface / orbite / cible |

| Vue et temps | |
|---|---|
| Molette, `PgPréc` / `PgSuiv` | zoom |
| Clic sur un objet | cibler / centrer la vue / contrôler |
| Clic droit (ou clic dans le vide) + glisser | déplacer la vue sur la carte |
| `F`, ou « ◎ Vaisseau » | revenir sur le vaisseau (et rezoomer dessus) |
| `C` | caméra : auto / horizon local / nord en haut |
| `,` et `;` (ou `.`) | ralentir / accélérer le temps |
| `Entrée` | temps normal (x1) |
| `N` | vaisseau suivant |
| `Retour arrière` | effacer la cible |
| `M` / `H` / `Échap` | missions / aide / pause |
| `F5` / `F9` | sauvegarder / charger |

| Manœuvres | |
|---|---|
| `A`, ou clic sur l'orbite | poser un nœud de manœuvre |
| glisser une poignée | régler le Δv (`Maj` : au dixième, `Ctrl` : par paquets de 10) |
| molette sur une poignée | régler le Δv au m/s près |
| glisser le centre du nœud | déplacer le nœud le long de l'orbite |
| `8` | SAS : pointer la manœuvre |
| `Suppr` | effacer le nœud |
| `G` | pilote automatique (si les aides sont activées) |

Sur un clavier QWERTY : flèches pour piloter, `W` plein gaz, `X` couper.

Le temps accéléré au-delà de x4 exige moteurs coupés et hors atmosphère (le vaisseau passe
alors « sur rails » : sa position est calculée exactement, jusqu'à x1 000 000).
Le jeu ralentit tout seul avant une rentrée atmosphérique ou un impact.

## Premier vol : se mettre en orbite

La vue est orientée pour que **le bon sens (prograde) soit vers la droite**.

1. Hangar : garde le modèle *Pionnier*, clique sur **LANCER**.
2. `W` (plein gaz). Vers 300 m d'altitude, penche doucement vers la droite ; sois à
   l'horizontale vers 6 km. `ESPACE` quand le premier étage est vide.
3. Coupe les gaz (`X`) quand l'**apoapside** atteint ~12 km. Laisse monter (`;` pour accélérer).
4. Un peu avant l'apoapside : SAS **PRO** (`2`) puis plein gaz jusqu'à ce que le
   **périapside** dépasse 7 km (le haut de l'atmosphère). Tu es en orbite.
5. Retour : SAS **RETRO** (`3`), freine jusqu'à un périapside d'environ 1 km, largue tout
   sauf la capsule (`ESPACE`), puis `P` sous 250 m/s.

Repères de Δv : orbite terrestre ≈ 1 050 m/s, aller vers la Lune ≈ 310, aller-retour
lunaire complet avec atterrissage ≈ 2 000, départ vers Mars depuis l'orbite basse ≈ 350.

## Planifier une manœuvre

C'est l'outil principal dès qu'on quitte l'orbite basse : on prépare la poussée à
l'avance, on voit la trajectoire qu'elle donnera, et on la règle au m/s près avant
d'allumer quoi que ce soit.

1. En vol, appuie sur `A` (le nœud se pose à l'apoapside) ou clique directement sur
   ta trajectoire à l'endroit voulu.
2. Quatre poignées apparaissent : **vertes** = prograde / rétrograde (accélérer ou
   freiner), **cyan** = radial + / − (pousser vers le haut ou vers le bas).
   Tire-les à la souris, ou pointe-les et tourne la molette pour le réglage fin.
   La trajectoire obtenue s'affiche en **bleu**, avec son périapside, son apoapside
   et la rencontre éventuelle avec un autre corps.
3. Le panneau de gauche donne le Δv, la **durée de combustion** et un compte à
   rebours jusqu'à l'**allumage** (la moitié de la combustion avant le nœud, pour que
   la poussée soit centrée dessus).
4. `8` (bouton « MAN ») oriente le vaisseau dans l'axe de la manœuvre. Le bouton
   **Filer** accélère le temps : le jeu redescend tout seul à x1 juste avant l'allumage.
5. Plein gaz (`W`) quand le compte à rebours arrive à zéro. Le Δv restant descend
   jusqu'à zéro, puis le nœud disparaît de lui-même.

Trois choses utiles :

- Une **combustion longue** (plus de ~6 % d'une orbite) n'atteint jamais tout à fait le
  résultat annoncé : le nœud vise une direction fixe alors que le vaisseau, lui, tourne
  autour de la planète. Le panneau te prévient. Surveille la trajectoire réelle pendant
  la poussée et coupe quand elle te convient, ou partage la manœuvre en deux tours.
- Pour un départ vers la Lune ou une planète, ce n'est pas seulement le Δv qui compte
  mais **l'endroit de l'orbite** où l'on pousse : promène le nœud le long de l'orbite
  (glisse son centre, ou `+ tour` / `− tour`) jusqu'à ce que la rencontre apparaisse.
- Avec une cible sélectionnée, le panneau affiche l'**approche prévue** après la
  manœuvre : c'est ce qu'on règle pour un rendez-vous.

## Aides au pilotage

Le menu **Options** (menu principal, ou ☰ / Échap puis Options en vol) les active ou les
désactive toutes : **Aides au pilotage : oui / non**. Les tutoriels s'adaptent à ce réglage. Le choix est gardé dans `reglages.json`, à côté de la
sauvegarde. Désactivées, le jeu redevient 100 % manuel.

Le bouton **Pilote** (touche `G` sur PC) propose ce qui est utile sur le moment :

- **Mise en orbite** : depuis le pas de tir, virage progressif, largage des étages vides,
  sortie de l'atmosphère puis circularisation. Arrivée vers 12-13 km, orbite quasi ronde.
- **Exécuter la manœuvre** (aussi le bouton « Exécuter » du panneau du nœud) : le temps
  s'accélère jusqu'à l'allumage, le vaisseau pointe, pousse et coupe au bon moment.
  Pour une circularisation, il pousse à l'horizontale jusqu'à l'orbite la plus ronde ;
  pour un transfert, il suit le prograde et coupe quand l'énergie visée est atteinte
  (ce qui compense la perte d'une longue poussée).
- **Retour vers la Terre** (en orbite autour d'une lune) : pose le nœud qui quitte la lune
  avec un périapside au ras de l'atmosphère de la planète.
- **Circulariser** : pose un nœud à la prochaine apoapside (ou au périapside en arrivant
  sur une planète : c'est la capture).
- **Atterrissage automatique** : désorbitation si besoin, chute en temps accéléré, freinage
  au dernier moment, puis descente verticale douce jusqu'au contact.
- **Transfert vers…** (avec une lune ou une planète en cible) : pose le nœud de départ.
  Vers une planète, il attend la fenêtre de tir et l'annonce (« fenêtre dans 1,6 j »).
- **Rendez-vous et amarrage** (avec un vaisseau en cible, par exemple la station) : calcule
  une rencontre (transfert au bon angle de phase, ou orbite de phasage si l'on est à la même
  altitude), l'exécute, avance le temps pendant la croisière, puis enchaîne sur l'amarrage.
  Depuis le pas de tir, décollage compris, Hermès rejoint ainsi la station tout seul.
- **Amarrage automatique** (cible à moins de 5 km) : approche au moteur principal jusqu'à
  25 m devant le port libre de la cible, puis ligne droite finale au RCS, de plus en plus
  doucement. Il faut un port libre de chaque côté.

Pendant une descente, le panneau **ATTERRISSAGE** donne l'altitude, les vitesses, le temps
avant l'impact et le moment où commencer à freiner (« MAINTENANT » en rouge), ou l'entrée
dans l'atmosphère. Près d'un vaisseau ciblé, le panneau **AMARRAGE** donne la distance au
port, les vitesses relatives, l'écart latéral et l'alignement (sur téléphone, ces lignes
s'ajoutent au panneau de la cible). Toucher aux gaz, à la rotation, au RCS ou au SAS rend la
main au joueur.

## Atterrir

SAS **RÉTRO** (vitesse par rapport au sol), puis attends que le panneau ATTERRISSAGE affiche
« Freinage : MAINTENANT » : plein gaz jusqu'à presque s'arrêter, puis descends doucement en
dosant les gaz. Le panneau donne les vitesses verticale et horizontale et l'inclinaison (en
rouge si ça ne passera pas). Près du sol, RÉTRO se redresse tout seul : on touche le sol
presque droit. Avec un train d'atterrissage, on peut se poser jusqu'à 14 m/s et 45° ;
sans, 8 m/s et 30°.

## Transfert de carburant

Un vaisseau se découpe en parties séparées par les découpleurs et les ports amarrés. Le
bouton **Carburant** (quand on est amarré), ou « Transfert de carburant » dans le menu pause,
les liste avec leurs jauges : **Remplir** puise le carburant et le monergol dans toutes les
autres parties. Pratique pour ravitailler un vaisseau à la station, ou pour vider l'étage du
bas dans celui du haut avant de le larguer.

## Rendez-vous et amarrage

1. Lance *Hermès* et mets-toi en orbite un peu plus bas que la Station Alpha (15 km).
   Un nœud de manœuvre réglé pour que « approche prévue » tombe sous quelques centaines
   de mètres fait le gros du travail.
2. Clique sur la station → **Cibler**. Le panneau de droite donne la distance, la vitesse
   relative et la **prochaine approche minimale** (marqueurs roses sur la trajectoire).
   Une orbite plus basse va plus vite : ajuste ton apoapside jusqu'à obtenir une approche
   de quelques centaines de mètres.
3. Au plus près : `V` jusqu'à « cible », SAS **RETRO**, et annule la vitesse relative.
4. Approche à quelques m/s, puis `R` (RCS) et `I K J L` pour aligner ton port dans le couloir
   en pointillés du port de la station. Contact à moins de 2,5 m/s, ports face à face.

## Aller sur la Lune (ou ailleurs)

Le plus simple est de poser un nœud (voir plus haut) et de le promener sur l'orbite
jusqu'à voir la rencontre. À la main, ça marche aussi :
cible la Lune, puis, en orbite basse, accélère en prograde en regardant la trajectoire :
dès qu'elle croise la Lune, le jeu affiche « Rencontre » et dessine le **survol prévu** (fantôme de
la Lune, périapside lunaire). Au périapside lunaire, freine en rétrograde pour te mettre en orbite. Même principe
pour les planètes : on s'évade de la Terre dans le sens de sa course (planètes extérieures) ou
à l'inverse (Vénus, Mercure), au bon moment, et on ajuste jusqu'à voir la rencontre.

## L'échelle

- Longueurs (rayons, distances) : **1/100** de la réalité. La gravité de surface est la vraie.
- Conséquence : vitesses ÷ 10 (orbite basse ≈ 735 m/s), durées ÷ 10 (un tour ≈ 10 min,
  la Lune à quelques heures, Mars à ~26 jours). Atmosphères à l'échelle 1/10 (7 km pour la Terre).
- Pour que les étages gardent de l'intérêt dans ce petit univers, les Isp des moteurs sont
  réduites aussi (100 à 140 s, 250 s pour le nucléaire).
- Physique : un seul corps attire le vaisseau à la fois (coniques raccordées). Moteurs
  allumés ou dans l'atmosphère, le mouvement est intégré numériquement (RK4) ; sinon il est
  calculé exactement par les équations de Kepler.

## Le code

```
main.py               boucle principale, passage d'une scène à l'autre
jeu/constantes.py     tous les réglages (tolérances, accélérations du temps, couleurs...)
jeu/orbite.py         mécanique képlérienne 2D, module autonome et réutilisable
jeu/corps.py          planètes et lunes (une ligne par corps)
jeu/pieces.py         catalogue des pièces et modèles de fusées (une ligne par pièce)
jeu/vaisseau.py       pile de pièces : masse, centre de masse, moteur actif, Δv, ports
jeu/trajectoire.py    prédiction : tronçons d'orbite, changements de sphère d'influence, rencontres
jeu/manoeuvre.py      nœuds de manœuvre : impulsion planifiée et trajectoire obtenue
jeu/pilote.py         aides : pilote auto, circularisation, transferts, rendez-vous, amarrage
jeu/reglages.py       réglages gardés d'une partie à l'autre (aides, son, tutoriels faits)
jeu/sons.py           sons fabriqués par le code (boucles et bruitages), cache .wav
jeu/musique.py        musique d'ambiance composée en direct selon l'humeur du moment
jeu/triche.py         menu secret : photos de la partie (retour en arrière), plein, options
jeu/tutoriel.py       les huit tutoriels : situations de départ, étapes, bulle (moteur commun)
jeu/scenarios.py      les missions historiques (Spoutnik, Vostok, Apollo 11, Apollo 13)
jeu/univers.py        la simulation : physique, rails, étages, amarrage, atterrissage
jeu/missions.py       les 20 missions et leurs conditions
jeu/sauvegarde.py     sauvegarde JSON
jeu/interface.py      texte, boutons, panneaux, formats (distances, durées)
jeu/rendu.py          caméra et dessin du monde (planètes, vaisseaux, trajectoires)
jeu/hud.py            instruments de vol
jeu/vol.py, hangar.py, menu.py   les trois écrans
jeu/plateforme.py     PC ou Android : mode tactile, taille de l'écran
jeu/tactile.py        suivi des doigts posés sur l'écran (plusieurs à la fois)
jeu/hud_tactile.py    instruments et commandes de vol pour écran tactile
jeu/polices/          polices DejaVu Sans (et leur licence)
jeu/version.py        la version du jeu (seule source, lue par buildozer.spec et le menu)
tests/                tests sans écran : python tests/tout.py (ou un seul fichier)
outils/               verifier_paquet.py, nouvelle_version.py, generer_visuels_store.py,
                      apk_rapide/ (APK de test sans SDK)
store/                fiche Google Play : textes FR/EN, icône, bannière, captures
docs/                 politique de confidentialité (texte à mettre en ligne, sur Google Sites)
android/              attributs ajoutés au manifeste Android
buildozer.spec, icone.png, presplash.png   construction Android
outils/android/       préparer Ubuntu/WSL2, construire (APK ou AAB), créer la clé d'envoi
CLAUDE.md             guide pour Claude Code      PUBLICATION.md  publier sur Google Play
LICENCES.md           licences des composants libres
```

Pour ajouter une pièce ou une planète, il suffit d'une ligne dans `pieces.py` ou `corps.py`.
Les tests pilotent de vraies missions automatiquement (mise en orbite des 7 modèles, à la main puis par le pilote automatique, voyage et
atterrissage sur la Lune, amarrage, rentrée sous parachute, transfert vers Mars,
planification puis exécution d'un nœud de manœuvre à la souris, boosters, transferts
automatiques vers la Lune et Mars, rendez-vous et amarrage depuis le pas de tir,
les huit tutoriels et les quatre missions historiques joués jusqu'au bout). `tests/test_tactile.py`
fait tout le trajet du menu jusqu'à l'orbite avec des doigts simulés, et secoue
l'interface tactile au hasard sur trois formats d'écran (20:9, 16:9, 4:3) ;
`tests/captures.py` enregistre des captures d'écran sans ouvrir de fenêtre.
`tests/test_attributs.py` vérifie que chaque `module.attribut` écrit dans le code existe
vraiment (avec le Python et le pygame de l'APK, c'est ce qui manquait pour éviter le plantage
de la version 1.3 au passage en arrière-plan).

## Idées pour la suite

Échauffement à la rentrée, stations ramifiées (ports latéraux), plusieurs nœuds
enchaînés, relief.
