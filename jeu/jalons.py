# -*- coding: utf-8 -*-
"""
Jalons : les petites réussites, cochées d'une partie à l'autre (reglages.json).

Pour ajouter un jalon : une ligne dans JALONS avec une fonction test(univers, vaisseau_actif).
Ils complètent les 20 missions de la carrière (aucun ne rapporte d'argent) et sont
vérifiés au même endroit, deux fois par seconde (univers._periodique).
"""
from math import hypot
from .constantes import NOM_STATION, CYAN
from .missions import _drapeau, _pose_sur_terre_avec
from .textes import t
from .vaisseau import Vaisseau
from . import reglages


class Jalon:
    def __init__(self, ident, titre, test):
        self.ident = ident
        self.titre = titre              # clé de jeu/textes.py
        self.test = test


def _proche(u, v):
    """À moins de 50 m d'un vaisseau ciblé (les missions s'arrêtent à 200 m)."""
    if v is None or not isinstance(u.cible, Vaisseau):
        return False
    a, b = u.etat(v), u.etat(u.cible)
    return hypot(a[0] - b[0], a[1] - b[1]) < 50.0


JALONS = [
    Jalon("haut", "jalon_haut_t",
          lambda u, v: v is not None and v.corps.nom == "Terre" and u.altitude(v) > 10_000),
    Jalon("etage", "jalon_etage_t", lambda u, v: reglages.STATS.get("etages", 0) >= 1),
    Jalon("crash", "jalon_crash_t", lambda u, v: reglages.STATS.get("crashs", 0) >= 1),
    Jalon("pose_terre", "jalon_pose_terre_t", _drapeau("pose:Terre")),
    Jalon("evasion", "jalon_evasion_t",
          lambda u, v: v is not None and v.corps.nom != "Terre"),
    Jalon("proche", "jalon_proche_t", _proche),
    Jalon("grande_station", "jalon_station_t",
          lambda u, v: any(s.contient_proprietaire(NOM_STATION) and s.compte("module") >= 5
                           for s in u.vaisseaux)),
    Jalon("colosse", "jalon_colosse_t",
          lambda u, v: any("orbite:Terre" in s.drapeaux and s.masse() > 40_000
                           for s in u.vaisseaux)),
    Jalon("noeud", "jalon_noeud_t", _drapeau("noeud")),
    Jalon("mercure", "jalon_mercure_t", _drapeau("pose:Mercure")),
    Jalon("venus", "jalon_venus_t", _drapeau("pose:Vénus")),
    Jalon("callisto", "jalon_callisto_t", _drapeau("pose:Callisto")),
    Jalon("retour_mars", "jalon_retour_mars_t", _pose_sur_terre_avec("pose:Mars")),
]


def verifier(u):
    """Valide les jalons dont la condition est remplie (comme missions.verifier)."""
    if u.tutoriel:
        return                                  # ni missions ni jalons pendant un tutoriel
    for j in JALONS:
        if j.ident in reglages.JALONS_FAITS:
            continue
        try:
            obtenu = j.test(u, u.actif)
        except Exception:
            obtenu = False
        if obtenu:
            reglages.jalon_fait(j.ident)
            u.bruit("succes")
            u.dire(t("nouveau_jalon", titre=t(j.titre)), CYAN, 8)
