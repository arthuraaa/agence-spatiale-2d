# -*- coding: utf-8 -*-
"""Ports latéraux : construction dans le hangar, amarrage d'une annexe sur le flanc,
désamarrage, sauvegarde. Les boosters (paire miroir) restent couverts par test_boosters.

    python tests/test_ports_radiaux.py
"""
import os
import sys
from math import atan2, hypot

RACINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, RACINE)
sys.path.insert(0, os.path.dirname(__file__))

from jeu.pieces import Piece
from jeu.sauvegarde import univers_vers_dict, dict_vers_univers
from jeu.univers import Univers
from jeu.vaisseau import (Vaisseau, pieces_depuis_plan, est_paire_boosters, porteurs_actifs)

DT = 1.0 / 30.0


def test_construction_et_masse():
    """Un port latéral dans le hangar : compte UNE fois (pas une paire de boosters)."""
    plan = ["capsule", "decoupleur", ["reservoir_l", ["port_radial"]], "mistral"]
    pieces = pieces_depuis_plan(plan, "Test")
    v = Vaisseau("", pieces, None)
    assert v.ports_radiaux() == [2], "le port latéral est sur la pièce 2"
    assert not any(est_paire_boosters(p) for p in pieces)
    assert not porteurs_actifs(pieces), "une annexe ne brûle jamais"
    masse_pile = sum(p.masse() for p in pieces) + sum(q.masse() for p in pieces
                                                      for q in p.laterales)
    assert abs(v.masse() - masse_pile) < 1e-6, "l'annexe compte une seule fois (pas deux)"
    g = v.geometrie()
    assert len(g.laterales) == 1 and g.laterales[0][5] == 1.0
    # le port libre est sur le flanc droit : direction perpendiculaire à l'axe du vaisseau
    from math import cos, sin
    bx, by, dx, dy = v.point_port_radial((0.0, 0.0, 0.0, 0.0), 2)
    ca, sa = cos(v.angle), sin(v.angle)
    assert abs(dx - sa) < 0.1 and abs(dy + ca) < 0.1, "port sur le côté droit du vaisseau"
    # avec des boosters en plus, la paire reste comptée deux fois
    v2 = Vaisseau("", pieces_depuis_plan(["capsule", ["reservoir_l", ["decoupleur_radial",
                                                                    "mistral"]]], "T"), None)
    assert all(est_paire_boosters(p) for p in v2.pieces if p.laterales)
    attendu = sum(p.masse() for p in v2.pieces) + 2 * sum(q.masse() for p in v2.pieces
                                                          for q in p.laterales)
    assert abs(v2.masse() - attendu) < 1e-6, "la paire de boosters compte deux fois"


def test_hangar():
    """Le hangar accroche un port latéral puis remplit l'annexe avec n'importe quelle pièce."""
    from jeu import hangar
    u = Univers(bac_a_sable=True)
    app = type("App", (), {"univers": u, "modele": ["capsule"], "nom_modele": "X"})()
    scene = hangar.SceneHangar(app)
    scene.ajouter("port_radial")
    assert "Choisis" in scene.message, "il faut d'abord choisir une pièce porteuse"
    scene.selection = 0
    scene.ajouter("port_radial")
    assert scene.cles == [["capsule", ["port_radial"]]] and scene.selection == (0, 0)
    scene.ajouter("module")
    assert scene.cles == [["capsule", ["port_radial", "module"]]], "l'annexe prend tout"
    pieces = pieces_depuis_plan(scene.cles)
    assert len(pieces[0].laterales) == 2, "le port et le module sont dans l'annexe"
    # sans annexe amarrée, le port est bien libre
    scene2 = hangar.SceneHangar(app)
    scene2.selection, scene2.cles = 0, [["capsule", ["port_radial"]]]
    v2 = Vaisseau("", pieces_depuis_plan(scene2.cles), None)
    assert v2.ports_radiaux() == [0]


def test_amarrer_puis_desamarrer():
    """Amarrage direct sur le port latéral, puis désamarrage avec U : l'annexe repart."""
    u = Univers(bac_a_sable=True)
    station = u.vaisseaux[0]                     # la Station Alpha du bac à sable
    station.pieces[1].laterales = [Piece("port_radial")]
    k = 1
    navette = Vaisseau("Navette", pieces_depuis_plan(
        ["port", "capsule", "reservoir_s", "moustique"], "Navette"), u.terre)
    es = u.etat(station)
    navette.x, navette.y = es[0] + 10.0, es[1]
    navette.vx, navette.vy = es[2], es[3]
    navette.mode = "physique"
    u.vaisseaux.append(navette)
    u.actif = navette
    u._amarrer(navette, station, "haut", ("lat", k), u.etat(navette), u.etat(station))
    assert len(u.vaisseaux) == 1 and u.actif is station, "l'annexe doit fusionner dans la station"
    pile = station.pieces[k].laterales
    assert pile[0].m.cle == "port_radial"
    assert [p.m.cle for p in pile[1:]] == ["port", "capsule", "reservoir_s", "moustique"]
    assert "amarre:Navette" in station.drapeaux and station.ports_radiaux() == []
    # le port est de nouveau libre après désamarrage, et l'annexe repart sur le côté
    u.actif = station
    u.desamarrer()
    assert len(u.vaisseaux) == 2 and u.actif is station
    assert [p.m.cle for p in station.pieces[k].laterales] == ["port_radial"]
    autre = next(v for v in u.vaisseaux if v is not station)
    assert [p.m.cle for p in autre.pieces] == ["port", "capsule", "reservoir_s", "moustique"]
    assert autre.controlable() and autre.nom == "Navette"
    d0 = hypot(autre.x - station.x, autre.y - station.y)
    for _ in range(60):
        u.avancer(DT)
    assert hypot(autre.x - station.x, autre.y - station.y) > d0, "l'annexe s'écarte"


def test_amarrage_en_vol_complet():
    """Comme test_vol : approche orbitale réelle sur le port latéral de la station du bac à sable."""
    u = Univers(bac_a_sable=True)
    station = u.vaisseaux[0]
    station.pieces[1].laterales = [Piece("port_radial")]
    es = u.etat(station)
    k = station.ports_radiaux()[0]
    navette = Vaisseau("Navette", pieces_depuis_plan(
        ["port", "capsule", "reservoir_s", "moustique"], "Navette"), u.terre)
    bx, by, bdx, bdy = station.point_port_radial(es, k)
    g = navette.geometrie()
    navette.angle = atan2(-bdy, -bdx)
    navette.x = bx + bdx * 4.0 + bdx * g.nez
    navette.y = by + bdy * 4.0 + bdy * g.nez
    navette.vx, navette.vy = es[2] - bdx * 0.6, es[3] - bdy * 0.6
    navette.mode = "physique"
    u.vaisseaux.append(navette)
    u.actif = navette
    for _ in range(60 * 60):
        u.avancer(DT)
        if len(u.vaisseaux) == 1:
            break
    assert len(u.vaisseaux) == 1 and u.actif is station, "pas d'amarrage en vol"
    assert len(station.pieces[1].laterales) == 5


def test_sauvegarde():
    """L'annexe amarrée survit à une sauvegarde/relecture (univers_vers_dict)."""
    u = Univers(bac_a_sable=True)
    station = Vaisseau("Station", pieces_depuis_plan(
        ["port", "module", ["module", ["port_radial", "module"]], "port"], "Station"), u.terre)
    station.x, station.y = 6_600_000.0, 0.0
    station.vx, station.vy = 0.0, 500.0
    station.mode = "physique"
    u.vaisseaux = [station]
    u.actif = station
    d = univers_vers_dict(u)
    u2 = dict_vers_univers(d)
    pile = u2.vaisseaux[0].pieces[2].laterales    # le porteur est la 3e pièce du plan
    assert [p.m.cle for p in pile] == ["port_radial", "module"]
    assert u2.vaisseaux[0].ports_radiaux() == [], "l'annexe reste amarrée"


if __name__ == "__main__":
    test_construction_et_masse()
    test_hangar()
    test_amarrer_puis_desamarrer()
    test_amarrage_en_vol_complet()
    test_sauvegarde()
    print("--- ports radiaux : OK")
