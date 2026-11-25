# -*- coding: utf-8 -*-
"""Le verdict de l'atterrissage automatique doit être consulté AVANT d'agir :

1. à sec, voile pliée : le verdict juge la rentrée AVANT d'ouvrir la voile.
   (bug « Retour au bercail » : la voile s'ouvrait avant le jugement, le bloc
   « plus de poussée » rendait la main à chaque image, et la capsule s'écrasait
   à sa vitesse terminale en silence — jamais de message de refus) ;
2. rentrée rasante rapide : « tenir face à la gravité » ne suffit pas, il faut
   pouvoir TUER la vitesse actuelle avant le sol (capture du 25/11 : 675 m/s à
   2,8 km — le pilote fonçait, GAZ à 0 %, « Freinage dans MAINTENANT ») ;
3. à sec avec dérive : le verdict peut séparer l'étage mort et poser la capsule
   (vol d'ombre, pose à moins de 8 m/s).

    python tests/test_pilote_verdicts.py
"""
import math
import os
import sys

RACINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, RACINE)
sys.path.insert(0, os.path.dirname(__file__))

import pygame
pygame.display.init()
pygame.display.set_mode((1, 1))

import main as jeu_main
from jeu import pilote, reglages
from jeu.orbite import Orbite
from jeu.pieces import MODELES as MOD

DT = 1.0 / 60.0


def pionnier(u_t, alt, v_tan, v_rad, a_sec):
    """Un Pionnier placé sur une trajectoire donnée (vitesse tangent/radial),
    avec prédiction ; renvoie (u, v, sc)."""
    app = jeu_main.Application(tactile=True)
    reglages.AIDES = True
    app.nouvelle_partie(True)
    app.scene.charger_modele([m[0] for m in MOD].index("Pionnier"))
    app.scene.lancer()
    u, sc = app.univers, app.scene
    v = u.actif
    c = u.terre
    if a_sec:
        for p in v.pieces:
            p.carburant = 0.0
    theta = math.radians(30.0)
    ux, uy = math.cos(theta), math.sin(theta)
    tx, ty = -uy, ux
    r = c.R + alt
    v.mode = "physique"
    v.x, v.y = r * ux, r * uy
    v.vx = v_tan * tx + v_rad * ux
    v.vy = v_tan * ty + v_rad * uy
    v.angle = math.atan2(v.y, v.x) + 0.5
    v.omega = 0.0
    v.gaz = 0.0
    v.orbite = Orbite(v.x, v.y, v.vx, v.vy, c.mu, u_t)
    v.troncons = []
    v.cache_etat = (None, None)
    u._predire(v)
    return u, v, sc


def piloter_jusquau_verdict(u, v, sc, limite_s=300.0):
    """Lance l'atterrissage auto et joue jusqu'à la fin du pilote (verdict rendu,
    pose ou destruction). Renvoie (fini, messages)."""
    u.accel = 0
    u.lancer_pilote(pilote.Atterrissage())
    msgs = []
    t = 0.0
    while u.pilote is not None and not v.detruit and v.mode != "pose" and t < limite_s:
        sc.maj(DT)
        t += DT
        for m in u.messages:
            if m[0] not in msgs:
                msgs.append(m[0])
    if v.mode == "pose":
        # la boucle sort à l'image de la pose, une image avant le détachement
        for _ in range(5):
            sc.maj(DT)
    return u.pilote is None, msgs


def test_verdict_consulte_a_sec():
    """À sec sur une retombée plane condamnée (état de la capture du bug) :
    refus honnête, voile jamais ouverte, vaisseau intact, main rendue."""
    u, v, sc = pionnier(0.0, 727.0, 541.9, -67.9, a_sec=True)
    fini, msgs = piloter_jusquau_verdict(u, v, sc)
    print("   à sec 727 m :", "refus" if fini else "??", msgs[-2:])
    assert fini, "le pilote n'a jamais rendu la main"
    assert not v.detruit, "vaisseau détruit malgré le refus"
    assert not v.parachute_ouvert(), "voile ouverte sans verdict favorable"
    assert any("moteur trop faible" in m for m in msgs), msgs


def test_refus_rentee_rasante_rapide():
    """Avec du carburant mais 675 m/s de dérive à 2,8 km du sol : la distance
    d'arrêt dépasse l'altitude — refus immédiat, jamais le fonçage silencieux."""
    u, v, sc = pionnier(0.0, 2766.0, 675.0, -140.0, a_sec=False)
    fini, msgs = piloter_jusquau_verdict(u, v, sc)
    print("   rasante 675 m/s :", "refus" if fini else "??", msgs[-2:])
    assert fini, "le pilote n'a jamais rendu la main"
    assert not v.detruit, "vaisseau détruit malgré le refus"
    assert any("moteur trop faible" in m for m in msgs), msgs


def test_etage_puis_pose_a_sec():
    """À sec depuis 6 km avec de la dérive : le verdict découvre que la capsule
    seule (voile) se pose, sépare l'étage mort et POSE le vaisseau."""
    u, v, sc = pionnier(0.0, 6000.0, 100.0, -200.0, a_sec=True)
    fini, msgs = piloter_jusquau_verdict(u, v, sc, limite_s=600.0)
    print("   à sec 6 km :", "posé" if v.mode == "pose" else msgs[-2:])
    assert fini and v.mode == "pose" and not v.detruit, msgs
    # la séparation passe par le largage standard (« Séparation de l'étage »)
    assert any("séparation de l'étage" in m.lower() for m in msgs), msgs


def test_etage_refuse_sur_orbite_stable():
    """Sur une orbite stable avec du carburant, la config APRÈS étage (capsule nue,
    sans moteur ni poussée) ne peut pas rejoindre l'état « après désorbitation »
    que le verdict juge : la séparation doit être refusée. (bug : « séparation de
    l'étage avant la pose » suivi aussitôt de « plus de carburant pour se poser » —
    l'étage accepté avait jugé un état inaccessible sans moteur)."""
    u, v, sc = pionnier(0.0, 21300.0, 684.4, 0.0, a_sec=False)   # orbite circulaire
    prg = pilote.Atterrissage()
    c = v.corps
    etat = pilote.etat_apres_desorbitation(c, c.R + 21300.0)
    assert not prg.etage_apres_posable(v, c, etat, u.t, chute_directe=False), \
        "étage accepté alors que la config post-étage n'a aucune poussée"


if __name__ == "__main__":
    test_verdict_consulte_a_sec()
    test_refus_rentee_rasante_rapide()
    test_etage_puis_pose_a_sec()
    test_etage_refuse_sur_orbite_stable()
    print("--- verdicts du pilote : OK")
