# -*- coding: utf-8 -*-
"""Musique d'ambiance : notes fabriquées, compositeur, humeurs, réglage du son."""
import os, sys, tempfile, time
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pygame
from jeu import musique, sons, reglages


def test_fabrication():
    dossier = tempfile.mkdtemp()
    t = time.time()
    musique.fabriquer_tout(dossier)
    duree = time.time() - t
    fichiers = [f for f in os.listdir(dossier) if f.endswith(".wav")]
    print("   %d notes fabriquées en %.2f s" % (len(fichiers), duree))
    assert len(fichiers) == len(musique.recettes()) > 10


def test_compositeur_et_humeurs():
    import main as jeu_main
    from jeu import triche
    app = jeu_main.Application(tactile=True)
    assert sons.ACTIF and pygame.mixer.get_num_channels() >= len(sons.BOUCLES) + sons.CANAUX_MUSIQUE
    comp = musique.COMPOSITEUR
    debut = time.time()
    while not comp.pret and time.time() - debut < 60:          # fabrication en arrière-plan
        time.sleep(0.05)
    assert comp.pret
    humeurs = [app.humeur_musique()]
    reglages.SON = "tout"
    for _ in range(600):                                         # 10 s de menu
        musique.maj(1 / 60, app.humeur_musique())
    joue = comp.notes_jouees
    for mode in ("sans_musique", "effets", "aucun"):             # pas de musique dans ces modes
        reglages.SON = mode
        for _ in range(300):
            musique.maj(1 / 60, "menu")
        assert comp.notes_jouees == joue, mode
    reglages.SON = "tout"
    app.nouvelle_partie(True)
    humeurs.append(app.humeur_musique())                         # hangar
    app.scene.lancer()
    humeurs.append(app.humeur_musique())                         # sur le pas de tir
    u = app.univers
    triche.mettre_en_orbite(u, u.actif)
    humeurs.append(app.humeur_musique())                         # en orbite
    lune = u.par_nom["Lune"]
    u.actif.corps = lune
    triche.mettre_en_orbite(u, u.actif)
    humeurs.append(app.humeur_musique())                         # autour de la Lune
    print("   %d notes jouées en 10 s ; humeurs : %s" % (joue, humeurs))
    assert joue > 5 and humeurs == ["menu", "hangar", "decollage", "espace", "mystere"]


if __name__ == "__main__":
    test_fabrication()
    test_compositeur_et_humeurs()
    for f in ("sauvegarde.json", "reglages.json"):
        if os.path.exists(f):
            os.remove(f)
    print("--- musique : OK")
