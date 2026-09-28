# -*- coding: utf-8 -*-
"""Lance le jeu sans écran (SDL dummy) et enregistre des captures pour vérifier le rendu."""
import os, sys, time
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pygame
from math import atan2
import main as jeu_main
from jeu.pieces import MODELES

SORTIE = sys.argv[1] if len(sys.argv) > 1 else "/tmp/captures"
os.makedirs(SORTIE, exist_ok=True)
app = jeu_main.Application()
n = [0]

def capture(nom, images=2):
    for _ in range(images):
        app.scene.maj(1 / 60)
        app.scene.dessiner(app.ecran)
    n[0] += 1
    pygame.image.save(app.ecran, os.path.join(SORTIE, "%02d_%s.png" % (n[0], nom)))

def touche(k, scancode=0):
    app.scene.evenement(pygame.event.Event(pygame.KEYDOWN, key=k, scancode=scancode, unicode="", mod=0))

capture("menu")
app.nouvelle_partie(True)
capture("hangar_pionnier")
app.scene.charger_modele(4)
app.scene.selection = 3
capture("hangar_selene")
app.scene.menu_modeles = True
capture("hangar_modeles")
app.scene.lancer()
capture("pas_de_tir", 5)
u, sc = app.univers, app.scene
v = u.actif
t0 = time.time()
v.gaz = 1.0
for k in range(60 * 14):
    x, y, vx, vy = u.etat(v)
    if u.altitude(v) > 250:
        v.sas = "off"; v.angle = atan2(y, x) + 0.5; v.omega = 0
    sc.maj(1 / 60)
capture("ascension")
sc.cam.zoom = 0.6
capture("ascension_large")
# suite du vol avec le pilote automatique des tests
sys.path.insert(0, os.path.dirname(__file__))
import test_vol
test_vol.mise_en_orbite(u, v, verbose=True)
u.accel = 0
sc.cam.zoom = 0.004
capture("orbite", 30)
u.cibler(u.par_nom["Lune"])
sc.cam.zoom = 0.0001
capture("carte_terre_lune", 40)
sc.ouvrir("missions"); capture("missions"); sc.ouvrir("missions")
sc.ouvrir("aide"); capture("aide"); sc.ouvrir("aide")
sc.ouvrir("pause"); capture("pause"); sc.ouvrir("pause")
sc.cam.zoom = 3e-7
capture("systeme_interne", 3)
sc.cam.zoom = 1.2e-8
capture("systeme_solaire", 3)
sc.centrer_sur(u.par_nom["Saturne"]); sc.cam.zoom = 2e-4
capture("saturne", 3)
sc.centrer_sur(u.vaisseaux[0]); sc.cam.zoom = 9.0
capture("station", 3)
sc.cam.focus = None; sc.cam.zoom = 6.0
capture("vaisseau_orbite", 3)
print("images par seconde de calcul+dessin (orbite, zoom 6) :", end=" ")
t0 = time.time()
for _ in range(120):
    sc.maj(1 / 60); sc.dessiner(app.ecran)
print("%.0f" % (120 / (time.time() - t0)))
print("captures dans", SORTIE)

# --- nœud de manœuvre -------------------------------------------------------
sys.path.insert(0, os.path.dirname(__file__))
u.cibler(None)
sc.cam.zoom = 0.004
u.accel = 0
u.placer_noeud(u.t + v.orbite.delai_apoapside(u.t), pro=120.0)
capture("noeud_orbite", 3)
u.regler_noeud(t=u.t + 22.0)
sc.cam.zoom = 0.012
capture("noeud_poignees", 3)
u.regler_noeud(t=u.t + v.orbite.delai_apoapside(u.t))
sc.cam.zoom = 0.00012
u.cibler(u.par_nom["Lune"])
u.regler_noeud(pro=284.0, t=u.t + v.orbite.delai_periapside(u.t))
capture("noeud_lune", 3)
