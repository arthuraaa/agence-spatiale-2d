# -*- coding: utf-8 -*-
"""Atterrissages : un joueur qui suit le panneau doit se poser, sans tourbillonner."""
import os, sys
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from math import hypot, atan2, degrees, radians
import main as jeu_main
from jeu import tutoriel, pilote, reglages
from jeu.orbite import angle_pi
DT = 1 / 60


def descente(ref=None, auto=False, regard=None):
    """Depuis l'orbite lunaire du tuto : désorbitation, chute, freinage au signal, descente douce."""
    app = jeu_main.Application(tactile=True)
    reglages.AIDES = True
    tutoriel.demarrer(app, "lune")
    app.tuto = None
    u = app.univers
    v, c = u.actif, u.actif.corps
    if auto:
        u.lancer_pilote(pilote.Atterrissage())
    else:
        v.ref_vitesse, v.sas = ref, "retro"
    phase, omega_max, k, dernier = "desorbite", 0.0, 0, None
    while v.mode != "pose" and not v.detruit and k < 60 * 60 * 30:
        x, y, vx, vy = u.etat(v)
        r = hypot(x, y)
        h = r - c.R - v.geometrie().bas
        w = c.vitesse_rotation
        svx, svy = vx + w * y, vy - w * x
        vv = (svx * x + svy * y) / r
        if h < 600:
            omega_max = max(omega_max, abs(v.omega))
            dernier = (vv, abs(-svx * y + svy * x) / r, degrees(abs(angle_pi(v.angle - atan2(y, x)))))
        if not auto:                                   # ce que fait un joueur qui suit le panneau
            if phase == "desorbite":
                v.gaz = 1.0
                if v.orbite is not None and v.orbite.rp < c.R - 3000:
                    v.gaz, phase = 0.0, "chute"
            elif phase == "chute":
                u.accel = 3 if h > 3000 else 0
                infos = dict((n, val) for n, val, _ in pilote.infos_atterrissage(u, v) or [])
                if infos.get("Freinage dans", 99) <= 0.5:
                    phase = "freinage"                 # « Freinage : MAINTENANT »
            elif phase == "freinage":
                u.accel, v.gaz = 0, 1.0
                if hypot(svx, svy) < 12.0 or vv > -3.0:
                    phase = "descente"
            else:
                v.gaz = max(0.0, min(1.0, 0.45 + 0.25 * (-max(2.0, h / 12.0) - vv)))
        if regard is not None:
            regard(u, v)
        u.avancer(DT)
        k += 1
    return u, v, omega_max, dernier


def test_joueur_se_pose():
    from jeu.hud import lignes_atterrissage
    vu = {}

    def regard(u, v):                                  # ce qu'affiche le panneau pendant la descente
        for nom, texte, couleur in lignes_atterrissage(u, v) or []:
            vu[nom] = texte
    for ref in ("surface", "orbite"):
        u, v, om, (vv, vh, incl) = descente(ref, regard=regard if ref == "surface" else None)
        print("   joueur (réf. %s) : %s, rotation max %.2f rad/s, au contact %.1f m/s vert., %.1f m/s horiz., %.0f°" % (
            ref, "posé" if v.mode == "pose" and not v.detruit else "ÉCRASÉ", om, -vv, vh, incl))
        assert v.mode == "pose" and not v.detruit, [m[0] for m in u.messages[-2:]]
        assert om < 0.3, "pas de tourbillon près du sol"
    print("   le panneau a affiché :", sorted(vu))
    assert "Vit. horizontale" in vu and vu.get("Inclinaison", "").endswith("°")


def test_pilote_se_pose():
    u, v, om, dernier = descente(auto=True)
    print("   pilote automatique :", [m[0] for m in u.messages[-1:]])
    assert v.mode == "pose" and not v.detruit and om < 0.3


def test_sas_redresse_pres_du_sol():
    """À 20 m du sol, même avec 30 m/s de vitesse horizontale, RÉTRO reste presque vertical."""
    app = jeu_main.Application(tactile=True)
    tutoriel.demarrer(app, "lune")
    u, v = app.univers, app.univers.actif
    c = v.corps
    r = c.R + v.geometrie().bas + 20.0
    v.mode, v.x, v.y = "physique", r, 0.0
    v.vx, v.vy = -2.0, 30.0 + c.vitesse_rotation * r      # 30 m/s sur le côté, par rapport au sol
    v.cache_etat = (None, None)
    v.ref_vitesse, v.sas = "surface", "retro"
    ecart = degrees(abs(angle_pi(u.angle_sas(v) - atan2(v.y, v.x))))
    print("   RÉTRO à 20 m avec 30 m/s de dérive : %.1f° de la verticale" % ecart)
    assert ecart < 16.0


def test_pilote_se_pose_sur_terre():
    """Retour Terre avec le Pionnier : orbite (scriptée comme test_vol), désorbitation,
    rentrée, parachute et atterrissage automatique. Le pilote ne doit brûler que la
    désorbitation : sans parachute il épuisait tout le carburant en plein vol (bug)."""
    import test_vol
    app = jeu_main.Application(tactile=True)
    reglages.AIDES = True
    app.nouvelle_partie(True)
    app.scene.charger_modele(0)
    app.scene.lancer()
    u, sc = app.univers, app.scene
    v = u.actif
    v.gaz = 1.0
    for _ in range(60 * 14):                           # décollage vertical puis basculement
        x, y, vx, vy = u.etat(v)
        if u.altitude(v) > 250:
            v.sas = "off"; v.angle = atan2(y, x) + 0.5; v.omega = 0
        sc.maj(DT)
    test_vol.mise_en_orbite(u, v)
    u.accel = 0
    u.lancer_pilote(pilote.Atterrissage())
    k = 0
    voile = False
    while (v.mode != "pose" and not v.detruit and u.pilote is not None
           and k < 60 * 60 * 40):
        u.avancer(DT)
        voile = voile or v.parachute_ouvert()
        k += 1
    fin = [m[0] for m in u.messages[-2:]]
    assert v.mode == "pose" and not v.detruit, fin
    print("   retour Terre automatique : posé, %.0f kg de carburant restants" % (
        sum(p.carburant for p in v.pieces)))
    # la voile doit servir : depuis une rentrée rasante, l'air seul ne l'y amène
    # pas — le pilote freine au moteur dans l'air mince jusqu'à sa vitesse
    # d'ouverture (sinon voile trop tard, impact à 146 m/s de dérive sur le relief).
    assert voile, "le pilote doit utiliser le parachute"


def en_orbite(u, nom_corps, moteur="moustique"):
    """Une capsule « Sélène » (moteur au choix) en orbite basse autour du corps donné."""
    from math import sqrt
    from jeu.univers import Orbite
    c = u.par_nom[nom_corps]
    v = u.lancer("Essai", ["capsule", "reservoir_m", "train", moteur])
    r = c.R + c.atm_h + 5000.0
    v.corps, v.mode = c, "rails"
    v.x, v.y = r, 0.0
    v.vx, v.vy = 0.0, sqrt(c.mu / r)
    v.angle, v.omega, v.gaz = 0.0, 0.0, 0.0
    v.orbite = Orbite(v.x, v.y, v.vx, v.vy, c.mu, u.t)
    v.troncons = []
    v.cache_etat = (None, None)
    u._predire(v)
    u.actif = v
    return v


def test_pilote_refuse_mars():
    """Le moustique (TWR 1,2 sur Mars) ne peut pas s'y poser : le pilote doit refuser
    proprement, sans gaspiller le carburant en freinage voué à l'échec (bug)."""
    app = jeu_main.Application(tactile=True)
    reglages.AIDES = True
    app.nouvelle_partie(True)
    u = app.univers
    v = en_orbite(u, "Mars")
    u.lancer_pilote(pilote.Atterrissage())
    k = 0
    while v.mode != "pose" and not v.detruit and u.pilote is not None and k < 60 * 60 * 60:
        u.avancer(DT)
        k += 1
    carbu = sum(p.carburant for p in v.pieces)
    print("   Mars : pilote arrêté, %.0f kg de carburant intacts, %s" % (
        carbu, [m[0] for m in u.messages[-1:]]))
    assert not v.detruit and v.mode != "pose", [m[0] for m in u.messages[-2:]]
    assert u.pilote is None, "le pilote doit renoncer"
    assert carbu > 1500, "le pilote a brûlé du carburant pour rien"


def test_retour_avec_train_accepte():
    """Étage de retour lunaire avec train (voile ~8,7 m/s, entre la limite sans train
    8 m/s et celle avec train 14 m/s) : le pilote devait le refuser « moteur trop
    faible » car son seuil de voile ignorait le train. Le pilote désorbite lui-même,
    ouvre la voile et se pose."""
    app = jeu_main.Application(tactile=True)
    reglages.AIDES = True
    app.nouvelle_partie(True)
    u = app.univers
    v = en_orbite(u, "Terre")
    v.pieces[1].carburant = 1400.0      # un retour lunaire a déjà brûlé une partie du réservoir
    v.cache_etat = (None, None)
    from math import sqrt
    c = u.terre
    vt = sqrt(2.0 * v.masse() * c.mu / (c.R * c.R) / (c.rho0 * 700.0))
    print("   voile de l'étage de retour : %.1f m/s (train : %s)" % (vt, v.a_un_train()))
    assert 8.0 < vt < 14.0, "l'étage doit être entre les deux limites pour ce test"
    u.lancer_pilote(pilote.Atterrissage())
    k = 0
    while v.mode != "pose" and not v.detruit and k < 60 * 60 * 60:
        u.avancer(DT)
        k += 1
    assert not any("moteur trop faible" in m[0] for m in u.messages), [m[0] for m in u.messages[-2:]]
    print("   posé :", [m[0] for m in u.messages[-1:]])
    assert v.mode == "pose" and not v.detruit, [m[0] for m in u.messages[-2:]]


def test_attente_dans_le_vide():
    """Entrée rasante au-dessus de l'atmosphère, trop vite pour ouvrir la voile
    (250 m/s) et moteur plus faible que la gravité : l'air n'amènerait la voile à
    sa vitesse d'ouverture qu'au ras du relief (le verdict le refuse désormais) —
    le pilote doit RAIDIR la rentrée (désorbitation raide, freinage borné dans le
    vide) et se poser. Il ne fallait ni fondre passivement jusqu'à l'écrasement,
    ni brûler sans fin hors désorbitation (ancien bug : plein gaz dans le vide)."""
    app = jeu_main.Application(tactile=True)
    reglages.AIDES = True
    app.nouvelle_partie(True)
    u = app.univers
    v = en_orbite(u, "Terre")
    v.pieces[1].carburant = 700.0        # léger : l'air seul amène la voile à 250 m/s
    from math import sqrt
    from jeu.univers import Orbite
    c = u.terre
    r = c.R + 12_000.0                   # 5 km au-dessus de l'atmosphère
    v.mode = "rails"
    v.x, v.y = r, 0.0
    # sous la vitesse circulaire et un peu tombant : entrée rasante (comme après
    # une désorbitation), vitesse ~690 m/s, moteur incapable d'arrêter la chute
    v.vx, v.vy = -100.0, 0.94 * sqrt(c.mu / r)
    v.angle, v.omega, v.gaz = 0.0, 0.0, 0.0
    v.orbite = Orbite(v.x, v.y, v.vx, v.vy, c.mu, u.t)
    v.troncons = []
    v.cache_etat = (None, None)
    u._predire(v)
    u.lancer_pilote(pilote.Atterrissage())
    brule_vide = False
    for k in range(60 * 1200):
        u.avancer(DT)
        if u.pilote is None:
            break
        assert v.detruit is False
        if u.altitude(v) > c.atm_h and getattr(u.pilote, "phase", "?") == "chute" \
                and v.gaz > 0.0:
            brule_vide = True            # le frein « brute » ne brûle que dans l'air
    assert not brule_vide, "gaz en phase « chute » au-dessus de l'atmosphère"
    print("   rentrée raidie puis posée :", [m[0] for m in u.messages[-1:]])
    assert v.mode == "pose" and not v.detruit, [m[0] for m in u.messages[-2:]]
    assert not any("moteur trop faible" in m[0] for m in u.messages)


def test_desorbite_haut_dans_le_ciel():
    """Rentrée lunaire haut dans le ciel (4200 km, près de l'apoapside, trajectoire
    rasant la planète) : la désorbitation doit se faire par rapport à l'ORBITE. Le
    pilote utilisait le « rétro surface » réglé pour l'atterrissage — direction qui
    dépend de la rotation de la planète et qui, là haut, ne veut plus rien dire :
    il poussait à côté, l'orbite s'échappait et tout le carburant partait pour rien."""
    app = jeu_main.Application(tactile=True)
    reglages.AIDES = True
    app.nouvelle_partie(True)
    u = app.univers
    # Alizé (TWR > 1) : assez fort pour être accepté par le pilote — le moustique
    # (TWR 0,55) est refusé d'entrée « moteur trop faible » et le test serait vide.
    v = en_orbite(u, "Terre", moteur="alize")
    from math import sqrt
    from jeu.univers import Orbite
    c = u.terre
    r = c.R + 4_200_000.0
    # près de l'apoapside d'une orbite qui rase la planète (rp à ~44 km d'altitude,
    # donc sans toucher le sol ni l'atmosphère) : vitesse tangentielle dérisoire
    a = (r + c.R + 44_000.0) / 2.0
    vt = sqrt(c.mu * (2.0 / r - 1.0 / a))
    v.mode = "rails"
    v.x, v.y = r, 0.0
    v.vx, v.vy = 2.0, vt                 # un peu montante : v_vert > 0
    v.angle = atan2(v.vy, v.vx)
    v.omega = v.gaz = 0.0
    v.orbite = Orbite(v.x, v.y, v.vx, v.vy, c.mu, u.t)
    v.troncons = []
    v.cache_etat = (None, None)
    u._predire(v)
    o = v.orbite
    print("   apoapside à %.0f km, rp à %.0f km d'altitude" % ((o.ra - c.R) / 1e3, (o.rp - c.R) / 1e3))
    assert o.elliptique and 0.0 < o.rp - c.R < c.atm_h + 60_000.0
    u.lancer_pilote(pilote.Atterrissage())
    rp_min = v.orbite.rp
    for _ in range(60 * 120):                        # deux minutes : il n'en faut pas plus
        u.avancer(DT)
        if u.pilote is None or v.mode == "pose" or v.detruit:
            break
        if v.orbite is not None:
            rp_min = min(rp_min, v.orbite.rp)
    o = v.orbite
    carb = sum(p.carburant for p in v.pieces)
    print("   après 2 min : carburant %.0f kg, rp mini à %.0f km d'altitude, orbite %s" % (
        carb, (rp_min - c.R) / 1e3,
        "échappée" if not o.elliptique else "rp à %.0f km" % ((o.rp - c.R) / 1e3)))
    assert o.elliptique, "l'orbite s'est échappée : la poussée allait dans le mauvais sens"
    # le pilote a bien désorbité (rp passé SOUS la surface) : la désorbitation se fait
    # par rapport à l'orbite. Depuis cette apoapside de 4 200 km, la rentrée est ensuite
    # jugée condamnée et le pilote remonte le périapside (abandon honnête) — le rp
    # final peut donc être remonté, seul le rp MINI prouve la mise à feu.
    assert rp_min < c.R, "le rp n'a pas baissé : le pilote n'a jamais désorbité (test vide)"
    assert carb > 1800.0, "désorbitation de %.0f m/s : %.0f kg brûlés pour rien" % (
        2000.0 - carb, 2000.0 - carb)


def test_pilote_se_pose_sur_titan():
    """Sur Titan l'atmosphère est si dense que le parachute se pose tout seul,
    sans un gramme de carburant (le pilote n'avait pas le droit d'y voir un obstacle)."""
    app = jeu_main.Application(tactile=True)
    reglages.AIDES = True
    app.nouvelle_partie(True)
    u = app.univers
    v = en_orbite(u, "Titan")
    u.lancer_pilote(pilote.Atterrissage())
    k = 0
    while v.mode != "pose" and not v.detruit and u.pilote is not None and k < 60 * 60 * 300:
        u.avancer(DT)
        k += 1
    print("   Titan :", [m[0] for m in u.messages[-1:]])
    assert v.mode == "pose" and not v.detruit, [m[0] for m in u.messages[-2:]]


if __name__ == "__main__":
    test_sas_redresse_pres_du_sol()
    test_joueur_se_pose()
    test_pilote_se_pose()
    test_pilote_se_pose_sur_terre()
    test_pilote_refuse_mars()
    test_retour_avec_train_accepte()
    test_attente_dans_le_vide()
    test_desorbite_haut_dans_le_ciel()
    test_pilote_se_pose_sur_titan()
    print("--- atterrissage : OK")
