# -*- coding: utf-8 -*-
"""Petite boîte à outils d'interface : texte, panneaux, boutons, formats de nombres."""
import os
import pygame
from .constantes import BLANC, GRIS, GRIS_FONCE, FOND_PANNEAU, BORD_PANNEAU, CYAN

# Polices livrées avec le jeu : mêmes caractères partout (la police par défaut de pygame,
# utilisée sur Android faute de mieux, n'a ni « → » ni « ≈ »).
_DOSSIER_POLICES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "polices")
_FICHIERS_POLICES = {False: "DejaVuSans.ttf", True: "DejaVuSans-Bold.ttf"}

_polices = {}
_cache_texte = {}
_cache_panneaux = {}

_ANCRES = {"hg": "topleft", "hd": "topright", "hc": "midtop", "c": "center", "mg": "midleft",
           "md": "midright", "bg": "bottomleft", "bd": "bottomright", "bc": "midbottom"}


def police(taille, gras=False):
    cle = (taille, gras)
    if cle not in _polices:
        chemin = os.path.join(_DOSSIER_POLICES, _FICHIERS_POLICES[gras])
        try:
            _polices[cle] = pygame.font.Font(chemin, taille)
        except (OSError, IOError, pygame.error):          # police absente : celle du système
            _polices[cle] = pygame.font.SysFont("dejavusans,verdana,arial,liberationsans,freesans",
                                                taille, bold=gras)
    return _polices[cle]


def image_texte(txt, taille=16, couleur=BLANC, gras=False):
    """Surface du texte rendu (avec cache : le rendu de police est lent)."""
    cle = (txt, taille, couleur, gras)
    s = _cache_texte.get(cle)
    if s is None:
        if len(_cache_texte) > 900:
            _cache_texte.clear()
        s = _cache_texte[cle] = police(taille, gras).render(txt, True, couleur)
    return s


def texte(surf, txt, pos, taille=16, couleur=BLANC, gras=False, ancre="hg"):
    """Écrit un texte. `ancre` dit quel point du texte est placé en `pos` (hg = haut-gauche...)."""
    s = image_texte(str(txt), taille, couleur, gras)
    r = s.get_rect()
    setattr(r, _ANCRES[ancre], (int(pos[0]), int(pos[1])))
    surf.blit(s, r)
    return r


def texte_multiligne(surf, txt, pos, largeur, taille=15, couleur=BLANC, interligne=4):
    """Texte avec retour à la ligne automatique. Renvoie la coordonnée y sous le texte."""
    f = police(taille)
    x, y = pos
    for paragraphe in txt.split("\n"):
        ligne = ""
        for mot in paragraphe.split(" "):
            essai = (ligne + " " + mot).strip()
            if f.size(essai)[0] > largeur and ligne:
                texte(surf, ligne, (x, y), taille, couleur)
                y += f.get_height() + interligne
                ligne = mot
            else:
                ligne = essai
        texte(surf, ligne, (x, y), taille, couleur)
        y += f.get_height() + interligne
    return y


def panneau(surf, rect, alpha=205, bord=True, couleur=FOND_PANNEAU):
    """Rectangle semi-transparent servant de fond aux panneaux."""
    rect = pygame.Rect(rect)
    cle = (rect.w, rect.h, alpha, couleur)
    s = _cache_panneaux.get(cle)
    if s is None:
        if len(_cache_panneaux) > 60:
            _cache_panneaux.clear()
        s = pygame.Surface((max(1, rect.w), max(1, rect.h)), pygame.SRCALPHA)
        s.fill(couleur + (alpha,))
        _cache_panneaux[cle] = s
    surf.blit(s, rect.topleft)
    if bord:
        pygame.draw.rect(surf, BORD_PANNEAU, rect, 1, border_radius=5)


class Bouton:
    """Bouton cliquable. `action` est une fonction sans argument."""

    def __init__(self, rect, libelle, action=None, taille=15, actif=True, allume=False, info=""):
        self.rect = pygame.Rect(rect)
        self.libelle = libelle
        self.action = action
        self.taille = taille
        self.actif = actif
        self.allume = allume          # bouton « enfoncé » (mode sélectionné)
        self.info = info

    def dessiner(self, surf, souris):
        survol = self.actif and self.rect.collidepoint(souris)
        if self.allume:
            fond, bord, coul = (30, 90, 130), CYAN, BLANC
        elif survol:
            fond, bord, coul = (40, 58, 92), CYAN, BLANC
        else:
            fond, bord, coul = (24, 34, 56), BORD_PANNEAU, BLANC if self.actif else GRIS_FONCE
        pygame.draw.rect(surf, fond, self.rect, border_radius=5)
        pygame.draw.rect(surf, bord, self.rect, 1, border_radius=5)
        texte(surf, self.libelle, self.rect.center, self.taille, coul, ancre="c")

    def clic(self, pos):
        """Exécute l'action si le clic est sur le bouton. Renvoie True si le clic est consommé."""
        if self.rect.collidepoint(pos):
            if self.actif and self.action:
                from . import sons
                sons.jouer("clic")
                self.action()
            return True
        return False


# --- formats ------------------------------------------------------------------
def fmt_nombre(x, decimales=0):
    return format(x, ",.%df" % decimales).replace(",", " ")


def fmt_distance(m):
    a = abs(m)
    if a < 10_000:
        return fmt_nombre(m) + " m"
    if a < 1e9:
        return fmt_nombre(m / 1e3, 1) + " km"
    return fmt_nombre(m / 1e9, 3) + " M km"


def fmt_vitesse(v):
    return (fmt_nombre(v, 1) if abs(v) < 1000 else fmt_nombre(v)) + " m/s"


def fmt_duree(s):
    if s is None or s != s or s == float("inf"):
        return "—"
    s = int(max(0, s))
    j, s = divmod(s, 86400)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    if j:
        return "%d j %02d h" % (j, h)
    if h:
        return "%d h %02d min" % (h, m)
    if m:
        return "%d min %02d s" % (m, s)
    return "%d s" % s


def fmt_date(t):
    t = int(t)
    j, s = divmod(t, 86400)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return "Jour %d  %02d:%02d:%02d" % (j + 1, h, m, s)


def fmt_masse(kg):
    return fmt_nombre(kg / 1000.0, 2) + " t" if kg >= 1000 else fmt_nombre(kg) + " kg"
