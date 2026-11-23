# -*- coding: utf-8 -*-
"""
Scénarios : des missions historiques à rejouer.

    Spoutnik 1 (1957), Vostok 1 (1961), Apollo 11 (1969), Apollo 13 (1970),
    Luna 2 (1959), Apollo-Soyouz (1975), Voyager 2 (1977), Cassini-Huygens (1997).

Même moteur que les tutoriels (tutoriel.py) : une situation de départ, des objectifs validés
tout seuls, une bulle qui explique, « Réessayer » après un crash, et une partie à part qui ne
touche jamais la carrière. Mais on guide moins : chaque objectif dit quoi faire, pas chaque geste.

Les vaisseaux changent de nom quand on les amarre ou les sépare : les objectifs suivent donc
les pièces de commande (« la capsule d'Eagle est posée sur la Lune »), qui gardent leur
propriétaire d'origine.
"""
from math import atan2, cos, sin, sqrt, pi

from .orbite import Orbite
from .vaisseau import construire
from .corps import Corps
from .tutoriel import Scenario, Etape, PAR_ID, placer_en_orbite, _vue_orbite

CSM = ["port", "capsule", "decoupleur", "reservoir_m", "alize"]          # vaisseau de commande et de service
LEM = ["port", "capsule", "reservoir_s", "moustique",                     # module lunaire : étage de remontée...
       "decoupleur", "reservoir_m", "train", "moustique"]                 # ... et étage de descente
SOYOUZ = ["port", "capsule", "decoupleur", "reservoir_m", "alize", "port"]  # le Soyouz (ASTP) :
# un port aux deux bouts, comme la station, pour que l'aide d'amarrage accroche le port
# le plus proche quel que soit le côté d'où arrive Apollo.
VOYAGER = ["sonde", "panneaux", "reservoir_m", "moustique", "decoupleur", "reservoir_l",
           "reservoir_l", "atome", "decoupleur", "reservoir_xxl", "reservoir_xxl", "titan"]
CASSINI = ["sonde", "panneaux", "reservoir_xxl", "atome"]                 # déjà en route pour Saturne


# --------------------------------------------------------------------------- outils
def vaisseau_de(u, nom):
    """Le vaisseau (intact) qui contient la pièce de commande d'origine `nom`, ou None."""
    for v in u.vaisseaux:
        if not v.detruit and any(p.m.commande and p.proprietaire == nom for p in v.pieces):
            return v
    return None


def _seul(u, nom, autre):
    """Le vaisseau de `nom`, s'il n'est pas amarré à celui de `autre`."""
    v = vaisseau_de(u, nom)
    return v if v is not None and v is not vaisseau_de(u, autre) else None


def _en_orbite(v, corps, marge=1000.0):
    o = v.orbite if v is not None else None
    return (v is not None and v.corps is corps and v.mode != "pose" and o is not None and o.elliptique
            and o.rp > corps.R + corps.atm_h + marge)


def _pose_sur(v, corps):
    return v is not None and v.mode == "pose" and v.corps is corps


def _pe(u):
    a = u.actif
    o = a.orbite if a is not None else None
    return (o.rp - a.corps.R) if o is not None else 0.0


def _ap(u):
    a = u.actif
    o = a.orbite if a is not None else None
    return (o.ra - a.corps.R) if o is not None and o.elliptique else 0.0


def _placer(u, v, x, y, vx, vy):
    """Met un vaisseau neuf à un endroit précis (sur rails) et en fait le vaisseau actif."""
    v.x, v.y, v.vx, v.vy = x, y, vx, vy
    v.angle = atan2(vy, vx)
    v.mode = "rails"
    v.orbite = Orbite(x, y, vx, vy, v.corps.mu, u.t)
    v.cache_etat = (None, None)
    u.vaisseaux.append(v)
    u.actif = v


def _amarrer_au_depart(u, a, b):
    """Amarre b nez à nez au port du haut de a (actif) : la pile de a reste en bas,
    c'est donc son moteur qui pousse l'ensemble."""
    ea = u.etat(a)
    px, py, dx, dy = a.point_port(ea, "haut")
    nez = b.geometrie().nez
    b.angle = atan2(-dy, -dx)
    b.x, b.y, b.vx, b.vy = px + dx * nez, py + dy * nez, ea[2], ea[3]
    b.mode = "physique"
    b.orbite = Orbite(b.x, b.y, b.vx, b.vy, a.corps.mu, u.t)
    b.cache_etat = (None, None)
    u.vaisseaux.append(b)
    u._amarrer(a, b, "haut", "haut", u.etat(a), u.etat(b))
    a.drapeaux.discard("amarre:" + b.nom)
    u.messages.clear()
    u.bruits.clear()


# --------------------------------------------------------------------------- départs
def _depart_pas_de_tir(nom, plan):
    def depart(app, u):
        u.lancer(nom, plan)
        app.aller_vol()
    return depart


def _depart_apollo11(app, u):
    lune = u.par_nom["Lune"]
    columbia = construire("Columbia", CSM, lune)
    placer_en_orbite(u, columbia, lune, 8000, 0.8)
    _amarrer_au_depart(u, columbia, construire("Eagle", LEM, lune))
    app.aller_vol()
    _vue_orbite(app, lune.R + 8000)


def _depart_apollo13(app, u):
    """En route vers la Lune, sur une orbite terrestre très allongée (la Lune est loin, de l'autre côté)."""
    terre, lune = u.terre, u.par_nom["Lune"]
    mu = terre.mu
    rp, ra = terre.R + 13_000, 2_300_000.0
    a, e = 0.5 * (rp + ra), (ra - rp) / (ra + rp)
    p = a * (1 - e * e)
    nu = 2.1                                           # déjà bien parti vers le haut de l'orbite
    lx, ly = lune.position_relative(u.t)
    theta = atan2(ly, lx) + pi                         # à l'opposé de la Lune : pas de rencontre
    r = p / (1 + e * cos(nu))
    vr, vt = sqrt(mu / p) * e * sin(nu), sqrt(mu / p) * (1 + e * cos(nu))
    ux, uy = cos(theta), sin(theta)
    aquarius = construire("Aquarius", LEM, terre)
    _placer(u, aquarius, r * ux, r * uy, vr * ux - vt * uy, vr * uy + vt * ux)
    odyssey = construire("Odyssey", CSM, terre)
    _amarrer_au_depart(u, aquarius, odyssey)           # Aquarius en bas : son moteur pousse l'ensemble
    for piece in u.actif.pieces:                       # l'explosion : le module de service est vide
        if piece.proprietaire == "Odyssey" and piece.m.carburant > 0:
            piece.carburant = 0.0
    app.aller_vol()
    app.scene.cam.zoom = 0.9 * min(app.ecran.get_size()) / (2.6 * ra)


# --------------------------------------------------------------------------- les missions
def _depart_apollo_soyouz(app, u):
    """Deux vaisseaux amis en orbite terrestre basse, à 3 km l'un de l'autre : plus qu'à se rejoindre."""
    terre = u.terre
    apollo = construire("Apollo", CSM, terre)
    placer_en_orbite(u, apollo, terre, 12000, 1.0)
    soyouz = construire("Soyouz", SOYOUZ, terre)
    placer_en_orbite(u, soyouz, terre, 12000, 1.04)
    for v in (apollo, soyouz):                         # monergol généreux : la capsule n'emporte
        for piece in v.pieces:                         # que 120 kg et le SAS de croisière en mange
            if piece.m.mono > 0.0:
                piece.mono = 500.0
    u.actif = apollo
    app.aller_vol()
    _vue_orbite(app, terre.R + 12000)


def _depart_cassini(app, u):
    """Cassini, déjà partie de la Terre : en attente sur une orbite haute circulaire,
    prête à filer vers Saturne dès sa fenêtre de tir."""
    terre = u.terre
    cassini = construire("Cassini", CASSINI, terre)
    placer_en_orbite(u, cassini, terre, 60_000, 0.4)
    app.aller_vol()
    _vue_orbite(app, terre.R + 60_000)


def _impact_sur(corps_nom):
    """Une explosion vient-elle de se produire sur ce corps ? (l'effet dure 1,6 s, largement vu)"""
    def fini(t, sc):
        corps = sc.u.par_nom.get(corps_nom)
        return corps is not None and any(e["corps"] is corps for e in sc.u.effets)
    return fini


def _cible_est(nom):
    """La cible du joueur est bien le vaisseau (ou corps) de `nom`."""
    def fini(t, sc):
        return (sc.u.cible is not None and not isinstance(sc.u.cible, Corps)
                and sc.u.cible is vaisseau_de(sc.u, nom))
    return fini


def _ok_capsule_seule(u, nom):
    """Le vaisseau actif est la capsule de `nom`, débarrassée de tout moteur (prête à rentrer)."""
    v = u.actif
    return v is not None and v is vaisseau_de(u, nom) and v.moteur_actif() is None


def _tour_complet_debut(t, sc):
    o = sc.u.actif.orbite
    t.t_tour = sc.u.t + (o.periode if o is not None and o.elliptique else 600.0)


MISSIONS = [
    Scenario("spoutnik", "Spoutnik 1", "Le premier satellite artificiel",
             _depart_pas_de_tir("Spoutnik", ["sonde", "reservoir_m", "alize", "decoupleur",
                                             "reservoir_l", "reservoir_l", "mistral"]), [
        Etape("4 octobre 1957. L'Union soviétique lance Spoutnik 1, une sphère de 58 cm munie de quatre "
              "antennes. C'est le premier objet fabriqué par l'homme à tourner autour de la Terre. "
              "À toi de rejouer ce lancement !"),
        Etape("Décolle : {GAZ}.", lambda t, sc: sc.u.altitude(sc.u.actif) > 1000),
        Etape("Penche doucement vers la droite et monte jusqu'à ce que l'apoapside dépasse 13 km. "
              "Quand un étage est vide : {ETAGE}. [[Besoin d'aide ? {PILOTE}, puis « Mise en orbite ».|]]",
              lambda t, sc: _ap(sc.u) > 13_000),
        Etape("Près de l'apoapside, SAS sur PRO et pousse jusqu'à ce que le périapside dépasse 8 km.",
              lambda t, sc: _pe(sc.u) > 8000),
        Etape("Bip… bip… Spoutnik tourne autour de la Terre ! Pendant 21 jours, ses signaux ont été "
              "captés par les radioamateurs du monde entier."),
    ], conseil="penche doucement dès 1 km, et appuie sur ÉTAGE quand un étage est vide.",
       genre="mission", annee=1957),

    Scenario("vostok", "Vostok 1", "Gagarine, premier homme dans l'espace",
             _depart_pas_de_tir("Vostok 1", ["capsule", "decoupleur", "reservoir_s", "moustique",
                                             "decoupleur", "reservoir_m", "alize", "decoupleur",
                                             # comme la vraie fusée : des boosters autour de l'étage central
                                             ["reservoir_l", ["decoupleur_radial", "coiffe", "reservoir_l",
                                                              "mistral"]], "reservoir_l", "mistral"]), [
        Etape("12 avril 1961. Youri Gagarine devient le premier homme dans l'espace : à bord de "
              "Vostok 1, il fait le tour de la Terre en 108 minutes, puis revient. À ton tour !"),
        Etape("Mets Vostok 1 en orbite : périapside au-dessus de 8 km. "
              "[[Besoin d'aide ? {PILOTE}, puis « Mise en orbite ».|]]",
              lambda t, sc: _pe(sc.u) > 8000 and sc.u.actif.gaz == 0.0),
        Etape("Fais un tour complet de la Terre : avance le temps ({TEMPS}) et regarde-toi tourner.",
              lambda t, sc: sc.u.t >= getattr(t, "t_tour", 1e18), debut=_tour_complet_debut),
        Etape("Pour rentrer, freine : SAS sur RÉTRO puis {GAZ}, jusqu'à ce que le périapside passe "
              "sous 3 km. Coupe alors les gaz.",
              lambda t, sc: _pe(sc.u) < 3000 and sc.u.actif.gaz == 0.0),
        Etape("Largue le module de service ({ETAGE}) : seule la capsule a un bouclier et un parachute.",
              lambda t, sc: _ok_capsule_seule(sc.u, "Vostok 1")),
        Etape("Avance le temps jusqu'à l'atmosphère. Sous 250 m/s, ouvre le parachute : {PARACHUTE}.",
              lambda t, sc: _pose_sur(vaisseau_de(sc.u, "Vostok 1"), sc.u.terre)),
        Etape("Gagarine a sauté en parachute à 7 km d'altitude et s'est posé dans un champ, près de la "
              "Volga. Il est devenu un héros sur toute la planète."),
    ], conseil="au retour, largue le module de service avant l'atmosphère et ouvre le parachute "
               "sous 250 m/s.", genre="mission", annee=1961),

    Scenario("apollo11", "Apollo 11", "Se poser sur la Lune, puis rentrer",
             _depart_apollo11, [
        Etape("Juillet 1969. Columbia (le vaisseau de commande) et Eagle (le module lunaire) tournent "
              "autour de la Lune, amarrés nez à nez. Michael Collins reste dans Columbia ; Neil "
              "Armstrong et Buzz Aldrin vont se poser avec Eagle."),
        Etape("Sépare Eagle de Columbia : {DESAMARRER}. Puis prends les commandes d'Eagle : {TAPER} "
              "dessus, puis « Contrôler ». (N'appuie pas sur ÉTAGE : ça larguerait le module de service !)",
              lambda t, sc: _seul(sc.u, "Eagle", "Columbia") is not None
              and sc.u.actif is _seul(sc.u, "Eagle", "Columbia"), bouton="Désamarrer"),
        Etape("Pose Eagle sur la Lune, en douceur. [[Besoin d'aide ? {PILOTE}, puis « Atterrissage "
              "automatique ».|SAS sur RÉTRO, freine franchement vers 2 km, puis descends doucement.]]",
              lambda t, sc: _pose_sur(vaisseau_de(sc.u, "Eagle"), sc.u.par_nom["Lune"])),
        Etape("« Houston, ici la base de la Tranquillité. L'Aigle s'est posé. » Il faut maintenant "
              "repartir : {ETAGE} largue l'étage de descente, qui sert de rampe de lancement. Remets "
              "Eagle en orbite. [[{PILOTE}, puis « Mise en orbite ».|Monte droit, puis penche vers "
              "l'horizon.]]",
              lambda t, sc: _en_orbite(vaisseau_de(sc.u, "Eagle"), sc.u.par_nom["Lune"])
              and not any(p.m.forme == "train" for p in vaisseau_de(sc.u, "Eagle").pieces)),
        Etape("Rejoins Columbia et amarre-toi. [[{TAPER} sur Columbia, « Cibler », puis {PILOTE} et "
              "« Rendez-vous et amarrage ».|{TAPER} sur Columbia, « Cibler », prépare une rencontre avec "
              "un nœud de manœuvre, puis approche doucement au RCS.]]",
              lambda t, sc: vaisseau_de(sc.u, "Eagle") is not None
              and vaisseau_de(sc.u, "Eagle") is vaisseau_de(sc.u, "Columbia")),
        Etape("L'équipage est réuni. Pour rentrer, désamarre Eagle ({DESAMARRER}), prends les commandes "
              "de Columbia, puis quitte la Lune vers la Terre. [[{PILOTE}, puis « Retour vers la "
              "Terre » et « Exécuter ».|Pousse en prograde jusqu'à quitter la Lune avec un périapside "
              "terrestre sous 3 km.]]",
              lambda t, sc: _seul(sc.u, "Columbia", "Eagle") is not None
              and _seul(sc.u, "Columbia", "Eagle").corps is sc.u.terre
              and _seul(sc.u, "Columbia", "Eagle").orbite.rp < sc.u.terre.R + sc.u.terre.atm_h),
        Etape("Cap sur la Terre ! Avance le temps ({TEMPS}). Avant l'atmosphère, largue le module de "
              "service ({ETAGE}), puis ouvre le parachute sous 250 m/s ({PARACHUTE}).",
              lambda t, sc: _pose_sur(vaisseau_de(sc.u, "Columbia"), sc.u.terre)),
        Etape("24 juillet 1969 : Columbia amerrit dans le Pacifique. Armstrong l'a dit en posant le "
              "pied sur la Lune : c'est un petit pas pour un homme, un bond de géant pour l'humanité."),
    ], conseil="pour te poser, freine dès « Freinage : MAINTENANT » (ou vers 2 km), puis descends "
               "doucement. Le pilote automatique sait le faire.", genre="mission", annee=1969),

    Scenario("apollo13", "Apollo 13", "« Houston, on a un problème »", _depart_apollo13, [
        Etape("Avril 1970, en route vers la Lune. Un réservoir d'oxygène explose dans le module de "
              "service d'Odyssey : plus de carburant. L'équipage se réfugie dans Aquarius, le module "
              "lunaire, qui devient un canot de sauvetage. Plus question de se poser : il faut rentrer."),
        Etape("Utilise le moteur d'Aquarius : SAS sur RÉTRO, puis pousse jusqu'à ce que ton "
              "périapside passe sous 3 km (ta trajectoire replonge alors dans l'atmosphère). Coupe.",
              lambda t, sc: sc.u.actif is not None and sc.u.actif.corps is sc.u.terre
              and _pe(sc.u) < 3000 and sc.u.actif.gaz == 0.0),
        Etape("Avance le temps ({TEMPS}). Avant l'atmosphère : désamarre Aquarius ({DESAMARRER}), prends "
              "les commandes d'Odyssey ({TAPER} dessus, « Contrôler »), et largue son module de service "
              "({ETAGE}).",
              lambda t, sc: _ok_capsule_seule(sc.u, "Odyssey")),
        Etape("Seule la capsule entre dans l'atmosphère. Sous 250 m/s, ouvre le parachute : {PARACHUTE}.",
              lambda t, sc: _pose_sur(vaisseau_de(sc.u, "Odyssey"), sc.u.terre)),
        Etape("17 avril 1970 : l'équipage d'Apollo 13 amerrit sain et sauf. On a appelé cette mission "
              "« l'échec réussi »."),
    ], conseil="largue Aquarius et le module de service avant l'atmosphère, puis ouvre le parachute "
               "sous 250 m/s.", genre="mission", annee=1970),

    Scenario("luna2", "Luna 2", "Le premier objet sur la Lune",
             _depart_pas_de_tir("Luna 2", ["sonde", "reservoir_m", "alize", "decoupleur",
                                           "reservoir_xl", "reservoir_xl", "titan"]), [
        Etape("14 septembre 1959. Luna 2 frappe le sol de la Lune : c'est le premier objet fabriqué "
              "par l'homme à toucher un autre monde. Pas d'atterrissage en douceur ici : il faut "
              "arriver en force, et le drapeau soviétique qu'elle porte éclatera avec elle."),
        Etape("Décolle et mets Luna 2 en orbite : périapside au-dessus de 8 km. "
              "[[Besoin d'aide ? {PILOTE}, puis « Mise en orbite ».|]]",
              lambda t, sc: _pe(sc.u) > 8000 and sc.u.actif.gaz == 0.0),
        Etape("Cible la Lune (dézoome, puis {TAPER} dessus), planifie le transfert et exécute-le. "
              "[[Dézoome, {TAPER} sur la Lune, puis {PILOTE} : « Transfert vers la Lune », et "
              "« Exécuter la manœuvre ».|Dézoome, tape sur la Lune pour la cibler, pose un nœud qui "
              "allonge ton orbite jusqu'à elle, puis exécute-le.]]",
              lambda t, sc: sc.u.actif is not None and "soi:Lune" in sc.u.actif.drapeaux),
        Etape("La Lune arrive à ta rencontre. Ne freine pas : fonce ! Luna 2 doit frapper le sol "
              "lunaire, son paquet de bannières à la main.",
              _impact_sur("Lune")),
        Etape("Luna 2 a frappé la Lune entre les cratères Archimède et Autolycus, ses bannières "
              "éparpillées sur le sol. Un an plus tard, Luna 3 enverra les premières photos de la "
              "face cachée de la Lune."),
    ], conseil="mise en orbite, puis cible la Lune et laisse le pilote planifier le transfert ; "
               "ne freine jamais en approche.", genre="mission", annee=1959, crash_prevu=True),

    Scenario("apollo_soyouz", "Apollo-Soyouz", "La première poignée de main dans l'espace",
             _depart_apollo_soyouz, [
        Etape("Juillet 1975. En pleine guerre froide, un Apollo américain et un Soyouz soviétique "
              "s'amarrent en orbite : la première mission conjointe de deux puissances rivales. "
              "Les deux équipages avaient appris la langue de l'autre... Toi, apprends l'amarrage !"),
        Etape("Apollo est aux commandes. Cible Soyouz : {TAPER} dessus, puis « Cibler ».",
              _cible_est("Soyouz")),
        Etape("Rejoins Soyouz et amarre-toi. [[{PILOTE}, puis « Rendez-vous et amarrage » (il faut "
              "être à moins de 5 km)|Approche-toi d'abord avec un nœud de manœuvre, puis finis au "
              "RCS en visant la cible.]]",
              lambda t, sc: vaisseau_de(sc.u, "Apollo") is not None
              and vaisseau_de(sc.u, "Apollo") is vaisseau_de(sc.u, "Soyouz")),
        Etape("« Apollo et Soyouz sont amarrés ! » Les commandants Leonov et Stafford échangent "
              "une poignée de main à travers le tunnel. C'est le dernier vol d'Apollo jusqu'à la "
              "future station internationale."),
    ], conseil="cible Soyouz d'abord : le pilote sait faire le rendez-vous et l'amarrage tout "
               "seul (option « Aides »).", genre="mission", annee=1975),

    Scenario("voyager2", "Voyager 2", "Le grand tour des géantes",
             _depart_pas_de_tir("Voyager 2", VOYAGER), [
        Etape("Août 1977. Voyager 2 s'envole pour le « grand tour » : les quatre géantes sont "
              "alignées comme une fois tous les 176 ans, et ses réservoirs pleins d'atome vont "
              "en profiter. À toi de la mettre sur sa route."),
        Etape("Décolle et mets Voyager 2 en orbite : périapside au-dessus de 8 km. "
              "[[Besoin d'aide ? {PILOTE}, puis « Mise en orbite ».|]]",
              lambda t, sc: _pe(sc.u) > 8000 and sc.u.actif.gaz == 0.0),
        Etape("Cible Jupiter (dézoome, puis {TAPER} dessus), planifie le transfert et exécute-le : "
              "il faut entrer dans sa sphère d'influence. [[Dézoome, {TAPER} sur Jupiter, puis "
              "{PILOTE} : « Transfert vers Jupiter », et « Exécuter la manœuvre ». Le voyage dure "
              "des mois : accélère le temps !|Dézoome, tape sur Jupiter pour la cibler, pose un "
              "nœud qui allonge ton orbite jusqu'à elle, puis exécute-le.]]",
              lambda t, sc: sc.u.actif is not None and "soi:Jupiter" in sc.u.actif.drapeaux),
        Etape("Voyager 2 survole Jupiter en 1979, Saturne en 1981, Uranus en 1986, Neptune en "
              "1989 : la seule sonde à avoir vu les quatre. Aujourd'hui elle flotte dans "
              "l'espace interstellaire, et elle parle encore."),
    ], conseil="mise en orbite, puis cible Jupiter et laisse le pilote planifier le transfert ; "
               "le plus dur est de penser à accélérer le temps.", genre="mission", annee=1977),

    Scenario("cassini", "Cassini-Huygens", "L'orbiteur et l'atterrisseur de Saturne",
             _depart_cassini, [
        Etape("Octobre 1997. Cassini-Huygens quitte la Terre pour Saturne : l'orbiteur de la "
              "NASA porte Huygens, l'atterrisseur européen destiné à Titan. Voilà la sonde en "
              "orbite d'attente, réservoirs pleins : plus qu'à viser juste."),
        Etape("Quitte l'orbite terrestre : cible Saturne ({TAPER} dessus), planifie le transfert "
              "et exécute-le. [[{TAPER} sur Saturne, puis {PILOTE} : « Transfert vers Saturne », "
              "et « Exécuter la manœuvre ». La fenêtre de tir peut être dans plusieurs jours : "
              "accélère le temps !|Tape sur Saturne pour la cibler, pose un nœud d'évasion vers "
              "elle, puis exécute-le.]]",
              lambda t, sc: sc.u.actif is not None and "soi:Saturne" in sc.u.actif.drapeaux),
        Etape("Voilà Saturne et ses anneaux. Freine pour rester en orbite : périapside "
              "au-dessus des nuages. [[SAS RÉTRO, et pousse à la périapside jusqu'à ce que "
              "l'orbite se ferme.|SAS RÉTRO, et pousse à la périapside jusqu'à ce que l'orbite "
              "se ferme.]]",
              lambda t, sc: sc.u.actif is not None
              and _en_orbite(sc.u.actif, sc.u.par_nom["Saturne"], 2000)),
        Etape("Le 1ᵉʳ juillet 2004, Cassini s'insère en orbite de Saturne. Le 25 décembre, "
              "Huygens se détache ; le 14 janvier 2005, il se pose sur Titan : première pose "
              "en douceur dans la lointaine périphérie du système solaire."),
    ], conseil="cible Saturne dès le départ ; à l'arrivée, freine à la périapside en SAS RÉTRO "
               "jusqu'à ce que l'orbite se ferme.", genre="mission", annee=1997),
]

for _m in MISSIONS:
    PAR_ID[_m.ident] = _m
