# -*- coding: utf-8 -*-
"""Album photo : captures de la partie (pose, amarrage, demande du joueur).

Les photos sont des PNG dans un sous-dossier « album » du dossier de
sauvegarde. Tout est tolérant aux pannes (disque plein, dossier non
inscriptible) : une photo qui échoue ne doit JAMAIS faire planter le jeu.
"""
import os
import time

import pygame

from . import sauvegarde
from .textes import t

MAX_ALBUM = 20                    # photos gardées au plus (les plus vieilles sont effacées)
HAUTEUR = 540                     # hauteur des PNG (la surface logique de l'écran tactile)
LIBELLES_GENRE = {"pose": "Posé", "amarrage": "Amarrage", "vol": "Photo"}


def dossier():
    return os.path.join(os.path.dirname(sauvegarde.chemin_sauvegarde()), "album")


def prendre(surface, genre, corps):
    """Réduit `surface` et l'enregistre en PNG ; FIFO au-delà de MAX_ALBUM."""
    try:
        h = min(HAUTEUR, surface.get_height())
        l = max(1, round(surface.get_width() * h / surface.get_height()))
        image = pygame.transform.smoothscale(surface, (l, h))
        nom = "photo-%s-%s-%s.png" % (genre, corps.replace(" ", "_"),
                                      time.strftime("%Y%m%d-%H%M%S"))
        os.makedirs(dossier(), exist_ok=True)
        chemin = os.path.join(dossier(), nom)
        i = 1                                     # deux photos à la même seconde : suffixe
        while os.path.exists(chemin):
            chemin = os.path.join(dossier(), "%s-%d.png" % (nom[:-4], i))
            i += 1
        pygame.image.save(image, chemin)
        _faire_place()
    except OSError:
        pass


def _faire_place():
    for chemin in lister()[MAX_ALBUM:]:
        supprimer(chemin)


def lister():
    """Chemins des photos, de la plus récente à la plus ancienne."""
    try:
        entrees = [os.path.join(dossier(), n) for n in os.listdir(dossier())]
        return sorted((e for e in entrees if e.endswith(".png")),
                      key=os.path.getmtime, reverse=True)
    except OSError:
        return []


def supprimer(chemin):
    try:
        os.remove(chemin)
        _cache_vignettes.pop(chemin, None)
    except OSError:
        pass


_cache_vignettes = {}             # {chemin: (mtime, hauteur, surface)} pour ne pas relire chaque frame


def vignette(chemin, hauteur=110):
    """La photo réduite (surface), ou None si le fichier est illisible."""
    try:
        mtime = os.path.getmtime(chemin)
    except OSError:
        _cache_vignettes.pop(chemin, None)
        return None
    en_cache = _cache_vignettes.get(chemin)
    if en_cache is not None and en_cache[0] == mtime and en_cache[1] == hauteur:
        return en_cache[2]
    try:
        image = pygame.image.load(chemin)
        l = max(1, round(image.get_width() * hauteur / image.get_height()))
        image = pygame.transform.smoothscale(image, (l, hauteur))
    except Exception:
        return None
    if len(_cache_vignettes) > 40:                # le cache suit la liste de l'album
        _cache_vignettes.clear()
    _cache_vignettes[chemin] = (mtime, hauteur, image)
    return image


def image(chemin, l_max, h_max):
    """La photo entière, réduite pour tenir dans (l_max, h_max) ; None si illisible."""
    try:
        img = pygame.image.load(chemin)
    except Exception:
        return None
    f = min(l_max / img.get_width(), h_max / img.get_height(), 1.0)
    return pygame.transform.smoothscale(img, (max(1, round(img.get_width() * f)),
                                              max(1, round(img.get_height() * f))))


def libelle(chemin):
    """Étiquette lisible déduite du nom : « Posé — Lune — 23/11 14:05 »."""
    nom = os.path.basename(chemin)
    morceaux = nom[:-4].split("-")                # photo, genre, corps, date, heure[, suffixe]
    genre, corps, date, heure = morceaux[1], "-".join(morceaux[2:-2]), morceaux[-2], morceaux[-1]
    try:
        quand = "%s/%s %s:%s" % (date[6:8], date[4:6], heure[:2], heure[2:4])
    except IndexError:
        quand = ""
    return "%s — %s — %s" % (t(LIBELLES_GENRE.get(genre, "Photo")),
                             corps.replace("_", " "), quand)
