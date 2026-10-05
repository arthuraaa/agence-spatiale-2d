# -*- coding: utf-8 -*-
"""Tutoriel : chaque scénario est joué jusqu'au bout, en faisant exactement ce que dit la bulle."""
import os, sys
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ["AGENCE_LANGUE"] = "fr"          # ce test clique sur des libellés français
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
from math import atan2, hypot, pi
import pygame
import main as jeu_main
from jeu import tutoriel, pilote, reglages, sauvegarde
from jeu.vaisseau import porteurs_actifs

APP = {}


def app_(tactile=False):
    if tactile not in APP:
        APP[tactile] = jeu_main.Application(tactile=tactile)
    reglages.AIDES = True
    return APP[tactile]


def jouer(sc, secondes, jusqua=None, accel=None):
    """Fait tourner l'écran en cours (simulation + tutoriel) ; s'arrête quand jusqua() est vrai."""
    for _ in range(int(secondes * 60)):
        if accel is not None:
            sc.u.accel = accel
        sc.maj(1 / 60)
        if jusqua is not None and jusqua():
            return True
    return jusqua is None


def etape(app):
    return app.tuto.k


def finir(app):
    """La dernière étape est une conclusion : on clique « Suivant »."""
    app.tuto.suivant()
    assert app.tuto.termine


def test_hangar():
    app = app_()
    tutoriel.demarrer(app, "hangar")
    sc = app.scene
    assert sc.cles == []
    sc.maj(1 / 60)
    assert etape(app) == 0 and app.tuto.etape.fini is None      # présentation : bouton « Suivant »
    app.tuto.suivant()
    for k, cle in enumerate(("capsule", "reservoir_m", "alize")):
        sc.ajouter(cle)
        sc.maj(1 / 60)
        assert etape(app) == k + 2, (cle, etape(app))
    for cle in ("decoupleur", "reservoir_l", "mistral"):
        sc.ajouter(cle)
    sc.maj(1 / 60)
    assert etape(app) == 5
    sc.lancer()
    app.scene.maj(1 / 60)
    assert etape(app) == 6
    finir(app)


def test_hangar_tete_de_fusee():
    """La capsule doit être tout en haut ; si une étape a été sautée, la bulle dit ce qui manque."""
    app = app_(True)
    tutoriel.demarrer(app, "hangar")
    sc = app.scene
    app.tuto.suivant()                                  # après la présentation : la tête de la fusée
    sc.ajouter("reservoir_m")                           # on commence par autre chose...
    sc.ajouter("capsule")                               # ... la capsule arrive dessous
    for _ in range(3):
        sc.maj(1 / 60)
    assert etape(app) == 1, "la capsule n'est pas en haut : l'étape attend"
    indice = tutoriel._aide_tete(sc)
    print("   indice :", tutoriel.formater(indice, True))
    assert "tout en haut" in indice
    sc.dessiner(app.ecran)                              # la bulle affiche l'indice sans erreur
    sc.deplacer(-1)                                     # on la remonte avec ▲
    sc.maj(1 / 60)
    assert etape(app) == 2 and sc.cles[0] == "capsule"
    # autre partie : on saute l'étape de la capsule, puis on essaie de lancer
    tutoriel.demarrer(app, "hangar")
    sc = app.scene
    while etape(app) < 5:
        app.tuto.suivant()
    for cle in ("reservoir_m", "alize"):
        sc.ajouter(cle)
    indice = tutoriel._aide_lancer(sc)
    print("   à LANCER sans capsule :", indice)
    assert "tête de la fusée" in indice
    sc.maj(1 / 60)
    sc.dessiner(app.ecran)
    pygame.image.save(app.ecran, "/tmp/tuto_hangar_indice.png")
    sc.lancer()
    assert app.scene is sc, "sans capsule, le lancement est refusé"


def test_crash_et_reessayer():
    """On s'écrase : la bulle le dit, donne un conseil, et « Réessayer » relance le tuto."""
    app = app_(True)
    tutoriel.demarrer(app, "decollage")
    sc, u = app.scene, app.univers
    v = u.actif
    v.gaz = 1.0
    jouer(sc, 4)                                        # la fusée a décollé
    v.gaz = 0.0
    x, y, _, _ = u.etat(v)
    r = (x * x + y * y) ** 0.5
    v.vx, v.vy = -x / r * 250.0, -y / r * 250.0         # et pique droit vers le sol
    v.cache_etat = (None, None)
    assert jouer(sc, 20, lambda: app.tuto.echec), "le crash doit être détecté"
    sc.dessiner(app.ecran)
    libelles = [b.libelle for b in sc.boutons]
    assert "Réessayer" in libelles and "Quitter" in libelles, libelles
    pygame.image.save(app.ecran, "/tmp/tuto_crash.png")
    l, h = app.ecran.get_size()
    b = next(b for b in sc.boutons if b.libelle == "Réessayer")
    for t in (pygame.FINGERDOWN, pygame.FINGERUP):      # on tape « Réessayer » au doigt
        sc.evenement(pygame.event.Event(t, finger_id=3, x=b.rect.centerx / l, y=b.rect.centery / h,
                                        dx=0.0, dy=0.0, touch_id=0))
    assert app.univers is not u, "un univers neuf"
    assert not app.tuto.echec and etape(app) == 0
    assert app.univers.actif.mode == "pose", "la fusée est de retour sur le pas de tir"
    app.scene.maj(1 / 60)
    app.scene.dessiner(app.ecran)
    assert any(b.libelle in ("Recommencer", "↺") for b in app.scene.hud.boutons), "bouton Recommencer"
    print("   crash détecté, conseil affiché, « Réessayer » relance le tuto")


def test_decollage():
    app = app_()
    tutoriel.demarrer(app, "decollage")
    sc, a = app.scene, app.univers.actif
    a.gaz = 1.0
    assert jouer(sc, 1, lambda: etape(app) == 1)
    assert jouer(sc, 60, lambda: etape(app) == 3)
    a.gaz = 0.0
    assert jouer(sc, 1, lambda: etape(app) == 4)
    finir(app)


def test_etages():
    app = app_()
    tutoriel.demarrer(app, "etages")
    sc, u = app.scene, app.univers
    u.actif.gaz = 1.0
    assert jouer(sc, 40, lambda: etape(app) == 2), "boosters vides"
    u.separer_etage()
    assert jouer(sc, 1, lambda: etape(app) == 3)
    assert jouer(sc, 60, lambda: u.actif.etage_epuise())
    u.separer_etage()
    assert jouer(sc, 1, lambda: etape(app) == 4)
    finir(app)


def test_orbite():
    """Comme un joueur : virage progressif, coupure à Ap > 13 km, attente, PRO et plein gaz."""
    app = app_()
    tutoriel.demarrer(app, "orbite")
    sc, u = app.scene, app.univers
    a = u.actif
    a.gaz = 1.0
    a.sas = "off"
    for _ in range(60 * 200):
        x, y = u.etat(a)[:2]
        alt = hypot(x, y) - a.corps.R
        a.angle = atan2(y, x) + min(pi / 2, (pi / 2) * max(0.0, (alt - 150) / 5500) ** 0.55)
        if a.etage_epuise():
            u.separer_etage()
        sc.maj(1 / 60)
        if etape(app) >= 3:
            break
    assert etape(app) == 3, etape(app)
    a.gaz = 0.0
    assert jouer(sc, 1, lambda: etape(app) == 4)
    assert jouer(sc, 120, lambda: etape(app) == 5, accel=3)
    u.accel = 0
    a.sas, a.gaz = "pro", 1.0
    assert jouer(sc, 1, lambda: etape(app) == 6)
    assert jouer(sc, 120, lambda: pilote.poussee_max(a) <= 0 or (a.orbite and a.orbite.rp - a.corps.R > 9_500))
    a.gaz = 0.0
    assert jouer(sc, 1, lambda: etape(app) == 7), (a.orbite.rp - a.corps.R)
    finir(app)


def test_manoeuvres():
    app = app_()
    tutoriel.demarrer(app, "manoeuvres")
    sc, u = app.scene, app.univers
    a = u.actif
    u.placer_noeud(u.t + 200.0)
    assert jouer(sc, 1, lambda: etape(app) == 1)
    a.noeud.pro = 100.0
    u.recalculer_plan()
    assert jouer(sc, 1, lambda: etape(app) == 2)
    u.lancer_pilote(pilote.ExecuterNoeud())
    assert jouer(sc, 600, lambda: etape(app) == 3)
    finir(app)


def test_amarrage():
    app = app_()
    tutoriel.demarrer(app, "amarrage")
    sc, u = app.scene, app.univers
    station = tutoriel._station(u)
    geo = pilote.geometrie_amarrage(u, u.actif, station)
    assert 45 < geo["distance"] < 55 and abs(geo["erreur"]) < 0.01, geo
    u.cibler(station)
    assert jouer(sc, 1, lambda: etape(app) == 1)
    u.actif.sas = "cible"
    assert jouer(sc, 1, lambda: etape(app) == 2)
    u.actif.rcs = True
    assert jouer(sc, 1, lambda: etape(app) == 3)
    u.lancer_pilote(pilote.Amarrage(station))
    assert jouer(sc, 300, lambda: etape(app) == 5), etape(app)
    finir(app)


def test_lune():
    app = app_()
    tutoriel.demarrer(app, "lune")
    sc, u = app.scene, app.univers
    a = u.actif
    a.sas = "retro"
    assert jouer(sc, 1, lambda: etape(app) == 1)
    jouer(sc, 8)                                       # le SAS retourne la fusée
    a.gaz = 1.0
    assert jouer(sc, 120, lambda: a.orbite.rp < a.corps.R)
    a.gaz = 0.0
    assert jouer(sc, 1, lambda: etape(app) == 2)
    assert jouer(sc, 900, lambda: etape(app) == 3, accel=3)
    u.accel = 0
    # descente freinée, comme un joueur appliqué : on vise une accélération (annuler la vitesse
    # horizontale, suivre une vitesse verticale qui diminue près du sol) et on y pointe la fusée
    c = a.corps
    for _ in range(60 * 900):
        x, y, vx, vy = u.etat(a)
        r = hypot(x, y)
        ux, uy = x / r, y / r
        w = c.vitesse_rotation
        svx, svy = vx + w * y, vy - w * x
        v_vert = svx * ux + svy * uy
        hx, hy = svx - v_vert * ux, svy - v_vert * uy        # vitesse horizontale
        alt = r - c.R - a.geometrie().bas
        a_max = pilote.poussee_max(a) / a.masse()
        voulue = -max(1.5, min(60.0, 0.08 * alt))
        av = c.g + (voulue - v_vert) * 1.2
        gx, gy = av * ux - 0.6 * hx, av * uy - 0.6 * hy
        a.angle = atan2(gy, gx) if alt > 3 else atan2(uy, ux)
        a.gaz = max(0.0, min(1.0, hypot(gx, gy) / a_max)) if alt < 6000 or hypot(hx, hy) > 5 else 0.0
        sc.maj(1 / 60)
        if a.mode == "pose" or a.detruit:
            break
    print("   (Lune : %s à %.0f m, vitesse verticale %.1f m/s, carburant %.0f kg, messages %s)" % (
        a.mode, u.altitude(a), v_vert, a.carburant_actif()[0], [m[0] for m in u.messages[-2:]]))
    assert a.mode == "pose" and not a.detruit
    assert jouer(sc, 1, lambda: etape(app) == 5), etape(app)
    finir(app)


def test_retour():
    app = app_()
    tutoriel.demarrer(app, "retour")
    sc, u = app.scene, app.univers
    a = u.actif
    a.sas = "retro"
    assert jouer(sc, 1, lambda: etape(app) == 1)
    jouer(sc, 8)
    a.gaz = 1.0
    assert jouer(sc, 120, lambda: a.orbite.rp - a.corps.R < 2_500)
    a.gaz = 0.0
    assert jouer(sc, 1, lambda: etape(app) == 2)
    u.separer_etage()
    assert jouer(sc, 1, lambda: etape(app) == 3)
    a = u.actif
    assert jouer(sc, 900, lambda: etape(app) == 4, accel=3)
    u.accel = 0
    assert jouer(sc, 300, lambda: hypot(*u.etat(a)[2:]) < 230)
    u.ouvrir_parachute()
    assert jouer(sc, 1, lambda: etape(app) == 5)
    assert jouer(sc, 600, lambda: etape(app) == 6, accel=2), (a.mode, a.detruit)
    finir(app)


def test_bulle_menu_et_sauvegarde():
    """Bulle sur PC et au doigt, liste des tutos dans le menu, et la vraie partie n'est pas touchée."""
    chemin = sauvegarde.chemin_sauvegarde()
    avant = os.path.getmtime(chemin) if os.path.exists(chemin) else None
    for tactile in (False, True):
        app = app_(tactile)
        for s in tutoriel.SCENARIOS:
            tutoriel.demarrer(app, s.ident)
            for _ in range(3):
                app.scene.maj(1 / 60)
                app.scene.dessiner(app.ecran)
            libelles = [b.libelle for b in getattr(app.scene, "hud", app.scene).boutons]
            assert "Quitter" in libelles and ("Passer" in libelles or "Suivant ›" in libelles), (s.ident, libelles)
        pygame.image.save(app.ecran, "/tmp/tuto_%s.png" % ("tactile" if tactile else "pc"))
    # au doigt : « Passer », puis « Quitter » ramène à la liste des tutos
    app = app_(True)
    tutoriel.demarrer(app, "orbite")
    sc = app.scene
    sc.maj(1 / 60)
    sc.dessiner(app.ecran)
    l, h = app.ecran.get_size()

    def taper(libelle):
        b = next(b for b in sc.hud.boutons if b.libelle == libelle)
        x, y = b.rect.center
        for t in (pygame.FINGERDOWN, pygame.FINGERUP):
            sc.evenement(pygame.event.Event(t, finger_id=7, x=x / l, y=y / h, dx=0.0, dy=0.0, touch_id=0))
        sc.maj(1 / 60)
        sc.dessiner(app.ecran)

    taper("Passer")
    assert app.tuto.k == 1
    taper("Quitter")
    assert app.tuto is None and app.scene.vue == "tutos"
    app.scene.dessiner(app.ecran)
    assert len(app.scene.boutons) == len(tutoriel.SCENARIOS) + 1
    pygame.image.save(app.ecran, "/tmp/tuto_liste.png")
    apres = os.path.getmtime(chemin) if os.path.exists(chemin) else None
    assert avant == apres, "un tutoriel ne doit jamais écrire la sauvegarde"
    print("   bulles PC et tactile, liste des tutos, sauvegarde intacte : OK")


if __name__ == "__main__":
    for nom in ("hangar", "decollage", "etages", "orbite", "manoeuvres", "amarrage", "lune", "retour"):
        globals()["test_" + nom]()
        print("   tuto « %s » : terminé" % tutoriel.PAR_ID[nom].titre)
    test_bulle_menu_et_sauvegarde()
    test_hangar_tete_de_fusee()
    test_crash_et_reessayer()
    from jeu import sauvegarde as _s                  # ce test a écrit des réglages : on range
    _f = os.path.join(os.path.dirname(_s.chemin_sauvegarde()), "reglages.json")
    if os.path.exists(_f):
        os.remove(_f)
    print("--- tutoriel : OK")
