# -*- coding: utf-8 -*-
"""
Mécanique orbitale képlérienne en 2D.

Module autonome (aucune dépendance au reste du jeu) : on lui donne une
position, une vitesse et le paramètre gravitationnel mu = G*M du corps
attiré, il en déduit la conique (ellipse ou hyperbole) et sait ensuite
donner la position exacte à n'importe quel instant, sans intégration
numérique. C'est ce qui permet d'accélérer le temps x1 000 000 sans dérive.

Conventions :
  - le corps attracteur est à l'origine (0, 0) ;
  - nu = anomalie vraie (angle depuis le périapside, dans le sens du mouvement) ;
  - "anomalie" tout court = anomalie excentrique E (ellipse) ou hyperbolique H.
"""
from math import sqrt, sin, cos, atan2, acos, pi, sinh, cosh, asinh, hypot, floor

TAU = 2.0 * pi
INFINI = float("inf")


def angle_pi(a):
    """Ramène un angle dans [-pi, pi[."""
    return (a + pi) % TAU - pi


def resoudre_kepler_ellipse(M, e):
    """Résout E - e*sin(E) = M (M dans [-pi, pi]). Newton encadré par bissection."""
    bas, haut = M - e, M + e
    E = M + e * sin(M)
    for _ in range(40):
        f = E - e * sin(E) - M
        if f > 0.0:
            haut = E
        else:
            bas = E
        nouveau = E - f / (1.0 - e * cos(E))
        if not (bas <= nouveau <= haut):
            nouveau = 0.5 * (bas + haut)
        if abs(nouveau - E) < 1e-13:
            return nouveau
        E = nouveau
    return E


def resoudre_kepler_hyperbole(M, e):
    """Résout e*sinh(H) - H = M. Newton encadré par bissection."""
    if M == 0.0:
        return 0.0
    signe = 1.0 if M > 0.0 else -1.0
    M = abs(M)
    bas = asinh(M / e)
    haut = asinh(M / (e - 1.0)) if e - 1.0 > 1e-12 else bas + 60.0
    H = haut
    for _ in range(60):
        f = e * sinh(H) - H - M
        if f > 0.0:
            haut = H
        else:
            bas = H
        nouveau = H - f / (e * cosh(H) - 1.0)
        if not (bas <= nouveau <= haut):
            nouveau = 0.5 * (bas + haut)
        if abs(nouveau - H) < 1e-13 * max(1.0, H):
            return signe * nouveau
        H = nouveau
    return signe * H


class Orbite:
    """Conique képlérienne définie par un état (x, y, vx, vy) à l'instant t0."""

    def __init__(self, x, y, vx, vy, mu, t0):
        self.mu = mu
        self.t0 = t0
        r = hypot(x, y)
        v2 = vx * vx + vy * vy
        h = x * vy - y * vx                      # moment cinétique (signé)
        self.sens = 1.0 if h >= 0.0 else -1.0    # +1 = anti-horaire, -1 = horaire
        self.h = abs(h)
        rv = x * vx + y * vy
        # vecteur excentricité (pointe vers le périapside)
        ex = ((v2 - mu / r) * x - rv * vx) / mu
        ey = ((v2 - mu / r) * y - rv * vy) / mu
        self.e = e = hypot(ex, ey)
        self.energie = energie = 0.5 * v2 - mu / r
        self.p = h * h / mu                      # paramètre de la conique
        self.elliptique = energie < 0.0
        # Cas dégénérés (chute quasi radiale, quasi parabole) : on ne s'en sert
        # pas pour propager, le jeu reste alors en intégration numérique.
        self.degeneree = (self.p < 1e-7 * r) or abs(e - 1.0) < 1e-7 \
            or abs(energie) < 1e-10 * mu / r
        if self.degeneree:
            e = self.e = (0.5 if self.elliptique else 1.5)
        self.a = a = -mu / (2.0 * energie) if energie != 0.0 else INFINI
        self.w = atan2(ey, ex) if self.e > 1e-10 and not self.degeneree else atan2(y, x)
        self._cw, self._sw = cos(self.w), sin(self.w)
        self.rp = self.p / (1.0 + e)             # rayon au périapside
        if self.elliptique:
            self.ra = self.p / (1.0 - e)         # rayon à l'apoapside
            self.n = sqrt(mu / a ** 3)           # mouvement moyen (rad/s)
            self.periode = TAU / self.n
            self._b = sqrt(max(0.0, 1.0 - e * e))
        else:
            self.ra = INFINI
            self.n = max(1e-30, sqrt(mu / (-a) ** 3)) if a != INFINI else 1e-30
            self.periode = INFINI
            self._b = sqrt(max(0.0, e * e - 1.0))
        nu0 = angle_pi(self.sens * (atan2(y, x) - self.w))
        self.M0 = self.M_depuis_nu(nu0)

    # ------------------------------------------------------------------ temps
    def M(self, t):
        """Anomalie moyenne (non bornée) à l'instant t."""
        return self.M0 + self.n * (t - self.t0)

    def anomalie(self, t):
        """Anomalie excentrique E (déroulée, continue) ou hyperbolique H à l'instant t."""
        M = self.M(t)
        if self.elliptique:
            k = floor((M + pi) / TAU)
            return resoudre_kepler_ellipse(M - TAU * k, self.e) + TAU * k
        return resoudre_kepler_hyperbole(M, self.e)

    def temps_de_anomalie(self, A):
        """Instant correspondant à une anomalie E ou H."""
        if self.elliptique:
            M = A - self.e * sin(A)
        else:
            M = self.e * sinh(A) - A
        return self.t0 + (M - self.M0) / self.n

    # ------------------------------------------------------------------ états
    def etat_depuis_anomalie(self, A):
        """(x, y, vx, vy) pour une anomalie E ou H donnée."""
        e, a, mu, b = self.e, self.a, self.mu, self._b
        if self.elliptique:
            c, s = cos(A), sin(A)
            r = a * (1.0 - e * c)
            xp, yp = a * (c - e), a * b * s
            k = sqrt(mu * a) / r
            vxp, vyp = -k * s, k * b * c
        else:
            c, s = cosh(A), sinh(A)
            r = -a * (e * c - 1.0)
            xp, yp = -a * (e - c), -a * b * s
            k = sqrt(mu * -a) / r
            vxp, vyp = -k * s, k * b * c
        yp *= self.sens
        vyp *= self.sens
        cw, sw = self._cw, self._sw
        return (xp * cw - yp * sw, xp * sw + yp * cw,
                vxp * cw - vyp * sw, vxp * sw + vyp * cw)

    def position_depuis_anomalie(self, A):
        x, y, _, _ = self.etat_depuis_anomalie(A)
        return x, y

    def etat(self, t):
        """(x, y, vx, vy) à l'instant t."""
        return self.etat_depuis_anomalie(self.anomalie(t))

    def position(self, t):
        x, y, _, _ = self.etat_depuis_anomalie(self.anomalie(t))
        return x, y

    # --------------------------------------------------------- anomalie vraie
    def nu_depuis_rayon(self, r):
        """Anomalie vraie (positive) où le rayon vaut r, ou None si jamais atteint."""
        if self.e < 1e-12:
            return None
        c = (self.p / r - 1.0) / self.e
        if c > 1.0 or c < -1.0:
            return None
        return acos(c)

    def M_depuis_nu(self, nu):
        e = self.e
        if self.elliptique:
            E = atan2(self._b * sin(nu), e + cos(nu))
            return E - e * sin(E)
        sh = self._b * sin(nu) / max(1e-12, 1.0 + e * cos(nu))
        return e * sh - asinh(sh)

    def point_depuis_nu(self, nu):
        """Position (x, y) pour une anomalie vraie."""
        r = self.p / (1.0 + self.e * cos(nu))
        th = self.w + self.sens * nu
        return r * cos(th), r * sin(th)

    def delai_jusqua_nu(self, nu, t):
        """Durée (>= 0) avant le prochain passage à l'anomalie vraie nu (None si passé)."""
        dM = self.M_depuis_nu(nu) - self.M(t)
        if self.elliptique:
            return (dM % TAU) / self.n
        return dM / self.n if dM >= 0.0 else None

    def delai_jusquau_rayon(self, r, t, en_descente):
        """Durée avant de franchir le rayon r, en descente (vers le périapside) ou en montée."""
        nu = self.nu_depuis_rayon(r)
        if nu is None:
            return None
        return self.delai_jusqua_nu(-nu if en_descente else nu, t)

    def delai_periapside(self, t):
        return self.delai_jusqua_nu(0.0, t)

    def delai_apoapside(self, t):
        return self.delai_jusqua_nu(pi, t) if self.elliptique else None
