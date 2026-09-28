# -*- coding: utf-8 -*-
"""Test « singe » : événements aléatoires (touches, clics, molette) sur toutes les scènes, sans écran."""
import os, sys, random
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pygame
import main as jeu_main

TOUCHES = [pygame.K_SPACE, pygame.K_t, pygame.K_r, pygame.K_p, pygame.K_u, pygame.K_v, pygame.K_x,
           pygame.K_w, pygame.K_f, pygame.K_c, pygame.K_n, pygame.K_BACKSPACE, pygame.K_m, pygame.K_h,
           pygame.K_ESCAPE, pygame.K_COMMA, pygame.K_SEMICOLON, pygame.K_RETURN, pygame.K_F5,
           pygame.K_DELETE, pygame.K_UP, pygame.K_DOWN, pygame.K_a, pygame.K_e]


def singe(graine, images=2500):
    rnd = random.Random(graine)
    app = jeu_main.Application()
    app.quitter = lambda: None                       # le singe ne doit pas fermer le jeu
    app.nouvelle_partie(rnd.random() < 0.5)
    scenes = set()
    for k in range(images):
        l, h = app.ecran.get_size()
        r = rnd.random()
        if r < 0.10:
            key = rnd.choice(TOUCHES)
            sc = rnd.choice([0, pygame.KSCAN_1 + rnd.randrange(7)])
            ev = pygame.event.Event(pygame.KEYDOWN, key=key, scancode=sc, unicode="a", mod=0)
            app.scene.evenement(ev)
        elif r < 0.24:
            pos = (rnd.randrange(l), rnd.randrange(h))
            app.scene.evenement(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1))
            app.scene.evenement(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=pos, button=1))
        elif r < 0.30:
            # glisser-déposer : poignées de manœuvre, points de la trajectoire, ou n'importe où
            cibles = list(getattr(app.scene.cam, "poignees", [])) if hasattr(app.scene, "cam") else []
            ech = list(getattr(app.scene.cam, "echantillons", [])) if hasattr(app.scene, "cam") else []
            if cibles and rnd.random() < 0.6:
                pos = tuple(int(c) for c in rnd.choice(cibles)[1])
            elif ech and rnd.random() < 0.5:
                e = rnd.choice(ech)
                pos = (int(e[0]), int(e[1]))
            else:
                pos = (rnd.randrange(l), rnd.randrange(h))
            app.scene.evenement(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1))
            for _ in range(rnd.randrange(1, 5)):
                pos = (pos[0] + rnd.randrange(-60, 61), pos[1] + rnd.randrange(-60, 61))
                app.scene.evenement(pygame.event.Event(pygame.MOUSEMOTION, pos=pos, rel=(0, 0),
                                                       buttons=(1, 0, 0)))
                app.scene.maj(1 / 60)
                app.scene.dessiner(app.ecran)
            app.scene.evenement(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=pos, button=1))
        elif r < 0.36:
            app.scene.evenement(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=rnd.choice([-3, -1, 1, 3])))
        elif r < 0.365:
            app.ecran = pygame.display.set_mode((rnd.choice([1024, 1280, 1600]), rnd.choice([600, 720, 900])),
                                                pygame.RESIZABLE)
        elif r < 0.40 and app.univers is not None and app.univers.actif is not None:
            app.univers.actif.gaz = rnd.random()     # simule l'appui prolongé sur les gaz
            app.univers.commandes.rotation = rnd.choice([-1, 0, 1])
        app.scene.maj(1 / 60)
        app.scene.dessiner(app.ecran)
        scenes.add(type(app.scene).__name__)
    return scenes


if __name__ == "__main__":
    vus = set()
    for g in range(6):
        vus |= singe(g)
        print("graine", g, "OK", sorted(vus))
    sauve = os.path.join(os.path.dirname(__file__), "..", "sauvegarde.json")
    if os.path.exists(sauve):
        os.remove(sauve)
    print("--- interface : OK")
