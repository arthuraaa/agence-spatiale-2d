# -*- coding: utf-8 -*-
"""Réglages du joueur, gardés d'une partie à l'autre (fichier reglages.json, à côté de la sauvegarde)."""
import json
import os

AIDES = True          # aides au pilotage : pilote automatique, assistants, atterrissage, docking
SON = "tout"          # "tout" (bruitages + ambiance), "effets" (bruitages seuls) ou "aucun"
TUTOS_FAITS = []      # identifiants des tutoriels terminés
TRICHE = True         # la triche est proposée en vol (menu Options)
NOMS_SON = {"tout": "tout", "sans_musique": "sans musique", "effets": "effets seuls", "aucun": "coupé"}


def _chemin():
    from .sauvegarde import chemin_sauvegarde
    return os.path.join(os.path.dirname(chemin_sauvegarde()), "reglages.json")


def charger():
    global AIDES, SON, TUTOS_FAITS, TRICHE
    try:
        with open(_chemin(), encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        return
    AIDES = bool(d.get("aides", True))
    SON = d.get("son", "tout") if d.get("son") in NOMS_SON else "tout"
    TUTOS_FAITS = [t for t in d.get("tutos", []) if isinstance(t, str)]
    TRICHE = bool(d.get("triche", True))


def _ecrire():
    try:
        with open(_chemin(), "w", encoding="utf-8") as f:
            json.dump({"aides": AIDES, "son": SON, "tutos": TUTOS_FAITS, "triche": TRICHE}, f)
    except OSError:
        pass


def basculer_aides():
    global AIDES
    AIDES = not AIDES
    _ecrire()


def changer_son():
    """Tout -> effets seuls -> coupé -> tout."""
    global SON
    ordre = list(NOMS_SON)
    SON = ordre[(ordre.index(SON) + 1) % len(ordre)]
    _ecrire()


def tuto_fait(ident):
    if ident not in TUTOS_FAITS:
        TUTOS_FAITS.append(ident)
        _ecrire()


def basculer_triche():
    global TRICHE
    TRICHE = not TRICHE
    _ecrire()
