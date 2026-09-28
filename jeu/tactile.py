# -*- coding: utf-8 -*-
"""
Doigts sur l'écran.

On transforme les événements de pygame (FINGERDOWN, FINGERMOTION, FINGERUP) en
trois gestes simples, « appui », « glisse » et « relache », chacun rattaché à un
objet Doigt qui se souvient d'où il est parti et de ce qu'il a attrapé.
Plusieurs doigts peuvent être posés à la fois (gaz d'une main, rotation de l'autre).

La souris est traitée comme un doigt de plus : on peut ainsi essayer toute
l'interface tactile sur PC avec  python main.py --tactile.
"""
from math import hypot
import pygame

SOURIS = "souris"
SEUIL_TAPE = 14          # px : un doigt qui a bougé de moins que ça fait une « tape »


class Doigt:
    def __init__(self, ident, pos):
        self.ident = ident
        self.depart = pos       # où le doigt s'est posé
        self.pos = pos          # où il est maintenant
        self.prise = None       # ce qu'il a attrapé en se posant (manette, poignée, monde...)
        self.bouge = False      # a-t-il glissé plus loin que SEUIL_TAPE ?


class Doigts:
    def __init__(self):
        self.actifs = {}              # identifiant -> Doigt
        self.vu_un_doigt = False      # dès qu'un vrai doigt a touché l'écran, on ignore la souris

    def lire(self, ev, taille):
        """Renvoie (geste, doigt) pour un événement de doigt ou de souris, sinon None."""
        largeur, hauteur = taille
        if ev.type in (pygame.FINGERDOWN, pygame.FINGERMOTION, pygame.FINGERUP):
            self.vu_un_doigt = True
            ident = ev.finger_id
            pos = (ev.x * largeur, ev.y * hauteur)      # x, y sont donnés entre 0 et 1
            geste = {pygame.FINGERDOWN: "appui", pygame.FINGERMOTION: "glisse",
                     pygame.FINGERUP: "relache"}[ev.type]
        elif ev.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEMOTION, pygame.MOUSEBUTTONUP):
            if self.vu_un_doigt or getattr(ev, "touch", False):
                return None                             # clic « simulé » à partir d'un doigt
            if ev.type != pygame.MOUSEMOTION and ev.button != 1:
                return None
            ident, pos = SOURIS, ev.pos
            geste = {pygame.MOUSEBUTTONDOWN: "appui", pygame.MOUSEMOTION: "glisse",
                     pygame.MOUSEBUTTONUP: "relache"}[ev.type]
        else:
            return None
        if geste == "appui":
            d = self.actifs[ident] = Doigt(ident, pos)
            return geste, d
        d = self.actifs.get(ident)
        if d is None:                                   # mouvement sans appui (souris survolant)
            return None
        d.pos = pos
        if hypot(pos[0] - d.depart[0], pos[1] - d.depart[1]) > SEUIL_TAPE:
            d.bouge = True
        if geste == "relache":
            del self.actifs[ident]
        return geste, d

    def tenant(self, prise):
        """Les doigts actuellement posés qui tiennent cette commande."""
        return [d for d in self.actifs.values() if d.prise == prise]

    def lacher_tout(self):
        self.actifs.clear()
