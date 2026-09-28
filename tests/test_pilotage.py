# -*- coding: utf-8 -*-
"""SAS, rotation manuelle, RCS et sauvegarde sur disque."""
import os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
from math import atan2, hypot, pi
from jeu.univers import Univers
from jeu.orbite import angle_pi
from jeu import sauvegarde
from test_vol import mise_en_orbite, modele, DT


def test_sas_rcs_sauvegarde():
    u = Univers(bac_a_sable=True)
    v = u.lancer("Hermès", modele("Hermès"))
    assert mise_en_orbite(u, v)
    u.accel = 0
    # --- SAS : on part à l'envers et on demande « prograde », puis « rétrograde »
    for mode, decalage in (("pro", 0.0), ("retro", pi), ("rad+", None)):
        v.sas = mode
        for _ in range(60 * 25):
            u.avancer(DT)
        x, y, vx, vy = u.etat(v)
        visee = atan2(y, x) if decalage is None else atan2(vy, vx) + decalage
        err = abs(angle_pi(v.angle - visee))
        print("   SAS %-5s : erreur %.2f°, omega %.4f rad/s (mode %s)" % (mode, err * 180 / pi, v.omega, v.mode))
        assert err < 0.03, (mode, err)
    # --- rotation manuelle puis stabilisation
    v.sas = "stab"
    u.commandes.rotation = 1
    for _ in range(60):
        u.avancer(DT)
    assert abs(v.omega) > 0.05, v.omega
    u.commandes.rotation = 0
    for _ in range(60 * 8):
        u.avancer(DT)
    assert abs(v.omega) < 1e-3, v.omega
    # --- RCS : translation avant
    v.sas = "stab"
    v.rcs = True
    mono0 = v.mono()
    x, y, vx0, vy0 = u.etat(v)
    u.commandes.avant = 1
    for _ in range(60 * 3):
        u.avancer(DT)
    u.commandes.avant = 0
    x, y, vx1, vy1 = u.etat(v)
    assert v.mono() < mono0
    print("   RCS : mono %.1f -> %.1f kg, mode %s" % (mono0, v.mono(), v.mode))
    for _ in range(30):
        u.avancer(DT)
    assert v.mode == "rails", v.mode
    # --- sauvegarde sur disque
    chemin = os.path.join(tempfile.gettempdir(), "test_sauvegarde_as2d.json")
    sauvegarde.sauvegarder(u, chemin)
    u2 = sauvegarde.charger(chemin)
    os.remove(chemin)
    a, b = u.etat(u.actif), u2.etat(u2.actif)
    assert hypot(a[0] - b[0], a[1] - b[1]) < 1e-3
    assert u2.missions_faites == u.missions_faites and len(u2.vaisseaux) == len(u.vaisseaux)
    assert abs(u2.t - u.t) < 1e-6 and u2.bac_a_sable
    for _ in range(120):
        u2.avancer(DT)
    print("   sauvegarde disque OK (%d vaisseaux)" % len(u2.vaisseaux))


if __name__ == "__main__":
    test_sas_rcs_sauvegarde()
    print("--- pilotage : OK")
