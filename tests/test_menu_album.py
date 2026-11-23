# -*- coding: utf-8 -*-
"""Menu principal (boutons dans l'écran, 4:3 comme 20:9) et écran Album photo.

    python tests/test_menu_album.py
"""
import os
import sys
import tempfile

RACINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, RACINE)
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
pygame.init()
pygame.display.set_mode((200, 100))

from jeu import album
from jeu.menu import SceneMenu
import jeu.sauvegarde as sauvegarde


class App:                                        # le minimum requis par SceneMenu
    def quitter(self):
        pass

    def continuer(self):
        pass

    def nouvelle_partie(self, sable):
        pass


def dessiner_menu(vue="principal", taille=(720, 540)):
    surf = pygame.Surface(taille).convert()
    sc = SceneMenu(App(), vue=vue)
    sc.dessiner(surf)
    return sc, surf


def test_menu_tient_dans_lecran():
    """Tous les boutons du menu principal restent dans l'écran, en 4:3 comme en 20:9."""
    for taille in ((720, 540), (1200, 540)):
        sc, _ = dessiner_menu("principal", taille)
        assert sc.boutons, "le menu doit avoir des boutons"
        for b in sc.boutons:
            assert b.rect.bottom <= taille[1] and b.rect.top >= 0, \
                "bouton %s hors écran en %s : %s" % (b.libelle, taille, b.rect)
        libelles = [b.libelle for b in sc.boutons]
        assert any("Réussites" in lb for lb in libelles), libelles
        assert any("Album" in lb for lb in libelles), libelles


def test_album_vide_et_en_clair():
    """La page Album s'affiche vide, puis avec des photos, dans les deux formats."""
    tmp = tempfile.TemporaryDirectory()
    sauvegarde.chemin_sauvegarde = lambda: os.path.join(tmp.name, "sauvegarde.json")
    for taille in ((720, 540), (1200, 540)):
        for chemin in album.lister():             # album vide pour ce format
            album.supprimer(chemin)
        sc, _ = dessiner_menu("album", taille)
        assert sc.boutons, "bouton Retour attendu même sans photo"
        # deux photos : vignettes cliquables, toutes dans l'écran
        surf_photo = pygame.Surface((720, 540))
        surf_photo.fill((30, 120, 30))
        album.prendre(surf_photo, "pose", "Lune")
        album.prendre(surf_photo, "amarrage", "Mars")
        sc, _ = dessiner_menu("album", taille)
        assert len(sc.boutons) == 3, "2 vignettes + Retour attendus"
        for b in sc.boutons:
            assert b.rect.bottom <= taille[1] and b.rect.top >= 0, \
                "vignette hors écran en %s : %s" % (taille, b.rect)


def test_album_deborde_pas_a_vingt_photos():
    """Un album plein reste affichable : les vignettes rétrécissent, rien ne sort."""
    tmp = tempfile.TemporaryDirectory()
    sauvegarde.chemin_sauvegarde = lambda: os.path.join(tmp.name, "sauvegarde.json")
    surf_photo = pygame.Surface((720, 540))
    surf_photo.fill((30, 120, 30))
    for _ in range(album.MAX_ALBUM):
        album.prendre(surf_photo, "vol", "Terre")
    for taille in ((720, 540), (1200, 540)):
        sc, _ = dessiner_menu("album", taille)
        for b in sc.boutons:
            assert b.rect.bottom <= taille[1] and b.rect.top >= 0, \
                "vignette hors écran en %s : %s" % (taille, b.rect)


def test_vue_photo():
    """Une photo s'affiche en grand ; la supprimer renvoie à l'album."""
    tmp = tempfile.TemporaryDirectory()
    sauvegarde.chemin_sauvegarde = lambda: os.path.join(tmp.name, "sauvegarde.json")
    surf_photo = pygame.Surface((720, 540))
    surf_photo.fill((30, 120, 30))
    album.prendre(surf_photo, "pose", "Lune")
    sc, surf = dessiner_menu("photo", (720, 540))
    sc.photo_index = 0
    sc.dessiner(surf)
    libelles = [b.libelle for b in sc.boutons]
    assert any("Supprimer" in lb for lb in libelles) and any("Retour" in lb for lb in libelles)
    # index invalide (photo supprimée entre-temps) : retour propre à l'album, pas de crash
    sc.photo_index = 5
    sc.dessiner(surf)
    assert sc.vue == "album"
    # index hors d'échelle sur une photo n'existe pas : liste vide → album vide, pas de crash
    album.supprimer(album.lister()[0])
    sc.photo_index = 0
    sc.vue = "photo"
    sc.dessiner(surf)
    assert sc.vue == "album"


if __name__ == "__main__":
    test_menu_tient_dans_lecran()
    test_album_vide_et_en_clair()
    test_album_deborde_pas_a_vingt_photos()
    test_vue_photo()
    print("--- menu + album : OK")
