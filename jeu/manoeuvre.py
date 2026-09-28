# -*- coding: utf-8 -*-
"""
Nœuds de manœuvre : préparer une poussée à l'avance et voir la trajectoire obtenue.

Un nœud dit : « à l'instant t, donne dv_pro m/s vers l'avant et dv_rad m/s vers
le haut ». On en déduit la vitesse juste après l'impulsion, donc une nouvelle
orbite, que l'on prolonge avec le module de prédiction habituel (trajectoire.py).
Le résultat est dessiné en bleu par-dessus la trajectoire actuelle.

Deux directions de réglage, comme dans KSP :
  prograde (vert) : dans le sens de la vitesse à l'instant du nœud ;
  radial + (cyan) : perpendiculaire à la vitesse, du côté opposé au corps.

Une impulsion instantanée n'existe pas dans la vraie vie : le jeu calcule donc
aussi la durée de combustion, et conseille d'allumer le moteur à la moitié de
cette durée avant le nœud.
"""
from math import hypot, exp, atan2
from .constantes import G0
from .orbite import Orbite
from .trajectoire import predire

FIN_MANOEUVRE = 0.05      # Δv restant (m/s) en dessous duquel la manœuvre est finie
FENETRE = 60.0            # on ne décompte le Δv du nœud qu'à moins d'une minute de l'allumage


class Manoeuvre:
    """Une impulsion planifiée : à l'instant t, dv = pro * prograde + rad * radial."""

    def __init__(self, t, pro=0.0, rad=0.0):
        self.t = t             # instant prévu de l'impulsion (temps de jeu, s)
        self.pro = pro         # Δv prograde (m/s), négatif = rétrograde
        self.rad = rad         # Δv radial (m/s), négatif = vers le corps
        self.restant = None    # (dvx, dvy) encore à donner, une fois la combustion commencée
        self.depart = None     # (dvx, dvy) au début de la combustion (détection du dépassement)
        self.applique = 0.0    # Δv déjà donné (m/s)
        self.pilote_energie = False   # exécution automatique : c'est le pilote qui dira « fini »

    @property
    def commencee(self):
        return self.restant is not None

    def dv(self):
        """Δv qu'il reste à donner (m/s)."""
        if self.restant is not None:
            return hypot(self.restant[0], self.restant[1])
        return hypot(self.pro, self.rad)

    def dv_prevu(self):
        """Δv total prévu au départ (m/s)."""
        return hypot(self.pro, self.rad)

    # ------------------------------------------------------------- exécution
    def commencer(self, vecteur):
        self.restant = self.depart = vecteur

    def consommer(self, dvx, dvy):
        """Retranche le Δv réellement donné. Renvoie True quand la manœuvre est finie."""
        self.restant = (self.restant[0] - dvx, self.restant[1] - dvy)
        self.applique += hypot(dvx, dvy)
        depassement = self.restant[0] * self.depart[0] + self.restant[1] * self.depart[1] < 0.0
        return self.dv() < FIN_MANOEUVRE or depassement

    # ----------------------------------------------------------- sauvegarde
    def vers_dict(self):
        d = {"t": self.t, "pro": self.pro, "rad": self.rad}
        if self.restant is not None:
            d["restant"], d["depart"] = list(self.restant), list(self.depart)
        return d

    @staticmethod
    def depuis_dict(d):
        n = Manoeuvre(d["t"], d.get("pro", 0.0), d.get("rad", 0.0))
        if d.get("restant"):
            n.restant, n.depart = tuple(d["restant"]), tuple(d.get("depart", d["restant"]))
        return n


# =============================================================================
# Calculs autour d'un nœud
# =============================================================================
def troncon_a(v, t):
    """Tronçon de la trajectoire prédite qui contient l'instant t (ou None)."""
    trs = v.troncons
    if not trs:
        return None
    for tr in trs:
        if tr.t0 <= t < tr.t1:
            return tr
    if t < trs[0].t0:                      # nœud dans le passé : on reste sur l'orbite actuelle
        return trs[0]
    dernier = trs[-1]                      # orbite fermée sans événement : elle se répète
    if dernier.fin in (None, "revoir") and dernier.orbite.elliptique:
        return dernier
    return None


def reperes(orb, t):
    """Vecteurs unitaires prograde et radial + à l'instant t."""
    x, y, vx, vy = orb.etat(t)
    n = hypot(vx, vy)
    if n < 1e-9:
        return (1.0, 0.0), (0.0, 1.0)
    px, py = vx / n, vy / n
    rx, ry = -py, px                       # perpendiculaire à la vitesse...
    if rx * x + ry * y < 0.0:              # ... tournée vers le haut (à l'opposé du corps)
        rx, ry = -rx, -ry
    return (px, py), (rx, ry)


def impulsion(v, n):
    """Vecteur Δv du nœud (m/s), ou None si le nœud n'est plus rattachable à la trajectoire."""
    if n.restant is not None:
        return n.restant
    tr = troncon_a(v, n.t)
    if tr is None:
        return None
    (px, py), (rx, ry) = reperes(tr.orbite, n.t)
    return (n.pro * px + n.rad * rx, n.pro * py + n.rad * ry)


def orbite_apres(v, n):
    """Orbite juste après l'impulsion : (orbite, corps) ou None si le calcul n'a pas de sens."""
    tr = troncon_a(v, n.t)
    if tr is None:
        return None
    x, y, vx, vy = tr.orbite.etat(n.t)
    dv = impulsion(v, n)
    if dv is None:
        return None
    orb = Orbite(x, y, vx + dv[0], vy + dv[1], tr.corps.mu, n.t)
    return None if orb.degeneree else (orb, tr.corps)


def plan(v, n, garde=0.0, max_troncons=4):
    """Trajectoire prévue après la manœuvre (liste de tronçons, vide si impossible)."""
    r = orbite_apres(v, n)
    if r is None:
        return []
    orb, corps = r
    return predire(orb, corps, n.t, garde, max_troncons)


def duree_combustion(v, dv):
    """Durée de la poussée à plein gaz (s) et True s'il y a assez de carburant."""
    mot = v.moteur_actif()
    if dv <= 1e-6:
        return 0.0, True
    if mot is None:
        return 0.0, False
    ve = mot.m.isp_vide * G0                       # vitesse d'éjection (m/s)
    m0 = v.geometrie().masse
    besoin = m0 * (1.0 - exp(-dv / ve))            # carburant nécessaire (kg)
    dispo = v.carburant_actif()[0]
    debit = mot.m.poussee / ve                     # kg/s à plein gaz
    if debit <= 0.0:
        return 0.0, False
    return min(besoin, dispo) / debit, besoin <= dispo


def instant_allumage(v, n):
    """Instant conseillé pour allumer : la moitié de la combustion avant le nœud."""
    return n.t - duree_combustion(v, n.dv())[0] / 2.0


def angle_dv(v, n):
    """Direction (rad) dans laquelle pointer le vaisseau pour exécuter le nœud, ou None."""
    dv = impulsion(v, n)
    if dv is None or hypot(dv[0], dv[1]) < 1e-6:
        return None
    return atan2(dv[1], dv[0])


def periode_au_noeud(v, n):
    """Durée d'un tour d'orbite à l'endroit du nœud (None si l'orbite n'est pas fermée)."""
    tr = troncon_a(v, n.t)
    if tr is None or not tr.orbite.elliptique:
        return None
    return tr.orbite.periode
