# -*- coding: utf-8 -*-
"""
Prédiction de trajectoire par « coniques raccordées ».

Un vaisseau ne subit la gravité que d'un seul corps à la fois : celui dont il
occupe la sphère d'influence (SOI). Sa trajectoire est donc une suite de
tronçons képlériens :

    orbite autour de la Terre -> entrée dans la SOI de la Lune -> survol
    hyperbolique de la Lune -> retour dans la SOI de la Terre -> ...

Chaque tronçon se termine par un événement daté avec précision :
  "sortie"  : on quitte la SOI du corps (on passe chez son parent)
  "entree"  : on entre dans la SOI d'un de ses satellites
  "atmo"    : on entre dans l'atmosphère
  "impact"  : on touche le sol (corps sans atmosphère)
  "revoir"  : rien de prévu sur ce tour d'orbite, mais à recalculer au suivant
  None      : orbite fermée sans histoire
La simulation se sert des mêmes tronçons pour déclencher ces événements.
"""
from math import hypot, ceil, floor, pi
from .orbite import Orbite, TAU, INFINI

HORIZON = 3.0e9          # durée maximale explorée (s)
MARGE_ENTREE = 0.985     # on « entre » un peu à l'intérieur de la SOI (évite les allers-retours)


class Troncon:
    __slots__ = ("orbite", "corps", "t0", "t1", "fin", "suivant", "entree")

    def __init__(self, orbite, corps, t0, t1, fin, suivant, entree):
        self.orbite = orbite      # Orbite (relative à `corps`)
        self.corps = corps
        self.t0 = t0
        self.t1 = t1
        self.fin = fin            # type d'événement de fin (voir plus haut)
        self.suivant = suivant    # corps dans lequel on entre si fin == "entree"
        self.entree = entree      # True si ce tronçon commence par une entrée dans `corps`


def fenetres_bande(orb, r_bas, r_haut, ta, tb):
    """Intervalles de temps de [ta, tb] pendant lesquels le rayon est dans [r_bas, r_haut]."""
    if orb.ra < r_bas or orb.rp > r_haut:
        return []
    if orb.e < 1e-9:
        return [(ta, tb)]
    nu1 = orb.nu_depuis_rayon(r_bas) if r_bas > orb.rp else None
    nu2 = orb.nu_depuis_rayon(r_haut) if r_haut < orb.ra else None
    if nu1 is None and nu2 is None:
        return [(ta, tb)]
    if nu1 is None:                                  # la bande contient le périapside
        M2 = orb.M_depuis_nu(nu2)
        base = [(-M2, M2)]
    elif nu2 is None:                                # la bande contient l'apoapside
        M1 = orb.M_depuis_nu(nu1)
        base = [(M1, TAU - M1)]
    else:
        M1, M2 = orb.M_depuis_nu(nu1), orb.M_depuis_nu(nu2)
        base = [(M1, M2), (-M2, -M1)]
    Mc = orb.M(ta)
    Mfin = Mc + orb.n * (tb - ta) if tb < INFINI else INFINI
    out = []
    for bas, haut in base:
        if orb.elliptique:
            k0 = int(floor((Mc - haut) / TAU))
            k1 = int(ceil((Mfin - bas) / TAU))
        else:
            k0 = k1 = 0
        for k in range(k0, k1 + 1):
            a = max(bas + TAU * k, Mc)
            b = min(haut + TAU * k, Mfin)
            if b > a:
                out.append((ta + (a - Mc) / orb.n, ta + (b - Mc) / orb.n))
    out.sort()
    return out


def _balayer(orb, enfant, wa, wb):
    """Cherche l'instant d'entrée dans la SOI de `enfant` entre wa et wb (ou None)."""
    soi = enfant.soi * MARGE_ENTREE
    pas_max = enfant.periode / 60.0
    if orb.elliptique:
        pas_max = min(pas_max, orb.periode / 60.0)
    n = int(min(600, max(8, ceil((wb - wa) / pas_max))))
    dt = (wb - wa) / n

    def ecart(t):
        x, y = orb.position(t)
        cx, cy = enfant.position_relative(t)
        return x - cx, y - cy

    px, py = ecart(wa)
    if hypot(px, py) < soi:
        return wa
    t_prec = wa
    for k in range(1, n + 1):
        t = wa + k * dt
        qx, qy = ecart(t)
        dx, dy = qx - px, qy - py
        d2 = dx * dx + dy * dy
        s = 0.0 if d2 == 0.0 else max(0.0, min(1.0, -(px * dx + py * dy) / d2))
        mx, my = px + s * dx, py + s * dy       # point le plus proche sur le segment
        if mx * mx + my * my < soi * soi:
            bas, haut = t_prec, t_prec + s * dt
            hx, hy = ecart(haut)
            trouve = hypot(hx, hy) < soi
            if not trouve:                       # approximation linéaire trop optimiste
                for j in range(1, 17):
                    tj = t_prec + dt * j / 16.0
                    ex, ey = ecart(tj)
                    if hypot(ex, ey) < soi:
                        haut, trouve = tj, True
                        break
            if trouve:
                for _ in range(60):              # bissection sur la vraie trajectoire
                    mil = 0.5 * (bas + haut)
                    ex, ey = ecart(mil)
                    if hypot(ex, ey) < soi:
                        haut = mil
                    else:
                        bas = mil
                    if haut - bas < 1e-3:
                        break
                return haut
        px, py, t_prec = qx, qy, t
    return None


def chercher_rencontre(orb, corps, ta, tb):
    """Première entrée dans la SOI d'un satellite de `corps` : (instant, satellite) ou None."""
    meilleur = None
    for enfant in corps.enfants:
        for wa, wb in fenetres_bande(orb, enfant.a - enfant.soi, enfant.a + enfant.soi, ta, tb):
            if meilleur is not None and wa >= meilleur[0]:
                break
            te = _balayer(orb, enfant, wa, wb)
            if te is not None:
                if meilleur is None or te < meilleur[0]:
                    meilleur = (te, enfant)
                break
    return meilleur


def fin_de_troncon(orb, corps, ta, garde=0.0):
    """Calcule l'événement qui termine le tronçon : (instant, type, corps suivant)."""
    candidats = []
    x, y = orb.position(ta)
    r_atm = corps.R + corps.atm_h - 1.0
    if corps.atm_h > 0.0 and hypot(x, y) > r_atm:
        r_lim, genre = r_atm, "atmo"
    else:
        r_lim, genre = corps.R + garde, "impact"
    if orb.rp < r_lim:
        d = orb.delai_jusquau_rayon(r_lim, ta, en_descente=True)
        if d is not None:
            candidats.append((ta + d, genre))
    if corps.soi < INFINI and (not orb.elliptique or orb.ra > corps.soi):
        d = orb.delai_jusquau_rayon(corps.soi, ta, en_descente=False)
        candidats.append((ta + (d or 0.0), "sortie"))
    candidats.sort()
    if candidats:
        limite = candidats[0][0]
    else:
        limite = ta + orb.periode if orb.elliptique else INFINI
    if corps.enfants:
        r = chercher_rencontre(orb, corps, ta, min(limite, ta + HORIZON))
        if r is not None and r[0] < limite:
            return r[0], "entree", r[1]
    if candidats:
        return candidats[0][0], candidats[0][1], None
    if orb.elliptique:
        croise = any(orb.rp < e.a + e.soi and orb.ra > e.a - e.soi for e in corps.enfants)
        return ta + orb.periode, ("revoir" if croise else None), None
    return INFINI, None, None


def predire(orb, corps, ta, garde=0.0, max_troncons=4):
    """Enchaîne les tronçons à partir de l'orbite `orb` autour de `corps` à l'instant ta."""
    out = []
    entree = False
    for _ in range(max_troncons):
        t1, fin, suivant = fin_de_troncon(orb, corps, ta, garde)
        out.append(Troncon(orb, corps, ta, t1, fin, suivant, entree))
        if fin == "sortie":
            x, y, vx, vy = orb.etat(t1)
            bx, by, bvx, bvy = corps.etat_relatif(t1)
            nouveau = corps.parent
            orb = Orbite(x + bx, y + by, vx + bvx, vy + bvy, nouveau.mu, t1)
            entree = False
        elif fin == "entree":
            x, y, vx, vy = orb.etat(t1)
            bx, by, bvx, bvy = suivant.etat_relatif(t1)
            nouveau = suivant
            orb = Orbite(x - bx, y - by, vx - bvx, vy - bvy, nouveau.mu, t1)
            entree = True
        else:
            break
        if orb.degeneree:
            break
        corps, ta = nouveau, t1
    return out


def approche_minimale(troncons, position_cible, parent, t, n=96):
    """
    Plus courte distance future entre la trajectoire et une cible.
    position_cible(t) donne la position de la cible relative à `parent`.
    Renvoie (instant, distance, (x, y) vaisseau, (x, y) cible) ou None.
    """
    meilleur = None
    for tr in troncons:
        if tr.corps is not parent:
            continue
        orb = tr.orbite
        ta = max(tr.t0, t)
        if tr.fin is not None and tr.t1 < INFINI:
            tb = tr.t1
        elif orb.elliptique:
            tb = ta + orb.periode
        else:
            tb = ta + 5.0e7
        if tb <= ta:
            continue

        def dist(tt):
            x, y = orb.position(tt)
            cx, cy = position_cible(tt)
            return hypot(x - cx, y - cy)

        pas = (tb - ta) / n
        ds = [dist(ta + k * pas) for k in range(n + 1)]
        k = min(range(n + 1), key=ds.__getitem__)
        bas, haut = ta + max(0, k - 1) * pas, ta + min(n, k + 1) * pas
        for _ in range(40):                      # recherche ternaire du minimum
            m1 = bas + (haut - bas) / 3.0
            m2 = haut - (haut - bas) / 3.0
            if dist(m1) < dist(m2):
                haut = m2
            else:
                bas = m1
        tm = 0.5 * (bas + haut)
        d = dist(tm)
        if meilleur is None or d < meilleur[1]:
            meilleur = (tm, d, orb.position(tm), position_cible(tm))
    return meilleur
