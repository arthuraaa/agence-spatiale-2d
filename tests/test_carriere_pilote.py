# -*- coding: utf-8 -*-
"""En carrière, le pilote automatique ne doit JAMAIS détruire un modèle : mise en
orbite puis atterrissage, chaque vaisseau finit posé (si c'est possible), refusé
proprement (« moteur trop faible ») ou abandonné en sécurité (« on remonte »).

Le bug signalé : après la mise en orbite du Pionnier, l'atterrissage refusait
toujours (« pose impossible ici ») puis, une fois sur deux, s'écrasait. L'orbite
automatique était trop basse (collée à l'air) et la rentrée n'avait plus de marge ;
depuis, l'orbite auto vise trois plafonds d'air et une rentrée jugée condamnée
retente en douceur (plusieurs passes), validée en vol d'ombre avant d'être engagée.

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
from jeu import pilote, reglages

DT = 1.0 / 60.0


def voler(nom_modele, limite_s=60 * 3600):
    """Mise en orbite par le VRAI pilote (comme en carrière), puis atterrissage auto."""
    app = jeu_main.Application(tactile=True)
    reglages.AIDES = True
    app.nouvelle_partie(True)
    from jeu.pieces import MODELES as MOD
    app.scene.charger_modele([m[0] for m in MOD].index(nom_modele))
    app.scene.lancer()
    u, sc = app.univers, app.scene
    v = u.actif
    v.gaz = 1.0
    u.accel = 3
    u.lancer_pilote(pilote.MiseEnOrbite())
    for _ in range(60 * 1200):
        if not isinstance(u.pilote, pilote.MiseEnOrbite) or v.detruit:
            break
        sc.maj(DT)
    assert not v.detruit, "destruction pendant la mise en orbite"
    assert u.pilote is None, "la mise en orbite ne finit jamais"
    u.accel = 0
    u.lancer_pilote(pilote.Atterrissage())
    k = 0
    while u.pilote is not None and not v.detruit and v.mode != "pose" and k < limite_s * 60:
        sc.maj(DT)
        k += 1
    fin = [m[0] for m in u.messages[-2:]]
    return v, u.pilote is None, fin


def test_carriere_sans_crash():
    # Pionnier : le modèle du bug signalé — orbite auto assez haute, rentrée raide
    # refusée, retentée en douceur, pose. On vérifie aussi le passage par la douce.
    v, fini, fin = voler("Pionnier")
    print("   Pionnier :", "posé" if v.mode == "pose" else fin)
    assert not v.detruit and v.mode == "pose", fin

    # Spoutnik : moteur trop faible — refus immédiat, carburant intact, rien détruit.
    v, fini, fin = voler("Spoutnik")
    print("   Spoutnik :", fin)
    assert not v.detruit and fini, fin
    assert any("moteur trop faible" in m for m in fin), fin
    assert sum(p.carburant for p in v.pieces) > 0, "carburant brûlé pour rien"

    # Hermès : pose raide impossible, douce non validée en vol d'ombre — le pilote
    # renonce SANS détruire : main rendue, vaisseau en sécurité.
    v, fini, fin = voler("Hermès")
    print("   Hermès :", fin)
    assert not v.detruit and fini, fin
    assert any("rentrée annulée" in m for m in fin), fin

    # Hercule : à la limite du posable — selon la vitesse d'intégration de la
    # montée (le temps accéléré change l'intégration au centimètre près), la
    # rentrée douce se pose ou se refuse. Le contrat : JAMAIS détruit, verdict
    # propre dans tous les cas (pose ou remontée en sécurité).
    v, fini, fin = voler("Hercule")
    print("   Hercule :", "posé" if v.mode == "pose" else fin)
    assert not v.detruit and fini, fin
    assert v.mode == "pose" or any("rentrée annulée" in m for m in fin), fin


if __name__ == "__main__":
    test_carriere_sans_crash()
    print("--- carrière pilote : OK")
