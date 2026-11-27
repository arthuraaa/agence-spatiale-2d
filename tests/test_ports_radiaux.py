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
    assert v.ports_radiaux() == [(2,)], "le port latéral est sur la pièce 2"
    assert not any(est_paire_boosters(p) for p in pieces)
    assert not porteurs_actifs(pieces), "une annexe ne brûle jamais"
    masse_pile = sum(p.masse() for p in pieces) + sum(q.masse() for p in pieces
                                                      for q in p.laterales)
    assert abs(v.masse() - masse_pile) < 1e-6, "l'annexe compte une seule fois (pas deux)"
    g = v.geometrie()
    assert len(g.laterales) == 1 and g.laterales[0][5] == 1.0
    # le port libre est sur le flanc droit : direction perpendiculaire à l'axe du vaisseau
    from math import cos, sin
    bx, by, dx, dy = v.point_port_radial((0.0, 0.0, 0.0, 0.0), (2,))
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
    assert v2.ports_radiaux() == [(0,)]


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
    u._amarrer(navette, station, "haut", ("lat", (k,)), u.etat(navette), u.etat(station))
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
    chemin = station.ports_radiaux()[0]
    navette = Vaisseau("Navette", pieces_depuis_plan(
        ["port", "capsule", "reservoir_s", "moustique"], "Navette"), u.terre)
    bx, by, bdx, bdy = station.point_port_radial(es, chemin)
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
    """L'annexe amarrée (et une sous-annexe) survit à une sauvegarde/relecture."""
    u = Univers(bac_a_sable=True)
    station = Vaisseau("Station", pieces_depuis_plan(
        ["port", "module", ["module", ["port_radial", "module"]], "port"], "Station"), u.terre)
    station.x, station.y = 6_600_000.0, 0.0
    station.vx, station.vy = 0.0, 500.0
    station.mode = "physique"
    # une sous-annexe amarrée au module de l'annexe de premier niveau
    sous = station.pieces[2].laterales[1]
    sous.laterales = [Piece("port_radial"), Piece("module")]
    u.vaisseaux = [station]
    u.actif = station
    d = univers_vers_dict(u)
    u2 = dict_vers_univers(d)
    pile = u2.vaisseaux[0].pieces[2].laterales    # le porteur est la 3e pièce du plan
    assert [p.m.cle for p in pile] == ["port_radial", "module"]
    assert u2.vaisseaux[0].ports_radiaux() == [], "l'annexe reste amarrée"
    sous2 = u2.vaisseaux[0].piece_au_chemin((2, 1, 1))
    assert sous2.m.cle == "module", "la sous-annexe est relue au fond de la branche"
    assert u2.vaisseaux[0].chemins_annexes() == [(2,), (2, 1)]


def test_annexe_d_annexe():
    """Amarrage en chaîne : la navette s'amarre au port latéral d'une annexe déjà en place,
    la géométrie s'écarte en escalier, et chaque niveau se détache séparément avec U."""
    u = Univers(bac_a_sable=True)
    station = u.vaisseaux[0]
    module_porteur = Piece("module")
    module_porteur.laterales = [Piece("port_radial")]
    station.pieces[1].laterales = [Piece("port_radial"), module_porteur]
    assert station.ports_radiaux() == [(1, 1)], "le port libre est au fond de la sous-annexe"
    navette = Vaisseau("Navette", pieces_depuis_plan(
        ["port", "capsule", "reservoir_s", "moustique"], "Navette"), u.terre)
    es = u.etat(station)
    u.actif = navette
    u._amarrer(navette, station, "haut", ("lat", (1, 1)), u.etat(navette), es)
    assert len(u.vaisseaux) == 1 and u.actif is station
    porteur = station.piece_au_chemin((1, 1))
    assert [p.m.cle for p in porteur.laterales[1:]] == \
        ["port", "capsule", "reservoir_s", "moustique"], "la navette est collée à la sous-annexe"
    # la sous-branche est une entrée de géométrie propre, plus loin à droite que sa parente
    g = station.geometrie()
    parent = next(e for e in g.laterales if e[0] == (1,))
    sous = next(e for e in g.laterales if e[0] == (1, 1))
    assert sous[2] > parent[2], "la sous-annexe s'écarte en escalier"
    # la masse compte toutes les pièces de tous les niveaux, une seule fois
    def masse_pile(pile):
        return sum(q.masse() + masse_pile(q.laterales) for q in pile)
    attendu = sum(p.masse() for p in station.pieces) + \
        masse_pile(station.pieces[1].laterales)
    assert abs(station.masse() - attendu) < 1e-6, "la masse descend dans les sous-branches"
    # U détache d'abord l'annexe de premier niveau, qui emmène la navette au flanc
    u.actif = station
    u.desamarrer()
    assert len(u.vaisseaux) == 2
    assert [p.m.cle for p in station.piece_au_chemin((1,)).laterales] == ["port_radial"]
    gros = next(v for v in u.vaisseaux if v is not station)
    assert [p.m.cle for p in gros.pieces] == ["module"], "l'annexe part avec la navette au flanc"
    assert [p.m.cle for p in gros.piece_au_chemin((0,)).laterales[1:]] == \
        ["port", "capsule", "reservoir_s", "moustique"]
    # et la navette peut se détacher à son tour du module
    u.actif = gros
    u.desamarrer()
    assert len(u.vaisseaux) == 3
    petite = next(v for v in u.vaisseaux if v is not station and v is not gros)
    assert [p.m.cle for p in petite.pieces] == ["port", "capsule", "reservoir_s", "moustique"]
    assert [p.m.cle for p in gros.piece_au_chemin((0,)).laterales] == ["port_radial"]


def test_amarrage_en_vol_sur_sous_annexe():
    """Comme test_amarrage_en_vol_complet, mais le port visé est au fond d'une annexe
    déjà amarrée : l'approche orbitale doit aboutir à une annexe d'annexe."""
    u = Univers(bac_a_sable=True)
    station = u.vaisseaux[0]
    module_porteur = Piece("module")
    module_porteur.laterales = [Piece("port_radial")]
    station.pieces[1].laterales = [Piece("port_radial"), module_porteur]
    es = u.etat(station)
    chemin = station.ports_radiaux()[0]
    navette = Vaisseau("Navette", pieces_depuis_plan(
        ["port", "capsule", "reservoir_s", "moustique"], "Navette"), u.terre)
    bx, by, bdx, bdy = station.point_port_radial(es, chemin)
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
    assert len(u.vaisseaux) == 1 and u.actif is station, "pas d'amarrage sur la sous-annexe"
    assert len(station.piece_au_chemin((1, 1)).laterales) == 5


def test_rendu_sous_annexe():
    """Une station avec annexe d'annexe se dessine entièrement (SDL factice, avec flamme)."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    pygame.init()
    pygame.display.set_mode((200, 100))
    from jeu.rendu import dessiner_pile
    station = Vaisseau("Station", pieces_depuis_plan(
        ["capsule", ["module", ["port_radial", "module"]], "mistral"], "Station"), None)
    module = station.pieces[1].laterales[1]
    module.laterales = [Piece("port_radial"), Piece("module"), Piece("port")]
    g = station.geometrie()
    assert any(e[0] == (1, 1) for e in g.laterales), "la sous-branche a sa géométrie propre"
    surf = pygame.Surface((200, 100)).convert()
    dessiner_pile(surf, station, g, (100.0, 50.0), (0.0, -6.0), (6.0, 0.0), flamme=1.0)
    assert surf.get_at((100, 50))[:3] != (0, 0, 0), "quelque chose est dessiné au centre"


if __name__ == "__main__":
    test_construction_et_masse()
    test_hangar()
    test_amarrer_puis_desamarrer()
    test_amarrage_en_vol_complet()
    test_annexe_d_annexe()
    test_amarrage_en_vol_sur_sous_annexe()
    test_rendu_sous_annexe()
    test_sauvegarde()
    print("--- ports radiaux : OK")
