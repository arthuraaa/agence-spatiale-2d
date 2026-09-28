# -*- coding: utf-8 -*-
"""Menu secret de triche : accès, retour en arrière après un crash, plein, options, carrière."""
import os, sys, time, tempfile
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from math import hypot
import pygame
import main as jeu_main
from jeu import sauvegarde, triche
DT = 1 / 60


def app_en_vol(tactile=False, carriere=False):
    from jeu import reglages
    app = jeu_main.Application(tactile=tactile)
    reglages.TRICHE = True                             # indépendant de reglages.json
    app.nouvelle_partie(not carriere)
    app.scene.lancer()
    return app


def cliquer(sc, libelle):
    b = next(b for b in sc.boutons if b.libelle.startswith(libelle))
    assert b.actif, libelle
    b.action()


def test_acces():
    app = app_en_vol()                                           # PC : F12
    sc = app.scene
    sc.evenement(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F12, scancode=0, unicode="", mod=0))
    assert sc.panneau == "options"
    app = app_en_vol(tactile=True)                               # téléphone : appui long sur l'horloge
    sc = app.scene
    sc.maj(DT)
    sc.dessiner(app.ecran)
    l, h = app.ecran.get_size()
    x, y = sc.hud.rect_temps.center
    sc.evenement(pygame.event.Event(pygame.FINGERDOWN, finger_id=4, x=x / l, y=y / h, dx=0.0, dy=0.0, touch_id=0))
    sc.maj(DT)
    assert sc.panneau is None, "un appui bref ne suffit pas"
    time.sleep(triche.APPUI_LONG + 0.1)
    sc.maj(DT)
    assert sc.panneau == "options"
    sc.dessiner(app.ecran)
    pygame.image.save(app.ecran, "/tmp/triche_tactile.png")
    print("   accès : F12, et appui long sur l'horloge au doigt")


def test_retour_apres_crash():
    app = app_en_vol()
    sc, u = app.scene, app.univers
    v = u.actif
    v.gaz = 1.0
    horloge = [0.0]
    vrai = time.monotonic
    time.monotonic = lambda: horloge[0]                          # une seconde réelle par seconde de jeu
    try:
        for _ in range(60 * 45):
            horloge[0] += DT
            sc.maj(DT)
        t_crash = u.t
        x, y, _, _ = u.etat(v)
        r = hypot(x, y)
        v.gaz, v.vx, v.vy = 0.0, -x / r * 2000.0, -y / r * 2000.0  # piqué droit vers le sol
        v.mode = "physique"
        v.cache_etat = (None, None)
        for _ in range(60 * 120):
            horloge[0] += DT
            sc.maj(DT)
            if u.perdu:
                break
    finally:
        time.monotonic = vrai
    assert u.perdu and u.actif is None, (v.mode, v.detruit, u.altitude(v), [m[0] for m in u.messages[-3:]])
    t_perdu = u.t
    sc.ouvrir("options")
    sc.dessiner(app.ecran)
    t0 = time.time()
    cliquer(sc, "Revenir 30 s")
    duree = time.time() - t0
    n = app.univers
    print("   crash à t=%.0f s ; retour à t=%.0f s (%.0f s plus tôt), en %.2f s ; %d photos" % (
        t_perdu, n.t, t_perdu - n.t, duree, len(app.historique.photos)))
    assert n is not u and n.actif is not None and not n.perdu
    assert 25.0 <= t_perdu - n.t <= 40.0
    app.scene.maj(DT)
    app.scene.dessiner(app.ecran)


def test_options():
    app = app_en_vol()
    sc, u = app.scene, app.univers
    v = u.actif
    v.gaz = 1.0
    for _ in range(60 * 10):
        u.avancer(DT)
    assert v.carburant_actif()[0] < v.carburant_actif()[1]
    sc.ouvrir("options"); sc.dessiner(app.ecran)
    cliquer(sc, "Faire le plein")
    assert v.carburant_actif()[0] == v.carburant_actif()[1]
    sc.dessiner(app.ecran); cliquer(sc, "Carburant infini")
    for _ in range(60 * 10):
        u.avancer(DT)
    assert v.carburant_actif()[0] == v.carburant_actif()[1], "carburant infini"
    sc.dessiner(app.ecran); cliquer(sc, "Indestructible")
    x, y, _, _ = u.etat(v)
    r = hypot(x, y)
    v.gaz, v.vx, v.vy = 0.0, -x / r * 150.0, -y / r * 150.0
    v.cache_etat = (None, None)
    for _ in range(60 * 60):
        u.avancer(DT)
        if v.mode == "pose" or v.detruit:
            break
    assert v.mode == "pose" and not v.detruit, "indestructible : posé malgré 150 m/s"
    sc.dessiner(app.ecran); cliquer(sc, "Mettre en orbite")
    o = v.orbite
    assert v.mode == "rails" and o.rp - v.corps.R > v.corps.atm_h + 2000
    print("   plein, carburant infini, indestructible (posé à 150 m/s), mise en orbite : OK")


def test_carriere_et_sauvegarde():
    app = app_en_vol(carriere=True)
    sc, u = app.scene, app.univers
    assert not u.piece_debloquee("titan")
    fonds = u.fonds
    sc.ouvrir("options"); sc.dessiner(app.ecran)
    cliquer(sc, "+50")
    sc.dessiner(app.ecran)
    cliquer(sc, "Tout débloquer")
    assert u.fonds == fonds + triche.FONDS and u.piece_debloquee("titan")
    u.triche["carburant"] = True
    chemin = os.path.join(tempfile.gettempdir(), "triche_as2d.json")
    sauvegarde.sauvegarder(u, chemin)
    u2 = sauvegarde.charger(chemin)
    os.remove(chemin)
    assert u2.triche == {"pieces": True, "carburant": True} and u2.piece_debloquee("titan")
    print("   carrière : +50 000, tout débloqué, options gardées dans la sauvegarde")


def test_menu_options():
    """Options : page du menu principal, et panneau en vol (réglages | triche)."""
    from jeu import reglages
    app = jeu_main.Application(tactile=True)
    app.aller_menu()
    sc = app.scene
    sc.dessiner(app.ecran)
    b = next(b for b in sc.boutons if b.libelle == "Options")
    b.action()
    sc.dessiner(app.ecran)
    libelles = [b.libelle for b in sc.boutons]
    assert any(x.startswith("Son :") for x in libelles) and any(x.startswith("Aides au pilotage") for x in libelles)
    triche_avant = reglages.TRICHE
    next(b for b in sc.boutons if b.libelle.startswith("Triche en vol")).action()
    assert reglages.TRICHE is (not triche_avant)
    reglages.basculer_triche()                         # on remet comme avant (en mémoire et sur disque)
    sc.dessiner(app.ecran)
    pygame.image.save(app.ecran, "/tmp/options_menu.png")
    next(b for b in sc.boutons if b.libelle == "Retour").action()
    assert sc.vue == "principal"
    # en vol : le menu pause mène aux options ; deux colonnes
    app.nouvelle_partie(True)
    app.scene.lancer()
    sc = app.scene
    sc.ouvrir("pause"); sc.dessiner(app.ecran)
    assert "Options" in [b.libelle for b in sc.boutons]
    assert not any(b.libelle.startswith("Son :") for b in sc.boutons), "le son est rangé dans Options"
    next(b for b in sc.boutons if b.libelle == "Options").action()
    sc.dessiner(app.ecran)
    libelles = [b.libelle for b in sc.boutons]
    assert "Faire le plein" in libelles and any(x.startswith("Son :") for x in libelles) and "Fermer" in libelles
    pygame.image.save(app.ecran, "/tmp/options_vol.png")
    reglages.TRICHE = False                            # triche désactivée : plus de colonne TRICHE
    sc.dessiner(app.ecran)
    assert "Faire le plein" not in [b.libelle for b in sc.boutons]
    reglages.TRICHE = True
    print("   Options : page du menu, panneau en vol (réglages | triche), triche désactivable")


if __name__ == "__main__":
    test_menu_options()
    test_acces()
    test_retour_apres_crash()
    test_options()
    test_carriere_et_sauvegarde()
    for f in ("sauvegarde.json", "reglages.json"):
        if os.path.exists(f):
            os.remove(f)
    print("--- triche : OK")
