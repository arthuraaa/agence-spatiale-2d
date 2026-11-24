# -*- coding: utf-8 -*-
"""Cache de geometrie() : même résultat qu'avant, recalculé dès que la pile change.
Le cache sert le FPS au dézoom (chaque vaisseau visible demande sa géométrie).

    python tests/test_geometrie.py
"""
import os
import sys

RACINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, RACINE)
sys.path.insert(0, os.path.dirname(__file__))

from jeu.univers import Univers
from jeu.vaisseau import construire


def test_cache_geometrie():
    u = Univers(bac_a_sable=True)
    v = construire("Essai", ["capsule", "reservoir_m", "alize"], u.terre)
    v.pieces[1].carburant = 800.0

    g1 = v.geometrie()
    # même pile, même contenu : le cache renvoie le même objet (et le même résultat)
    assert v.geometrie() is g1
    assert g1.masse == sum(p.masse() for p in v.pieces)

    # carburant brûlé : la géométrie (masse, cdm) doit être recalculée
    v.pieces[1].carburant = 300.0
    g2 = v.geometrie()
    assert g2 is not g1 and g2.masse < g1.masse

    # RCS rechargé (mono) : même invalidation
    v.pieces[0].mono = v.pieces[0].mono + 10.0
    g3 = v.geometrie()
    assert g3 is not g2 and g3.masse > g2.masse

    # pile modifiée (séparation d'étage) : recalcul, la pièce partie ne compte plus
    v.pieces = v.pieces[:2]
    g4 = v.geometrie()
    assert g4 is not g3 and g4.masse < g3.masse and len(g4.segments) == 2

    # boosters latéraux : leur carburant entre dans la masse et doit invalider le cache
    base = construire("AvecBoosters", ["capsule", "reservoir_m",
                                       ["decoupleur_radial", ["reservoir_m", "alize"]]], u.terre)
    # (les pièces radiales portent leurs boosters dans p.laterales)
    radial = [p for p in base.pieces if p.laterales]
    assert radial, "le plan doit contenir un booster radial"
    radial[0].laterales[0].carburant = 400.0
    gb1 = base.geometrie()
    radial[0].laterales[0].carburant = 100.0
    gb2 = base.geometrie()
    assert gb2 is not gb1 and gb2.masse < gb1.masse, \
        "brûler un booster latéral doit recalculer la géométrie"


if __name__ == "__main__":
    test_cache_geometrie()
    print("--- geometrie : OK")
