# -*- coding: utf-8 -*-
"""Aides au pilotage : tout est piloté par le pilote automatique, comme dans le jeu."""
import os, sys, tempfile
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
from math import hypot
from jeu.univers import Univers
from jeu import pilote, reglages
from test_vol import modele, DT


def laisser_piloter(u, limite=400_000):
    """Fait tourner la simulation tant que le pilote automatique travaille."""
    while u.pilote is not None and limite > 0:
        u.avancer(DT)
        limite -= 1
    return u.pilote is None


def orbite_auto(nom):
    u = Univers(bac_a_sable=True)
    v = u.lancer(nom, modele(nom))
    u.lancer_pilote(pilote.MiseEnOrbite())
    for _ in range(60 * 40):                  # la montée : aucune alerte d'atterrissage
        u.avancer(DT)
        assert pilote.infos_atterrissage(u, v) is None, "fausse alerte pendant la montée"
    assert laisser_piloter(u), "le pilote n'a pas fini"
    o = v.orbite
    ok = v.mode == "rails" and o.elliptique and o.rp - v.corps.R > v.corps.atm_h + 500
    print("   %-9s Pe %5.1f km  Ap %5.1f km  Δv restant %4.0f m/s  débris %d" % (
        nom, (o.rp - v.corps.R) / 1e3, (o.ra - v.corps.R) / 1e3, v.delta_v(), len(u.vaisseaux) - 2))
    assert ok, nom
    return u, v


def test_mise_en_orbite():
    """Du pas de tir à l'orbite, sans aucune intervention : le SAS fait tourner la fusée."""
    for nom in ("Pionnier", "Hercule", "Sélène", "Arès"):
        orbite_auto(nom)


def test_circularisation():
    u, v = orbite_auto("Hermès")
    assert pilote.planifier_circularisation(u, v) and v.noeud is not None
    u.lancer_pilote(pilote.ExecuterNoeud())
    assert laisser_piloter(u)
    o = v.orbite
    print("   circularisée : Pe %.2f km, Ap %.2f km (écart %.1f %%)" % (
        (o.rp - v.corps.R) / 1e3, (o.ra - v.corps.R) / 1e3, 100 * (o.ra - o.rp) / o.ra))
    assert v.noeud is None and (o.ra - o.rp) / o.ra < 0.01


def test_transfert_lune():
    """Assistant : nœud de départ vers la Lune, puis exécution automatique ; la rencontre doit rester."""
    u, v = orbite_auto("Sélène")
    lune = u.par_nom["Lune"]
    u.cibler(lune)
    assert pilote.planifier_transfert(u, v, lune), [m[0] for m in u.messages]
    assert any(tr.entree and tr.corps is lune for tr in v.plan), "le plan doit rencontrer la Lune"
    print("   plan :", u.messages[-1][0])
    u.lancer_pilote(pilote.ExecuterNoeud())
    assert laisser_piloter(u)
    u._predire(v)
    tr = next((t for t in v.troncons if t.entree and t.corps is lune), None)
    assert tr is not None, "après exécution, la trajectoire réelle doit rencontrer la Lune : %s" % (
        [(t.corps.nom, t.fin) for t in v.troncons])
    print("   exécuté : rencontre réelle, périapside lunaire %.0f km dans %.1f h" % (
        (tr.orbite.rp - lune.R) / 1e3, (tr.t0 - u.t) / 3600))
    # capture : on laisse arriver dans la sphère de la Lune, puis « Circulariser » au périapside
    for _ in range(200_000):
        if v.corps is lune:
            break
        u.accel = 10
        u.avancer(DT)
    assert v.corps is lune
    u.accel = 0
    assert pilote.planifier_circularisation(u, v)
    u.lancer_pilote(pilote.ExecuterNoeud())
    assert laisser_piloter(u)
    o = v.orbite
    print("   capture : orbite lunaire Pe %.0f km, Ap %.0f km" % ((o.rp - lune.R) / 1e3, (o.ra - lune.R) / 1e3))
    assert o.elliptique and o.rp > lune.R and (o.ra - o.rp) / o.ra < 0.05
    # aide à l'atterrissage : désorbitation au-dessus de la Lune (pas d'atmosphère)
    assert pilote.infos_atterrissage(u, v) is None, "rien à afficher en orbite stable"
    v.sas, v.gaz = "retro", 1.0
    for _ in range(60 * 120):
        u.avancer(DT)
        if v.orbite.rp < lune.R - 3_000:
            break
    v.gaz = 0.0
    for _ in range(60 * 120):
        u.avancer(DT)
        if pilote.infos_atterrissage(u, v):
            break
    infos = dict((nom, val) for nom, val, _ in pilote.infos_atterrissage(u, v) or [])
    print("   descente lunaire :", {k: (round(x) if isinstance(x, float) else x) for k, x in infos.items()})
    assert "Impact dans" in infos and "Freinage dans" in infos
    assert 0 < infos["Freinage dans"] < infos["Impact dans"]


def test_transfert_mars():
    """Assistant interplanétaire : fenêtre de tir, départ depuis l'orbite terrestre, rencontre prévue."""
    import time
    u, v = orbite_auto("Arès")
    mars = u.par_nom["Mars"]
    u.cibler(mars)
    t0 = time.time()
    assert pilote.planifier_transfert(u, v, mars)
    duree = time.time() - t0
    print("   %s   (calcul : %.2f s)" % (u.messages[-1][0], duree))
    assert any(tr.entree and tr.corps is mars for tr in v.plan), [(t.corps.nom, t.fin) for t in v.plan]


def test_aide_atterrissage():
    """Retour vers la Terre : le panneau annonce l'entrée dans l'atmosphère."""
    u, v = orbite_auto("Pionnier")
    assert pilote.infos_atterrissage(u, v) is None, "rien à afficher en orbite stable"
    v.sas, v.gaz = "retro", 1.0
    for _ in range(60 * 60):
        u.avancer(DT)
        if v.orbite is not None and v.orbite.rp < v.corps.R + 2_000:
            break
    v.gaz = 0.0
    for _ in range(60 * 600):
        u.accel = 3 if v.mode == "rails" else 0
        u.avancer(DT)
        if pilote.infos_atterrissage(u, v):
            break
    infos = dict((nom, val) for nom, val, _ in pilote.infos_atterrissage(u, v) or [])
    print("   retour sur Terre :", {k: (round(x) if isinstance(x, float) else x) for k, x in infos.items()})
    assert infos["Vit. verticale"] < 0 and ("Entrée atmo. dans" in infos or "Impact dans" in infos)


def test_option_et_interface():
    """L'option masque tout ; activée, le bouton PILOTE propose les bonnes actions et les lance."""
    import pygame
    import main as jeu_main
    reglages.AIDES = True
    app = jeu_main.Application(tactile=False)
    reglages.AIDES = True           # indépendant de reglages.json
    app.nouvelle_partie(True)
    app.scene.lancer()
    sc, u = app.scene, app.univers

    def image():
        sc.maj(1 / 60)
        sc.dessiner(app.ecran)

    image()
    libelles = [b.libelle for b in sc.hud.boutons]
    assert "Pilote auto (G)" in libelles, libelles
    sc.evenement(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_g, scancode=0, unicode="g", mod=0))
    image()
    actions = [b.libelle for b in sc.hud.boutons_popup]
    print("   menu PILOTE sur le pas de tir :", actions)
    assert "Mise en orbite" in actions
    b = next(b for b in sc.hud.boutons_popup if b.libelle == "Mise en orbite")
    sc.evenement(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=b.rect.center, button=1))
    assert isinstance(u.pilote, pilote.MiseEnOrbite)
    for _ in range(120):
        image()
    assert u.actif.gaz == 1.0 and u.actif.mode == "physique", "le pilote doit avoir décollé"
    sc.evenement(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_x, scancode=0, unicode="x", mod=0))
    assert u.pilote is None, "une commande manuelle rend la main"
    # option désactivée : plus de bouton, et « Filer » revient dans le panneau de manœuvre
    chemin = os.path.join(os.path.dirname(sys.modules["jeu.sauvegarde"].chemin_sauvegarde()), "reglages.json")
    sc.basculer_aides()
    assert not reglages.AIDES and os.path.exists(chemin)
    image()
    assert not any(b.libelle.startswith("Pilote") for b in sc.hud.boutons)
    u.lancer_pilote(pilote.MiseEnOrbite())
    assert u.pilote is None, "aides désactivées : le pilote ne démarre pas"
    reglages.AIDES = None
    reglages.charger()
    assert reglages.AIDES is False, "le réglage est relu depuis le disque"
    sc.basculer_aides()
    assert reglages.AIDES
    os.remove(chemin)
    # écran tactile : bouton « Pilote » en haut à droite, menu avec les mêmes actions
    app2 = jeu_main.Application(tactile=True)
    reglages.AIDES = True           # indépendant de reglages.json
    app2.nouvelle_partie(True)
    app2.scene.lancer()
    for _ in range(2):
        app2.scene.maj(1 / 60)
        app2.scene.dessiner(app2.ecran)
    b = next(b for b in app2.scene.hud.boutons if b.libelle == "Pilote")
    app2.scene.hud.clic(b.rect.center)
    app2.scene.dessiner(app2.ecran)
    actions = [x.libelle for x in app2.scene.hud.boutons_popup]
    assert "Mise en orbite" in actions, actions
    pygame.image.save(app2.ecran, os.path.join(tempfile.gettempdir(), "menu_pilote_tactile.png"))
    print("   interface : option, bouton, menu, reprise en main, écran tactile : OK")
    for f in ("sauvegarde.json",):
        if os.path.exists(f):
            os.remove(f)


if __name__ == "__main__":
    test_mise_en_orbite()
    test_circularisation()
    test_transfert_lune()
    test_transfert_mars()
    test_aide_atterrissage()
    test_option_et_interface()
    print("--- aides : OK")
