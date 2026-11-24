# -*- coding: utf-8 -*-
"""En carrière, le pilote automatique d'atterrissage ne doit JAMAIS détruire un
modèle : après la mise en orbite, chaque vaisseau finit posé (si c'est possible),
refusé proprement (« moteur trop faible ») ou abandonné en sécurité (« on remonte »).
Le bug : le Pionnier s'écrasait après la mise en orbite, faute de verdict honnête.

    python tests/test_carriere_pilote.py
"""
import os
import sys

RACINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, RACINE)
sys.path.insert(0, os.path.dirname(__file__))

import pygame
pygame.display.init()
pygame.display.set_mode((1, 1))

import main as jeu_main
import test_vol
from jeu import pilote, reglages

DT = 1.0 / 60.0


def voler(nom_modele, limite_s=60 * 3600):
    """Mise en orbite scriptée (comme en carrière), puis pilote d'atterrissage."""
    app = jeu_main.Application(tactile=True)
    reglages.AIDES = True
    app.nouvelle_partie(True)
    from jeu.pieces import MODELES as MOD
    app.scene.charger_modele([m[0] for m in MOD].index(nom_modele))
    app.scene.lancer()
    u, sc = app.univers, app.scene
    v = u.actif
    v.gaz = 1.0
    for _ in range(60 * 14):                    # décollage puis basculement (patron test_vol)
        x, y, vx, vy = u.etat(v)
        if u.altitude(v) > 250:
            v.sas = "off"; v.angle = __import__("math").atan2(y, x) + 0.5; v.omega = 0
        sc.maj(DT)
    test_vol.mise_en_orbite(u, v, verbose=False)
    u.accel = 0
    u.lancer_pilote(pilote.Atterrissage())
    k = 0
    while u.pilote is not None and not v.detruit and v.mode != "pose" and k < limite_s * 60:
        sc.maj(DT)
        k += 1
    fin = [m[0] for m in u.messages[-2:]]
    return v, u.pilote is None, fin


def test_carriere_sans_crash():
    # Pionnier : le modèle du bug signalé — mise en orbite puis pose automatique.
    v, fini, fin = voler("Pionnier")
    print("   Pionnier :", "posé" if v.mode == "pose" else fin)
    assert not v.detruit and v.mode == "pose", fin

    # Hercule : trop lourd pour la pose — le pilote doit renoncer SANS détruire :
    # séparation de l'étage, remontée au-dessus de l'air, main rendue.
    v, fini, fin = voler("Hercule")
    print("   Hercule :", fin)
    assert not v.detruit, "le pilote a détruit le vaisseau"
    assert fini and not any("Posé" in m for m in fin), fin
    assert any("rentrée annulée" in m for m in fin), fin

    # Spoutnik : moteur trop faible — refus immédiat, carburant intact, rien détruit.
    v, fini, fin = voler("Spoutnik")
    print("   Spoutnik :", fin)
    assert not v.detruit and fini, fin
    assert any("moteur trop faible" in m for m in fin), fin
    assert sum(p.carburant for p in v.pieces) > 0, "carburant brûlé pour rien"


if __name__ == "__main__":
    test_carriere_sans_crash()
    print("--- carrière pilote : OK")
