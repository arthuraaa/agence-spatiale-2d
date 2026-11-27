# -*- coding: utf-8 -*-
"""Foreuse (ISRU) : extraction de carburant du sol, monergol en prime, drapeau,
missions « Raffinerie lunaire » et « Ravitaillement spatial », jalon.

    python tests/test_forage.py
"""
import os
import sys
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

from jeu.univers import Univers
from jeu.vaisseau import construire
from jeu import missions, reglages

DT = 1.0 / 30.0


def pose_foreur(u, plan, corps_nom, longitude=0.7):
    """Un vaisseau posé sur `corps_nom`, réservoirs et monergol vidés, piloté."""
    v = construire("Foreur", plan, u.par_nom[corps_nom])
    v.mode = "pose"
    v.longitude = longitude
    u.vaisseaux.append(v)
    u.actif = v
    for p in v.pieces:
        p.carburant, p.mono = 0.0, 0.0
    return v


def test_taux_par_corps():
    """Les corps exploitables ont leur taux, les autres rien."""
    u = Univers(bac_a_sable=True)
    attendus = {"Lune": 3.0, "Mars": 4.0, "Mercure": 3.0, "Titan": 6.0,
                "Io": 2.0, "Europe": 2.0, "Ganymède": 2.0, "Callisto": 2.0, "Pluton": 2.0}
    for n, taux in attendus.items():
        assert u.par_nom[n].forage == taux, "%s : %s" % (n, u.par_nom[n].forage)
    for n in ("Terre", "Vénus", "Jupiter", "Saturne", "Uranus", "Neptune", "Soleil"):
        assert u.par_nom[n].forage == 0.0, "%s ne doit pas être exploitable" % n


def test_extraction():
    """Posé sur la Lune avec une foreuse : 3 kg/s de carburant, un dixième en monergol."""
    u = Univers(bac_a_sable=True)
    v = pose_foreur(u, ["capsule", "reservoir_m", "foreuse"], "Lune")
    assert v.foreuse() == (3.0, 2000.0), v.foreuse()   # le réservoir M vide : 2000 kg à extraire
    u.avancer(DT)
    extrait = sum(p.carburant for p in v.pieces)
    assert abs(extrait - 3.0 * DT) < 1e-9, extrait
    assert abs(sum(p.mono for p in v.pieces) - extrait / 10.0) < 1e-12
    assert "extraction:Lune" in v.drapeaux
    # une fois plein : la foreuse s'arrête et ne déborde pas
    for p in v.pieces:
        p.carburant = p.m.carburant
    assert v.foreuse() == (0.0, 0.0)
    u.avancer(DT)
    assert sum(p.carburant for p in v.pieces) == 2000.0
    assert sum(p.mono for p in v.pieces) <= sum(p.m.mono for p in v.pieces)


def test_conditions():
    """Pas d'extraction sans foreuse, sur un corps stérile, ou en vol."""
    u = Univers(bac_a_sable=True)
    v = pose_foreur(u, ["capsule", "reservoir_m"], "Lune")          # pas de foreuse à bord
    assert v.foreuse() == (0.0, 0.0)
    u.avancer(DT)
    assert sum(p.carburant for p in v.pieces) == 0.0
    v2 = pose_foreur(u, ["capsule", "reservoir_m", "foreuse"], "Terre")   # la Terre est stérile
    assert v2.foreuse() == (0.0, 0.0)
    # et dès qu'on quitte le sol, même sur la Lune, la foreuse ne mord plus
    v3 = pose_foreur(u, ["capsule", "reservoir_m", "foreuse"], "Lune")
    v3.mode = "physique"
    assert v3.foreuse() == (0.0, 0.0)


def test_suivant_le_temps_jeu():
    """L'extraction suit le temps simulé : à ×100 000, Mars remplit bien plus vite."""
    u = Univers(bac_a_sable=True)
    v = pose_foreur(u, ["capsule", "reservoir_m", "foreuse"], "Mars")     # 4 kg/s
    u.accel = 3                                                            # ×4
    u.avancer(DT)
    assert abs(sum(p.carburant for p in v.pieces) - 16.0 * DT) < 1e-9


def test_missions_et_jalon():
    """« Raffinerie lunaire » dès la première goutte ; « Ravitaillement spatial » posé
    sur Terre avec du carburant d'ailleurs ; jalon « Carburant d'ailleurs »."""
    u = Univers(bac_a_sable=True)
    v = pose_foreur(u, ["capsule", "reservoir_m", "foreuse"], "Lune")
    assert not missions._carburant_dailleurs(u, v)
    u.avancer(DT)                                  # extraction : le drapeau est posé
    for _ in range(30):                            # missions et jalons : 2×/s de temps réel
        u.avancer(DT)
    assert "raffinerie" in u.missions_faites
    assert "extraction" in reglages.JALONS_FAITS
    # le vaisseau repart et se repose sur Terre : le drapeau d'extraction l'accompagne
    v.corps = u.par_nom["Terre"]
    assert missions._carburant_dailleurs(u, v)
    for _ in range(30):
        u.avancer(DT)
    assert "ravitaillement" in u.missions_faites
    # mais extraire sur Terre ne compte pas : la Terre ne fournit rien (et pas de triche)
    v2 = pose_foreur(u, ["capsule", "reservoir_m", "foreuse"], "Terre")
    assert not missions._carburant_dailleurs(u, v2)


def test_equilibre():
    """Un réservoir XXL lunaire se remplit au bon rythme : 18 000 kg à 3 kg/s,
    soit 6 000 s de jeu (≈ 2 min réelles à ×50)."""
    u = Univers(bac_a_sable=True)
    v = pose_foreur(u, ["capsule", "reservoir_xxl", "foreuse"], "Lune")
    u.accel = 5                                          # ×50 : pas de 1,7 s de jeu
    while v.foreuse()[1] > 0.0:
        u.avancer(DT)
    assert sum(p.carburant for p in v.pieces) == 18_000.0, sum(p.carburant for p in v.pieces)
    assert abs(u.t - 6_000.0) < 5.0, u.t                 # 18 000 kg / 3 kg/s (± 3 pas)
    print("   plein XXL : %.0f s de jeu, soit %.0f s réels à ×50" % (u.t, u.t / 50.0))


def test_rendu():
    """La foreuse se dessine (SDL factice) : caisse, tube, voyant."""
    import pygame
    pygame.init()
    pygame.display.set_mode((120, 80))
    from jeu.rendu import dessiner_pile
    v = construire("Foreuse", ["foreuse"], None)
    surf = pygame.Surface((120, 80)).convert()
    dessiner_pile(surf, v, v.geometrie(), (60.0, 40.0), (0.0, -1.0), (30.0, 0.0))
    assert surf.get_at((60, 40))[:3] != (0, 0, 0), "la foreuse ne se dessine pas"


if __name__ == "__main__":
    test_taux_par_corps()
    test_extraction()
    test_conditions()
    test_suivant_le_temps_jeu()
    test_missions_et_jalon()
    test_equilibre()
    test_rendu()
    print("--- foreuse : OK")
