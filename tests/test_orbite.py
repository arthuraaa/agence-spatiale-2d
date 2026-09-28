# -*- coding: utf-8 -*-
"""Vérifie la propagation képlérienne contre une intégration numérique RK4."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from math import hypot, sqrt
from jeu.orbite import Orbite


def rk4(x, y, vx, vy, mu, duree, n):
    h = duree / n
    def acc(x, y):
        r3 = hypot(x, y) ** 3
        return -mu * x / r3, -mu * y / r3
    for _ in range(n):
        ax1, ay1 = acc(x, y)
        x2, y2, vx2, vy2 = x + vx*h/2, y + vy*h/2, vx + ax1*h/2, vy + ay1*h/2
        ax2, ay2 = acc(x2, y2)
        x3, y3, vx3, vy3 = x + vx2*h/2, y + vy2*h/2, vx + ax2*h/2, vy + ay2*h/2
        ax3, ay3 = acc(x3, y3)
        x4, y4, vx4, vy4 = x + vx3*h, y + vy3*h, vx + ax3*h, vy + ay3*h
        ax4, ay4 = acc(x4, y4)
        x += h*(vx + 2*vx2 + 2*vx3 + vx4)/6
        y += h*(vy + 2*vy2 + 2*vy3 + vy4)/6
        vx += h*(ax1 + 2*ax2 + 2*ax3 + ax4)/6
        vy += h*(ay1 + 2*ay2 + 2*ay3 + ay4)/6
    return x, y, vx, vy


def test_propagation():
    mu = 3.986e10
    cas = [
        (73710.0, 0.0, 0.0, 735.0),        # quasi circulaire, anti-horaire
        (73710.0, 0.0, 50.0, -900.0),      # elliptique, horaire
        (0.0, 80000.0, -1300.0, 100.0),    # hyperbolique
        (-50000.0, 60000.0, 300.0, 1150.0),  # hyperbolique horaire ?
        (73710.0, 10.0, -20.0, 1030.0),    # très elliptique
    ]
    for (x, y, vx, vy) in cas:
        o = Orbite(x, y, vx, vy, mu, 100.0)
        x0, y0, vx0, vy0 = o.etat(100.0)
        assert hypot(x0 - x, y0 - y) < 1e-4 and hypot(vx0 - vx, vy0 - vy) < 1e-7, (x0, y0, vx0, vy0)
        for duree in (30.0, 400.0, 2500.0):
            xa, ya, vxa, vya = o.etat(100.0 + duree)
            xn, yn, vxn, vyn = rk4(x, y, vx, vy, mu, duree, 40000)
            assert hypot(xa - xn, ya - yn) < 0.05, (x, y, duree, xa - xn, ya - yn)
            assert hypot(vxa - vxn, vya - vyn) < 1e-3
        # cohérence des délais
        if o.elliptique:
            d = o.delai_apoapside(100.0)
            xa, ya, _, _ = o.etat(100.0 + d)
            assert abs(hypot(xa, ya) - o.ra) < 1e-3 * o.ra
        d = o.delai_periapside(100.0)
        if d is not None:
            xa, ya, _, _ = o.etat(100.0 + d)
            assert abs(hypot(xa, ya) - o.rp) < 1e-6 * o.rp + 1e-3
        d = o.delai_jusquau_rayon(1.2 * o.rp, 100.0, en_descente=False)
        if d is not None:
            xa, ya, _, _ = o.etat(100.0 + d)
            assert abs(hypot(xa, ya) - 1.2 * o.rp) < 1e-3, hypot(xa, ya) - 1.2*o.rp
        # aller-retour anomalie <-> temps
        A = o.anomalie(777.0)
        assert abs(o.temps_de_anomalie(A) - 777.0) < 1e-6


if __name__ == "__main__":
    test_propagation()
    print("orbite : OK")
