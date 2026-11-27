# -*- coding: utf-8 -*-
"""
Corps célestes et système solaire.

Échelle : toutes les longueurs (rayons, distances) sont divisées par 100 par
rapport à la réalité, mais la gravité de surface est conservée. Conséquence :
les vitesses sont divisées par 10 (orbite basse terrestre ~ 735 m/s) et les
durées aussi (un tour d'orbite basse ~ 10 minutes). Les atmosphères sont à
l'échelle 1/10 pour rester jouables.

Les corps suivent des orbites circulaires « sur rails » autour de leur parent.
"""
from math import cos, sin, sqrt, pi
from zlib import crc32
from .orbite import TAU, INFINI, angle_pi
from .constantes import LONGITUDE_PAS_DE_TIR


class Corps:
    def __init__(self, nom, rayon, g, parent=None, a=0.0, phase=0.0,
                 couleur=(150, 150, 150), atmosphere=None, rotation=0.0,
                 gazeux=False, etoile=False, taches=(), anneaux=None,
                 couleur_nuit=None, couleur_sol=None, pas_de_tir=False, forage=0.0):
        self.nom = nom
        self.R = float(rayon)                 # rayon (m)
        self.g = g                            # gravité de surface (m/s²)
        self.mu = g * rayon * rayon           # paramètre gravitationnel (m³/s²)
        self.parent = parent
        self.enfants = []
        self.a = float(a)                     # rayon de l'orbite autour du parent (m)
        self.phase = phase                    # angle à t = 0 (rad)
        self.couleur = couleur
        self.couleur_nuit = couleur_nuit or tuple(int(c * 0.35) for c in couleur)
        self.couleur_sol = couleur_sol or couleur          # sol vu de près
        self.couleur_sol_nuit = tuple(int(c * 0.3) for c in self.couleur_sol)
        self.gazeux = gazeux or etoile        # pas de surface : on ne peut pas s'y poser
        self.forage = forage                  # carburant extrait du sol par une foreuse (kg/s)
        self.etoile = etoile
        self.taches = taches                  # décor : (angle, distance, taille, couleur)
        self.anneaux = anneaux                # (rayon int., rayon ext., couleur) en rayons du corps
        # atmosphère : (hauteur, densité au sol, hauteur d'échelle, couleur du ciel)
        if atmosphere:
            self.atm_h, self.rho0, self.H, self.couleur_ciel = atmosphere
        else:
            self.atm_h, self.rho0, self.H, self.couleur_ciel = 0.0, 0.0, 1.0, (0, 0, 0)
        if parent is not None:
            parent.enfants.append(self)
            self.n = sqrt(parent.mu / self.a ** 3)          # vitesse angulaire orbitale
            self.periode = TAU / self.n
            self.soi = self.a * (self.mu / parent.mu) ** 0.4  # sphère d'influence
        else:
            self.n, self.periode, self.soi = 0.0, INFINI, INFINI
        # rotation propre : None = synchrone (toujours la même face vers le parent)
        if rotation is None:
            rotation = self.periode
        self.vitesse_rotation = TAU / rotation if rotation else 0.0   # rad/s
        # relief du terrain : quelques ondulations, déterministes (graine = nom du corps),
        # donc les mêmes collines d'une partie à l'autre et d'un appareil à l'autre
        self.pas_de_tir = pas_de_tir
        if self.gazeux:
            self.relief_max, self._ondes = 0.0, ()    # pas de surface solide
        else:
            graine = crc32(nom.encode("utf-8"))
            self.relief_max = 0.01 * self.R           # plafond de hauteur des collines (m)
            self._ondes = tuple(                      # (pulsation, amplitude, phase)
                (k, a, ((graine >> (8 * i)) & 255) / 255.0 * TAU)
                for i, (k, a) in enumerate(((6.0, 0.40), (19.0, 0.40), (60.0, 0.35))))

    # --- position relative au parent ---------------------------------------
    def position_relative(self, t):
        ang = self.phase + self.n * t
        return self.a * cos(ang), self.a * sin(ang)

    def etat_relatif(self, t):
        """(x, y, vx, vy) par rapport au parent."""
        ang = self.phase + self.n * t
        c, s = cos(ang), sin(ang)
        v = self.a * self.n
        return self.a * c, self.a * s, -v * s, v * c

    def position_absolue(self, t):
        x = y = 0.0
        c = self
        while c.parent is not None:
            px, py = c.position_relative(t)
            x += px
            y += py
            c = c.parent
        return x, y

    def angle_rotation(self, t):
        """Angle de rotation propre (repère tournant lié au sol)."""
        return self.vitesse_rotation * t

    def densite(self, altitude):
        from math import exp
        if altitude >= self.atm_h or self.rho0 <= 0.0:
            return 0.0
        return self.rho0 * exp(-max(0.0, altitude) / self.H)

    def relief(self, longitude):
        """Hauteur du terrain (m) au-dessus du rayon R, à cette longitude (repère lié au sol)."""
        if not self._ondes:
            return 0.0
        s = 0.0
        for k, a, p in self._ondes:
            s += a * sin(k * longitude + p)
        h = self.relief_max * (0.5 + 0.43 * s)      # 0 ≤ h ≤ relief_max (somme des a < 1/0.43)
        if self.pas_de_tir:                         # zone plate autour du pas de tir
            d = abs(angle_pi(longitude - LONGITUDE_PAS_DE_TIR))
            if d < 0.05:
                return h * d / 0.05
        return h

    def ancetres(self):
        c, out = self, []
        while c is not None:
            out.append(c)
            c = c.parent
        return out

    def __repr__(self):
        return "<Corps %s>" % self.nom


def creer_systeme_solaire():
    """Construit le système solaire (échelle 1/100). Renvoie (liste, dictionnaire par nom)."""
    soleil = Corps("Soleil", 6_957_000, 274.0, couleur=(255, 214, 90), etoile=True)

    mercure = Corps("Mercure", 24_397, 3.70, soleil, 5.791e8, 2.1, (150, 140, 130),
                    rotation=506_000, forage=3,
                    taches=[(0.5, 0.4, 0.18, (120, 112, 104)), (2.8, 0.6, 0.22, (128, 120, 112)),
                            (4.4, 0.3, 0.15, (115, 108, 100))])
    venus = Corps("Vénus", 60_518, 8.87, soleil, 1.0821e9, 4.0, (226, 190, 120),
                  atmosphere=(12_000, 65.0, 1_600, (235, 205, 140)), rotation=-2_100_000,
                  taches=[(1.0, 0.45, 0.30, (236, 205, 140)), (3.6, 0.5, 0.35, (214, 176, 108))])
    terre = Corps("Terre", 63_710, 9.81, soleil, 1.496e9, 0.0, (52, 104, 190),
                  atmosphere=(7_000, 1.225, 850, (110, 170, 255)), rotation=8_616.4,
                  couleur_nuit=(14, 28, 60), couleur_sol=(74, 128, 72), pas_de_tir=True,
                  taches=[(0.3, 0.55, 0.30, (74, 150, 84)), (1.5, 0.50, 0.24, (96, 160, 90)),
                          (2.6, 0.62, 0.26, (180, 160, 100)), (3.9, 0.48, 0.33, (70, 140, 80)),
                          (5.2, 0.60, 0.22, (90, 150, 86)), (0.0, 0.0, 0.16, (240, 244, 250))])
    lune = Corps("Lune", 17_374, 1.62, terre, 3.844e6, 1.0, (170, 170, 172), rotation=None,
                 forage=3,
                 taches=[(0.7, 0.4, 0.22, (130, 130, 134)), (2.4, 0.55, 0.18, (138, 138, 142)),
                         (4.1, 0.35, 0.26, (124, 124, 130)), (5.4, 0.6, 0.14, (140, 140, 146))])
    mars = Corps("Mars", 33_895, 3.71, soleil, 2.279e9, 0.9, (196, 100, 62),
                 atmosphere=(5_000, 0.020, 1_100, (226, 160, 120)), rotation=8_864, forage=4,
                 taches=[(0.9, 0.5, 0.28, (160, 78, 48)), (3.0, 0.55, 0.24, (150, 72, 46)),
                         (4.6, 0.4, 0.20, (170, 86, 54)), (0.0, 0.0, 0.13, (240, 236, 232))])
    jupiter = Corps("Jupiter", 699_110, 24.79, soleil, 7.785e9, 3.3, (206, 170, 130),
                    atmosphere=(25_000, 1.6, 2_700, (220, 190, 150)), rotation=3_573, gazeux=True,
                    taches=[(0.0, 0.0, 0.82, (188, 142, 104)), (0.0, 0.0, 0.62, (222, 190, 150)),
                            (0.0, 0.0, 0.40, (180, 130, 96)), (0.0, 0.0, 0.2, (214, 180, 140)),
                            (2.0, 0.70, 0.10, (190, 90, 70))])
    io = Corps("Io", 18_216, 1.796, jupiter, 4.217e6, 0.0, (226, 206, 96), rotation=None,
               forage=2,
               taches=[(1.0, 0.5, 0.2, (200, 150, 60)), (3.5, 0.4, 0.25, (240, 220, 140))])
    europe = Corps("Europe", 15_608, 1.314, jupiter, 6.709e6, 2.0, (200, 190, 170), rotation=None,
                   forage=2,
                   taches=[(2.0, 0.5, 0.25, (170, 150, 130))])
    ganymede = Corps("Ganymède", 26_341, 1.428, jupiter, 1.0704e7, 4.0, (150, 140, 128), rotation=None,
                     forage=2,
                     taches=[(0.6, 0.5, 0.3, (120, 112, 104)), (3.4, 0.45, 0.25, (176, 170, 160))])
    callisto = Corps("Callisto", 24_103, 1.235, jupiter, 1.8827e7, 1.0, (110, 100, 92), rotation=None,
                     forage=2,
                     taches=[(1.2, 0.5, 0.2, (140, 132, 124)), (4.0, 0.5, 0.22, (90, 82, 76))])
    saturne = Corps("Saturne", 582_320, 10.44, soleil, 1.4335e10, 5.2, (220, 196, 140),
                    atmosphere=(25_000, 0.8, 5_900, (226, 206, 160)), rotation=3_836, gazeux=True,
                    anneaux=(1.24, 2.27, (196, 178, 136)),
                    taches=[(0.0, 0.0, 0.8, (206, 180, 124)), (0.0, 0.0, 0.5, (228, 208, 156)),
                            (0.0, 0.0, 0.25, (204, 178, 122))])
    titan = Corps("Titan", 25_747, 1.352, saturne, 1.22187e7, 3.0, (214, 160, 70), rotation=None,
                  forage=6,
                  atmosphere=(10_000, 5.4, 2_000, (226, 170, 80)))
    uranus = Corps("Uranus", 253_620, 8.87, soleil, 2.8725e10, 0.5, (150, 214, 222),
                   atmosphere=(20_000, 0.5, 2_800, (170, 224, 230)), rotation=-6_206, gazeux=True)
    neptune = Corps("Neptune", 246_220, 11.15, soleil, 4.4951e10, 5.9, (70, 110, 220),
                    atmosphere=(20_000, 0.6, 2_000, (100, 140, 235)), rotation=5_800, gazeux=True,
                    taches=[(2.2, 0.55, 0.14, (50, 80, 180))])
    pluton = Corps("Pluton", 11_883, 0.62, soleil, 5.906e10, 4.4, (196, 176, 156), rotation=55_200,
                   forage=2,
                   taches=[(1.0, 0.4, 0.35, (230, 220, 206))])

    liste = [soleil, mercure, venus, terre, lune, mars, jupiter, io, europe, ganymede,
             callisto, saturne, titan, uranus, neptune, pluton]
    return liste, {c.nom: c for c in liste}
