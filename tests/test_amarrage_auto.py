# -*- coding: utf-8 -*-
"""Aide au docking (amarrage et rendez-vous automatiques), transfert de carburant, carte."""
import os, sys, time
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
from math import hypot, atan2
from jeu.univers import Univers
from jeu.vaisseau import construire
from jeu import pilote, reglages
from test_vol import DT
from test_aides import orbite_auto, laisser_piloter

reglages.AIDES = True


def distance(u, a, b):
    e1, e2 = u.etat(a), u.etat(b)
    return hypot(e1[0] - e2[0], e1[1] - e2[1])


def test_amarrage_proche():
    """À 800 m derrière la station, en dérive : le pilote s'approche, s'aligne et s'amarre."""
    reglages.AIDES = True
    u = Univers(bac_a_sable=True)
    station = u.vaisseaux[0]
    x, y, vx, vy = u.etat(station)
    vt = hypot(vx, vy)
    tx, ty = vx / vt, vy / vt
    v = construire("Navette", ["port", "capsule", "reservoir_s", "moustique"], u.terre)
    v.x, v.y = x - tx * 800.0, y - ty * 800.0
    v.vx, v.vy = vx + ty * 1.5, vy - tx * 1.5              # dérive de travers
    v.angle = atan2(vy, vx)
    v.mode = "physique"
    u.vaisseaux.append(v)
    u.actif = v
    u.cibler(station)
    print("   station à %.1f km d'altitude, ports libres %s ; navette à %.0f m" % (
        u.altitude(station) / 1e3, station.ports_libres(), distance(u, v, station)))
    infos = dict((n, val) for n, val, _ in pilote.infos_amarrage(u, v))
    assert abs(infos["Distance au port"] - 800) < 60, infos
    actions = [lib for lib, _ in pilote.actions(u, v)]
    assert "Amarrage automatique" in actions, actions
    mono0, carb0, t0 = v.mono(), v.carburant_actif()[0], u.t
    u.lancer_pilote(pilote.Amarrage(station))
    ok = laisser_piloter(u, 60 * 60 * 40)
    a = u.actif
    print("   amarré en %.0f s de jeu : %s pièces, monergol %.0f -> %.0f kg, carburant %.0f -> %.0f kg" % (
        u.t - t0, len(a.pieces), mono0, a.mono(), carb0, a.carburant_actif()[0]))
    assert ok and "amarre:Station Alpha" in a.drapeaux and station not in u.vaisseaux, [m[0] for m in u.messages[-3:]]


def test_amarrage_auto_sur_port_lateral():
    """Le pilote d'amarrage doit savoir viser le port latéral d'une station, s'y amarrer,
    puis S'ARRÊTER : après la fusion, c'est la cible qui reste et qu'on pilote — l'aide
    continuait à manœuvrer la station et vidait son monergol pour rien."""
    reglages.AIDES = True
    u = Univers(bac_a_sable=True)
    from jeu.pieces import Piece
    station = u.vaisseaux[0]
    station.pieces[1].laterales = [Piece("port_radial")]
    es = u.etat(station)
    chemin = station.ports_radiaux()[0]
    v = construire("Navette", ["port", "capsule", "reservoir_s", "moustique"], u.terre)
    bx, by, bdx, bdy = station.point_port_radial(es, chemin)
    g = v.geometrie()
    v.angle = atan2(-bdy, -bdx)                            # le nez face au port latéral
    v.x = bx + bdx * 60.0 + bdx * g.nez
    v.y = by + bdy * 60.0 + bdy * g.nez
    v.vx, v.vy = es[2] - bdx * 0.8, es[3] - bdy * 0.8
    v.mode = "physique"
    u.vaisseaux.append(v)
    u.actif = v
    u.cibler(station)
    mono_station = station.mono()
    u.lancer_pilote(pilote.Amarrage(station))
    ok = laisser_piloter(u, 60 * 60 * 40)
    assert ok and len(u.vaisseaux) == 1 and u.actif is station, [m[0] for m in u.messages][-3:]
    assert [p.m.cle for p in station.pieces[1].laterales] == \
        ["port_radial", "port", "capsule", "reservoir_s", "moustique"], \
        "pas amarré sur le port latéral"
    assert station.mono() == mono_station, \
        "la station a brûlé du monergol APRÈS l'amarrage (%.1f -> %.1f)" % (mono_station, station.mono())


def test_rendez_vous_depuis_le_sol():
    """Du pas de tir jusqu'au port de la station, sans aucune intervention."""
    reglages.AIDES = True
    u, v = orbite_auto("Hermès")
    station = u.vaisseaux[0]
    u.cibler(station)
    actions = [lib for lib, _ in pilote.actions(u, v)]
    assert "Rendez-vous et amarrage" in actions, actions
    t0, horloge = u.t, time.time()
    u.lancer_pilote(pilote.RendezVous(station))
    etapes = []
    limite = 3_000_000
    while u.pilote is not None and limite > 0:
        if hasattr(u.pilote, "etape") and (not etapes or etapes[-1] != u.pilote.etape):
            etapes.append(u.pilote.etape)
            print("   t+%5.0f s  %-11s distance %.1f km" % (u.t - t0, u.pilote.etape, distance(u, v, station) / 1e3))
        u.avancer(DT)
        limite -= 1
    a = u.actif
    print("   fin : t+%.0f s de jeu (%.0f s de calcul), messages : %s" % (
        u.t - t0, time.time() - horloge, [m[0] for m in u.messages[-3:]]))
    assert "amarre:Station Alpha" in a.drapeaux, etapes


def test_transfert_carburant():
    """« Remplir » une section avec le carburant des autres : rien ne se perd."""
    u = Univers(bac_a_sable=True)
    v = u.lancer("Citerne", ["capsule", "reservoir_m", "decoupleur", "reservoir_l", "mistral"])
    sections = v.sections_reservoirs()
    assert len(sections) == 2
    haut, bas = sections
    haut[1].carburant = 300.0                          # le réservoir M a presque tout brûlé
    total = sum(p.carburant for p in v.pieces)
    carb, mono = v.remplir(0)
    print("   transfert : %.0f kg vers le haut ; réservoir M %.0f kg, réservoir L %.0f kg" % (
        carb, haut[1].carburant, bas[0].carburant))
    assert abs(carb - 1700.0) < 1e-6 and abs(haut[1].carburant - 2000.0) < 1e-6
    assert abs(sum(p.carburant for p in v.pieces) - total) < 1e-6 and mono == 0.0
    assert v.remplir(0) == (0.0, 0.0), "déjà plein"


def test_interface_carburant_et_carte():
    import pygame
    import main as jeu_main
    # ---- PC : panneau de transfert depuis le menu pause, bouton « Remplir »
    app = jeu_main.Application(tactile=False)
    reglages.AIDES = True           # indépendant de reglages.json
    app.nouvelle_partie(True)
    app.scene.charger_modele(0)
    app.scene.lancer()
    sc, u = app.scene, app.univers
    a = u.actif
    secs = a.sections_reservoirs()                      # capsule | réservoir M + Alizé | 2 réservoirs L + Mistral
    assert [len(x) for x in secs] == [1, 2, 3], [len(x) for x in secs]
    secs[1][0].carburant = 0.0                          # on vide le réservoir M de l'étage du haut
    sc.ouvrir("carburant")
    sc.maj(1 / 60)
    sc.dessiner(app.ecran)
    b = next(b for b in sc.boutons if b.libelle == "Remplir" and b.actif)
    sc.evenement(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=b.rect.center, button=1))
    assert "Transfert vers" in u.messages[-1][0], u.messages[-1][0]
    pygame.image.save(app.ecran, "/tmp/panneau_carburant.png")
    sc.ouvrir("carburant")
    # ---- PC : faire glisser la vue à la souris, puis revenir sur la fusée
    sc.cam.zoom = 1e-4                                  # vue de la Terre entière
    sc.maj(1 / 60)
    sc.dessiner(app.ecran)
    l, h = app.ecran.get_size()
    p0 = (l // 2 + 40, h // 2 - 150)                    # un endroit vide de la vue
    sc.evenement(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=p0, button=3))
    sc.evenement(pygame.event.Event(pygame.MOUSEMOTION, pos=(p0[0] - 200, p0[1] + 100), rel=(-200, 100), buttons=(0, 0, 1)))
    sc.evenement(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=(p0[0] - 200, p0[1] + 100), button=3))
    decalage = hypot(sc.cam.dx, sc.cam.dy) * sc.cam.zoom
    print("   vue déplacée de %.0f px à la souris" % decalage)
    assert 200 < decalage < 250
    sc.maj(1 / 60)
    sc.dessiner(app.ecran)
    assert any(b.libelle == "Revenir au vaisseau (F)" for b in sc.hud.boutons)
    sc.evenement(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_f, scancode=0, unicode="f", mod=0))
    for _ in range(240):
        sc.maj(1 / 60)
    g = u.actif.geometrie()
    print("   retour sur la fusée : décalage %.2f m, fusée haute de %.0f px" % (
        hypot(sc.cam.dx, sc.cam.dy), g.longueur * sc.cam.zoom))
    assert sc.cam.dx == sc.cam.dy == 0.0 and not sc.cam.retour and 60 < g.longueur * sc.cam.zoom < 200
    # ---- tactile : glisser d'un doigt, pincer, ◎
    app2 = jeu_main.Application(tactile=True)
    reglages.AIDES = True           # indépendant de reglages.json
    app2.nouvelle_partie(True)
    app2.scene.lancer()
    sc2 = app2.scene
    sc2.maj(1 / 60)
    sc2.dessiner(app2.ecran)
    l, h = app2.ecran.get_size()

    def doigt(type_, ident, pos):
        sc2.evenement(pygame.event.Event(type_, finger_id=ident, x=pos[0] / l, y=pos[1] / h,
                                         dx=0.0, dy=0.0, touch_id=0))

    depart = (l // 2 + 150, h // 3)
    doigt(pygame.FINGERDOWN, 1, depart)
    for k in range(1, 11):
        doigt(pygame.FINGERMOTION, 1, (depart[0] - 12 * k, depart[1] + 6 * k))
        sc2.maj(1 / 60)
    doigt(pygame.FINGERUP, 1, (depart[0] - 120, depart[1] + 60))
    decalage = hypot(sc2.cam.dx, sc2.cam.dy) * sc2.cam.zoom
    print("   vue déplacée de %.0f px au doigt" % decalage)
    assert 120 < decalage < 140
    sc2.maj(1 / 60)
    sc2.dessiner(app2.ecran)
    b = next(b for b in sc2.hud.boutons if b.libelle == "Vaisseau")
    sc2.hud.clic(b.rect.center)
    for _ in range(240):
        sc2.maj(1 / 60)
    assert sc2.cam.dx == sc2.cam.dy == 0.0
    print("   carte : glisser (souris, doigt) et retour sur la fusée : OK")


if __name__ == "__main__":
    test_transfert_carburant()
    test_interface_carburant_et_carte()
    test_amarrage_proche()
    test_amarrage_auto_sur_port_lateral()
    test_rendez_vous_depuis_le_sol()
    print("--- amarrage, carburant, carte : OK")
