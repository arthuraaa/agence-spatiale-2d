# -*- coding: utf-8 -*-
"""Le pilote automatique d'atterrissage (Aides) se pose tout seul, sur le terrain :
plusieurs longitudes lunaires, avec du relief sous le site.

    python tests/test_pilote_atterrissage.py
"""
import os
import sys
from math import atan2, cos, hypot, pi, sin, sqrt

RACINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, RACINE)
sys.path.insert(0, os.path.dirname(__file__))

from jeu import pilote, reglages
from jeu.orbite import Orbite
from jeu.univers import Univers
from jeu.vaisseau import construire

DT = 1.0 / 30.0


def atterrir(nom_corps, lon, plan):
    """Orbite basse au-dessus de la longitude lon, puis pilote d'atterrissage."""
    u = Univers(bac_a_sable=True)
    reglages.AIDES = True                       # lancer_pilote l'exige (on remet False à la fin)
    corps = next(c for c in u.corps if c.nom == nom_corps)
    v = construire("Sélène", plan, corps)
    v.corps = corps
    r = corps.R + 20_000.0                      # orbite ronde à 20 km
    ang = lon
    vit = sqrt(corps.mu / r)
    x, y = r * cos(ang), r * sin(ang)
    vx, vy = -vit * sin(ang), vit * cos(ang)
    v.x, v.y, v.vx, v.vy = x, y, vx, vy
    v.angle = atan2(vy, vx)
    v.mode = "rails"
    v.orbite = Orbite(x, y, vx, vy, corps.mu, u.t)
    u.vaisseaux.append(v)
    u.actif = v
    u.lancer_pilote(pilote.Atterrissage())
    for _ in range(60 * 1800):                  # 60 min de jeu au plus (30 im/s)
        u.avancer(DT)
        if v.mode == "pose" or v.detruit or u.pilote is None:
            break
    reglages.AIDES = False
    return u, v


def test_atterrissage_automatique():
    """Le pilote se pose en douceur, SUR le terrain, sur plusieurs corps et longitudes."""
    cas = [("Lune", lon, ["capsule", "decoupleur", "reservoir_l", "reservoir_l",
                          "train", "alize"]) for lon in (0.7, 2.0, 3.4, 4.8)]
    cas += [("Mercure", 2.2, ["capsule", "decoupleur", "reservoir_l", "reservoir_l",
                              "reservoir_l", "train", "mistral"])]
    # Terre : vrai lander (train au-dessus du moteur, comme le modèle Sélène) + boosters
    # latéraux : le pilote doit les larguer avant d'ouvrir le parachute
    cas += [("Terre", 2.2, ["capsule", "reservoir_m", "train", "moustique", "decoupleur",
                            "reservoir_l", "alize", "decoupleur",
                            ["reservoir_l", ["decoupleur_radial", "coiffe", "reservoir_l",
                                             "mistral"]],
                            "mistral"])]
    for corps, lon, plan in cas:
        u, v = atterrir(corps, lon, plan)
        assert v.mode == "pose" and not v.detruit, \
            "%s longitude %.1f : mode=%s detruit=%s messages=%s" % (
                corps, lon, v.mode, v.detruit, [m[0] for m in u.messages][-3:])
        assert "pose:" + corps in v.drapeaux, "posé sur " + corps
        alt = u.altitude(v) - v.geometrie().bas
        assert abs(alt) < 0.5, "reposé exactement sur le terrain (altitude %s)" % alt
        # vitesse surface-relative (le sol tourne sous le vaisseau, surtout sur Terre)
        w = v.corps.vitesse_rotation
        v_vert = hypot(v.vx + w * v.y, v.vy - w * v.x)
        assert v_vert < 15.0, "vitesse résiduelle faible après la pose"


if __name__ == "__main__":
    test_atterrissage_automatique()
    print("--- pilote d'atterrissage : OK")
