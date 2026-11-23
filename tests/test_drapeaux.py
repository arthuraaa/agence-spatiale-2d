# -*- coding: utf-8 -*-
"""Drapeaux plantés : pose, refus, plafond, sauvegarde, dessin.

    python tests/test_drapeaux.py
"""
import os
import sys
from math import cos, sin

RACINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, RACINE)
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
pygame.init()
pygame.display.set_mode((200, 100))           # requis par Surface.convert()

from jeu import rendu, sauvegarde
from jeu.rendu import Camera
from jeu.univers import Univers
from jeu.vaisseau import construire
from jeu.constantes import PLAFOND_DRAPEAUX


def vaisseau_pose(u, nom_corps="Lune", longitude=0.7):
    """Un vaisseau posé sur `nom_corps` à `longitude`, piloté."""
    v = construire("Pionnier", ["capsule"], u.par_nom[nom_corps])
    v.corps = u.par_nom[nom_corps]
    v.mode = "pose"
    v.longitude = longitude
    u.vaisseaux.append(v)
    u.actif = v
    return v


def test_plantation():
    """Posé : le drapeau est enregistré (corps + longitude) et marque le vaisseau."""
    u = Univers(bac_a_sable=True)
    v = vaisseau_pose(u)
    u.planter_drapeau()
    assert len(u.drapeaux_sol) == 1, "le drapeau doit être enregistré"
    d = u.drapeaux_sol[0]
    assert d["corps"] == "Lune" and abs(d["longitude"] - 0.7) < 1e-9
    assert "drapeau:Lune" in v.drapeaux, "le vaisseau doit garder la trace du drapeau"
    assert any("Drapeau planté" in m[0] for m in u.messages), "message attendu"
    # un second drapeau à une autre longitude : les deux restent
    v.longitude = 2.0
    u.planter_drapeau()
    assert len(u.drapeaux_sol) == 2


def test_refus():
    """En vol, ou sur un corps sans surface : refus propre, rien n'est planté."""
    u = Univers(bac_a_sable=True)
    v = vaisseau_pose(u)
    v.mode = "physique"                       # en vol : refus
    u.planter_drapeau()
    assert not u.drapeaux_sol and any("posé" in m[0] for m in u.messages)
    v.mode = "pose"
    v.corps = u.par_nom["Jupiter"]            # géante gazeuse : pas de surface
    u.planter_drapeau()
    assert not u.drapeaux_sol, "rien à planter sur Jupiter"
    assert any("pas de surface" in m[0] for m in u.messages)


def test_plafond():
    """PLAFOND_DRAPEAUX drapeaux par corps au plus : le suivant est refusé."""
    u = Univers(bac_a_sable=True)
    v = vaisseau_pose(u)
    for k in range(PLAFOND_DRAPEAUX):
        v.longitude = k * 0.1
        u.planter_drapeau()
    assert len(u.drapeaux_sol) == PLAFOND_DRAPEAUX
    v.longitude = 3.0
    u.planter_drapeau()
    assert len(u.drapeaux_sol) == PLAFOND_DRAPEAUX, "plafond dépassé"
    assert "Trop de drapeaux" in u.messages[-1][0], "message de refus attendu"
    # le plafond est par corps : sur la Terre, on peut encore planter
    v.corps = u.par_nom["Terre"]
    v.mode = "pose"
    v.longitude = 1.5
    u.planter_drapeau()
    assert sum(1 for d in u.drapeaux_sol if d["corps"] == "Terre") == 1


def test_sauvegarde():
    """Les drapeaux survivent à un aller-retour de sauvegarde (et aux vieilles sauvegardes)."""
    u = Univers(bac_a_sable=True)
    vaisseau_pose(u)
    u.planter_drapeau()
    u2 = sauvegarde.dict_vers_univers(sauvegarde.univers_vers_dict(u))
    assert u2.drapeaux_sol == u.drapeaux_sol, "drapeaux perdus à la sauvegarde"
    # une sauvegarde d'avant les drapeaux : liste vide, pas d'exception
    d = sauvegarde.univers_vers_dict(u)
    del d["drapeaux_sol"]
    u3 = sauvegarde.dict_vers_univers(d)
    assert u3.drapeaux_sol == []


def test_dessin():
    """Le drapeau se dessine (fanion rouge visible) en 4:3 et en 20:9."""
    for (l, h) in ((720, 540), (1200, 540)):
        u = Univers(bac_a_sable=True)
        vaisseau_pose(u)
        u.planter_drapeau()
        d = u.drapeaux_sol[0]
        c = u.par_nom["Lune"]
        ang = d["longitude"] + c.angle_rotation(u.t)
        bx, by = u.position_corps(c)
        r = c.R + c.relief(d["longitude"])
        cam = Camera()
        cam.taille(l, h)
        cam.zoom = 2.0
        cam.x, cam.y = bx + r * cos(ang), by + r * sin(ang)
        surf = pygame.Surface((l, h)).convert()
        surf.fill((0, 0, 0))
        rendu._drapeaux_sol(surf, u, cam)
        couleurs = {surf.get_at((x, y))[:3] for x in range(0, l, 3) for y in range(0, h, 3)}
        assert (215, 40, 35) in couleurs, "fanion rouge attendu à l'écran (%dx%d)" % (l, h)
        # zoom arrière : plus rien (le drapeau est trop petit pour être visible)
        cam.zoom = 0.01
        surf.fill((0, 0, 0))
        rendu._drapeaux_sol(surf, u, cam)
        couleurs = {surf.get_at((x, y))[:3] for x in range(0, l, 3) for y in range(0, h, 3)}
        assert (215, 40, 35) not in couleurs, "drapeau visible même dézoomé"


if __name__ == "__main__":
    test_plantation()
    test_refus()
    test_plafond()
    test_sauvegarde()
    test_dessin()
    print("--- drapeaux : OK")
