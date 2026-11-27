# -*- coding: utf-8 -*-
"""Rentrée atmosphérique : grondement du plasma, voile incandescent, caméra qui vibre.

    python tests/test_rentree.py
"""
import os
import sys

RACINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, RACINE)
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
pygame.init()
pygame.display.set_mode((200, 100))           # requis par Surface.convert()

from jeu import rendu, sons
from jeu.rendu import Camera
from jeu.univers import Univers


def test_son_rentree():
    """La boucle « rentree » existe et gronde vraiment (ni vide, ni muette)."""
    assert "rentree" in sons.BOUCLES and "rentree" in sons.RECETTES
    e = sons.RECETTES["rentree"]()
    assert len(e) > sons.FREQ, "la boucle doit durer plus d'une seconde"
    assert max(abs(v) for v in e) > 0.1


def test_halo_rentree():
    """L'écran rougeoye à grande vitesse dans l'air dense, pas à basse vitesse ni sur rails."""
    corps = type("Corps", (), {"atm_h": 70000.0, "densite": staticmethod(lambda a: 1.0),
                               "vitesse_rotation": 0.0})()
    v = type("Vaisseau", (), {"detruit": False, "mode": "physique", "corps": corps})()
    u = type("Univers", (), {})()
    u.actif = v
    u.altitude = lambda a: 30000.0
    u.etat = lambda a: (0.0, 0.0, 1500.0, 0.0)
    surf = pygame.Surface((200, 100)).convert()
    surf.fill((0, 0, 255))
    rendu._halo_rentree(surf, u)              # chaleur 1.0 : voile orange bien visible
    r, g, b = surf.get_at((100, 50))[:3]
    assert r > 100 and b < 255, "l'écran doit rougeoyer pendant la rentrée"
    u.etat = lambda a: (0.0, 0.0, 200.0, 0.0)   # chaleur 0.2 : sous le seuil
    surf.fill((0, 0, 255))
    rendu._halo_rentree(surf, u)
    assert surf.get_at((100, 50))[:3] == (0, 0, 255), "pas de voile à basse vitesse"
    u.etat = lambda a: (0.0, 0.0, 3000.0, 0.0)
    v.mode = "rails"                          # sur rails : pas encore de plasma
    surf.fill((0, 0, 255))
    rendu._halo_rentree(surf, u)
    assert surf.get_at((100, 50))[:3] == (0, 0, 255), "pas de voile hors mode physique"


def test_chaleur_visible_au_freinage_carriere():
    """Recalibrage : le plasma doit apparaître pendant le freinage atmosphérique
    d'une rentrée de carrière (5 km à 736 m/s sur Terre), rester sous la voile,
    ne rien montrer au décollage (1 km à 200 m/s) ni sous la voile ouverte,
    et embraser tout l'écran sur une rentrée raide (2 km à 900 m/s)."""
    u = Univers(bac_a_sable=True)
    t = u.terre
    frein = rendu.chaleur_rentree(t.densite(5000.0), 736.0)
    assert frein >= 0.05, "plasma invisible au freinage de la rentrée carrière"
    assert frein < 0.25, "pas encore de voile orange au freinage normal"
    assert rendu.chaleur_rentree(t.densite(1000.0), 200.0) == 0.0, "rien au décollage"
    assert rendu.chaleur_rentree(t.densite(3000.0), 12.0) == 0.0, "rien sous la voile"
    assert rendu.chaleur_rentree(t.densite(2000.0), 900.0) >= 0.25, "voile en rentrée raide"


def test_tremblement():
    """La caméra vibre d'une frame à l'autre pendant la rentrée, et se tait ensuite."""
    u = Univers(bac_a_sable=True)
    cam = Camera()
    cam.taille(200, 100)
    cam.tremble = 1.0
    cam.suivre(u, 1.0 / 60.0)
    assert abs(cam._jx) <= 3.0 and abs(cam._jy) <= 3.0, "vibration de quelques pixels au plus"
    x0, y0 = cam.vers_ecran(0.0, 0.0)
    cam.suivre(u, 1.0 / 60.0)                 # frame suivante : la vibration est re-tirée
    x1, y1 = cam.vers_ecran(0.0, 0.0)
    assert (x0, y0) != (x1, y1), "la vibration doit changer d'une frame à l'autre"
    cam.tremble = 0.0
    cam.suivre(u, 1.0 / 60.0)
    assert cam.vers_ecran(0.0, 0.0) == (100.0, 50.0), "vue immobile quand la chaleur retombe"


if __name__ == "__main__":
    test_son_rentree()
    test_chaleur_visible_au_freinage_carriere()
    test_halo_rentree()
    test_tremblement()
    print("--- rentree : OK")
