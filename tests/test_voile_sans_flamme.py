# -*- coding: utf-8 -*-
"""Le pilote d'atterrissage n'ouvre jamais le parachute dans la flamme : à
l'ouverture de la voile les gaz sont coupés, et sous voile le moteur ne rallume
que sous 300 m (l'aide de la dernière ligne droite). Le bug : la phase « freinage »
brûlait pendant TOUTE la descente sous voile — parachute déployé dans les flammes.

    python tests/test_voile_sans_flamme.py
"""
import os, sys
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from math import hypot

from jeu.univers import Univers
from jeu.vaisseau import construire
from jeu import pilote


def vaisseau_dans_lair(u, altitude, vitesse):
    """Capsule + réservoir + moteur, plongeant à `vitesse` (relative au sol)."""
    v = construire("Essai", ["capsule", "reservoir_m", "alize"], u.terre)
    c = u.terre
    v.corps = c
    lon = 0.0
    r = c.R + c.relief(lon) + altitude + v.geometrie().bas
    v.x, v.y = r, 0.0
    w = c.vitesse_rotation
    svx, svy = -vitesse, 0.0            # vitesse voulue : vers le bas local
    v.vx, v.vy = svx, svy + w * r        # (vitesse_surface : vx + w·y, vy − w·x)
    v.angle, v.omega = 1.5 * 3.14159, 0.0
    v.gaz = 1.0                          # le moteur brûle (phase freinage)
    v.mode = "physique"                  # état lu directement (x, y, vx, vy)
    v.troncons = []
    v.cache_etat = (None, None)
    u.vaisseaux.append(v)
    u.actif = v
    return v


def test_voile_sans_flamme():
    u = Univers(bac_a_sable=True)
    v = vaisseau_dans_lair(u, 4000.0, 240.0)     # dans l'air, freinage en cours
    prg = pilote.Atterrissage()
    prg.phase = "freinage"
    prg.piloter(u, v)
    assert v.parachute_ouvert(), "la voile devait s'ouvrir (240 m/s, dans l'air)"
    assert v.gaz == 0.0, "voile ouverte : les gaz doivent être coupés (pas de \
parachute déployé dans la flamme)"


def test_aide_sous_voile_gardee():
    u = Univers(bac_a_sable=True)
    v = vaisseau_dans_lair(u, 80.0, 15.0)        # tout près du sol, presque doux
    for p in v.parachutes():
        p.parachute = "ouvert"                   # voile déjà déployée
    prg = pilote.Atterrissage()
    prg.phase = "freinage"
    prg.piloter(u, v)
    assert v.gaz > 0.0, "sous 300 m, l'aide moteur sous voile doit rallumer"


if __name__ == "__main__":
    test_voile_sans_flamme()
    test_aide_sous_voile_gardee()
    print("--- voile sans flamme : OK")
