# -*- coding: utf-8 -*-
"""
Missions : une liste d'objectifs testés deux fois par seconde.
Pour ajouter une mission : une ligne dans MISSIONS avec une fonction test(univers, vaisseau_actif).
"""
from math import hypot
from .constantes import NOM_STATION, VERT, CYAN
from .pieces import CATALOGUE
from .textes import t


class Mission:
    def __init__(self, ident, titre, description, prime, test):
        self.ident = ident
        self.titre = titre
        self.description = description
        self.prime = prime
        self.test = test


# --- briques pour écrire les tests ------------------------------------------
def _sur(v, nom):
    return v is not None and v.corps.nom == nom


def _drapeau(nom):
    return lambda u, v: v is not None and nom in v.drapeaux


def _pose_sur_terre_avec(drapeau):
    return lambda u, v: _sur(v, "Terre") and v.mode == "pose" and drapeau in v.drapeaux


def _satellites(u):
    """Satellites = vaisseaux avec une sonde et des panneaux, en orbite stable autour de la Terre."""
    for s in u.vaisseaux:
        if s.mode == "rails" and s.corps.nom == "Terre" and s.compte("sonde") and s.compte("panneaux"):
            o = s.orbite
            if o.elliptique and o.ra < s.corps.soi:
                yield s


def _satellite_haut(u, v):
    return any(s.orbite.rp - s.corps.R > 30_000 for s in _satellites(u))


def _geostationnaire(u, v):
    jour = 8616.4
    return any(abs(s.orbite.periode / jour - 1.0) < 0.03 and s.orbite.e < 0.06 for s in _satellites(u))


def _rendez_vous(u, v):
    if v is None:
        return False
    for s in u.vaisseaux:
        if s is not v and s.corps is v.corps and s.contient_proprietaire(NOM_STATION):
            a, b = u.etat(v), u.etat(s)
            if hypot(a[0] - b[0], a[1] - b[1]) < 200 and hypot(a[2] - b[2], a[3] - b[3]) < 10:
                return True
    return False


def _station_agrandie(u, v):
    return any(s.contient_proprietaire(NOM_STATION) and s.compte("module") >= 3 for s in u.vaisseaux)


def _grand_tour(u, v):
    return v is not None and all("soi:" + n in v.drapeaux
                                 for n in ("Jupiter", "Saturne", "Uranus", "Neptune"))


MISSIONS = [
    Mission("decollage", "Premier décollage", "Dépasser 1 km d'altitude.", 2_000,
            lambda u, v: _sur(v, "Terre") and v.mode != "pose" and u.altitude(v) > 1_000),
    Mission("espace", "Dans l'espace", "Sortir de l'atmosphère (7 km).", 4_000,
            lambda u, v: _sur(v, "Terre") and u.altitude(v) > 7_000),
    Mission("orbite", "En orbite !", "Orbite terrestre stable (périapside au-dessus de 7 km).",
            10_000, _drapeau("orbite:Terre")),
    Mission("retour", "Retour au bercail", "Revenir se poser sur Terre après une orbite.",
            8_000, _pose_sur_terre_avec("orbite:Terre")),
    Mission("satellite", "Satellite", "Mettre une sonde + panneaux solaires en orbite à plus de 30 km.",
            8_000, _satellite_haut),
    Mission("rdv", "Rendez-vous", "S'approcher à moins de 200 m de la Station Alpha (< 10 m/s).",
            8_000, _rendez_vous),
    Mission("amarrage", "Amarrage", "S'amarrer à la Station Alpha.", 15_000,
            _drapeau("amarre:" + NOM_STATION)),
    Mission("module", "Agrandir la station", "Ajouter un module habitat à la Station Alpha.",
            20_000, _station_agrandie),
    Mission("geo", "Géostationnaire", "Un satellite dont la période égale le jour terrestre (2 h 24).",
            20_000, _geostationnaire),
    Mission("lune_soi", "Survol lunaire", "Entrer dans la sphère d'influence de la Lune.",
            12_000, _drapeau("soi:Lune")),
    Mission("lune_orbite", "Orbite lunaire", "Se mettre en orbite autour de la Lune.",
            15_000, _drapeau("orbite:Lune")),
    Mission("lune_sol", "Alunissage", "Se poser en douceur sur la Lune.", 30_000,
            _drapeau("pose:Lune")),
    Mission("lune_retour", "Retour de la Lune", "Revenir sur Terre après s'être posé sur la Lune.",
            40_000, _pose_sur_terre_avec("pose:Lune")),
    Mission("mars_soi", "Cap sur Mars", "Entrer dans la sphère d'influence de Mars.", 40_000,
            _drapeau("soi:Mars")),
    Mission("mars_orbite", "Orbite martienne", "Se mettre en orbite autour de Mars.", 50_000,
            _drapeau("orbite:Mars")),
    Mission("mars_sol", "Premiers pas sur Mars", "Se poser sur Mars.", 80_000, _drapeau("pose:Mars")),
    Mission("venus_soi", "Étoile du berger", "Survoler Vénus.", 40_000, _drapeau("soi:Vénus")),
    Mission("jupiter_soi", "La géante", "Atteindre Jupiter.", 80_000, _drapeau("soi:Jupiter")),
    Mission("titan_sol", "Titan", "Se poser sur Titan (pense au parachute !).", 150_000,
            _drapeau("pose:Titan")),
    Mission("grand_tour", "Grand Tour", "Visiter Jupiter, Saturne, Uranus et Neptune avec un seul vaisseau.",
            300_000, _grand_tour),
]


def mission_suggeree(u):
    """Première mission pas encore accomplie (affichée comme objectif)."""
    for m in MISSIONS:
        if m.ident not in u.missions_faites:
            return m
    return None


def verifier(u):
    """Valide les missions dont la condition est remplie."""
    for m in MISSIONS:
        if m.ident in u.missions_faites:
            continue
        try:
            reussie = m.test(u, u.actif)
        except Exception:
            reussie = False
        if reussie:
            u.missions_faites.add(m.ident)
            if not u.bac_a_sable:
                u.fonds += m.prime
                u.bruit("succes")
                u.dire(t("Mission accomplie : {titre}  (+{prime})", titre=t(m.titre),
                        prime=format(m.prime, ",").replace(",", " ")), VERT, 8)
                nouvelles = [p.nom for p in CATALOGUE.values() if p.debloque_par == m.ident]
                if nouvelles:
                    u.dire(t("Nouvelles pièces : {noms}", noms=", ".join(t(n) for n in nouvelles)), CYAN, 10)
            else:
                u.bruit("succes")
                u.dire(t("Mission accomplie : {titre}", titre=t(m.titre)), VERT, 8)
