# -*- coding: utf-8 -*-
"""Constantes et réglages du jeu (tout ce qui se règle est ici)."""
from math import radians, pi

TITRE = "Agence Spatiale 2D"
LARGEUR, HAUTEUR = 1280, 720      # taille initiale de la fenêtre (redimensionnable)
FPS = 60

G0 = 9.80665                      # gravité standard, sert au calcul de l'Isp

# --- Temps ------------------------------------------------------------------
# Accélérations du temps. Les 4 premières marchent en mode « physique »
# (poussée, atmosphère). Au-delà, le vaisseau doit être « sur rails »
# (orbite képlérienne calculée exactement, donc stable à toute vitesse).
ACCELERATIONS = [1, 2, 3, 4, 10, 50, 100, 1000, 10_000, 100_000, 1_000_000]
ACCEL_MAX_PHYSIQUE = 3            # index maximum autorisé en mode physique
PAS_PHYSIQUE = 1.0 / 60.0         # pas d'intégration maximum (s)

# --- Affichage ---------------------------------------------------------------
# Vue « depuis le sud » : tout tourne dans le sens horaire à l'écran, donc on
# part vers la DROITE pour se mettre en orbite dans le bon sens (prograde).
MIROIR_X = True
ZOOM_MIN, ZOOM_MAX = 2e-9, 40.0   # pixels par mètre
RAYON_GRAND_CERCLE = 1500         # au-delà (px), on dessine les cercles en polygone

# --- Pilotage ----------------------------------------------------------------
CARDAN = radians(6)               # débattement max de la tuyère (rad)
ALPHA_MIN = 0.06                  # accélération angulaire minimale (rad/s²)
OMEGA_MAX = 1.2                   # vitesse de rotation max visée par le SAS (rad/s)
ISP_RCS = 100.0                   # Isp des propulseurs RCS (s)
PLAFOND_TRAINEE = 120.0           # décélération max due à la traînée (m/s²)

# --- Atterrissage / amarrage -----------------------------------------------
POSE_V_MAX = 8.0                  # vitesse verticale max pour se poser (m/s)
POSE_V_MAX_TRAIN = 14.0           # ... avec un train d'atterrissage
POSE_H_MAX = 8.0                  # vitesse horizontale max (m/s)
POSE_H_MAX_TRAIN = 10.0           # ... avec un train d'atterrissage (il sert à ça)
POSE_INCLINAISON = radians(30)    # inclinaison max
POSE_INCLINAISON_TRAIN = radians(45)
AMARRAGE_DISTANCE = 1.2           # distance max entre les deux ports (m)
AMARRAGE_VITESSE = 2.5            # vitesse relative max (m/s)
AMARRAGE_COS = 0.90               # alignement mini (cosinus de l'angle entre ports)
PORTEE_PHYSIQUE = 100_000.0       # au-delà, les débris en vol atmosphérique sont supprimés

# --- Carrière ---------------------------------------------------------------
FONDS_DEPART = 25_000
TAUX_RECUPERATION = 0.75          # part du prix remboursée quand on récupère un vaisseau
LONGITUDE_PAS_DE_TIR = pi / 2     # position du pas de tir sur la Terre (rad)
NOM_STATION = "Station Alpha"
PLAFOND_DRAPEAUX = 20             # drapeaux plantés max par corps

# --- Couleurs ---------------------------------------------------------------
NOIR = (4, 6, 12)
BLANC = (235, 238, 245)
GRIS = (150, 156, 170)
GRIS_FONCE = (70, 76, 90)
CYAN = (90, 210, 255)
ORANGE = (255, 170, 60)
VERT = (110, 230, 130)
ROUGE = (255, 90, 80)
JAUNE = (255, 225, 90)
MAGENTA = (255, 110, 220)
FOND_PANNEAU = (14, 20, 34)
BORD_PANNEAU = (60, 80, 120)
COULEURS_TRAJECTOIRE = [CYAN, ORANGE, VERT, MAGENTA]
BLEU_PLAN = (150, 160, 255)                       # trajectoire prévue après la manœuvre
COULEURS_PLAN = [BLEU_PLAN, (120, 185, 245), (140, 215, 200), (190, 155, 255)]

# --- Nœuds de manœuvre ------------------------------------------------------
NOEUD_RAYON_POIGNEE = 36          # distance des poignées au centre du nœud (px)
NOEUD_CLIC = 12                   # tolérance de clic sur une poignée ou la trajectoire (px)
NOEUD_SENSIBILITE = 1.0           # m/s par pixel de glissement (Maj : /10, Ctrl : x10)
NOEUD_PAS_MOLETTE = 1.0           # m/s par cran de molette (Maj : /10, Ctrl : x10)
# sur écran tactile, un doigt est moins précis qu'une souris
NOEUD_RAYON_POIGNEE_TACTILE = 52
NOEUD_CLIC_TACTILE = 26
TOLERANCE_DOIGT = 30              # px : zone de sélection minimale d'un objet sous le doigt
