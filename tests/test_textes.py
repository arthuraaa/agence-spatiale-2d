# -*- coding: utf-8 -*-
"""Le module de textes bilingue : choix de langue, gabarits, couverture.

    python tests/test_textes.py
"""
import json
import os
import sys
import tempfile

RACINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, RACINE)

from jeu import reglages, textes


def _forcer(imposee):
    """Règle la langue imposée par AGENCE_LANGUE sans toucher aux variables d'env."""
    textes._imposee = imposee


def test_langues():
    _forcer("fr")
    assert textes.t("langue") == "Langue"
    _forcer("en")
    assert textes.t("langue") == "Language"
    _forcer("fr")
    assert textes.t("langue") == "Langue"
    # Clé inconnue : la clé elle-même (visible en jouant, pas de plantage).
    assert textes.t("cle_inexistante") == "cle_inexistante"


def test_gabarits():
    textes.TOUT["essai_gabarit"] = {"fr": "Orbite de {corps}", "en": "Orbit of {body}"}
    _forcer("fr")
    assert textes.t("essai_gabarit", corps="la Lune") == "Orbite de la Lune"
    _forcer("en")
    assert textes.t("essai_gabarit", body="the Moon") == "Orbit of the Moon"
    del textes.TOUT["essai_gabarit"]


def test_couverture():
    """Chaque texte doit exister dans les deux langues, sans chaîne vide."""
    manquantes = [c for c, e in textes.TOUT.items()
                  if not e.get("fr") or not e.get("en")]
    assert not manquantes, "textes incomplets (fr/en) : %s" % manquantes


def test_cles_utilisees():
    """Chaque t("...") du code doit exister dans TOUT : une clé absente s'affiche
    brute au joueur, accolades comprises (bug du panneau de carburant)."""
    import glob, io, re
    # clés dynamiques que le scan ne peut pas reconstruire ("Vit. %s" % ..., "son_" + ...)
    dynamiques = {"Vit. %s", "son_"}
    utilisees = set()
    for chemin in glob.glob(os.path.join(RACINE, "jeu", "*.py")):
        if chemin.endswith("textes.py"):
            continue                       # ses exemples de docstring ne sont pas des clés
        src = io.open(chemin, encoding="utf-8").read()
        utilisees |= set(re.findall(r'\bt\(\s*"((?:[^"\\]|\\.)*)"', src))
        utilisees |= set(re.findall(r"\bt\(\s*'((?:[^'\\]|\\.)*)'", src))
    manquantes = sorted(c for c in utilisees - dynamiques if c not in textes.TOUT)
    assert not manquantes, "clés de texte absentes du dictionnaire : %s" % manquantes


def test_reglages_compatibles():
    """Une reglages.json sans champ « langue » (ancienne sauvegarde) doit rester lisible."""
    with tempfile.TemporaryDirectory() as tmp:
        chemin = os.path.join(tmp, "reglages.json")
        with open(chemin, "w", encoding="utf-8") as f:
            json.dump({"aides": True, "son": "tout", "tutos": [], "triche": False}, f)
        reglages._chemin = lambda: chemin          # on ne touche pas au vrai fichier du joueur
        reglages.LANGUE = "en"                     # valeur qui doit être écrasée par le défaut
        reglages.charger()
        assert reglages.LANGUE == "", "une ancienne sauvegarde doit donner la langue auto"
        assert reglages.TRICHE is False            # les autres réglages restent lus
        # Le champ langue est bien écrit et relu pour une langue invalide aussi.
        reglages.changer_langue("xx")
        assert reglages.LANGUE == "", "un code inconnu doit retomber sur la langue auto"
        reglages.changer_langue("en")
        assert reglages.LANGUE == "en"
        with open(chemin, encoding="utf-8") as f:
            assert json.load(f)["langue"] == "en"


def test_defaut_systeme():
    """Sans réglage ni AGENCE_LANGUE, la langue vient du système (fr si français, en sinon)."""
    _forcer("")
    reglages.LANGUE = ""
    sauve = (os.environ.get("LC_ALL"), os.environ.get("LANG"))
    try:
        textes._detectee = None
        os.environ["LC_ALL"] = os.environ["LANG"] = "fr_FR.UTF-8"
        assert textes.langue_active() == "fr"
        textes._detectee = None
        os.environ["LC_ALL"] = os.environ["LANG"] = "C"
        assert textes.langue_active() == "en"
    finally:
        textes._detectee = None
        for cle, val in zip(("LC_ALL", "LANG"), sauve):
            if val is None:
                os.environ.pop(cle, None)
            else:
                os.environ[cle] = val


if __name__ == "__main__":
    test_langues()
    test_gabarits()
    test_couverture()
    test_cles_utilisees()
    test_reglages_compatibles()
    test_defaut_systeme()
    print("--- textes : OK")
