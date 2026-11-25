# -*- coding: utf-8 -*-
"""Le pilote automatique doit survivre à une sauvegarde / chargement : le bug —
quitter le jeu pendant un vol automatique perdait le pilote, qui abandonnait le
vaisseau sans prévenir. La sauvegarde stocke la classe du programme et ses champs
simples ; les sous-programmes (nœud de circularisation...) sont recréés en
repartant d'une phase sûre, et une cible disparue ne fait pas planter le jeu.

    python tests/test_pilote_sauvegarde.py
"""
import math
import os
import sys
import tempfile

RACINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, RACINE)
sys.path.insert(0, os.path.dirname(__file__))

import pygame
pygame.display.init()
pygame.display.set_mode((1, 1))

from jeu import pilote, sauvegarde
from jeu.univers import Univers
from jeu.vaisseau import construire


def univers_en_orbite(prg, deuxieme=False):
    """Un univers minimal avec un vaisseau en orbite (et son pilote éventuel)."""
    u = Univers(bac_a_sable=True, avec_station=False)
    c = u.par_nom["Terre"]

    def orbite(nom, alt_m):
        v = construire(nom, ["capsule", "reservoir_m", "alize"], c)
        r = c.R + alt_m
        vv = math.sqrt(c.mu / r)
        v.mode = "physique"
        v.x, v.y, v.vx, v.vy = r, 0.0, 0.0, vv
        v.angle = 0.0
        u.vaisseaux.append(v)
        return v

    orbite("Alouette", 21000.0)
    if deuxieme:
        orbite("Compagnon", 21500.0)
    u.actif = u.vaisseaux[0]
    u.pilote = prg
    return u


def test_atterrissage_restauré():
    """Un atterrissage en cours reprend où il en était après sauvegarde/chargement."""
    prg = pilote.Atterrissage()
    prg.phase = "chute"
    prg.rasant = True                      # rentrée douce de secours engagée
    prg.voile_a_temps = True
    u = univers_en_orbite(prg)
    with tempfile.TemporaryDirectory() as tmp:
        chemin = os.path.join(tmp, "sauvegarde.json")
        sauvegarde.sauvegarder(u, chemin)
        u2 = sauvegarde.charger(chemin)
    p = u2.pilote
    assert type(p) is pilote.Atterrissage, "le pilote d'atterrissage est perdu"
    assert p.phase == "chute" and p.rasant is True and p.voile_a_temps is True
    assert p.en_ombre is False and p.abandon is False


def test_mise_en_orbite_repart_dune_phase_sure():
    """La circularisation passe par un sous-programme non sauvegardé : on repart
    de la montée plutôt que de pointer un nœud qui n'existe plus."""
    prg = pilote.MiseEnOrbite()
    prg.phase = "circularisation"          # prg.circularisation = None (objet perdu)
    u = univers_en_orbite(prg)
    u2 = sauvegarde.dict_vers_univers(sauvegarde.univers_vers_dict(u))
    assert type(u2.pilote) is pilote.MiseEnOrbite
    assert u2.pilote.phase == "montee", "phase pointant un nœud perdu non réparée"


def test_rendez_vous_cible_et_phase():
    """Rendez-vous : la cible revient par son NOM, et « depart » (nœud perdu) repart du plan."""
    prg = pilote.RendezVous(None)
    prg.etape = "depart"
    prg.sous = pilote.ExecuterNoeud()      # sous-programme, non sauvegardé
    u = univers_en_orbite(prg, deuxieme=True)
    prg.cible = u.vaisseaux[1]
    u2 = sauvegarde.dict_vers_univers(sauvegarde.univers_vers_dict(u))
    p = u2.pilote
    assert type(p) is pilote.RendezVous
    assert p.etape == "plan", "étape « depart » sans nœud : il faut replanifier"
    assert p.cible is not None and p.cible.nom == "Compagnon"


def test_rendez_vous_amarrage_replanifie():
    """Sauvegardé pendant l'étape « amarrage » (sous = Amarrage, non sauvegardé) :
    on replanifie plutôt que de lire self.sous à None."""
    prg = pilote.RendezVous(None)
    prg.etape = "amarrage"
    prg.sous = pilote.Amarrage(None)
    prg.t_rencontre = 1234.0
    u = univers_en_orbite(prg, deuxieme=True)
    prg.cible = u.vaisseaux[1]
    u2 = sauvegarde.dict_vers_univers(sauvegarde.univers_vers_dict(u))
    p = u2.pilote
    assert type(p) is pilote.RendezVous and p.etape == "plan", "étape amarrage avec sous=None"
    fin = p.piloter(u2, u2.actif)          # ici : pas de plan possible (univers de jouet),
    assert isinstance(fin, bool)           # mais AUCUN crash sur le sous-programme perdu


def test_amarrage_cible_par_nom():
    prg = pilote.Amarrage(None)
    u = univers_en_orbite(prg, deuxieme=True)
    prg.cible = u.vaisseaux[1]
    u2 = sauvegarde.dict_vers_univers(sauvegarde.univers_vers_dict(u))
    assert u2.pilote.cible is not None and u2.pilote.cible.nom == "Compagnon"


def test_cible_perdue_ne_plante_pas():
    """La cible du rendez-vous a disparu (détruite...) : pas de pilote, pas de crash."""
    prg = pilote.RendezVous(None)
    u = univers_en_orbite(prg, deuxieme=True)
    prg.cible = u.vaisseaux[1]
    d = sauvegarde.univers_vers_dict(u)
    d["vaisseaux"] = d["vaisseaux"][:1]    # le compagnon a disparu
    d["actif"] = 0
    assert sauvegarde.dict_vers_univers(d).pilote is None


def test_vieille_sauvegarde_sans_pilote():
    """Une sauvegarde d'avant la restauration du pilote doit rester lisible."""
    u = univers_en_orbite(None)
    d = sauvegarde.univers_vers_dict(u)
    assert d["pilote"] is None             # pas de pilote : champ à None, pas absent
    d.pop("pilote")                        # … et le format encore plus ancien
    assert sauvegarde.dict_vers_univers(d).pilote is None


def test_classe_inconnue_ne_plante_pas():
    u = univers_en_orbite(None)
    d = sauvegarde.univers_vers_dict(u)
    d["pilote"] = {"classe": "MachineAPlomb", "etat": {"phase": "chute"}}
    assert sauvegarde.dict_vers_univers(d).pilote is None


if __name__ == "__main__":
    test_atterrissage_restauré()
    test_mise_en_orbite_repart_dune_phase_sure()
    test_rendez_vous_cible_et_phase()
    test_rendez_vous_amarrage_replanifie()
    test_amarrage_cible_par_nom()
    test_cible_perdue_ne_plante_pas()
    test_vieille_sauvegarde_sans_pilote()
    test_classe_inconnue_ne_plante_pas()
    print("--- pilote sauvegardé : OK")
