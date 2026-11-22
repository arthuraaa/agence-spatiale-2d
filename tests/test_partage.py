# -*- coding: utf-8 -*-
"""Partage de fusées : code court dans le presse-papiers, import vérifié."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
from jeu.univers import Univers
from jeu import hangar
from jeu.pieces import MODELES


def _scene(cles):
    """Un hangar branché sur un faux écran d'application."""
    u = Univers(bac_a_sable=True)
    app = type("App", (), {"univers": u, "modele": list(cles), "nom_modele": "X"})()
    return hangar.SceneHangar(app)


def test_aller_retour_avec_boosters():
    """Le code rend exactement la fusée, boosters latéraux compris."""
    hercule = next(cles for nom, _, cles in MODELES if nom == "Hercule")
    code = hangar.code_de_plan("Hercule de test", hercule)
    assert code.startswith("AGS1.") and " " not in code
    resultat = hangar.plan_de_code(code)
    assert resultat is not None
    nom, cles = resultat
    assert nom == "Hercule de test" and cles == hercule


def test_codes_fausse():
    """Un code tronqué, sans marque, ou avec une clé inconnue est refusé."""
    assert hangar.plan_de_code("") is None
    assert hangar.plan_de_code("bonjour") is None
    assert hangar.plan_de_code("AGS1.###") is None
    assert hangar.plan_de_code("AGS1." + hangar.code_de_plan("A", ["capsule"])[5:-3]) is None
    verrou = hangar.code_de_plan("Mauvaise clé", ["capsule", "piece_inconnue"])
    assert hangar.plan_de_code(verrou) is None


def test_coller_code():
    """« Coller un code » charge la fusée du presse-papiers, avec son nom."""
    scene = _scene(["capsule"])
    sauve = hangar.lire_presse_papiers           # le faux presse-papiers est rendu à la fin
    try:
        hangar.lire_presse_papiers = lambda: hangar.code_de_plan(
            "Sonde amie", ["sonde", "reservoir_m", "mistral"])
        scene.coller_code()
        assert scene.nom == "Sonde amie"
        assert scene.cles == ["sonde", "reservoir_m", "mistral"]
        assert "importée" in scene.message
        hangar.lire_presse_papiers = lambda: "n'importe quoi"
        scene.coller_code()
        assert scene.cles == ["sonde", "reservoir_m", "mistral"], \
            "un code illisible ne doit rien charger"
        assert "illisible" in scene.message
    finally:
        hangar.lire_presse_papiers = sauve


def test_coller_code_verrouille():
    """En carrière, une fusée avec des pièces verrouillées s'importe mais reste bloquante."""
    u = Univers(bac_a_sable=False)               # carrière : débloqué par défaut seulement
    app = type("App", (), {"univers": u, "modele": ["capsule"], "nom_modele": "X"})()
    scene = hangar.SceneHangar(app)
    sauve = hangar.lire_presse_papiers
    try:
        hangar.lire_presse_papiers = lambda: hangar.code_de_plan(
            "Avenir", ["capsule", "grand_tank_inconnu"])
        scene.coller_code()
        assert "illisible" in scene.message      # la clé inconnue est refusée
        # une pièce réelle mais verrouillée : le nucléaire (débloqué par la mission « Alunissage »)
        hangar.lire_presse_papiers = lambda: hangar.code_de_plan(
            "Rêve", ["capsule", "reservoir_xl", "atome"])
        scene.coller_code()
        assert scene.cles == ["capsule", "reservoir_xl", "atome"]
        assert "verrouillées" in scene.message
        assert any("débloquées" in txt for txt, bloquant in scene.problemes()), \
            "les pièces verrouillées doivent apparaître dans les problèmes"
    finally:
        hangar.lire_presse_papiers = sauve


def test_presse_papiers_indisponible():
    """Sans serveur graphique (SDL « dummy »), le presse-papiers échoue proprement."""
    assert hangar.copier_dans_presse_papiers(hangar.code_de_plan("A", ["capsule"])) is False
    assert not hangar.lire_presse_papiers(), "rien ne doit être lu, sans plantage"


if __name__ == "__main__":
    for nom, f in sorted(list(globals().items())):
        if nom.startswith("test_") and callable(f):
            f()
            print("OK  ", nom)
    print("Tous les tests passent.")
