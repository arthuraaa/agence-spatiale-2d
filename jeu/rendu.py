# -*- coding: utf-8 -*-
"""
Dessin du monde : caméra, corps célestes, trajectoires, vaisseaux.

Une seule vue à zoom continu : de la fusée (40 px/m) au système solaire entier.
Astuce principale : quand un disque devient gigantesque à l'écran (planète vue
de près), on ne dessine que l'arc visible sous forme de polygone.
"""
import random
from math import cos, sin, atan2, hypot, pi, log10, ceil, acosh, acos, log, exp, degrees
import pygame
from pygame import gfxdraw
from .constantes import (MIROIR_X, ZOOM_MIN, ZOOM_MAX, RAYON_GRAND_CERCLE, LONGITUDE_PAS_DE_TIR,
                         NOIR, BLANC, GRIS, CYAN, ORANGE, VERT, ROUGE, JAUNE, MAGENTA,
                         COULEURS_TRAJECTOIRE, COULEURS_PLAN, BLEU_PLAN, NOEUD_RAYON_POIGNEE)
from . import manoeuvre as mod_manoeuvre
from .orbite import TAU, INFINI, angle_pi
from .corps import Corps
from .textes import t
from .interface import texte, fmt_distance, fmt_vitesse


def melange(c1, c2, f):
    """Couleur intermédiaire entre c1 (f = 0) et c2 (f = 1)."""
    f = max(0.0, min(1.0, f))
    return (int(c1[0] + (c2[0] - c1[0]) * f), int(c1[1] + (c2[1] - c1[1]) * f),
            int(c1[2] + (c2[2] - c1[2]) * f))


def degrade_vertical(surf, c_haut, c_bas, bandes=64):
    """Remplit l'écran d'un dégradé vertical (peu coûteux : 64 bandes rectangulaires)."""
    L, H = surf.get_size()
    for k in range(bandes):
        y0 = k * H // bandes
        y1 = max(y0 + 1, (k + 1) * H // bandes)
        surf.fill(melange(c_haut, c_bas, k / (bandes - 1)), (0, y0, L, y1 - y0))


# =============================================================================
# Caméra
# =============================================================================
class Camera:
    def __init__(self):
        self.x = self.y = 0.0          # position visée (repère absolu, m)
        self.zoom = 4.0                # pixels par mètre
        self.angle = 0.0               # rotation de la vue (rad)
        self.focus = None              # None = vaisseau actif, sinon un Corps ou un Vaisseau
        self.dx = self.dy = 0.0        # décalage libre de la vue (on la fait glisser), en m
        self.retour = False            # retour animé vers le vaisseau en cours
        self.zoom_vise = None          # zoom à atteindre pendant ce retour
        self.mode = "auto"             # auto | horizon | nord
        self.l, self.h = 1280, 720
        self.echantillons = []         # [(x_ecran, y_ecran, instant)] le long de la trajectoire
        self.poignees = []             # [(nom, (x, y), (dx, dy))] du nœud de manœuvre
        self.rayon_poignee = NOEUD_RAYON_POIGNEE   # plus grand sur écran tactile
        self._c, self._s = 1.0, 0.0
        self._mx = -1.0 if MIROIR_X else 1.0
        self.tremble = 0.0             # rentrée atmosphérique : la vue vibre (0 à 1)
        self._jx = self._jy = 0.0      # vibration de la frame courante, en pixels

    def taille(self, l, h):
        self.l, self.h = l, h

    def zoomer(self, facteur):
        self.zoom = max(ZOOM_MIN, min(ZOOM_MAX, self.zoom * facteur))
        self.retour, self.zoom_vise = False, None      # le joueur reprend la main sur la vue

    def glisser(self, p0, p1):
        """Fait glisser la vue (souris ou doigt) : le point du monde sous p0 vient sous p1."""
        x0, y0 = self.vers_monde(*p0)
        x1, y1 = self.vers_monde(*p1)
        self.dx += x0 - x1
        self.dy += y0 - y1
        self.x += x0 - x1
        self.y += y0 - y1
        self.retour, self.zoom_vise = False, None

    def hors_vaisseau(self, u):
        """Vrai si la vue a quitté le vaisseau actif : centrée ailleurs, décalée, ou fusée réduite à un point."""
        a = u.actif
        if a is None or self.retour:
            return False
        return (self.focus is not None or hypot(self.dx, self.dy) * self.zoom > 60.0
                or a.geometrie().longueur * self.zoom < 2.0)

    def revenir(self, u):
        """Retour animé sur le vaisseau actif ; on rezoome si la fusée n'est plus qu'un point."""
        a = u.actif
        if a is None:
            return
        ax, ay = u.position_absolue(a)
        self.dx, self.dy = self.x - ax, self.y - ay     # on part de la vue actuelle
        self.focus = None
        g = a.geometrie()
        self.zoom_vise = None
        if g.longueur * self.zoom < 20.0:
            self.zoom_vise = max(ZOOM_MIN, min(ZOOM_MAX, 0.18 * self.h / max(g.longueur, 6.0)))
        self.retour = True

    def _animer_retour(self, dt):
        """D'abord glisser jusqu'à la fusée au zoom actuel, puis zoomer sur elle."""
        f = min(1.0, 10.0 * dt)
        self.dx -= self.dx * f
        self.dy -= self.dy * f
        if self.zoom_vise is not None and hypot(self.dx, self.dy) * self.zoom < 40.0:
            self.zoom *= exp(log(self.zoom_vise / self.zoom) * min(1.0, 5.0 * dt))
        if hypot(self.dx, self.dy) * self.zoom < 0.5 and \
                (self.zoom_vise is None or abs(log(self.zoom_vise / self.zoom)) < 0.02):
            self.dx = self.dy = 0.0
            if self.zoom_vise is not None:
                self.zoom = self.zoom_vise
            self.retour, self.zoom_vise = False, None

    def suivre(self, u, dt):
        """Place la caméra sur son sujet et règle la rotation de la vue."""
        sujet = self.focus if self.focus is not None else u.actif
        if sujet is not None and getattr(sujet, "detruit", False):
            sujet = self.focus = None
        if self.retour:
            self._animer_retour(dt)
        if sujet is not None:
            sx, sy = u.position_absolue(sujet)
            self.x, self.y = sx + self.dx, sy + self.dy
        cible = 0.0
        if sujet is not None and not isinstance(sujet, Corps):
            e = u.etat(sujet)
            pres = self.zoom * sujet.corps.R > 900.0
            if self.mode == "horizon" or (self.mode == "auto" and pres):
                cible = atan2(e[1], e[0]) - pi / 2      # verticale locale vers le haut de l'écran
        ecart = angle_pi(cible - self.angle)
        self.angle = angle_pi(self.angle + ecart * min(1.0, 6.0 * dt))
        self._c, self._s = cos(self.angle), sin(self.angle)
        # une vibration unique par frame : tout le monde bouge ensemble (pas de lignes déchirées)
        if self.tremble > 0.0:
            a = 6.0 * self.tremble
            self._jx = (random.random() - 0.5) * a
            self._jy = (random.random() - 0.5) * a
        else:
            self._jx = self._jy = 0.0

    def vers_ecran(self, ax, ay):
        dx, dy = ax - self.x, ay - self.y
        rx = dx * self._c + dy * self._s
        ry = -dx * self._s + dy * self._c
        return (self.l / 2 + self._mx * rx * self.zoom + self._jx,
                self.h / 2 - ry * self.zoom + self._jy)

    def direction_ecran(self, dx, dy):
        """Transforme une direction du monde en direction à l'écran (y vers le bas)."""
        return self._mx * (dx * self._c + dy * self._s), -(-dx * self._s + dy * self._c)

    def vers_monde(self, sx, sy):
        rx = (sx - self._jx - self.l / 2) / self.zoom * self._mx
        ry = -(sy - self._jy - self.h / 2) / self.zoom
        return self.x + rx * self._c - ry * self._s, self.y + rx * self._s + ry * self._c


# =============================================================================
# Primitives robustes (gros cercles, lignes hors écran)
# =============================================================================
def disque(surf, couleur, cx, cy, r):
    """Disque plein, même s'il est immense (on ne dessine alors que la partie visible)."""
    L, H = surf.get_size()
    if cx + r < 0 or cx - r > L or cy + r < 0 or cy - r > H:
        return
    if r < 1.0:
        surf.fill(couleur, (int(cx), int(cy), 2, 2))
        return
    if r <= RAYON_GRAND_CERCLE:
        pygame.draw.circle(surf, couleur, (int(cx), int(cy)), int(r))
        return
    mx, my, demi = L / 2, H / 2, hypot(L, H) / 2
    d = hypot(mx - cx, my - cy)
    if d - demi > r:
        return
    if d + demi < r:
        surf.fill(couleur)
        return
    a0 = atan2(my - cy, mx - cx)
    # r - demi peut s'annuler (disque immense centré sur un grand écran) : on borne, et
    # l'ouverture est alors clampée à pi (le polygone couvre le disque entier)
    ouverture = min(pi, 2.2 * demi / max(r - demi, 1e-6) + 0.02)
    n = 48
    pts = [(cx + r * cos(a0 - ouverture + 2 * ouverture * k / n),
            cy + r * sin(a0 - ouverture + 2 * ouverture * k / n)) for k in range(n + 1)]
    r_int = r - 3 * demi
    if r_int > 0:
        pts += [(cx + r_int * cos(a0 + ouverture - 2 * ouverture * k / 8),
                 cy + r_int * sin(a0 + ouverture - 2 * ouverture * k / 8)) for k in range(9)]
    else:
        pts.append((cx, cy))
    pygame.draw.polygon(surf, couleur, pts)


def cercle(surf, couleur, cx, cy, r, epaisseur=1):
    """Contour de cercle, même immense."""
    L, H = surf.get_size()
    if r < 1.0 or cx + r < 0 or cx - r > L or cy + r < 0 or cy - r > H:
        return
    if r <= RAYON_GRAND_CERCLE:
        pygame.draw.circle(surf, couleur, (int(cx), int(cy)), int(r), epaisseur)
        return
    mx, my, demi = L / 2, H / 2, hypot(L, H) / 2
    d = hypot(mx - cx, my - cy)
    if d < 1e-9 or abs(d - r) > demi:
        return
    c = (r * r + d * d - demi * demi) / (2 * r * d)
    ouverture = acos(max(-1.0, min(1.0, c))) * 1.05 + 1e-4
    a0 = atan2(my - cy, mx - cx)
    n = 64
    pts = [(cx + r * cos(a0 - ouverture + 2 * ouverture * k / n),
            cy + r * sin(a0 - ouverture + 2 * ouverture * k / n)) for k in range(n + 1)]
    pygame.draw.lines(surf, couleur, False, pts, epaisseur)


def _couper(x0, y0, x1, y1, xmin, ymin, xmax, ymax):
    """Découpe un segment sur un rectangle (Liang-Barsky). Renvoie None s'il est dehors."""
    dx, dy = x1 - x0, y1 - y0
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, x0 - xmin), (dx, xmax - x0), (-dy, y0 - ymin), (dy, ymax - y0)):
        if p == 0:
            if q < 0:
                return None
        else:
            r = q / p
            if p < 0:
                if r > t1:
                    return None
                if r > t0:
                    t0 = r
            else:
                if r < t0:
                    return None
                if r < t1:
                    t1 = r
    return x0 + t0 * dx, y0 + t0 * dy, x0 + t1 * dx, y0 + t1 * dy


def ligne_brisee(surf, couleur, pts, epaisseur=1):
    """Polyligne dont les points peuvent être très loin hors de l'écran."""
    if len(pts) < 2:
        return
    L, H = surf.get_size()
    if all(-20000 < x < 20000 and -20000 < y < 20000 for x, y in pts):
        if epaisseur == 1:
            pygame.draw.aalines(surf, couleur, False, pts)
        else:
            pygame.draw.lines(surf, couleur, False, pts, epaisseur)
        return
    x0, y0 = pts[0]
    for x1, y1 in pts[1:]:
        s = _couper(x0, y0, x1, y1, -40, -40, L + 40, H + 40)
        if s is not None:
            pygame.draw.line(surf, couleur, (s[0], s[1]), (s[2], s[3]), epaisseur)
        x0, y0 = x1, y1


def pointilles(surf, couleur, p0, p1, pas=8):
    d = hypot(p1[0] - p0[0], p1[1] - p0[1])
    if d < 1 or d > 6000:
        return
    n = int(d / pas)
    for k in range(0, n, 2):
        a, b = k / n, min(1.0, (k + 1) / n)
        pygame.draw.line(surf, couleur, (p0[0] + (p1[0] - p0[0]) * a, p0[1] + (p1[1] - p0[1]) * a),
                         (p0[0] + (p1[0] - p0[0]) * b, p0[1] + (p1[1] - p0[1]) * b))


# =============================================================================
# Pièces et vaisseaux
# =============================================================================
def _rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def formes_piece(p, l, h):
    """Polygones d'une pièce en coordonnées locales (x latéral, y de 0 en bas à h en haut)."""
    f = p.m.forme
    c = p.m.couleur
    d = l / 2
    if f == "radial":                     # dessiné à part : les attaches entre cœur et booster
        return []
    if f == "capsule":
        return [(c, [(-d, 0), (d, 0), (l * .3, h * .85), (l * .18, h), (-l * .18, h), (-l * .3, h * .85)]),
                ((70, 60, 56), [(-d, 0), (d, 0), (l * .47, h * .1), (-l * .47, h * .1)]),
                ((40, 72, 116), _rect(-l * .11, h * .45, l * .11, h * .66))]
    if f == "sonde":
        return [(c, _rect(-d, 0, d, h)), ((60, 50, 30), _rect(-d, h * .35, d, h * .5)),
                ((200, 200, 205), _rect(-0.03, h, 0.03, h + 0.5))]
    if f == "coiffe":
        return [(c, [(-d, 0), (d, 0), (l * .3, h * .6), (l * .1, h * .93), (0, h), (-l * .1, h * .93),
                     (-l * .3, h * .6)]),
                ((200, 70, 60), [(-l * .1, h * .93), (l * .1, h * .93), (0, h)])]
    if f == "reservoir":
        bande = (235, 130, 50) if l <= 1.6 else (70, 110, 190)
        return [(c, _rect(-d, 0, d, h)), (bande, _rect(-d, h * .78, d, h * .78 + min(0.5, h * .12))),
                ((150, 154, 166), _rect(-d, 0, d, 0.08)), ((150, 154, 166), _rect(-d, h - 0.08, d, h))]
    if f == "moteur":
        haut = (95, 98, 108) if p.m.cle != "atome" else c
        return [(haut, _rect(-l * .28, h * .6, l * .28, h)),
                ((58, 60, 68), [(-l * .2, h * .62), (l * .2, h * .62), (l * .46, 0), (-l * .46, 0)]),
                ((128, 132, 144), _rect(-l * .46, 0, l * .46, h * .06))]
    if f == "decoupleur":
        return [(c, _rect(-d, 0, d, h)), ((230, 200, 60), _rect(-d, h * .35, d, h * .65))]
    if f == "port":
        return [((120, 126, 140), _rect(-l * .38, 0, l * .38, h * .55)), (c, _rect(-d, h * .55, d, h)),
                ((60, 64, 74), _rect(-l * .2, h * .88, l * .2, h))]
    if f == "train":
        return [(c, _rect(-d, 0, d, h))]
    if f == "module":
        k = 0.45
        return [(c, [(-d + k, 0), (d - k, 0), (d, k), (d, h - k), (d - k, h), (-d + k, h), (-d, h - k), (-d, k)]),
                ((90, 130, 200), _rect(-d, h * .47, d, h * .53)),
                ((40, 72, 116), _rect(-0.3, h * .18, 0.3, h * .28)),
                ((40, 72, 116), _rect(-0.3, h * .68, 0.3, h * .78))]
    if f == "panneaux":
        out = [(c, _rect(-d, 0, d, h)), ((150, 154, 166), _rect(-d - 6.4, h * .46, d + 6.4, h * .54))]
        for s in (-1, 1):
            out.append(((36, 62, 140), _rect(s * (d + 0.5), h * .1, s * (d + 6.4), h * .9)))
            for k in range(1, 5):
                xk = s * (d + 0.5 + 5.9 * k / 5)
                out.append(((80, 110, 200), _rect(xk - 0.04, h * .1, xk + 0.04, h * .9)))
        return out
    return [(c, _rect(-d, 0, d, h))]


def _flamme(surf, P, demi_ouv, yb, l, flamme, vide):
    """Flamme d'un moteur actif, en couches superposées : halo translucide,
    corps orange, cœur clair, pointe blanche. Scintille (longueur et inclinaison
    tirées au hasard à chaque image). demi_ouv : demi-largeur à la tuyère, en m."""
    lf = l * (1.3 + 2.6 * flamme) * (0.85 + 0.3 * random.random())
    g = (random.random() - 0.5) * 0.18 * l             # petit tremblement latéral
    try:                                               # halo diffus autour du jet
        gfxdraw.filled_polygon(surf, [P(-demi_ouv * 1.6, yb), P(demi_ouv * 1.6, yb),
                                      P(g, yb - lf * 1.25)], (255, 110, 20, 60))
    except (OverflowError, pygame.error):
        pass
    pygame.draw.polygon(surf, (255, 150, 40), [P(-demi_ouv, yb), P(demi_ouv, yb), P(g, yb - lf)])
    pygame.draw.polygon(surf, (255, 225, 140), [P(-demi_ouv * .55, yb), P(demi_ouv * .55, yb),
                                                P(g * .5, yb - lf * .6)])
    pygame.draw.polygon(surf, (255, 255, 240), [P(-demi_ouv * .22, yb), P(demi_ouv * .22, yb),
                                                P(g * .3, yb - lf * .32)])


def _fumee(surf, P, yb, l, z, vide):
    """Panne de fumée sous la tuyère quand l'air est dense (vide proche de 0)."""
    for k in range(5):
        f = (k + 1) / 5.0
        d = l * (1.5 + 4.0 * f) * (1.2 - vide)         # plus bas : panache qui s'étale
        r = max(2.0, l * (0.45 + 1.2 * f) * z)
        jx = (random.random() - 0.5) * r / z
        x, y = P(jx, yb - d)
        try:
            gfxdraw.filled_circle(surf, int(x), int(y), int(r),
                                  (185, 185, 192, int(75 * (1.0 - f))))
        except (OverflowError, pygame.error):
            pass


def _plasma(surf, sx, sy, ux, uy, taille, chaleur):
    """Traînée de plasma derrière un vaisseau qui rentre dans l'atmosphère.
    (ux, uy) : direction du sillage à l'écran ; chaleur dans (0, 1)."""
    L = taille * (1.2 + 3.0 * chaleur)
    try:                                           # halo incandescent contre la coque
        gfxdraw.filled_circle(surf, int(sx), int(sy), int(max(3, L * 0.18)),
                              (255, 120, 40, int(70 * chaleur)))
    except (OverflowError, pygame.error):
        pass
    for k, (d, ep, coul) in enumerate(((0.55, 0.10, (255, 90, 30)),
                                       (0.85, 0.07, (255, 170, 80)),
                                       (1.0, 0.045, (255, 240, 200)))):
        e = ep * L
        try:
            gfxdraw.filled_polygon(surf, [
                (int(sx - uy * e), int(sy + ux * e)), (int(sx + uy * e), int(sy - ux * e)),
                (int(sx + ux * L * d + uy * e * 2), int(sy + uy * L * d - ux * e * 2)),
                (int(sx + ux * L * d * 1.05), int(sy + uy * L * d * 1.05)),
                (int(sx + ux * L * d - uy * e * 2), int(sy + uy * L * d + ux * e * 2))],
                (coul[0], coul[1], coul[2], int(80 * chaleur * (1.0 - k * 0.2))))
        except (OverflowError, pygame.error):
            pass


def dessiner_pile(surf, v, g, origine, axe, perp, flamme=0.0, vide=1.0, selection=None,
                  jour=1.0):
    """
    Dessine toutes les pièces d'un vaisseau.
    origine : position écran du centre de masse ; axe / perp : vecteurs écran (px par mètre)
    correspondant à « vers le nez » et « latéral ». Sert aussi au hangar.
    jour : éclairage solaire (1 = plein jour, 0.14 = côté nuit).
    """
    ox, oy = origine
    ax, ay = axe
    bx, by = perp
    nuit = 1.0 - jour

    def P(x, y):
        return ox + ax * y + bx * x, oy + ay * y + by * x

    def teinte(couleur):
        return melange(couleur, (22, 28, 46), nuit) if nuit > 0.0 else couleur

    bas_pile = -(g.longueur - g.haut)
    i_moteur = None
    if flamme > 0.0:
        from .vaisseau import indice_moteur
        i_moteur = indice_moteur(v.pieces)
    for i, (p, (yh, yb), l) in enumerate(zip(v.pieces, g.segments, g.largeurs)):
        h = p.m.h
        if p.m.forme == "train":                       # jambes du train d'atterrissage
            efficace = yb - bas_pile < 6.0
            pied = bas_pile - 0.5 if efficace else yb - 1.0
            for s in (-1, 1):
                x0, x1 = s * l / 2, s * (l / 2 + (1.7 if efficace else 0.8))
                pygame.draw.polygon(surf, teinte((120, 124, 136)), [P(x0, yb + h), P(x0, yb), P(x1, pied),
                                                            P(x1 - s * 0.25, pied)])
                pygame.draw.polygon(surf, teinte((70, 72, 80)), [P(x1 - s * 0.6, pied), P(x1 + s * 0.4, pied),
                                                         P(x1 + s * 0.4, pied - 0.15), P(x1 - s * 0.6, pied - 0.15)])
        for couleur, pts in formes_piece(p, l, h):
            if p.retournee:
                poly = [P(x, yh - y) for x, y in pts]
            else:
                poly = [P(x, yb + y) for x, y in pts]
            pygame.draw.polygon(surf, teinte(couleur), poly)
        if selection is p:
            pygame.draw.polygon(surf, CYAN, [P(-l / 2, yb), P(l / 2, yb), P(l / 2, yh), P(-l / 2, yh)], 2)
        if i == i_moteur:                              # flamme du moteur actif
            _flamme(surf, P, l * (0.34 + 0.3 * vide), yb, l, flamme, vide)
            if vide < 0.85:                            # fumée quand l'air est dense
                _fumee(surf, P, yb, l, hypot(ax, ay), vide)
        if p.parachute == "ouvert" and p.ouverture > 0.0:
            _voile(surf, P, p, l, yh)
    _dessiner_boosters(surf, v, g, P, flamme, vide, selection, nuit)


def _dessiner_boosters(surf, v, g, P, flamme, vide, selection, nuit):
    """Piles latérales : les boosters à gauche ET à droite du cœur, une annexe amarrée
    (port latéral) seulement à droite."""
    from .vaisseau import porteurs_actifs, moteur_et_reservoirs, indice_moteur
    actifs = porteurs_actifs(v.pieces) if flamme > 0.0 else []
    for k, pile, ecart, segs, demi, n in getattr(g, "laterales", []):
        i_moteur = None
        if v.pieces[k] in actifs and sum(r.carburant for r in moteur_et_reservoirs(pile)[1]) > 0:
            i_moteur = indice_moteur(pile)
        haut_b, bas_b = segs[0][0], segs[-1][1]
        l_b = max(q.m.l for q in pile)
        for cote in ((-1.0, 1.0) if n == 2 else (1.0,)):
            # deux attaches (le découpleur radial) entre la pile centrale et le booster
            for ya in (haut_b - 0.9, bas_b + 1.2):
                x0, x1 = cote * demi, cote * (ecart - l_b / 2)
                pygame.draw.polygon(surf, melange((60, 62, 70), (22, 28, 46), nuit),
                                    [P(x0, ya), P(x1, ya), P(x1, ya - 0.35), P(x0, ya - 0.35)])
            for j, (q, (yh, yb)) in enumerate(zip(pile, segs)):
                l, h = q.m.l, q.m.h
                xc = cote * ecart
                for couleur, pts in formes_piece(q, l, h):
                    pygame.draw.polygon(surf, melange(couleur, (22, 28, 46), nuit),
                                        [P(xc + x, yb + y) for x, y in pts])
                if selection is q:
                    pygame.draw.polygon(surf, CYAN, [P(xc - l / 2, yb), P(xc + l / 2, yb),
                                                     P(xc + l / 2, yh), P(xc - l / 2, yh)], 2)
                if j == i_moteur:
                    _flamme(surf, P, l * (0.34 + 0.3 * vide), yb, l, flamme, vide)


def _voile(surf, P, p, l, yh):
    """Parachute ouvert au-dessus de la pièce p."""
    o = p.ouverture
    yc, rc = yh + 3 + 8 * o, 0.8 + 4.2 * o
    voile = [P(rc * cos(pi * k / 12), yc + rc * 0.8 * sin(pi * k / 12)) for k in range(13)]
    pygame.draw.line(surf, (220, 220, 220), P(-l * .18, yh), voile[-1])
    pygame.draw.line(surf, (220, 220, 220), P(l * .18, yh), voile[0])
    pygame.draw.polygon(surf, (240, 130, 40), voile)
    pygame.draw.polygon(surf, (250, 240, 230), voile, 1)


def icone_vaisseau(surf, cam, v, sx, sy, couleur):
    t = v.type()
    if t == "debris":
        pygame.draw.line(surf, couleur, (sx - 3, sy - 3), (sx + 3, sy + 3))
        pygame.draw.line(surf, couleur, (sx - 3, sy + 3), (sx + 3, sy - 3))
    elif t == "station":
        pygame.draw.polygon(surf, couleur, [(sx, sy - 6), (sx + 6, sy), (sx, sy + 6), (sx - 6, sy)], 2)
    else:
        dx, dy = cam.direction_ecran(cos(v.angle), sin(v.angle))
        pygame.draw.polygon(surf, couleur, [(sx + dx * 9, sy + dy * 9),
                                            (sx - dx * 5 - dy * 5, sy - dy * 5 + dx * 5),
                                            (sx - dx * 5 + dy * 5, sy - dy * 5 - dx * 5)])


# =============================================================================
# Le monde
# =============================================================================
# Côté nuit des planètes : disque d'ombre précalculé une fois (alpha par pixel,
# dégradé lisse depuis le terminateur), tourné vers l'anti-Soleil à chaque image.
# Les polygones semi-transparents ne conviennent pas : gfxdraw repeint deux fois
# les arêtes partagées et laisse des rayures radiales.
_OMBRE = pygame.Surface((128, 128), pygame.SRCALPHA)
for _j in range(128):
    _yy = (_j + 0.5) / 64.0 - 1.0
    for _i in range(64, 128):                      # moitié droite = côté nuit
        _xx = (_i + 0.5) / 64.0 - 1.0
        if _xx * _xx + _yy * _yy <= 1.0:
            _OMBRE.set_at((_i, _j), (0, 0, 10, int(150 * _xx ** 0.75)))
_OMBRES = {}          # cache des ombres tournées / mises à l'échelle


def _ombre_nuit(surf, sx, sy, rp, a0):
    """Assombrit le côté nuit d'un corps (centre sx,sy, rayon rp, nuit vers a0)."""
    taille = (max(16, min(int(2 * rp), 3 * RAYON_GRAND_CERCLE)) + 31) // 32 * 32  # toujours ≥ 2rp
    cle = (int(a0 * 28.65 / 4), taille)            # angle quantisé par pas de 4°
    ombre = _OMBRES.get(cle)
    if ombre is None:
        ombre = pygame.transform.rotozoom(_OMBRE, -degrees(a0), taille / 128.0)
        _OMBRES[cle] = ombre
        # budget mémoire : les grosses ombres coûtent cher, on jette les plus anciennes
        pixels = sum(o.get_width() * o.get_height() for o in _OMBRES.values())
        while len(_OMBRES) > 1 and pixels > 12_000_000:
            vieille = _OMBRES.pop(next(iter(_OMBRES)))
            pixels -= vieille.get_width() * vieille.get_height()
    surf.blit(ombre, ombre.get_rect(center=(int(sx), int(sy))))


_rng = random.Random(7)
# Étoiles : (rayon normalisé, angle, luminosité, taille, phase, vitesse de
# scintillement, teinte bleutée). Phase et vitesse rendent le ciel vivant.
_ETOILES = [(_rng.random() ** 0.5, _rng.random() * TAU, _rng.choice((90, 120, 150, 200, 255)),
             _rng.choice((1, 1, 1, 2)), _rng.random() * TAU,
             _rng.choice((1.5, 2.5, 4.0, 7.0)), _rng.choice((0, 0, 15, 30)))
            for _ in range(240)]


def _fond(surf, u, cam):
    """Ciel en dégradé (horizon clair, zénith sombre ; noir dans l'espace) puis étoiles."""
    ciel = 0.0
    fond = NOIR
    a = cam.focus if cam.focus is not None else u.actif
    c = None
    if a is not None and not isinstance(a, Corps) and a.corps.atm_h > 0 and cam.zoom * a.corps.R > 900:
        c = a.corps
        e = u.etat(a)
        r = hypot(e[0], e[1])
        ciel = min(1.0, (3.0 * c.densite(r - c.R) / c.rho0) ** 0.5)
        bx, by = u.position_corps(c)
        ds = hypot(bx, by) or 1.0
        jour = max(0.06, min(1.0, 0.5 + 1.2 * (-(e[0] * bx + e[1] * by) / (r * ds))))
        ciel *= jour
    if ciel > 0.02:
        degrade_vertical(surf, melange(NOIR, c.couleur_ciel, ciel * 0.35),
                         melange(NOIR, c.couleur_ciel, min(1.0, ciel * 1.3)))
        fond = melange(NOIR, c.couleur_ciel, ciel)
    else:
        surf.fill(NOIR)
    if ciel < 0.7:
        instant = pygame.time.get_ticks() / 1000.0
        demi = hypot(cam.l, cam.h) / 2
        s = -1.0 if MIROIR_X else 1.0
        noit = 1.0 - ciel / 0.7
        for rr, th, lum0, taille, phase, vit, bleu in _ETOILES:
            lum = int(lum0 * noit * (0.75 + 0.25 * sin(instant * vit + phase)))
            if lum < 10:
                continue
            ang = th + s * cam.angle
            x = int(cam.l / 2 + rr * demi * cos(ang))
            y = int(cam.h / 2 + rr * demi * sin(ang))
            coul = (lum, lum, min(255, lum + 15 + bleu))
            surf.fill(coul, (x, y, taille, taille))
            if lum0 == 255 and lum > 150:              # croix sur les plus brillantes
                pygame.draw.line(surf, coul, (x - 3 * taille, y), (x + 4 * taille, y))
                pygame.draw.line(surf, coul, (x, y - 3 * taille), (x, y + 4 * taille))
        if ciel < 0.15:                                # étoile filante, une toutes les 17 s
            periode = 17.0
            phase = (instant % periode) / periode
            if phase < 0.05:
                f = phase / 0.05
                alea = random.Random(int(instant / periode))
                x0, y0 = alea.random() * cam.l * 0.8, alea.random() * cam.h * 0.4
                vx, vy = 400 + 300 * alea.random(), 150 + 100 * alea.random()
                lum = int(220 * sin(pi * f))           # s'allume puis s'éteint
                if lum > 40:
                    xa, ya = x0 + vx * f, y0 + vy * f
                    xb, yb = x0 + vx * (f - 0.06), y0 + vy * (f - 0.06)
                    pygame.draw.aaline(surf, (lum, lum, min(255, lum + 20)), (xb, yb), (xa, ya))
    return fond


def _dessiner_corps(surf, u, cam, c, fond):
    L, H = surf.get_size()
    bx, by = u.position_corps(c)
    sx, sy = cam.vers_ecran(bx, by)
    rp = c.R * cam.zoom
    # orbite du corps autour de son parent (cachée quand le corps est gros à l'écran)
    if c.parent is not None and rp < 40:
        px, py = cam.vers_ecran(*u.position_corps(c.parent))
        ro = c.a * cam.zoom
        if ro > 12:
            cercle(surf, melange(NOIR, c.couleur, 0.35), px, py, ro)
    r_max = max(rp * (c.anneaux[1] if c.anneaux else 1.0), (c.R + c.atm_h) * cam.zoom, 4)
    if sx + r_max < 0 or sx - r_max > L or sy + r_max < 0 or sy - r_max > H:
        return
    if rp < 2.0:
        pygame.draw.circle(surf, c.couleur, (int(sx), int(sy)), 2 if c.parent and c.parent.parent else 3)
    else:
        soleil_x, soleil_y = cam.direction_ecran(-bx, -by)        # direction du Soleil à l'écran
        if c.etoile:
            for k, f in ((2.2, 0.12), (1.6, 0.25), (1.25, 0.5)):
                disque(surf, melange(fond, c.couleur, f), sx, sy, rp * k)
        if c.anneaux:
            disque(surf, c.anneaux[2], sx, sy, rp * c.anneaux[1])
            disque(surf, melange(c.anneaux[2], NOIR, 0.45), sx, sy, rp * (c.anneaux[0] + c.anneaux[1]) / 2)
            disque(surf, fond, sx, sy, rp * c.anneaux[0])
        if c.atm_h > 0 and hypot(cam.x - bx, cam.y - by) > c.R + c.atm_h:
            # halo atmosphérique, vu de l'espace seulement : de l'intérieur, les
            # disques recouvriraient tout l'écran et écraseraient le dégradé du ciel
            for k, f in enumerate((0.07, 0.15, 0.26, 0.4, 0.58)):
                disque(surf, melange(fond, c.couleur_ciel, f), sx, sy, (c.R + c.atm_h * (1 - k / 5)) * cam.zoom)
        if rp > RAYON_GRAND_CERCLE and not c.etoile:              # vu de près : éclairage local
            ds = hypot(bx, by) or 1.0
            dx, dy = cam.x - bx, cam.y - by
            dd = hypot(dx, dy) or 1.0
            jour = max(0.0, min(1.0, 0.5 + 1.5 * (-(dx * bx + dy * by) / (dd * ds))))
            # en se rapprochant, la couleur « vue de l'espace » devient la couleur du sol
            f = min(1.0, (rp - RAYON_GRAND_CERCLE) / (3.0 * RAYON_GRAND_CERCLE))
            sol = melange(melange(c.couleur_nuit, c.couleur, jour),
                          melange(c.couleur_sol_nuit, c.couleur_sol, jour), f)
            disque(surf, sol, sx, sy, rp)
            _decor_sol(surf, u, cam, c, melange(sol, NOIR, 0.15))
        else:
            disque(surf, c.couleur, sx, sy, rp)
            if rp > 10:
                rot = c.angle_rotation(u.t)
                for ang, dist, taille, coul in c.taches:
                    tx, ty = cam.vers_ecran(bx + c.R * dist * cos(ang + rot), by + c.R * dist * sin(ang + rot))
                    rt = max(1, int(rp * taille))
                    if rt < 3:                     # trop petit pour un bord adouci
                        pygame.draw.circle(surf, coul, (int(tx), int(ty)), rt)
                    else:                          # bord adouci : auréole puis cœur
                        pygame.draw.circle(surf, melange(coul, c.couleur, 0.5), (int(tx), int(ty)), rt)
                        pygame.draw.circle(surf, coul, (int(tx), int(ty)), int(rt * 0.65))
            if not c.etoile and rp > 5 and abs(sx) < 9000 and abs(sy) < 9000:
                a0 = atan2(-soleil_y, -soleil_x)                  # direction de la nuit
                _ombre_nuit(surf, sx, sy, rp, a0)
    # sphère d'influence et nom
    rs = c.soi * cam.zoom if c.soi < INFINI else 0
    if 40 < rs < 30000 and rp < 400:
        cercle(surf, melange(fond, c.couleur, 0.22), sx, sy, rs)
    if rp < 90 and (c.parent is None or c.a * cam.zoom > 45):
        texte(surf, t(c.nom), (sx, sy + max(rp, 3) + 4), 13, melange(GRIS, c.couleur, 0.4), ancre="hc")


def _decor_sol(surf, u, cam, c, couleur):
    """Cailloux réguliers au sol : donnent la sensation de vitesse près de la surface."""
    bx, by = u.position_corps(c)
    if abs(hypot(cam.x - bx, cam.y - by) - c.R) * cam.zoom > hypot(cam.l, cam.h):
        return
    esp = 10.0 ** ceil(log10(90.0 / cam.zoom))
    rot = c.angle_rotation(u.t)
    k0 = int(round((atan2(cam.y - by, cam.x - bx) - rot) * c.R / esp))
    fonce = melange(couleur, NOIR, 0.35)
    for k in range(k0 - 14, k0 + 15):
        ang = k * esp / c.R + rot
        t = 2 + (k * 7919) % 5
        px, py = cam.vers_ecran(bx + (c.R - 0.2 * t / cam.zoom) * cos(ang), by + (c.R - 0.2 * t / cam.zoom) * sin(ang))
        if -10 < px < cam.l + 10 and -10 < py < cam.h + 10:
            pygame.draw.circle(surf, fonce, (int(px), int(py)), t)


def _pas_de_tir(surf, u, cam):
    if cam.zoom < 0.08:
        return
    c = u.terre
    bx, by = u.position_corps(c)
    ang = LONGITUDE_PAS_DE_TIR + c.angle_rotation(u.t)
    ox, oy = cam.vers_ecran(bx + c.R * cos(ang), by + c.R * sin(ang))
    if not (-400 < ox < cam.l + 400 and -400 < oy < cam.h + 400):
        return
    hx, hy = cam.direction_ecran(cos(ang), sin(ang))              # vers le haut
    ex, ey = cam.direction_ecran(-sin(ang), cos(ang))             # vers l'est
    z = cam.zoom

    def P(e, h):
        return ox + (ex * e + hx * h) * z, oy + (ey * e + hy * h) * z

    pygame.draw.polygon(surf, (120, 124, 132), [P(-14, -2.5), P(14, -2.5), P(14, 0), P(-14, 0)])
    pygame.draw.polygon(surf, (90, 94, 102), [P(-14, -0.5), P(14, -0.5), P(14, 0), P(-14, 0)])
    pygame.draw.polygon(surf, (150, 64, 54), [P(-9.5, 0), P(-7.5, 0), P(-7.5, 30), P(-9.5, 30)])
    for h in range(4, 30, 5):
        pygame.draw.line(surf, (200, 110, 95), P(-9.5, h), P(-7.5, h + 3))
    pygame.draw.polygon(surf, (150, 64, 54), [P(-7.5, 19), P(-2.5, 19), P(-2.5, 20), P(-7.5, 20)])
    # balise rouge clignotante au sommet de la tour
    if pygame.time.get_ticks() % 1100 < 450:
        tx, ty = P(-8.5, 30.5)
        pygame.draw.circle(surf, (255, 70, 55), (int(tx), int(ty)), 2)
        pygame.draw.circle(surf, (255, 70, 55), (int(tx), int(ty)), 4, 1)


def _anomalies_troncon(tr, t, n, dense):
    """Anomalies (E ou H) échantillonnées le long d'un tronçon, du présent vers la fin."""
    orb = tr.orbite
    ta = max(t, tr.t0)
    A0 = orb.anomalie(ta)
    ferme = tr.fin in (None, "revoir") and orb.elliptique
    if ferme:
        A1 = A0 + TAU
    elif tr.t1 < INFINI:
        A1 = orb.anomalie(tr.t1)
    else:
        A1 = max(A0 + 0.5, acosh(max(1.0, (60.0 * orb.rp / -orb.a + 1.0) / orb.e)))
    out = []
    for k in range(n + 1):
        f = k / n
        if ferme:
            f = f - sin(TAU * f) / TAU          # points resserrés près du vaisseau
        elif dense:
            f = f ** 1.7
        out.append(A0 + (A1 - A0) * f)
    return out


def point_trajectoire(u, cam, tr, indice, t):
    """Position dans le monde d'un point de trajectoire, à l'instant t."""
    x, y = tr.orbite.position(t)
    corps = tr.corps
    if indice > 0 and tr.entree and cam.focus is not corps:   # survol futur : là où sera le corps
        ox, oy = u.position_corps(corps.parent)
        cx, cy = corps.position_relative(t)
        return ox + cx + x, oy + cy + y
    ox, oy = u.position_corps(corps)
    return ox + x, oy + y


def _dessiner_trajectoire(surf, u, cam, troncons, couleurs, marqueurs=True, echantillons=None):
    t = u.t
    for i, tr in enumerate(troncons):
        if tr.t1 <= t and tr.fin is not None:
            continue
        orb, c = tr.orbite, tr.corps
        couleur = couleurs[i % len(couleurs)]
        dans_parent = i > 0 and tr.entree and cam.focus is not c
        if dans_parent:                        # survol futur : dessiné là où sera le corps
            ox, oy = u.position_corps(c.parent)
        else:
            ox, oy = u.position_corps(c)
        pts = []
        for A in _anomalies_troncon(tr, t, 150 if i == 0 else 90, i == 0):
            x, y = orb.position_depuis_anomalie(A)
            tA = orb.temps_de_anomalie(A) if (dans_parent or echantillons is not None) else 0.0
            if dans_parent:
                cx, cy = c.position_relative(tA)
                x, y = x + cx, y + cy
            p = cam.vers_ecran(ox + x, oy + y)
            pts.append(p)
            if echantillons is not None:
                echantillons.append((p[0], p[1], tA))
        ligne_brisee(surf, couleur, pts)
        if not marqueurs:
            continue

        taille = (orb.ra if orb.elliptique and orb.ra < INFINI else 4.0 * orb.rp) * cam.zoom

        def marque(delai, libelle, coul):
            if taille < 45 or delai is None or (max(t, tr.t0) + delai > tr.t1 and tr.fin not in (None, "revoir")):
                return
            tm = max(t, tr.t0) + delai
            x, y = orb.position(tm)
            if dans_parent:
                cx, cy = c.position_relative(tm)
                x, y = x + cx, y + cy
            px, py = cam.vers_ecran(ox + x, oy + y)
            if -50 < px < cam.l + 50 and -50 < py < cam.h + 50:
                pygame.draw.circle(surf, coul, (int(px), int(py)), 4, 1)
                texte(surf, libelle, (px + 7, py - 8), 12, coul)

        base = max(t, tr.t0)
        nom = (" " + c.nom) if i > 0 else ""
        marque(orb.delai_periapside(base), "Pe%s %s" % (nom, fmt_distance(orb.rp - c.R)), couleur)
        if orb.elliptique and orb.ra < c.soi:
            marque(orb.delai_apoapside(base), "Ap%s %s" % (nom, fmt_distance(orb.ra - c.R)), couleur)
        if tr.fin in ("atmo", "impact", "sortie", "entree") and pts:
            px, py = pts[-1]
            if -50 < px < cam.l + 50 and -50 < py < cam.h + 50:
                if tr.fin in ("atmo", "impact"):
                    pygame.draw.line(surf, ROUGE, (px - 5, py - 5), (px + 5, py + 5), 2)
                    pygame.draw.line(surf, ROUGE, (px - 5, py + 5), (px + 5, py - 5), 2)
                else:
                    pygame.draw.circle(surf, couleur, (int(px), int(py)), 3)
        if dans_parent:                        # fantôme du corps au moment du survol
            d = orb.delai_periapside(tr.t0)
            tm = tr.t0 + (d if d is not None and tr.t0 + d < tr.t1 else 0.0)
            cx, cy = c.position_relative(tm)
            px, py = cam.vers_ecran(ox + cx, oy + cy)
            cercle(surf, melange(NOIR, c.couleur, 0.6), px, py, max(3, c.R * cam.zoom))
            cercle(surf, melange(NOIR, c.couleur, 0.3), px, py, c.soi * cam.zoom)


def _dessiner_vaisseaux(surf, u, cam, temps_reel):
    a = u.actif
    for v in u.vaisseaux:
        if v.detruit:
            continue
        ax, ay = u.position_absolue(v)
        sx, sy = cam.vers_ecran(ax, ay)
        if not (-600 < sx < cam.l + 600 and -600 < sy < cam.h + 600):
            continue
        g = v.geometrie()
        couleur = BLANC if v is a else (MAGENTA if v is u.cible else
                                        (GRIS if v.type() == "debris" else CYAN))
        if g.longueur * cam.zoom > 12:
            dx, dy = cam.direction_ecran(cos(v.angle), sin(v.angle))
            px, py = cam.direction_ecran(-sin(v.angle), cos(v.angle))
            z = cam.zoom
            flamme = 0.0
            rho = v.corps.densite(u.altitude(v))
            if v.mode == "physique" and v.gaz > 0 and (v.carburant_actif()[0] > 0 or
                                                      v.carburant_boosters()[0] > 0):
                flamme = v.gaz
            # éclairage solaire : le vaisseau s'assombrit du côté nuit, comme les planètes
            e = u.etat(v)
            bx, by = u.position_corps(v.corps)
            r = hypot(e[0], e[1]) or 1.0
            ds = hypot(bx, by) or 1.0
            jour = max(0.14, min(1.0, 0.5 + 1.2 * (-(e[0] * bx + e[1] * by) / (r * ds))))
            dessiner_pile(surf, v, g, (sx, sy), (dx * z, dy * z), (px * z, py * z), flamme,
                          1.0 - min(1.0, rho / 1.225), jour=jour)
            # plasma de rentrée : la coque chauffe quand l'air est dense et la vitesse forte
            chaleur = min(1.0, rho * (e[2] * e[2] + e[3] * e[3]) / 2000000.0)
            if chaleur > 0.05:
                cvx, cvy = cam.direction_ecran(e[2], e[3])
                nv = hypot(cvx, cvy) or 1.0
                _plasma(surf, sx, sy, -cvx / nv, -cvy / nv, g.longueur * z, chaleur)
            if v is a and v.rcs and (u.commandes.avant or u.commandes.cote) and v.mono() > 0:
                s = 1.0 if MIROIR_X else -1.0
                fx = -(u.commandes.avant * dx + u.commandes.cote * s * px)
                fy = -(u.commandes.avant * dy + u.commandes.cote * s * py)
                for k in (g.haut * 0.6, -(g.longueur - g.haut) * 0.6):
                    bx, by = sx + dx * k * z, sy + dy * k * z
                    pygame.draw.line(surf, BLANC, (bx, by), (bx + fx * (8 + 1.5 * z), by + fy * (8 + 1.5 * z)), 2)
            # couloirs d'approche des ports libres
            if (v is u.cible or v is a) and u.cible is not None and not isinstance(u.cible, Corps):
                e = u.etat(v)
                for ext in v.ports_libres():
                    qx, qy, qdx, qdy = v.point_port(e, ext)
                    cx, cy = u.position_corps(v.corps)
                    p0 = cam.vers_ecran(cx + qx, cy + qy)
                    p1 = cam.vers_ecran(cx + qx + qdx * (40 if v is u.cible else 12),
                                        cy + qy + qdy * (40 if v is u.cible else 12))
                    pointilles(surf, VERT if v is u.cible else JAUNE, p0, p1)
        else:
            icone_vaisseau(surf, cam, v, sx, sy, couleur)
            if v is a:
                pygame.draw.circle(surf, BLANC, (int(sx), int(sy)), 13, 1)
            if v.type() != "debris":
                texte(surf, v.nom, (sx + 12, sy + 6), 12, couleur)
        if v is u.cible:
            pygame.draw.rect(surf, MAGENTA, (int(sx) - 16, int(sy) - 16, 32, 32), 1)


def dessiner_noeud(surf, u, cam, v):
    """Dessine le nœud de manœuvre et ses poignées. Renvoie [(nom, (x, y), (dx, dy)), ...]."""
    n = v.noeud
    tr = mod_manoeuvre.troncon_a(v, n.t)
    if tr is None or tr not in v.troncons:
        return []
    wx, wy = point_trajectoire(u, cam, tr, v.troncons.index(tr), n.t)
    sx, sy = cam.vers_ecran(wx, wy)
    if not (-100 < sx < cam.l + 100 and -100 < sy < cam.h + 100):
        return []
    (px, py), (rx, ry) = mod_manoeuvre.reperes(tr.orbite, n.t)
    ep, er = cam.direction_ecran(px, py), cam.direction_ecran(rx, ry)
    R = cam.rayon_poignee
    poignees = []
    for nom, (dx, dy), coul, tire in (("pro", ep, VERT, n.pro > 0.0),
                                      ("retro", (-ep[0], -ep[1]), VERT, n.pro < 0.0),
                                      ("rad+", er, CYAN, n.rad > 0.0),
                                      ("rad-", (-er[0], -er[1]), CYAN, n.rad < 0.0)):
        hx, hy = sx + dx * R, sy + dy * R
        pygame.draw.line(surf, melange(NOIR, coul, 0.5), (sx + dx * 11, sy + dy * 11), (hx, hy))
        pointe = [(hx + dx * 8, hy + dy * 8),
                  (hx - dx * 4 - dy * 6, hy - dy * 4 + dx * 6),
                  (hx - dx * 4 + dy * 6, hy - dy * 4 - dx * 6)]
        pygame.draw.polygon(surf, coul, pointe, 0 if tire else 1)
        poignees.append((nom, (hx, hy), (dx, dy)))
    # le nœud lui-même, et la direction dans laquelle il faut pointer le vaisseau
    dv = mod_manoeuvre.impulsion(v, n)
    total = hypot(dv[0], dv[1]) if dv else 0.0
    if total > 1e-6:
        ax, ay = cam.direction_ecran(dv[0] / total, dv[1] / total)
        bout = (sx + ax * (R + 26), sy + ay * (R + 26))
        pygame.draw.line(surf, BLEU_PLAN, (sx + ax * 12, sy + ay * 12), bout, 2)
        pygame.draw.polygon(surf, BLEU_PLAN, [(bout[0] + ax * 9, bout[1] + ay * 9),
                                              (bout[0] - ay * 5, bout[1] + ax * 5),
                                              (bout[0] + ay * 5, bout[1] - ax * 5)])
        texte(surf, fmt_vitesse(total), (bout[0] + ax * 14, bout[1] + ay * 14 - 7), 13, BLEU_PLAN,
              ancre="hc" if abs(ax) < 0.7 else ("hg" if ax > 0 else "hd"))
    pygame.draw.circle(surf, NOIR, (int(sx), int(sy)), 10)
    pygame.draw.circle(surf, BLEU_PLAN, (int(sx), int(sy)), 10, 2)
    pygame.draw.circle(surf, BLEU_PLAN, (int(sx), int(sy)), 3)
    poignees.append(("centre", (sx, sy), (0.0, 0.0)))
    return poignees


def _marqueurs_approche(surf, cam, u, approche, couleur):
    """Petits triangles reliant le vaisseau et la cible au moment de leur approche mini."""
    tm, d, pv, pc, parent = approche
    ox, oy = u.position_corps(parent)
    p0 = cam.vers_ecran(ox + pv[0], oy + pv[1])
    p1 = cam.vers_ecran(ox + pc[0], oy + pc[1])
    if hypot(p0[0] - p1[0], p0[1] - p1[1]) <= 6:
        return
    for p in (p0, p1):
        if -50 < p[0] < cam.l + 50 and -50 < p[1] < cam.h + 50:
            pygame.draw.polygon(surf, couleur, [(p[0], p[1] - 6), (p[0] + 5, p[1] + 4),
                                                (p[0] - 5, p[1] + 4)], 1)
    pointilles(surf, couleur, p0, p1, 6)


def _dessiner_effets(surf, u, cam):
    """Explosions : flash, boule de feu, débris projetés et onde de choc."""
    for e in u.effets:
        c = e["corps"]
        bx, by = u.position_corps(c)
        ang = e["lon"] + c.angle_rotation(u.t)
        sx, sy = cam.vers_ecran(bx + e["r"] * cos(ang), by + e["r"] * sin(ang))
        age = e["age"]
        r = max(5.0, e["taille"] * cam.zoom * (0.4 + 1.8 * age))
        if r > 900 or not (-r < sx < cam.l + r and -r < sy < cam.h + r):
            continue
        f = max(0.0, 1.0 - age / 1.6)
        if f > 0.15:                       # débris : éclats qui s'éloignent en pâlissant
            for k in range(12):
                a = ang + k * TAU / 12 + ((k * 2654435761) % 97) / 97.0
                d = r * (1.3 + 1.5 * ((k * 7919) % 7) / 6.0)
                ff = f * (0.55 + 0.45 * ((k * 31) % 10) / 9.0)
                pygame.draw.circle(surf, (int(255 * ff), int(170 * ff), int(70 * ff)),
                                   (int(sx + d * cos(a)), int(sy + d * sin(a))), 2)
        pygame.draw.circle(surf, (int(255 * f), int(120 * f), int(30 * f)), (int(sx), int(sy)), int(r))
        pygame.draw.circle(surf, (int(255 * f), int(220 * f), int(120 * f)), (int(sx), int(sy)), int(r * 0.6))
        if age < 0.5:
            pygame.draw.circle(surf, (255, 255, 235), (int(sx), int(sy)), int(r * 0.3))
        if age < 0.7:                      # onde de choc : cercle qui grandit et s'estompe
            pygame.draw.circle(surf, melange((255, 210, 140), NOIR, age / 0.7),
                               (int(sx), int(sy)), int(r * 1.45), 2)


_voiles_rentree = {}                       # (l, h) -> surface orange, une par taille d'écran


def _halo_rentree(surf, u):
    """Voile incandescent sur tout l'écran quand la coque du vaisseau actif chauffe."""
    a = u.actif
    if a is None or a.detruit or a.mode != "physique":
        return
    alt = u.altitude(a)
    c = a.corps
    rho = c.densite(alt) if alt < c.atm_h else 0.0
    if rho <= 0.0:
        return
    x, y, vx, vy = u.etat(a)              # vitesse air : on enlève la rotation de la planète
    w = c.vitesse_rotation
    chaleur = min(1.0, rho * ((vx + w * y) ** 2 + (vy - w * x) ** 2) / 2000000.0)
    if chaleur < 0.25:                    # le plasma près de la coque suffit en dessous
        return
    l, h = surf.get_size()
    voile = _voiles_rentree.get((l, h))
    if voile is None:                     # une surface orange réutilisée d'une frame à l'autre
        voile = _voiles_rentree[(l, h)] = pygame.Surface((l, h)).convert()
        voile.fill((255, 84, 20))
    voile.set_alpha(int(120 * (chaleur - 0.25) / 0.75))
    surf.blit(voile, (0, 0))


def dessiner_monde(surf, u, cam, temps_reel=0.0):
    """Dessine toute la scène spatiale."""
    fond = _fond(surf, u, cam)
    for c in u.corps:
        _dessiner_corps(surf, u, cam, c, fond)
    _pas_de_tir(surf, u, cam)
    a = u.actif
    cible = u.cible
    if cible is not None and not isinstance(cible, Corps) and cible.mode == "rails" and cible.troncons:
        _dessiner_trajectoire(surf, u, cam, cible.troncons[:1], [(150, 70, 130)], marqueurs=False)
    cam.echantillons, cam.poignees = [], []
    if a is not None and a.mode != "pose" and a.troncons and a.orbite is not None:
        _dessiner_trajectoire(surf, u, cam, a.troncons, COULEURS_TRAJECTOIRE,
                              echantillons=cam.echantillons)
    if a is not None and a.plan:                     # trajectoire prévue après la manœuvre
        _dessiner_trajectoire(surf, u, cam, a.plan, COULEURS_PLAN)
    if u.approche is not None and a is not None:
        _marqueurs_approche(surf, cam, u, u.approche, MAGENTA)
    if u.approche_plan is not None and a is not None:
        _marqueurs_approche(surf, cam, u, u.approche_plan, BLEU_PLAN)
    if a is not None and a.noeud is not None and a.troncons:
        cam.poignees = dessiner_noeud(surf, u, cam, a)
    _dessiner_vaisseaux(surf, u, cam, temps_reel)
    _dessiner_effets(surf, u, cam)
    _halo_rentree(surf, u)


def objet_sous_souris(u, cam, pos, tolerance=14.0):
    """Vaisseau ou corps sous le pointeur (ou None). Les vrais vaisseaux passent avant les débris.
    `tolerance` (px) : rayon minimal de la zone cliquable (plus grand pour un doigt)."""
    meilleur, dmin = None, 1e18
    for v in u.vaisseaux:
        sx, sy = cam.vers_ecran(*u.position_absolue(v))
        d = hypot(sx - pos[0], sy - pos[1])
        if d < max(tolerance, v.geometrie().longueur * cam.zoom * 0.5):
            d += 1000.0 if v.type() == "debris" else 0.0
            if d < dmin:
                meilleur, dmin = v, d
    if meilleur is not None:
        return meilleur
    for c in u.corps:
        sx, sy = cam.vers_ecran(*u.position_corps(c))
        if hypot(sx - pos[0], sy - pos[1]) < max(tolerance - 2.0, c.R * cam.zoom) and c.R < dmin:
            meilleur, dmin = c, c.R       # à l'intérieur de plusieurs disques : le plus petit corps
    return meilleur
