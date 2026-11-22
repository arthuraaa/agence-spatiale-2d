# -*- coding: utf-8 -*-
"""Sons fabriqués par le code : recettes, boucles sans claquement, cache, réglage, déclenchement en vol."""
import os, sys, time, io, wave
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
from array import array
from jeu import sons, reglages
from test_vol import modele, DT


def echantillons(nom):
    with wave.open(io.BytesIO(sons.fabriquer_wav(nom))) as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, sons.FREQ)
        return array("h", w.readframes(w.getnframes()))


def test_recettes():
    """Chaque son existe, n'est pas muet, ne sature pas ; les boucles se raccordent sans claquer."""
    for nom in sons.RECETTES:
        x = echantillons(nom)
        crete = max(abs(v) for v in x)
        assert 3000 < crete <= 32767, (nom, crete)
        if nom in sons.BOUCLES:
            ecart_moyen = sum(abs(x[i + 1] - x[i]) for i in range(len(x) - 1)) / (len(x) - 1)
            saut = abs(x[0] - x[-1])                 # ce qu'on entend quand la boucle recommence
            assert saut < 6 * ecart_moyen + 50, (nom, saut, ecart_moyen)
    print("   %d sons fabriqués ; les %d boucles se raccordent sans claquement"
         % (len(sons.RECETTES), len(sons.BOUCLES)))


def test_mixeur_cache_reglage():
    import pygame
    pygame.mixer.pre_init(sons.FREQ, -16, 2, 1024)
    pygame.init()
    assert sons.initialiser() and len(sons._sons) == len(sons.RECETTES)
    assert sons.cache_complet()
    t = time.time()
    sons._sons.clear()
    sons.initialiser()
    print("   mixeur %s ; relecture du cache : %.3f s" % (pygame.mixer.get_init(), time.time() - t))
    assert time.time() - t < 0.5
    ancien = reglages.SON
    vus = []
    for _ in range(len(reglages.NOMS_SON)):          # tout -> sans musique -> effets -> coupé -> tout
        reglages.changer_son()
        vus.append(reglages.SON)
    assert vus == ["sans_musique", "effets", "aucun", "tout"] if ancien == "tout" else len(set(vus)) == 4
    reglages.SON = "aucun"
    sons._dernier.pop("bip", None)
    sons.jouer("bip")
    assert "bip" not in sons._dernier, "son coupé : rien ne doit être joué"
    reglages.SON = "tout"
    sons.jouer("bip")
    assert "bip" in sons._dernier


def test_bruitages_en_vol():
    """Le décollage fait gronder le moteur et souffler le vent ; ÉTAGE, nœud et crash font du bruit."""
    import main as jeu_main
    reglages.SON = "tout"
    app = jeu_main.Application(tactile=False)
    app.nouvelle_partie(True)
    app.scene.charger_modele(4)                       # Hercule
    app.scene.lancer()
    sc, u = app.scene, app.univers
    a = u.actif
    a.gaz = 1.0
    for _ in range(60 * 12):
        sc.maj(1 / 60)
    print("   décollage : moteur %.2f, vent %.2f, ambiance %.2f" % (
        sons._volumes.get("moteur", 0), sons._volumes.get("vent", 0), sons._volumes.get("ambiance", 0)))
    assert sons._volumes["moteur"] > 0.9 and sons._volumes["vent"] > 0.05
    entendus = []
    ancien_jouer = sons.jouer
    sons.jouer = lambda nom, volume=1.0: entendus.append(nom)
    try:
        u.separer_etage()                              # les boosters
        a.gaz = 0.0
        sc.maj(1 / 60)
        for _ in range(10):
            sc.maj(1 / 60)
    finally:
        sons.jouer = ancien_jouer
    print("   bruitages entendus :", sorted(set(entendus)))
    for _ in range(30):
        sc.maj(1 / 60)
    assert sons._volumes["moteur"] < 0.05, "moteurs coupés : plus de grondement"
    assert "separation" in entendus
    from jeu import tutoriel                          # un nœud posé en orbite fait « bip »
    tutoriel.demarrer(app, "manoeuvres")
    u2 = app.univers
    assert u2.placer_noeud(u2.t + 200.0) is not None and "bip" in u2.bruits
    app.aller_menu()
    app.scene.maj(1 / 60)
    assert sons._volumes["moteur"] == 0.0 and sons._volumes["vent"] == 0.0


if __name__ == "__main__":
    test_recettes()
    test_mixeur_cache_reglage()
    test_bruitages_en_vol()
    from jeu import sauvegarde as _s                  # ce test a écrit des réglages : on range
    _f = os.path.join(os.path.dirname(_s.chemin_sauvegarde()), "reglages.json")
    if os.path.exists(_f):
        os.remove(_f)
    print("--- sons : OK")
