# -*- coding: utf-8 -*-
"""Scénarios historiques : chaque mission se joue jusqu'au bout, et l'interface suit."""
import os, sys, time
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ["AGENCE_LANGUE"] = "fr"          # ce test clique sur des libellés français
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from math import hypot
import pygame
import main as jeu_main
from jeu import tutoriel, pilote, reglages, scenarios
from jeu.constantes import ACCELERATIONS
DT = 1 / 60
MAX = len(ACCELERATIONS) - 1

def nouvelle(ident):
    app = jeu_main.Application(tactile=True)
    reglages.AIDES = True
    tutoriel.demarrer(app, ident)
    return app

def etape(app):
    return "FINI" if app.tuto.termine else app.tuto.k

def tourner(app, jusqua, chaque=None, limite=60 * 60 * 60):
    k = 0
    while k < limite:
        sc = app.scene
        if app.tuto.echec:
            raise AssertionError("ÉCHEC (crash) à l'étape %s : %s" % (etape(app), [m[0] for m in app.univers.messages[-3:]]))
        if jusqua(app):
            return True
        if app.tuto.etape.fini is None and not app.tuto.termine:
            app.tuto.suivant()
        if chaque:
            chaque(app)
        sc.maj(DT)
        k += 1
    raise AssertionError("délai dépassé à l'étape %s" % etape(app))

def pilote_auto(app, prog):
    app.univers.lancer_pilote(prog)
    tourner(app, lambda a: a.univers.pilote is None)

def vitesse_sol(u, v):
    x, y, vx, vy = u.etat(v); w = v.corps.vitesse_rotation
    return hypot(vx + w * y, vy - w * x)

def rentrer_en_parachute(app, nom):
    """Accélérer jusqu'à l'air, ouvrir le parachute sous 250 m/s, attendre le sol."""
    def chaque(a):
        u = a.univers; v = u.actif
        if v is None: return
        u.accel = MAX if u.altitude(v) > v.corps.atm_h + 2000 else 0
        if u.altitude(v) < v.corps.atm_h and vitesse_sol(u, v) < 240 and any(p.parachute == "plie" for p in v.pieces):
            u.ouvrir_parachute()
    tourner(app, lambda a: scenarios._pose_sur(scenarios.vaisseau_de(a.univers, nom), a.univers.terre), chaque)

def spoutnik():
    app = nouvelle("spoutnik")
    tourner(app, lambda a: etape(a) == 1)
    pilote_auto(app, pilote.MiseEnOrbite())
    tourner(app, lambda a: a.tuto.termine)
    return app

def vostok():
    app = nouvelle("vostok")
    tourner(app, lambda a: etape(a) == 1)
    pilote_auto(app, pilote.MiseEnOrbite())
    tourner(app, lambda a: etape(a) == 2)
    tourner(app, lambda a: etape(a) == 3, lambda a: setattr(a.univers, "accel", 6))
    u = app.univers; v = u.actif
    v.sas = "retro"
    def freiner(a):
        a.univers.accel = 0
        v = a.univers.actif
        v.gaz = 1.0 if scenarios._pe(a.univers) >= 2500 and abs(v.angle - (a.univers.angle_sas(v) or v.angle)) < 0.2 else 0.0
        if v.etage_epuise() and v.gaz > 0: a.univers.separer_etage()
    tourner(app, lambda a: etape(a) == 4, freiner)
    while app.univers.actif.moteur_actif() is not None:
        app.univers.separer_etage(); app.scene.maj(DT)
    tourner(app, lambda a: etape(a) == 5)
    rentrer_en_parachute(app, "Vostok 1")
    tourner(app, lambda a: a.tuto.termine)
    return app

def apollo13():
    app = nouvelle("apollo13")
    tourner(app, lambda a: etape(a) == 1)
    u = app.univers; v = u.actif
    v.sas = "retro"
    def freiner(a):
        v = a.univers.actif
        err = abs(((v.angle - (a.univers.angle_sas(v) or v.angle)) + 3.14159) % 6.28318 - 3.14159)
        v.gaz = 1.0 if scenarios._pe(a.univers) >= 2000 and err < 0.1 else 0.0
    tourner(app, lambda a: etape(a) == 2, freiner)
    def approcher(a):
        u = a.univers
        u.accel = MAX if u.altitude(u.actif) > 60_000 else 0
    tourner(app, lambda a: a.univers.altitude(a.univers.actif) < 40_000, approcher)
    u = app.univers
    u.desamarrer(); app.scene.maj(DT)
    odyssey = scenarios.vaisseau_de(u, "Odyssey")
    app.scene.controler(odyssey)
    while app.univers.actif.moteur_actif() is not None:
        app.univers.separer_etage(); app.scene.maj(DT)
    tourner(app, lambda a: etape(a) == 3)
    rentrer_en_parachute(app, "Odyssey")
    tourner(app, lambda a: a.tuto.termine)
    return app


def apollo11():
    app = nouvelle("apollo11")
    tourner(app, lambda a: etape(a) == 1)
    journal = lambda txt: print("   t=%6.0f s  étape %s  %s" % (app.univers.t, etape(app), txt))
    u = app.univers
    u.desamarrer(); app.scene.maj(DT)
    app.scene.controler(scenarios._seul(u, "Eagle", "Columbia"))
    tourner(app, lambda a: etape(a) == 2); journal("Eagle séparé et contrôlé")
    pilote_auto(app, pilote.Atterrissage())
    tourner(app, lambda a: etape(a) == 3); journal("Eagle posé : %s" % [m[0] for m in app.univers.messages[-1:]])
    app.univers.separer_etage(); app.scene.maj(DT)
    pilote_auto(app, pilote.MiseEnOrbite())
    tourner(app, lambda a: etape(a) == 4)
    o = app.univers.actif.orbite; lune = app.univers.par_nom["Lune"]
    journal("Eagle en orbite : Pe %.1f km, Ap %.1f km" % ((o.rp - lune.R) / 1e3, (o.ra - lune.R) / 1e3))
    u = app.univers
    columbia = scenarios.vaisseau_de(u, "Columbia")
    u.cibler(columbia)
    pilote_auto(app, pilote.RendezVous(columbia))
    tourner(app, lambda a: etape(a) == 5); journal("amarrés : %s" % [m[0] for m in app.univers.messages[-1:]])
    u = app.univers
    u.desamarrer(); app.scene.maj(DT)
    app.scene.controler(scenarios._seul(u, "Columbia", "Eagle"))
    assert pilote.planifier_retour(u, u.actif), [m[0] for m in u.messages[-2:]]
    journal(u.messages[-1][0])
    pilote_auto(app, pilote.ExecuterNoeud())
    tourner(app, lambda a: etape(a) == 6, lambda a: setattr(a.univers, "accel", MAX))
    journal("Columbia autour de la Terre, périapside %.1f km" % (
        (app.univers.actif.orbite.rp - app.univers.terre.R) / 1e3))
    def approcher(a):
        u = a.univers
        u.accel = MAX if u.altitude(u.actif) > 60_000 else 0
    tourner(app, lambda a: a.univers.altitude(a.univers.actif) < 40_000, approcher)
    while app.univers.actif.moteur_actif() is not None:
        app.univers.separer_etage(); app.scene.maj(DT)
    rentrer_en_parachute(app, "Columbia")
    tourner(app, lambda a: a.tuto.termine)
    return app




def luna2():
    """Luna 2 : l'impact EST la mission (crash_prevu). Mise en orbite, transfert, fonce."""
    app = nouvelle("luna2")
    tourner(app, lambda a: etape(a) == 1)
    pilote_auto(app, pilote.MiseEnOrbite())
    tourner(app, lambda a: etape(a) == 2)
    u = app.univers
    lune = u.par_nom["Lune"]
    u.cibler(lune)
    assert pilote.planifier_transfert(u, u.actif, lune), [m[0] for m in u.messages[-2:]]
    pilote_auto(app, pilote.ExecuterNoeud())
    journal = lambda txt: print("   t=%6.0f s  étape %s  %s" % (u.t, etape(app), txt))
    def approcher(a):
        u = a.univers; v = u.actif
        if v is None: return
        if v.corps is u.par_nom["Lune"]:
            u.accel = 4                     # Luna 2 ne freine pas, elle vise le sol :
            v.sas = "retro"                 # frein rétrograde jusqu'à une trajectoire d'impact
            v.gaz = 1.0 if scenarios._pe(u) > -5000 \
                and abs(v.angle - (u.angle_sas(v) or v.angle)) < 0.2 else 0.0
        else:
            u.accel = MAX
    tourner(app, lambda a: etape(a) == 3, approcher); journal("entrée dans la SOI lunaire")
    tourner(app, lambda a: a.tuto.termine, approcher, limite=4 * 60 * 60 * 60)
    return app


def apollo_soyouz():
    """Apollo-Soyouz : rendez-vous et amarrage entre deux vaisseaux amis."""
    app = nouvelle("apollo_soyouz")
    tourner(app, lambda a: etape(a) == 1)
    u = app.univers
    soyouz = scenarios.vaisseau_de(u, "Soyouz")
    u.cibler(soyouz)
    tourner(app, lambda a: etape(a) == 2)
    pilote_auto(app, pilote.RendezVous(soyouz))
    tourner(app, lambda a: a.tuto.termine)
    return app


def test_missions_jouees_jusquau_bout():
    for nom in ("spoutnik", "vostok", "apollo13", "apollo11", "luna2", "apollo_soyouz"):
        t0 = time.time()
        app = globals()[nom]()
        assert app.tuto.termine and nom in reglages.TUTOS_FAITS
        print("   %-9s : mission accomplie en %.0f s de jeu (%.0f s de calcul)" % (
            nom, app.univers.t, time.time() - t0))


def test_interface():
    app = jeu_main.Application(tactile=True)
    app.aller_menu()
    sc = app.scene
    sc.dessiner(app.ecran)
    next(b for b in sc.boutons if b.libelle == "Scénarios").action()
    sc.dessiner(app.ecran)
    pygame.image.save(app.ecran, "/tmp/scenarios_liste.png")
    assert len(sc.boutons) == len(scenarios.MISSIONS) + 1              # les missions, et « Retour »
    i = [s.ident for s in scenarios.MISSIONS].index("apollo11")        # boutons sans libellé :
    sc.boutons[i].action()                                             # repéré dans l'ordre de la liste
    assert app.tuto.s.ident == "apollo11"
    for _ in range(3):
        app.scene.maj(1 / 60)
    app.scene.dessiner(app.ecran)
    pygame.image.save(app.ecran, "/tmp/scenarios_apollo11.png")
    assert any(b.libelle == "Recommencer" or b.libelle == "↺" for b in app.scene.hud.boutons)
    # un crash : « Réessayer » relance la mission
    app = nouvelle("spoutnik")
    tourner(app, lambda a: etape(a) == 1)
    u, v = app.univers, app.univers.actif
    v.gaz = 1.0
    for _ in range(240):
        app.scene.maj(1 / 60)
    x, y, _, _ = u.etat(v)
    r = hypot(x, y)
    v.gaz, v.vx, v.vy, v.mode = 0.0, -x / r * 300.0, -y / r * 300.0, "physique"
    v.cache_etat = (None, None)
    for _ in range(60 * 30):
        app.scene.maj(1 / 60)
        if app.tuto.echec:
            break
    assert app.tuto.echec
    app.scene.dessiner(app.ecran)
    next(b for b in app.scene.boutons if b.libelle == "Réessayer").action()
    assert not app.tuto.echec and app.univers is not u and app.tuto.s.ident == "spoutnik"
    print("   interface : liste des missions, bulle MISSION, Réessayer après un crash")


if __name__ == "__main__":
    test_interface()
    test_missions_jouees_jusquau_bout()
    for f in ("sauvegarde.json", "reglages.json"):
        if os.path.exists(f):
            os.remove(f)
    print("--- scénarios : OK")
