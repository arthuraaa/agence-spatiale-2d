# -*- coding: utf-8 -*-
"""Relief du terrain : hauteurs déterministes, pose sur une colline, altitude affichée,
silhouette dessinée. Le pas de tir reste plat.

    python tests/test_relief.py
"""
import os
import sys
from math import cos, hypot, sin

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

RACINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, RACINE)
sys.path.insert(0, os.path.dirname(__file__))

from jeu.constantes import LONGITUDE_PAS_DE_TIR
from jeu.orbite import angle_pi
from jeu.corps import creer_systeme_solaire
from jeu.rendu import _terrain_relief, _decor_sol
from jeu.univers import Univers
from jeu.vaisseau import Vaisseau, pieces_depuis_plan

DT = 1.0 / 30.0


def test_deterministe():
    """Le relief ne dépend que du nom du corps : les mêmes collines à chaque partie."""
    liste, par_nom = creer_systeme_solaire()
    terre = par_nom["Terre"]
    assert terre.relief_max > 0.0
    for lon in range(720):
        h = terre.relief(lon / 720.0 * 6.283)
        assert 0.0 <= h <= terre.relief_max, "le relief reste entre 0 et relief_max"
    assert par_nom["Soleil"].relief_max == 0.0 and par_nom["Soleil"].relief(1.0) == 0.0, \
        "pas de relief sur une étoile"
    _, encore = creer_systeme_solaire()              # reconstruit : mêmes hauteurs
    for c in encore.values():
        for lon in (0.1, 1.0, 2.5, 4.0):
            assert abs(c.relief(lon) - par_nom[c.nom].relief(lon)) < 1e-9
    assert terre.relief(LONGITUDE_PAS_DE_TIR) == 0.0, "le pas de tir est plat"


def test_pose_et_altitude():
    """Un vaisseau posé repose sur le terrain : altitude() = hauteur du bas au-dessus du sol."""
    u = Univers(bac_a_sable=True)
    terre = u.terre
    lon = 2.0                                        # loin du pas de tir
    assert terre.relief(lon) > 1.0, "il y a du relief à cette longitude"
    v = Vaisseau("Sonde", pieces_depuis_plan(["capsule"], "S"), terre)
    v.mode = "pose"
    v.longitude = lon
    v.cache_etat = (None, None)
    bas = v.geometrie().bas
    e = u.etat(v)
    attendu = terre.R + terre.relief(lon) + bas
    assert abs(hypot(e[0], e[1]) - attendu) < 1e-6, "posé au sommet du terrain"
    assert abs(u.altitude(v) - bas) < 1e-6, "altitude() mesure au-dessus du terrain"


def test_contact_sur_une_coline():
    """Une descente molle touche le sol au niveau du terrain, pas au niveau de la sphère."""
    u = Univers(bac_a_sable=True)
    terre = u.terre
    lon = 2.0
    v = Vaisseau("Module Lunaire", pieces_depuis_plan(
        ["capsule", "reservoir_m", "train", "moustique"], "M"), terre)
    bas = v.geometrie().bas
    ang = lon + terre.angle_rotation(u.t)
    r = terre.R + terre.relief(lon) + bas + 3.0      # 3 m au-dessus du sol (vitesse d'impact ~9 m/s)
    v.mode = "physique"
    v.x, v.y = r * cos(ang), r * sin(ang)
    w = terre.vitesse_rotation
    v.vx, v.vy = -w * v.y, w * v.x                   # vitesse du sol (descente sans dérive)
    v.angle = ang
    u.vaisseaux.append(v)
    u.actif = v
    for _ in range(300):
        u.avancer(DT)
        if v.mode == "pose" or v.detruit:
            break
    assert v.mode == "pose" and not v.detruit, "posé sur la colline"
    assert abs(angle_pi(v.longitude - lon)) < 1e-6, "resté à la longitude visée"
    assert abs(u.altitude(v) - bas) < 0.5, "reposé à la hauteur du terrain"


def test_silhouette_dessinee():
    """La silhouette du terrain se dessine et remplit le bas de l'écran."""
    import pygame
    pygame.init()
    _, par_nom = creer_systeme_solaire()
    terre = par_nom["Terre"]
    surf = pygame.Surface((400, 300))
    surf.fill((0, 0, 0))
    cam = type("Cam", (), {"x": 0.0, "y": -(terre.R + 100.0), "zoom": 0.05,
                           "l": 400, "h": 300})()
    cam.vers_ecran = lambda x, y: (200.0 + (x - cam.x) * cam.zoom,
                                   150.0 - (y - cam.y) * cam.zoom)
    u = type("U", (), {"t": 0.0,
                       "position_corps": staticmethod(lambda c: (0.0, 0.0))})()
    coul = (120, 120, 120)
    _terrain_relief(surf, u, cam, terre, 0.0, 0.0, coul)
    assert surf.get_at((200, 175))[:3] == coul, "le sol bosselé est dessiné sous la caméra"
    _decor_sol(surf, u, cam, terre, (60, 60, 60))    # cailloux posés sur le terrain : rien ne plante


if __name__ == "__main__":
    test_deterministe()
    test_pose_et_altitude()
    test_contact_sur_une_coline()
    test_silhouette_dessinee()
    print("--- relief : OK")
