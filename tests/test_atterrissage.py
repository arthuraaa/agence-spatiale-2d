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
    while v.mode != "pose" and not v.detruit and k < 60 * 60 * 40:
        u.avancer(DT)
        k += 1
    assert v.mode == "pose" and not v.detruit, [m[0] for m in u.messages[-2:]]
    print("   retour Terre automatique : posé, %.0f kg de carburant restants" % (
        sum(p.carburant for p in v.pieces)))
    assert sum(p.carburant for p in v.pieces) > 200, "le pilote a trop brûlé : il doit utiliser le parachute"


if __name__ == "__main__":
    test_sas_redresse_pres_du_sol()
    test_joueur_se_pose()
    test_pilote_se_pose()
    test_pilote_se_pose_sur_terre()
    print("--- atterrissage : OK")
