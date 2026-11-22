# -*- coding: utf-8 -*-
"""Réglages du joueur, gardés d'une partie à l'autre (fichier reglages.json, à côté de la sauvegarde)."""
import json
import os

AIDES = True          # aides au pilotage : pilote automatique, assistants, atterrissage, docking
SON = "tout"          # "tout", "sans_musique", "effets" (bruitages seuls) ou "aucun"
TUTOS_FAITS = []      # identifiants des tutoriels terminés
TRICHE = True         # la triche est proposée en vol (menu Options)
LANGUE = ""           # "fr", "en", ou "" = langue du système (jeu/textes.py)
NOMS_SON = {"tout": "tout", "sans_musique": "sans musique", "effets": "effets seuls", "aucun": "coupé"}


def _chemin():
    from .sauvegarde import chemin_sauvegarde
    return os.path.join(os.path.dirname(chemin_sauvegarde()), "reglages.json")


def charger():
    global AIDES, SON, TUTOS_FAITS, TRICHE, LANGUE
    try:
        with open(_chemin(), encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        return
    if not isinstance(d, dict):                       # fichier corrompu : on repart des défauts
        return
    AIDES = bool(d.get("aides", True))
    son = d.get("son", "tout")
    SON = son if isinstance(son, str) and son in NOMS_SON else "tout"
    tutos = d.get("tutos", [])
    TUTOS_FAITS = [x for x in tutos if isinstance(x, str)] if isinstance(tutos, list) else []
    TRICHE = bool(d.get("triche", True))
    langue = d.get("langue", "")
    LANGUE = langue if isinstance(langue, str) and langue in ("", "fr", "en") else ""


def _ecrire():
    try:
        # écriture atomique : un coupure de courant ne laisse pas un reglages.json à moitié écrit
        tmp = _chemin() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"aides": AIDES, "son": SON, "tutos": TUTOS_FAITS, "triche": TRICHE,
                       "langue": LANGUE}, f)
        os.replace(tmp, _chemin())
    except OSError:
        pass


def basculer_aides():
    global AIDES
    AIDES = not AIDES
    _ecrire()


def changer_son():
    """Tout -> sans musique -> effets seuls -> coupé -> tout."""
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


def changer_langue(code):
    """Change la langue du jeu ("fr", "en" ou "" = langue du système)."""
    global LANGUE
    LANGUE = code if code in ("", "fr", "en") else ""
    _ecrire()
