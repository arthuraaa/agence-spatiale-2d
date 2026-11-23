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


def test_refus_sans_surface_ni_moteur():
    """Le pilote refuse proprement : géante gazeuse (pas de surface) et capsule sans
    moteur (rien pour se poser). Il ne doit ni engloutir le vaisseau ni boucler."""
    # Jupiter : le pilote s'arrête immédiatement, le vaisseau reste intact en orbite
    u, v = atterrir("Jupiter", 0.5, ["capsule", "decoupleur", "reservoir_l",
                                     "reservoir_l", "train", "mistral"])
    assert not v.detruit and v.mode != "pose", "Jupiter : le vaisseau doit rester en orbite"
    assert any("pas de surface" in m[0] for m in u.messages), \
        "message « pas de surface » attendu, messages=%s" % [m[0] for m in u.messages][-3:]
    # Lune : une capsule sans moteur ne peut pas se poser — message clair, pas de plantage
    reglages.AIDES = True
    u2 = Univers(bac_a_sable=True)
    corps = next(c for c in u2.corps if c.nom == "Lune")
    v2 = construire("Sélène", ["capsule", "reservoir_m", "train"], corps)
    r = corps.R + 5000.0
    v2.x, v2.y = r, 0.0
    v2.vx, v2.vy = 0.0, -30.0                   # chute lente au-dessus du sol
    v2.angle = -pi / 2
    v2.mode = "physique"
    u2.vaisseaux.append(v2)
    u2.actif = v2
    u2.lancer_pilote(pilote.Atterrissage())
    for _ in range(60 * 120):
        u2.avancer(DT)
        if u2.pilote is None:
            break
    reglages.AIDES = False
    assert u2.pilote is None, "le pilote doit s'arrêter (aucun moteur)"
    assert any("aucun moteur" in m[0] for m in u2.messages), \
        "message « aucun moteur » attendu, messages=%s" % [m[0] for m in u2.messages][-3:]


def test_moteur_seul_sans_parachute():
    """Rentrée Terre sans voile (pièce « sonde ») : le pilote doit se poser au moteur.
    Sans planage (couper les gaz tant que la distance d'arrêt est confortable), le
    freinage continu en plein ciel brûlait tout le carburant en pertes de gravité."""
    u, v = atterrir("Terre", 2.2, ["sonde", "decoupleur", "reservoir_l", "reservoir_l",
                                   "train", "mistral"])
    assert v.mode == "pose" and not v.detruit, \
        "moteur seul : %s %s %s" % (v.mode, v.detruit, [m[0] for m in u.messages][-3:])
    assert sum(p.carburant for p in v.pieces) > 0.0, "carburant gaspillé en plein ciel"


if __name__ == "__main__":
    test_atterrissage_automatique()
    test_moteur_seul_sans_parachute()
    test_refus_sans_surface_ni_moteur()
    print("--- pilote d'atterrissage : OK")
