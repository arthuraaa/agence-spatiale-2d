# -*- coding: utf-8 -*-
"""
Fabrique les visuels de la fiche Google Play, dans store/ :

    python outils/generer_visuels_store.py

  - store/icone-512.png           icône 512 x 512 ;
  - store/banniere-1024x500.png   « image de présentation » (feature graphic) ;
  - store/captures/*.png          captures 1920 x 1080 (16:9 : Google Play refuse les
                                  captures plus allongées que 2:1, donc pas le 20:9 d'un téléphone).

Les captures sont prises dans le vrai jeu, en mode tactile, sans ouvrir de fenêtre.
"""
import os
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["AGENCE_ECRAN"] = "1920x1080"
RACINE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, RACINE)
os.chdir(RACINE)
from math import atan2, hypot, pi, cos, sin
import random
import pygame

STORE = os.path.join(RACINE, "store")
TAILLE = (1920, 1080)


def sauver(surface, nom):
    chemin = os.path.join(STORE, "captures", nom + ".png")
    pygame.image.save(pygame.transform.smoothscale(surface, TAILLE), chemin)
    print("  " + os.path.relpath(chemin, RACINE))


def image(app, n=3):
    for _ in range(n):
        app.scene.maj(1 / 60)
    app.scene.dessiner(app.ecran)
    return app.ecran.copy()


def captures():
    import main as jeu_main
    from jeu import tutoriel, pilote, reglages
    from jeu.pieces import MODELES
    from jeu.vaisseau import construire
    reglages.AIDES = True

    def nouvelle():
        app = jeu_main.Application(tactile=True)
        reglages.AIDES = True
        return app

    # 1) décollage d'une fusée à boosters
    app = nouvelle()
    app.nouvelle_partie(True)
    app.scene.charger_modele(next(k for k, m in enumerate(MODELES) if m[0] == "Hercule"))
    app.scene.lancer()
    app.univers.lancer_pilote(pilote.MiseEnOrbite())
    for _ in range(60 * 9):
        app.scene.maj(1 / 60)
    app.scene.cam.zoom = 6.0
    sauver(image(app, 1), "1-decollage")
    # 2) le hangar
    app = nouvelle()
    app.nouvelle_partie(True)
    app.scene.charger_modele(next(k for k, m in enumerate(MODELES) if m[0] == "Hercule"))
    sauver(image(app), "2-hangar")
    # 3) Apollo 11 autour de la Lune
    app = nouvelle()
    tutoriel.demarrer(app, "apollo11")
    image(app)
    app.tuto.suivant()
    sauver(image(app), "3-apollo11")
    # 4) une manœuvre planifiée en orbite
    app = nouvelle()
    tutoriel.demarrer(app, "manoeuvres")
    app.tuto = None
    u, v = app.univers, app.univers.actif
    o = v.orbite
    u.placer_noeud(u.t + 0.25 * o.periode, pro=70.0)
    sauver(image(app, 5), "4-manoeuvre")
    # 5) approche de la station
    app = nouvelle()
    app.nouvelle_partie(True)
    app.scene.lancer()
    u = app.univers
    station = u.vaisseaux[0]
    x, y, vx, vy = u.etat(station)
    t = hypot(vx, vy)
    v = construire("Navette", ["port", "capsule", "reservoir_s", "moustique"], u.terre)
    v.x, v.y, v.vx, v.vy = x - vx / t * 600.0, y - vy / t * 600.0, vx + vy / t * 1.5, vy - vx / t * 1.5
    v.angle, v.mode = atan2(vy, vx), "physique"
    u.vaisseaux.append(v)
    u.actif = v
    u.cibler(station)
    u.lancer_pilote(pilote.Amarrage(station))
    for _ in range(60 * 60 * 10):
        app.scene.maj(1 / 60)
        geo = pilote.geometrie_amarrage(u, v, station)
        if geo is not None and geo["distance"] < 18.0:
            break
    app.scene.cam.zoom = 8.0
    sauver(image(app, 1), "5-amarrage")
    # 6) descente vers la Lune, panneau d'atterrissage
    app = nouvelle()
    tutoriel.demarrer(app, "lune")
    app.tuto = None
    u, v = app.univers, app.univers.actif
    u.lancer_pilote(pilote.Atterrissage())
    for _ in range(60 * 60 * 20):
        app.scene.maj(1 / 60)
        if u.altitude(v) < 900 and v.mode != "pose":
            break
    app.scene.cam.zoom = 1.2
    sauver(image(app, 1), "6-alunissage")


def banniere():
    """Image de présentation 1024 x 500 : ciel étoilé, planète, fusée, titre."""
    random.seed(7)
    s = pygame.Surface((1024, 500))
    for y in range(500):                                    # dégradé du noir vers le bleu nuit
        k = y / 500.0
        pygame.draw.line(s, (int(6 + 10 * k), int(10 + 18 * k), int(24 + 40 * k)), (0, y), (1024, y))
    for _ in range(260):
        x, y = random.randrange(1024), random.randrange(500)
        c = random.randint(120, 255)
        s.set_at((x, y), (c, c, min(255, c + 20)))
    pygame.draw.circle(s, (40, 90, 170), (760, 1180), 820)  # la Terre, en bas à droite
    pygame.draw.circle(s, (70, 140, 220), (760, 1180), 820, 6)
    pygame.draw.circle(s, (205, 205, 215), (905, 95), 38)   # la Lune
    pygame.draw.circle(s, (170, 170, 182), (893, 88), 9)
    pygame.draw.circle(s, (170, 170, 182), (918, 108), 6)
    icone = pygame.image.load(os.path.join(RACINE, "icone.png")).convert_alpha()
    s.blit(pygame.transform.smoothscale(icone, (300, 300)), (640, 150))
    gros = pygame.font.Font(os.path.join(RACINE, "jeu", "polices", "DejaVuSans-Bold.ttf"), 64)
    moyen = pygame.font.Font(os.path.join(RACINE, "jeu", "polices", "DejaVuSans.ttf"), 30)
    s.blit(gros.render("AGENCE", True, (238, 242, 255)), (60, 120))
    s.blit(gros.render("SPATIALE 2D", True, (238, 242, 255)), (60, 195))
    s.blit(moyen.render("Construis, lance, pose-toi sur la Lune", True, (120, 205, 240)), (62, 292))
    chemin = os.path.join(STORE, "banniere-1024x500.png")
    pygame.image.save(s, chemin)
    print("  " + os.path.relpath(chemin, RACINE))


def main():
    pygame.init()
    pygame.display.set_mode((1, 1))
    os.makedirs(os.path.join(STORE, "captures"), exist_ok=True)
    icone = pygame.image.load(os.path.join(RACINE, "icone.png"))
    # Google Play veut un carré plein : il arrondit lui-même les coins. On remplit donc les
    # coins transparents de l'icône du jeu avec le bleu nuit de son fond.
    carre = pygame.Surface((512, 512))
    carre.fill(icone.get_at((2, icone.get_height() // 2))[:3])
    carre.blit(pygame.transform.smoothscale(icone, (512, 512)), (0, 0))
    pygame.image.save(carre, os.path.join(STORE, "icone-512.png"))
    print("  store/icone-512.png")
    banniere()
    captures()
    for f in ("sauvegarde.json", "reglages.json"):
        if os.path.exists(os.path.join(RACINE, f)):
            os.remove(os.path.join(RACINE, f))


if __name__ == "__main__":
    main()
