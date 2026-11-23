# -*- coding: utf-8 -*-
"""Les six nouvelles missions de carrière : conditions de réussite exactes.

    python tests/test_missions_nouvelles.py
"""
import os
import sys
from math import sqrt

RACINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, RACINE)
sys.path.insert(0, os.path.dirname(__file__))

from jeu.orbite import Orbite
from jeu.univers import Univers
from jeu import missions
from jeu.vaisseau import construire

IDENTS = ("station_lunaire", "echantillons", "satellite_mars",
          "io_europe", "venus_sol", "europe_sol")


def univers_():
    return Univers(bac_a_sable=True)


def sur_orbite(u, v, corps, alt=60_000.0):
    """Téléporte le vaisseau sur une orbite ronde autour de `corps`, sur rails."""
    v.corps = corps
    r = corps.R + alt
    vit = sqrt(corps.mu / r)
    v.x, v.y, v.vx, v.vy = r, 0.0, 0.0, vit
    v.mode = "rails"
    v.gaz = 0.0
    v.orbite = Orbite(v.x, v.y, v.vx, v.vy, corps.mu, u.t)
    v.cache_etat = (None, None)
    u._predire(v)
    return v


def mission(ident):
    return next(m for m in missions.MISSIONS if m.ident == ident)


def test_identites_et_ordre():
    """Les six missions existent, avec des primes croissantes à la fin de la liste."""
    for ident in IDENTS:
        mission(ident)
    primes = [m.prime for m in missions.MISSIONS]
    nouvelles = primes[-len(IDENTS):]
    assert nouvelles == sorted(nouvelles), "primes des nouvelles missions non triées : %s" % nouvelles


def test_station_lunaire():
    """Un amarrage en orbite lunaire compte ; ni en orbite terrestre, ni sans amarre."""
    u = univers_()
    a = construire("A", ["port", "capsule", "reservoir_s"], u.par_nom["Lune"])
    a.corps = u.par_nom["Lune"]
    u.vaisseaux.append(a)
    u.actif = a
    a.drapeaux.add("amarre:Voyage")
    sur_orbite(u, a, u.par_nom["Lune"])
    assert mission("station_lunaire").test(u, a), "amarrage en orbite lunaire refusé"
    # en orbite terrestre : non
    sur_orbite(u, a, u.par_nom["Terre"])
    assert not mission("station_lunaire").test(u, a)
    # en orbite lunaire mais sans amarre : non
    a.drapeaux.discard("amarre:Voyage")
    sur_orbite(u, a, u.par_nom["Lune"])
    assert not mission("station_lunaire").test(u, a)


def test_echantillons():
    """Posé sur Terre avec pose:Lune ET drapeau:Lune ; sans le drapeau, non."""
    u = univers_()
    v = construire("Capsule", ["capsule"], u.terre)
    v.corps = u.terre
    v.mode = "pose"
    v.longitude = 0.0
    u.vaisseaux.append(v)
    u.actif = v
    m = mission("echantillons")
    assert not m.test(u, v), "rien ne justifie encore les échantillons"
    v.drapeaux.add("pose:Lune")
    assert not m.test(u, v), "sans drapeau planté, pas d'échantillons"
    v.drapeaux.add("drapeau:Lune")
    assert m.test(u, v), "posé sur Terre avec pose:Lune et drapeau:Lune : accepté"


def test_satellite_mars():
    """Une sonde + panneaux en orbite martienne haute compte (comme sur Terre)."""
    u = univers_()
    s = construire("Sonde", ["sonde", "panneaux"], u.par_nom["Mars"])
    s.corps = u.par_nom["Mars"]
    u.vaisseaux.append(s)
    u.actif = s
    m = mission("satellite_mars")
    sur_orbite(u, s, u.par_nom["Mars"], alt=20_000.0)
    assert not m.test(u, s), "orbite trop basse (30 km exigés)"
    sur_orbite(u, s, u.par_nom["Mars"], alt=40_000.0)
    assert m.test(u, s), "sonde + panneaux à 40 km : accepté"
    # le satellite terrestre existant marche toujours
    s2 = construire("Sonde2", ["sonde", "panneaux"], u.terre)
    s2.corps = u.terre
    u.vaisseaux.append(s2)
    sur_orbite(u, s2, u.terre, alt=40_000.0)
    assert any(True for _ in missions._satellites(u)), "satellite terrestre cassé"


def test_io_europe():
    """Io et Europe visités par le MÊME vaisseau (drapeaux soi: cumulés)."""
    u = univers_()
    v = construire("Voyage", ["sonde"], u.par_nom["Jupiter"])
    v.corps = u.par_nom["Jupiter"]
    u.vaisseaux.append(v)
    u.actif = v
    m = mission("io_europe")
    assert not m.test(u, v)
    v.drapeaux.add("soi:Io")
    assert not m.test(u, v), "Io seul ne suffit pas"
    v.drapeaux.add("soi:Europe")
    assert m.test(u, v), "Io + Europe : accepté"


def test_poses_venus_europe():
    """venus_sol et europe_sol se valident sur les drapeaux de pose."""
    u = univers_()
    v = construire("Atterrisseur", ["capsule"], u.par_nom["Vénus"])
    v.corps = u.par_nom["Vénus"]
    u.vaisseaux.append(v)
    u.actif = v
    assert not mission("venus_sol").test(u, v)
    v.drapeaux.add("pose:Vénus")
    assert mission("venus_sol").test(u, v)
    v.corps = u.par_nom["Europe"]
    v.drapeaux.add("pose:Europe")
    assert mission("europe_sol").test(u, v)


def test_verification_complete():
    """missions.verifier valide et paie sans exception pour les nouvelles missions."""
    u = univers_()
    v = construire("Atterrisseur", ["capsule"], u.par_nom["Europe"])
    v.corps = u.par_nom["Europe"]
    v.mode = "physique"
    u.vaisseaux.append(v)
    u.actif = v
    v.drapeaux.add("pose:Europe")
    missions.verifier(u)
    assert "europe_sol" in u.missions_faites
    missions.mission_suggeree(u)                    # ne doit pas lever


if __name__ == "__main__":
    test_identites_et_ordre()
    test_station_lunaire()
    test_echantillons()
    test_satellite_mars()
    test_io_europe()
    test_poses_venus_europe()
    test_verification_complete()
    print("--- missions nouvelles : OK")
