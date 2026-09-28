# -*- coding: utf-8 -*-
"""
Tutoriels : de courts scénarios qui expliquent chacun une mécanique du jeu.

Un scénario prépare une situation (fusée sur le pas de tir, vaisseau près de la station,
en orbite autour de la Lune...) puis enchaîne des étapes. Chaque étape affiche une
explication simple dans une bulle, fait clignoter le bouton concerné, et passe toute
seule à la suivante dès que le joueur a fait ce qui est demandé (sa condition devient
vraie). Les tutoriels se jouent dans un univers à part : la vraie partie n'est jamais
sauvegardée par-dessus.
"""
import re
from math import atan2, cos, sin, sqrt
import pygame

from . import reglages, sons
from .interface import texte, panneau, Bouton, police
from .orbite import Orbite, angle_pi
from .pieces import CATALOGUE
from .vaisseau import construire, porteurs_actifs

ORANGE, BLANC, GRIS, JAUNE = (255, 170, 60), (235, 238, 245), (150, 158, 172), (255, 214, 70)

# Les mêmes gestes ne se disent pas pareil au clavier et au doigt : (PC, écran tactile)
COMMANDES = {
    "PILOTE": ("le bouton « Pilote auto » (touche G)", "le bouton « Pilote » en haut à droite"),
    "DESAMARRER": ("U (ou le bouton « Désamarrer »)", "le bouton « Désamarrer »"),
    "GAZ": ("appuie sur W (plein gaz d'un coup) ou maintiens Z", "pousse la manette de gauche tout en haut"),
    "COUPER": ("appuie sur X", "descends la manette de gauche tout en bas"),
    "TOURNER": ("Q et D (ou les flèches ← →)", "les boutons ⟲ et ⟳, en bas à droite"),
    "ETAGE": ("Espace (ou le bouton « Étage »)", "le bouton ÉTAGE"),
    "TEMPS": ("la touche « . » (et « , » pour ralentir)", "le bouton ▶ en haut"),
    "RCS": ("appuie sur R", "touche le bouton RCS"),
    "AVANT": ("maintiens I", "maintiens ▲"),
    "ARRIERE": ("K", "▼"),
    "TAPER": ("clique", "tape"),
    "PARACHUTE": ("P (ou le bouton « Parachute »)", "le bouton Parachute"),
    "ZOOM": ("la molette", "deux doigts qui pincent"),
}


def formater(txt, tactile):
    # [[texte avec les aides|texte sans les aides]] : selon le réglage « Aides au pilotage »
    txt = re.sub(r"\[\[(.*?)\|(.*?)\]\]", lambda m: m.group(1) if reglages.AIDES else m.group(2), txt)
    txt = re.sub(r"\s{2,}", " ", txt).strip()
    for cle, (pc, doigt) in COMMANDES.items():
        txt = txt.replace("{%s}" % cle, doigt if tactile else pc)
    # une commande insérée en début de phrase prend la majuscule (« … toi. Clique dessus »)
    return re.sub(r"(^|[.!?]\s+)([a-zàâçéèêëîïôûùüÿ])", lambda m: m.group(1) + m.group(2).upper(), txt)


def couper_lignes(txt, f, largeur):
    """Coupe un texte en lignes qui tiennent dans `largeur` pixels."""
    lignes, ligne = [], ""
    for mot in txt.split(" "):
        essai = (ligne + " " + mot).strip()
        if ligne and f.size(essai)[0] > largeur:
            lignes.append(ligne)
            ligne = mot
        else:
            ligne = essai
    return lignes + [ligne]


# =============================================================================
# Petits outils pour écrire les conditions
# =============================================================================
def _actif(sc):
    return sc.u.actif


def _alt(sc):
    a = sc.u.actif
    return sc.u.altitude(a) if a is not None else 0.0


def _ap(sc):
    a = sc.u.actif
    o = a.orbite if a is not None else None
    if o is None:
        return 0.0
    return o.ra - a.corps.R if o.elliptique else 1e12


def _pe(sc):
    a = sc.u.actif
    return a.orbite.rp - a.corps.R if a is not None and a.orbite is not None else 0.0


def _inclinaison(sc):
    """Angle entre l'axe de la fusée et la verticale du lieu."""
    a = sc.u.actif
    x, y = sc.u.etat(a)[:2]
    return abs(angle_pi(a.angle - atan2(y, x)))


def _station(u):
    return next((v for v in u.vaisseaux if v.nom.startswith("Station")), None)


def _en_vol(sc):
    from .vol import SceneVol
    return isinstance(sc, SceneVol)


# =============================================================================
# Scénarios
# =============================================================================
class Etape:
    """Une explication, et la condition qui fait passer à la suite (None : bouton « Suivant »)."""

    def __init__(self, texte, fini=None, bouton=None, tactile=None, debut=None, aide=None):
        self.texte = texte
        self.texte_tactile = tactile
        self.fini = fini              # fonction(tuto, scène) -> bool
        self.bouton = bouton          # libellé (ou libellés) du bouton à faire clignoter
        self.debut = debut            # fonction(tuto, scène) appelée quand l'étape commence
        self.aide = aide              # fonction(tuto, scène) -> indice à afficher en plus, ou None


class Scenario:
    def __init__(self, ident, titre, resume, depart, etapes, conseil="", genre="tuto", annee=None):
        self.ident, self.titre, self.resume = ident, titre, resume
        self.genre = genre            # "tuto" (tutoriels) ou "mission" (scénarios historiques)
        self.annee = annee
        self.conseil = conseil        # le petit conseil donné après un crash
        self.depart = depart          # fonction(app, univers) : pose le décor et ouvre la bonne scène
        self.etapes = etapes


def _pas_de_tir(nom_modele):
    def depart(app, u):
        from .pieces import MODELES
        nom, _, plan = next(m for m in MODELES if m[0] == nom_modele)
        u.lancer(nom, plan)
        app.aller_vol()
    return depart


def placer_en_orbite(u, v, corps, altitude, angle=0.0):
    """Met un vaisseau neuf sur une orbite ronde (sens direct), et en fait le vaisseau actif."""
    r = corps.R + altitude
    x, y = r * cos(angle), r * sin(angle)
    vit = sqrt(corps.mu / r)
    v.corps = corps
    v.x, v.y, v.vx, v.vy = x, y, -vit * sin(angle), vit * cos(angle)
    v.angle = atan2(v.vy, v.vx)
    v.mode = "rails"
    v.orbite = Orbite(v.x, v.y, v.vx, v.vy, corps.mu, u.t)
    v.cache_etat = (None, None)
    u.vaisseaux.append(v)
    u.actif = v
    u._predire(v)                                     # trajectoire prête dès la première image
    return v


def _vue_orbite(app, rayon):
    """Zoom qui montre toute l'orbite (pour la voir, et taper dessus)."""
    app.scene.cam.zoom = 0.36 * app.ecran.get_height() / rayon


def _depart_manoeuvres(app, u):
    v = construire("Hermès", ["port", "capsule", "decoupleur", "reservoir_m", "alize"], u.terre)
    placer_en_orbite(u, v, u.terre, 13_000, 0.6)
    app.aller_vol()
    _vue_orbite(app, u.terre.R + 13_000)


def _depart_amarrage(app, u):
    station = _station(u)
    es = u.etat(station)
    px, py, dx, dy = station.point_port(es, "haut")
    v = construire("Navette", ["port", "capsule", "reservoir_s", "moustique"], u.terre)
    ecart = 50.0 + v.geometrie().nez                  # 50 m entre les deux ports, face à face
    v.x, v.y = px + dx * ecart, py + dy * ecart
    v.vx, v.vy = es[2], es[3]
    v.angle = atan2(-dy, -dx)
    v.mode = "rails"
    v.orbite = Orbite(v.x, v.y, v.vx, v.vy, u.terre.mu, u.t)
    u.vaisseaux.append(v)
    u.actif = v
    u._predire(v)
    app.aller_vol()
    app.scene.cam.zoom = 4.0


def _depart_lune(app, u):
    lune = u.par_nom["Lune"]
    v = construire("Alunisseur", ["capsule", "reservoir_m", "train", "moustique"], lune)
    placer_en_orbite(u, v, lune, 10_000, 1.0)
    app.aller_vol()
    _vue_orbite(app, lune.R + 10_000)


def _depart_retour(app, u):
    v = construire("Capsule", ["capsule", "decoupleur", "reservoir_s", "moustique"], u.terre)
    placer_en_orbite(u, v, u.terre, 13_000, 2.2)
    app.aller_vol()
    _vue_orbite(app, u.terre.R + 13_000)


def _depart_hangar(app, u):
    app.aller_hangar()
    app.scene._vider()
    app.scene.nom = "Ma fusée"


def _memoriser_pieces(tuto, sc):
    tuto.memo["pieces"] = len(sc.u.actif.pieces)


def _cles(sc):
    return [e if isinstance(e, str) else e[0] for e in sc.cles]


def _aide_tete(sc):
    """Indice si la capsule manque, ou n'est pas tout en haut."""
    cles = _cles(sc)
    if "capsule" in cles and cles[0] != "capsule":
        return "La capsule doit être tout en haut : sélectionne-la, puis monte-la avec ▲."
    if cles and "capsule" not in cles:
        return "Il manque encore la capsule : {TAPER} « Capsule Mk1 » dans la liste de gauche."
    return None


def _aide_lancer(sc):
    """Si la fusée n'est pas prête (une étape sautée...), on dit ce qui manque."""
    if not any(CATALOGUE[c].commande for c in _cles(sc)):
        return "Il manque la tête de la fusée : ajoute une Capsule Mk1 tout en haut (rubrique Commande)."
    bloquants = [txt for txt, bloquant in sc.problemes() if bloquant]
    return ("Pas encore prêt : " + bloquants[0][0].lower() + bloquants[0][1:] + ".") if bloquants else None


SCENARIOS = [
    Scenario("hangar", "Construire une fusée", "Pièces, étages, poussée et Δv", _depart_hangar, [
        Etape("Voici le hangar : les pièces à gauche, ta fusée au centre, ses chiffres à droite. "
              "Une fusée se construit de haut en bas, en commençant par sa tête."),
        Etape("Pose d'abord la tête de la fusée : la Capsule Mk1 (rubrique Commande, en haut de la "
              "liste). C'est elle qui pilote : sans elle, la fusée ne peut pas décoller.",
              lambda t, sc: _cles(sc)[:1] == ["capsule"], aide=lambda t, sc: _aide_tete(sc)),
        Etape("Ajoute un Réservoir M : une nouvelle pièce se place sous la pièce sélectionnée.",
              lambda t, sc: "reservoir_m" in _cles(sc)),
        Etape("Ajoute un moteur Alizé tout en bas. Un moteur brûle le carburant des réservoirs "
              "placés au-dessus de lui.",
              lambda t, sc: bool(sc.cles) and CATALOGUE[_cles(sc)[-1]].forme == "moteur"),
        Etape("À droite, le TWR (poussée ÷ poids) doit dépasser 1 pour décoller, et le Δv dit jusqu'où "
              "tu iras (environ 1 050 m/s pour l'orbite). Pour aller plus loin, ajoute un Découpleur, "
              "puis dessous un Réservoir L et un moteur Mistral : un premier étage !",
              lambda t, sc: "decoupleur" in _cles(sc) and
              sum(CATALOGUE[c].forme == "moteur" for c in _cles(sc)) >= 2),
        Etape("Les accolades à droite de la fusée montrent ses étages, dans l'ordre où ils s'allument. "
              "Tout est prêt : appuie sur LANCER !", lambda t, sc: _en_vol(sc), bouton="LANCER",
              aide=lambda t, sc: _aide_lancer(sc)),
        Etape("Ta fusée est sur le pas de tir. Tu sais construire : le tuto « Premier décollage » "
              "t'apprend à la piloter."),
    ]),
    Scenario("decollage", "Premier décollage", "Les gaz, le SAS et l'altitude", _pas_de_tir("Pionnier"), [
        Etape("Bienvenue ! Ta fusée est sur le pas de tir. Pour décoller, {GAZ}.",
              lambda t, sc: _actif(sc).gaz > 0.9),
        Etape("Elle décolle ! Le SAS (bouton STAB allumé, en bas) la garde bien droite tout seul. "
              "Ton altitude s'affiche en haut à gauche.",
              lambda t, sc: _alt(sc) > 800, bouton="STAB"),
        Etape("Continue jusqu'à 3 km d'altitude.", lambda t, sc: _alt(sc) > 3000),
        Etape("Maintenant, coupe les moteurs : {COUPER}.", lambda t, sc: _actif(sc).gaz == 0.0),
        Etape("Sans moteur, la fusée monte encore sur sa lancée, ralentit, puis retombe : c'est la "
              "gravité. Pour ne plus retomber, il faut aller très vite sur le côté : c'est l'orbite "
              "(tuto « Se mettre en orbite »)."),
    ]),
    Scenario("etages", "Étages et boosters", "Larguer ce qui est vide", _pas_de_tir("Hercule"), [
        Etape("Cette fusée a deux boosters sur les côtés. Au décollage, tous ses moteurs poussent "
              "ensemble : {GAZ}.", lambda t, sc: _actif(sc).gaz > 0.9),
        Etape("En bas à gauche, la jauge « Carburant (boosters) » descend vite. Attends qu'elle soit vide…",
              lambda t, sc: _actif(sc).carburant_boosters()[0] <= 0.0),
        Etape("Les boosters sont vides : ce n'est plus que du poids. Largue-les avec {ETAGE}.",
              lambda t, sc: not porteurs_actifs(_actif(sc).pieces), bouton="ÉTAGE"),
        Etape("Plus légère, la fusée accélère mieux. Quand l'étage central est vide à son tour, "
              "{ETAGE} encore.", lambda t, sc: len(_actif(sc).pieces) < t.memo["pieces"],
              bouton="ÉTAGE", debut=_memoriser_pieces),
        Etape("Chaque étage largué allège la fusée : c'est le secret pour aller loin. Le Δv, en bas à "
              "gauche, dit quelle vitesse tu peux encore gagner avec ce qui reste."),
    ]),
    Scenario("orbite", "Se mettre en orbite", "Tomber à côté de la Terre", _pas_de_tir("Pionnier"), [
        Etape("Être en orbite, c'est aller si vite sur le côté qu'on tombe… à côté de la Terre, sans "
              "jamais la toucher. Pour commencer, {GAZ}.", lambda t, sc: _actif(sc).gaz > 0.9),
        Etape("Passé 1 km, penche doucement la fusée vers la droite avec {TOURNER}, d'environ 30°.",
              lambda t, sc: _alt(sc) > 1000 and _inclinaison(sc) > 0.35),
        Etape("Continue de pencher petit à petit, pour être presque couché vers 7 km. Surveille "
              "l'apoapside (Ap) à gauche : c'est le point le plus haut de ta trajectoire.",
              lambda t, sc: _ap(sc) > 13_000),
        Etape("Ap dépasse 13 km : {COUPER}. La fusée file sur sa lancée vers ce point haut.",
              lambda t, sc: _actif(sc).gaz == 0.0),
        Etape("Accélère le temps avec {TEMPS} en attendant d'arriver presque à l'apoapside "
              "(« Temps → Ap » à gauche).",
              lambda t, sc: _actif(sc).orbite is not None and _actif(sc).orbite.elliptique and
              _actif(sc).orbite.delai_apoapside(sc.u.t) < 25.0),
        Etape("Remets le temps normal, mets le SAS sur PRO (la fusée pointe dans le sens où elle va), "
              "puis {GAZ} : le périapside (Pe), ton point le plus bas, remonte.",
              lambda t, sc: _actif(sc).sas == "pro" and _actif(sc).gaz > 0.5, bouton="PRO"),
        Etape("Quand Pe dépasse 9 km, {COUPER} : tu es en orbite !",
              lambda t, sc: _pe(sc) > 9_000 and _actif(sc).gaz == 0.0),
        Etape("Bravo, tu tournes autour de la Terre sans moteur ! [[Le jeu sait aussi le faire tout seul : "
              "{PILOTE}, puis « Mise en orbite ».|Le jeu sait aussi le faire tout seul : active les aides au "
              "pilotage dans le menu Options.]]"),
    ]),
    Scenario("manoeuvres", "Les manœuvres", "Préparer puis exécuter un changement d'orbite", _depart_manoeuvres, [
        Etape("Tu es en orbite (la ligne autour de la Terre, c'est ta trajectoire). Pour la changer, "
              "on prépare une manœuvre : {TAPER} sur ta trajectoire pour y poser un nœud.",
              lambda t, sc: _actif(sc).noeud is not None),
        Etape("Le nœud a des poignées. Tire la poignée verte (prograde) vers l'extérieur : la "
              "trajectoire prévue, en pointillés, grandit. Vise environ +100 m/s.",
              lambda t, sc: _actif(sc).noeud is not None and _actif(sc).noeud.pro > 80.0),
        Etape("Le panneau du nœud dit quand allumer le moteur et combien de Δv donner. [[Appuie sur "
              "« Exécuter » dans ce panneau : le jeu avance le temps, pointe le vaisseau, pousse et coupe "
              "tout seul.|Appuie sur « Filer » pour avancer le temps jusqu'au nœud. Puis SAS sur MAN, plein gaz "
              "quand le compte à rebours arrive à zéro, et coupe quand il ne reste plus de Δv.]]",
              lambda t, sc: _actif(sc).noeud is None and _ap(sc) > 30_000, bouton=("Exécuter", "Filer", "MAN")),
        Etape("Ton orbite s'est allongée : tu montes maintenant bien plus haut. C'est avec des manœuvres "
              "comme celle-là qu'on rejoint la Lune ou une station."),
    ]),
    Scenario("amarrage", "S'amarrer à la station", "Cible, SAS, RCS et port d'amarrage", _depart_amarrage, [
        Etape("Voici la station Alpha, juste devant toi. {TAPER} dessus, puis choisis « Cibler ».",
              lambda t, sc: sc.u.cible is not None and sc.u.cible is _station(sc.u)),
        Etape("Mets le SAS sur CIBLE : ton nez, et le port d'amarrage qu'il porte, pointent vers la station.",
              lambda t, sc: _actif(sc).sas == "cible", bouton="CIBLE"),
        Etape("Active le RCS : de petits propulseurs qui déplacent le vaisseau sans le faire tourner. {RCS}.",
              lambda t, sc: _actif(sc).rcs, bouton="RCS"),
        Etape("Avance doucement : {AVANT} un court instant. Le panneau de la cible montre ta vitesse de "
              "rapprochement : reste sous 1 m/s.",
              lambda t, sc: _rapprochement(sc) > 0.3),
        Etape("Laisse-toi glisser jusqu'au contact : les ports s'accrochent tout seuls s'ils se touchent "
              "à moins de 2,5 m/s. Trop vite ? {ARRIERE} pour freiner.",
              lambda t, sc: "amarre:Station Alpha" in _actif(sc).drapeaux),
        Etape("Amarré ! Les deux vaisseaux n'en font plus qu'un. Le bouton « Carburant » sert à faire le "
              "plein, « Désamarrer » à repartir. [[Astuce : {PILOTE}, puis « Amarrage automatique », "
              "s'amarre tout seul.|]]", bouton="Carburant"),
    ]),
    Scenario("lune", "Se poser sur la Lune", "Descendre et freiner au bon moment", _depart_lune, [
        Etape("Tu tournes autour de la Lune, à 10 km. Pour descendre, il faut freiner : mets le SAS sur "
              "RÉTRO (la fusée pointe à l'envers de sa course).",
              lambda t, sc: _actif(sc).sas == "retro", bouton=("RÉTRO", "RETRO")),
        Etape("Maintenant {GAZ}, et coupe dès que le périapside (Pe) passe sous 0 : ta trajectoire "
              "touche alors le sol.", lambda t, sc: _pe(sc) < 0.0 and _actif(sc).gaz == 0.0),
        Etape("Tu tombes vers la Lune. Accélère le temps ({TEMPS}) : le jeu ralentit tout seul avant "
              "l'impact. [[Le panneau ATTERRISSAGE, à gauche, calcule le moment où freiner.|Avec les aides "
              "au pilotage (menu Options), un panneau calcule le moment où freiner.]]",
              lambda t, sc: _alt(sc) < 4000),
        Etape("[[Quand le panneau affiche « Freinage : MAINTENANT »|Vers 2 km d'altitude]], garde le SAS "
              "sur RÉTRO et mets plein gaz jusqu'à presque t'arrêter. Puis dose les gaz pour descendre "
              "doucement, vers −3 m/s.",
              lambda t, sc: _alt(sc) < 150 or _actif(sc).mode == "pose", bouton=("RÉTRO", "RETRO")),
        Etape("Pose-toi en douceur : près du sol, le SAS te redresse tout seul, et le train "
              "d'atterrissage amortit le choc. Vise moins de 5 m/s.",
              lambda t, sc: _actif(sc).mode == "pose"),
        Etape("Posé sur la Lune ! Pour repartir, fais comme pour l'orbite, en plus facile : pas d'air, "
              "et une pesanteur six fois plus faible. [[Astuce : {PILOTE}, puis « Atterrissage automatique », "
              "se pose tout seul.|]]"),
    ]),
    Scenario("retour", "Rentrer sur Terre", "Freiner, larguer, parachute", _depart_retour, [
        Etape("Pour rentrer sur Terre, on freine : SAS sur RÉTRO.",
              lambda t, sc: _actif(sc).sas == "retro", bouton=("RÉTRO", "RETRO")),
        Etape("{GAZ}, puis coupe quand le périapside (Pe) passe sous 3 km : ta trajectoire plonge "
              "alors dans l'atmosphère.", lambda t, sc: _pe(sc) < 3000 and _actif(sc).gaz == 0.0),
        Etape("Largue l'étage avec {ETAGE} : la capsule seule est assez légère pour son parachute.",
              lambda t, sc: not any(p.m.forme == "decoupleur" for p in _actif(sc).pieces), bouton="ÉTAGE"),
        Etape("Accélère le temps ({TEMPS}) en attendant l'atmosphère : le jeu ralentit tout seul avant "
              "d'y entrer.", lambda t, sc: _alt(sc) < _actif(sc).corps.atm_h),
        Etape("L'air freine la capsule. Quand ta vitesse passe sous 250 m/s, ouvre le parachute : {PARACHUTE}.",
              lambda t, sc: any(p.parachute == "ouvert" for p in _actif(sc).pieces), bouton="Parachute"),
        Etape("Il n'y a plus qu'à attendre l'atterrissage…", lambda t, sc: _actif(sc).mode == "pose"),
        Etape("Bienvenue sur Terre ! Tu as fait le tour complet d'une mission : décoller, tourner, revenir."),
    ]),
]
PAR_ID = {s.ident: s for s in SCENARIOS}

CONSEILS = {
    "decollage": "garde les gaz à fond et le SAS sur STAB : la fusée monte toute droite.",
    "etages": "appuie sur ÉTAGE dès qu'un étage est vide, sans couper les gaz.",
    "orbite": "penche doucement (environ 45° vers 5 km), et pousse assez longtemps près de "
              "l'apoapside pour remonter le périapside au-dessus de 7 km.",
    "manoeuvres": "regarde l'orbite prévue en bleu avant de pousser.",
    "amarrage": "dans les derniers mètres, approche à moins de 1 m/s.",
    "lune": "freine plus tôt : dès « Freinage : MAINTENANT », plein gaz en SAS RÉTRO, puis dose "
            "les gaz pour toucher le sol à moins de 5 m/s.",
    "retour": "largue le module de service avant l'atmosphère, puis ouvre le parachute sous 250 m/s.",
}
for _s in SCENARIOS:
    _s.conseil = CONSEILS.get(_s.ident, _s.conseil)


def _rapprochement(sc):
    from .pilote import geometrie_amarrage
    geo = geometrie_amarrage(sc.u, sc.u.actif, _station(sc.u))
    return -geo["w_axial"] if geo else 0.0


# =============================================================================
# Déroulement
# =============================================================================
def demarrer(app, ident):
    """Lance un scénario dans un univers neuf (bac à sable), à part de la vraie partie."""
    from .univers import Univers
    s = PAR_ID[ident]
    u = Univers(bac_a_sable=True)
    u.tutoriel = ident
    app.univers = u
    app.tuto = Tutoriel(s)
    s.depart(app, u)


class Tutoriel:
    def __init__(self, scenario):
        self.s = scenario
        self.k = 0                     # étape en cours
        self.termine = False
        self.memo = {}                 # ce qu'une étape veut retenir (nombre de pièces...)
        self._commencee = False
        self.hauteur = 0               # hauteur de la bulle (pour décaler les messages du jeu)
        self.echec = False             # le vaisseau s'est écrasé : on propose de réessayer

    @property
    def etape(self):
        return self.s.etapes[self.k]

    def suivant(self):
        """Étape suivante ; après la dernière, le scénario est terminé."""
        if self.k + 1 >= len(self.s.etapes):
            self.termine = True
            reglages.tuto_fait(self.s.ident)
            sons.jouer("succes")
            return
        self.k += 1
        self._commencee = False
        sons.jouer("bip")

    def maj(self, scene):
        if self.termine or self.echec:
            return
        u = getattr(scene, "u", None)
        if u is not None and hasattr(scene, "cam") and (u.perdu or u.actif is None):
            self.echec = True                  # écrasé (ou plus rien à piloter) : on réessaiera
            sons.jouer("alerte")
            return
        e = self.etape
        if not self._commencee:
            self._commencee = True
            if e.debut is not None:
                e.debut(self, scene)
        if e.fini is None:
            return
        try:
            ok = e.fini(self, scene)
        except (AttributeError, TypeError, KeyError, IndexError):
            ok = False                 # pas de vaisseau actif, orbite pas encore calculée...
        if ok:
            self.suivant()

    # ------------------------------------------------------------------ bulle
    def dessiner(self, surf, scene, boutons, cherche):
        """Bulle d'explication ; ses boutons rejoignent `boutons`, et le bouton à utiliser
        (cherché dans `cherche`) clignote."""
        from .hangar import SceneHangar
        l, h = surf.get_size()
        tactile = scene.tactile
        en_bas = False                             # bulle posée au-dessus des boutons du hangar
        if isinstance(scene, SceneHangar):
            x0, y0, larg = scene.lg + 16, 10, l - scene.lg - scene.ld - 32
            if larg < 300:                         # écran étroit : sur le bas du panneau de droite
                x0, larg, en_bas = l - scene.ld + 8, scene.ld - 16, True
        elif tactile:
            from .hud_tactile import MX, M, L_PANNEAU
            larg = max(300, l - 2 * (MX + L_PANNEAU + 16))
            x0, y0 = max(MX + L_PANNEAU + 12, (l - larg) // 2), M + 62   # jamais sur le panneau d'infos
            x0 = min(x0, l - MX - 4 - larg)
        else:
            larg = min(600, l - 620)
            x0, y0 = (l - larg) // 2, 58
        larg = max(260, larg)
        taille = 15 if tactile else 14
        f = police(taille)
        e = self.etape
        mission = self.s.genre == "mission"
        indice = None
        if self.echec:
            titre, couleur = "OUPS !", (255, 110, 90)
            corps = "Ta fusée s'est écrasée. Pas de panique : ça arrive à tous les astronautes !"
            if self.s.conseil:
                corps += " Conseil : " + self.s.conseil
        elif self.termine:
            suite = self._suivant_scenario()
            if mission:
                titre, couleur = "MISSION ACCOMPLIE !", (120, 230, 140)
                corps = "Mission « %s » réussie." % self.s.titre + (
                    " La suivante : « %s »." % suite.titre if suite else " Tu as rejoué toutes les missions !")
            else:
                titre, couleur = "BRAVO !", ORANGE
                corps = "Tuto « %s » terminé." % self.s.titre + (
                    " Le suivant : « %s »." % suite.titre if suite else " Tu as fait tous les tutos !")
        else:
            titre, couleur = "%s %d/%d · %s" % ("MISSION" if mission else "TUTO", self.k + 1,
                                                len(self.s.etapes), self.s.titre), ORANGE
            corps = e.texte_tactile if (tactile and e.texte_tactile) else e.texte
            if e.aide is not None:
                try:
                    indice = e.aide(self, scene)
                except (AttributeError, TypeError, KeyError, IndexError):
                    indice = None
        lignes = couper_lignes(formater(corps, tactile), f, larg - 24)
        lignes_indice = couper_lignes(formater(indice, tactile), f, larg - 24) if indice else []
        hb = 44 if tactile else 28
        haut = 36 + (len(lignes) + len(lignes_indice)) * (taille + 5) + hb + 14
        if en_bas:
            y0 = max(10, h - 162 - haut)
        panneau(surf, (x0, y0, larg, haut), alpha=238)
        texte(surf, titre, (x0 + 12, y0 + 10), taille - 1, couleur, gras=True)
        yy = y0 + 34
        for ligne in lignes:
            texte(surf, ligne, (x0 + 12, yy), taille, BLANC)
            yy += taille + 5
        for ligne in lignes_indice:                # l'indice, en jaune
            texte(surf, ligne, (x0 + 12, yy), taille, JAUNE)
            yy += taille + 5
        # boutons, alignés à droite
        yb = y0 + haut - hb - 8
        app = scene.app
        entrees = []
        page = "scenarios" if mission else "tutos"
        if self.echec:
            entrees.append(("Réessayer", lambda: demarrer(app, self.s.ident)))
            entrees.append(("Quitter", lambda: app.aller_menu(page)))
        elif self.termine:
            suite = self._suivant_scenario()
            if suite is not None:
                entrees.append(("Mission suivante ›" if mission else "Tuto suivant ›",
                                lambda s=suite: demarrer(app, s.ident)))
            entrees.append(("Liste des missions" if mission else "Liste des tutos", lambda: app.aller_menu(page)))
        else:
            entrees.append(("Suivant ›" if e.fini is None else "Passer", self.suivant))
            entrees.append(("Recommencer", lambda: demarrer(app, self.s.ident)))
            entrees.append(("Quitter", lambda: app.aller_menu(page)))
        marge = 34 if tactile else 22
        if sum(f.size(lib)[0] + marge + 8 for lib, _ in entrees) > larg - 16:
            entrees = [("↺" if lib == "Recommencer" else lib, act) for lib, act in entrees]   # place comptée
        x = x0 + larg - 12
        for lib, act in entrees:
            w = f.size(lib)[0] + marge
            x -= w
            b = Bouton((x, yb, w, hb), lib, act, taille)
            b.dessiner(surf, pygame.mouse.get_pos())
            boutons.append(b)
            x -= 8
        self.hauteur = 0 if en_bas else haut + 8
        # le bouton à utiliser clignote
        if not (self.termine or self.echec) and e.bouton:
            for lib in (e.bouton if isinstance(e.bouton, tuple) else (e.bouton,)):
                b = next((b for b in cherche if b.libelle.lower().startswith(lib.lower())), None)
                if b is not None:
                    k = 0.5 + 0.5 * sin(pygame.time.get_ticks() / 140.0)
                    pygame.draw.rect(surf, JAUNE, b.rect.inflate(8 + 8 * k, 8 + 8 * k), 3, border_radius=9)
                    break

    def _suivant_scenario(self):
        liste = [s for s in PAR_ID.values() if s.genre == self.s.genre]
        i = liste.index(self.s)
        return liste[i + 1] if i + 1 < len(liste) else None


# Les missions historiques (scenarios.py) utilisent ce moteur : on les enregistre dans PAR_ID.
from . import scenarios  # noqa: E402,F401
