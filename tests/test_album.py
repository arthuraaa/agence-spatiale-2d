# -*- coding: utf-8 -*-
"""Album photo : prise de photo, FIFO, étiquettes, tolérance aux pannes d'écriture.

    python tests/test_album.py
"""
import os
import sys
import tempfile
from math import cos, sin

RACINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, RACINE)
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
pygame.init()
pygame.display.set_mode((200, 100))           # requis par Surface.convert() / smoothscale

from jeu import album
import jeu.sauvegarde as sauvegarde


def dans_dossier_temporaire():
    """Redirige le dossier de sauvegarde vers un répertoire temporaire le temps du test."""
    tmp = tempfile.TemporaryDirectory()
    sauvegarde.chemin_sauvegarde = lambda: os.path.join(tmp.name, "sauvegarde.json")
    return tmp


def test_prendre_et_lire():
    """Une photo prise est un PNG listé, vignetté et étiqueté."""
    with dans_dossier_temporaire():
        surf = pygame.Surface((200, 100))
        surf.fill((200, 30, 30))
        album.prendre(surf, "pose", "Lune")
        photos = album.lister()
        assert len(photos) == 1 and photos[0].endswith(".png"), photos
        v = album.vignette(photos[0])
        assert v is not None and v.get_height() == 110, "vignette attendue"
        # dans le cache : deux appels renvoient la même surface (pas de relecture)
        assert album.vignette(photos[0]) is v
        lib = album.libelle(photos[0])
        assert "Posé" in lib and "Lune" in lib, lib
        # une photo de plus, plus récente : la plus récente en tête de liste
        album.prendre(surf, "amarrage", "Mars")
        photos = album.lister()
        assert len(photos) == 2 and "amarrage" in os.path.basename(photos[0])


def test_fifo():
    """Au-delà de MAX_ALBUM photos, la plus vieille est effacée."""
    with dans_dossier_temporaire():
        surf = pygame.Surface((80, 60))
        creees = []
        for _ in range(album.MAX_ALBUM):          # l'album se remplit
            album.prendre(surf, "vol", "Terre")
            creees += list(set(album.lister()) - set(creees))
        assert len(creees) == album.MAX_ALBUM
        base = 1_000_000_000.0
        for k, chemin in enumerate(creees):       # mtimes artificiels, dans l'ordre de prise
            os.utime(chemin, (base + k, base + k))
        album.prendre(surf, "vol", "Terre")       # une de plus : la plus ancienne doit partir
        photos = album.lister()
        assert len(photos) == album.MAX_ALBUM, "le FIFO n'a pas fait le ménage"
        assert creees[0] not in photos, "la photo la plus ancienne doit partir"
        assert set(creees[1:]) <= set(photos), "les autres photos doivent rester"


def test_tolerant_aux_pannes():
    """Dossier non inscriptible (ou impossible) : aucune exception ne s'échappe."""
    with dans_dossier_temporaire():
        bloquant = os.path.join(tempfile.mkdtemp(), "blocage")
        open(bloquant, "w").close()               # un fichier là où le dossier devrait être
        sauvegarde.chemin_sauvegarde = lambda: os.path.join(bloquant, "sauvegarde.json")
        surf = pygame.Surface((80, 60))
        album.prendre(surf, "pose", "Lune")       # ne doit rien lever
        assert album.lister() == []
        album.supprimer(os.path.join(bloquant, "inexistant.png"))   # pas d'exception non plus
        assert album.vignette(os.path.join(bloquant, "inexistant.png")) is None


def test_libelle():
    """L'étiquette décode genre, corps et date depuis le nom de fichier."""
    nom = os.path.join(album.dossier(), "photo-pose-Lune-20261123-140501.png")
    lib = album.libelle(nom)
    assert lib == "Posé — Lune — 23/11 14:05", lib
    nom = os.path.join(album.dossier(), "photo-amarrage-Station_Alpha-20261123-093000.png")
    lib = album.libelle(nom)
    assert "Amarrage" in lib and "Station Alpha" in lib and "09:30" in lib, lib


if __name__ == "__main__":
    test_prendre_et_lire()
    test_fifo()
    test_tolerant_aux_pannes()
    test_libelle()
    print("--- album : OK")
