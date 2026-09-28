# -*- coding: utf-8 -*-
"""Transfert de Hohmann Terre -> Mars : la prédiction doit trouver la rencontre avec Mars."""
import os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from math import sqrt, pi, cos, sin, hypot
from jeu.corps import creer_systeme_solaire
from jeu.orbite import Orbite, TAU
from jeu.trajectoire import predire, approche_minimale


def test_transfert_mars():
    corps, par_nom = creer_systeme_solaire()
    soleil, terre, mars = par_nom["Soleil"], par_nom["Terre"], par_nom["Mars"]
    r1, r2 = terre.a, mars.a
    at = 0.5 * (r1 + r2)
    duree = pi * sqrt(at ** 3 / soleil.mu)
    phase_ideale = (pi - mars.n * duree) % TAU
    # on cherche la prochaine fenêtre de tir
    t = 0.0
    while True:
        phase = ((mars.phase + mars.n * t) - (terre.phase + terre.n * t)) % TAU
        if abs(phase - phase_ideale) < 0.002:
            break
        t += 500.0
    print("fenêtre de tir à J+%.1f, durée du transfert %.1f jours, phase idéale %.1f°" % (
        t / 86400, duree / 86400, phase_ideale * 180 / pi))
    x, y, vx, vy = terre.etat_relatif(t)
    k = sqrt(soleil.mu * (2 / r1 - 1 / at)) / hypot(vx, vy)
    o = Orbite(x * 1.0001, y * 1.0001, vx * k, vy * k, soleil.mu, t)   # juste hors de la Terre
    t0 = time.time()
    trs = predire(o, soleil, t + 3 * 86400, 0.0, 4)     # on démarre 3 jours après (sorti de la SOI)
    dt = time.time() - t0
    print("   tronçons :", [(tr.corps.nom, tr.fin, tr.suivant.nom if tr.suivant else None) for tr in trs],
          " (%.1f ms)" % (dt * 1000))
    assert trs[0].fin == "entree" and trs[0].suivant is mars, "rencontre avec Mars non trouvée"
    pe = trs[1].orbite.rp - mars.R
    print("   arrivée à J+%.1f, périapside martien %.0f km, vitesse d'arrivée %.0f m/s" % (
        trs[0].t1 / 86400, pe / 1e3, sqrt(2 * max(trs[1].orbite.energie, 0))))
    r = approche_minimale(trs, mars.position_relative, soleil, t + 3 * 86400)
    assert r is not None and r[1] < mars.soi * 1.01
    assert dt < 0.25, "prédiction trop lente"


if __name__ == "__main__":
    test_transfert_mars()
    print("--- Mars : OK")
