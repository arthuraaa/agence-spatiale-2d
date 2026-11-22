# -*- coding: utf-8 -*-
"""Sauvegarde / chargement de la partie au format JSON."""
import json
import os
from .pieces import Piece
from .vaisseau import Vaisseau
from .corps import Corps
from .manoeuvre import Manoeuvre

_DOSSIER_JEU = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def chemin_sauvegarde():
    """À côté du jeu si le dossier est accessible en écriture, sinon dans le dossier utilisateur."""
    prive = os.environ.get("ANDROID_PRIVATE")            # APK Android : dossier privé de l'appli
    if prive and os.access(prive, os.W_OK):
        return os.path.join(prive, "sauvegarde.json")
    if os.access(_DOSSIER_JEU, os.W_OK):
        return os.path.join(_DOSSIER_JEU, "sauvegarde.json")
    return os.path.join(os.path.expanduser("~"), "agence_spatiale_2d.json")


def vaisseau_vers_dict(u, v):
    return {
        "nom": v.nom, "corps": v.corps.nom, "mode": v.mode, "etat": list(u.etat(v)),
        "angle": v.angle, "omega": v.omega, "longitude": v.longitude, "gaz": v.gaz,
        "sas": v.sas, "rcs": v.rcs, "ref": v.ref_vitesse, "drapeaux": sorted(v.drapeaux),
        "noeud": v.noeud.vers_dict() if v.noeud is not None else None,
        "pieces": [p.vers_dict() for p in v.pieces],
        "racine": next((i for i, p in enumerate(v.pieces) if p is v.racine), -1),
        # séparation récente : l'index de l'autre vaisseau (le lien anti-recollage est refait au chargement)
        "separe_de": next((i for i, w in enumerate(u.vaisseaux) if w.id == v.separe_de), None),
    }


def univers_vers_dict(u):
    cible = None
    if isinstance(u.cible, Corps):
        cible = {"corps": u.cible.nom}
    elif u.cible in u.vaisseaux:
        cible = {"vaisseau": u.vaisseaux.index(u.cible)}
    return {
        "version": 1, "t": u.t, "bac_a_sable": u.bac_a_sable, "fonds": u.fonds,
        "missions": sorted(u.missions_faites),
        "vaisseaux": [vaisseau_vers_dict(u, v) for v in u.vaisseaux],
        "actif": u.vaisseaux.index(u.actif) if u.actif in u.vaisseaux else -1,
        "cible": cible,
        "triche": dict(u.triche),
    }


def dict_vers_univers(d):
    from .univers import Univers
    u = Univers(d.get("bac_a_sable", False), avec_station=False)
    u.t = d["t"]
    u.fonds = d.get("fonds", u.fonds)
    u.missions_faites = set(d.get("missions", []))
    u.triche = dict(d.get("triche", {}))
    sur_rails = []
    for dv in d["vaisseaux"]:
        pieces = [Piece.depuis_dict(x) for x in dv["pieces"]]
        v = Vaisseau(dv["nom"], pieces, u.par_nom[dv["corps"]])
        i = dv.get("racine", -1)
        v.racine = pieces[i] if 0 <= i < len(pieces) else None
        v.angle, v.omega = dv["angle"], dv.get("omega", 0.0)
        v.longitude, v.gaz = dv.get("longitude", 0.0), dv.get("gaz", 0.0)
        v.sas, v.rcs = dv.get("sas", "stab"), dv.get("rcs", False)
        v.ref_vitesse = dv.get("ref", "orbite")
        v.drapeaux = set(dv.get("drapeaux", []))
        if dv.get("noeud"):
            v.noeud = Manoeuvre.depuis_dict(dv["noeud"])
        if dv["mode"] == "pose":
            v.mode = "pose"
        else:
            v.x, v.y, v.vx, v.vy = dv["etat"]
            v.mode = "physique"
            if dv["mode"] == "rails":
                sur_rails.append(v)
        u.vaisseaux.append(v)
    for v, dv in zip(u.vaisseaux, d["vaisseaux"]):    # liens de séparation récente (ids refaits à neuf)
        i = dv.get("separe_de")
        if isinstance(i, int) and 0 <= i < len(u.vaisseaux) and u.vaisseaux[i] is not v:
            v.separe_de = u.vaisseaux[i].id
    i = d.get("actif", -1)
    u.actif = u.vaisseaux[i] if 0 <= i < len(u.vaisseaux) else None
    for v in sur_rails:
        u._mettre_sur_rails(v)
    u.recalculer_plan()
    c = d.get("cible")
    if c:
        if "corps" in c:
            u.cible = u.par_nom.get(c["corps"])
        elif 0 <= c.get("vaisseau", -1) < len(u.vaisseaux):
            u.cible = u.vaisseaux[c["vaisseau"]]
    return u


def sauvegarder(u, chemin=None):
    if getattr(u, "tutoriel", None):                  # un tutoriel ne remplace jamais la vraie partie
        return None
    chemin = chemin or chemin_sauvegarde()
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(univers_vers_dict(u), f, ensure_ascii=False, indent=1)
    return chemin


def charger(chemin=None):
    chemin = chemin or chemin_sauvegarde()
    with open(chemin, "r", encoding="utf-8") as f:
        donnees = json.load(f)
    try:
        return dict_vers_univers(donnees)
    except TypeError:                                 # sauvegarde fausse (types inattendus) :
        raise ValueError("sauvegarde illisible")      # même refus propre qu'un JSON cassé


def sauvegarde_existe():
    return os.path.exists(chemin_sauvegarde())
