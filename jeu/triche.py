# -*- coding: utf-8 -*-
"""
Menu de triche (secret) : appui long sur l'horloge, en vol (touche F12 sur PC).

    - revenir 30 s en arrière : le jeu prend une « photo » de la partie toutes les 5 s de jeu ;
    - faire le plein (carburant et monergol) ;
    - carburant infini, vaisseau indestructible ;
    - mettre le vaisseau en orbite ;
    - en carrière : +50 000 de fonds, débloquer toutes les pièces.

Les options (carburant infini, indestructible, pièces) sont gardées dans la partie : u.triche.
"""
import json
import zlib
from math import atan2, cos, sin, sqrt

from .orbite import Orbite

APPUI_LONG = 1.2          # s d'appui sur l'horloge pour ouvrir le menu
PAS_PHOTO = 5.0           # s de jeu entre deux photos de la partie...
PAS_PHOTO_REEL = 1.0      # ... et au moins 1 s réelle entre deux (en temps accéléré)
NB_PHOTOS = 40            # photos gardées (plus de 3 minutes à vitesse normale)
RECUL = 30.0              # « revenir 30 s en arrière »
FONDS = 50_000


class Historique:
    """Photos régulières de la partie en vol, pour revenir en arrière."""

    def __init__(self):
        self.univers = None
        self.photos = []                    # (temps de jeu, partie compressée)
        self.dernier_reel = -1e9

    def suivre(self, u):
        """Une autre partie (nouvelle carrière, tuto...) repart sans photos."""
        if u is not self.univers:
            self.univers, self.photos, self.dernier_reel = u, [], -1e9

    def enregistrer(self, u, maintenant):
        self.suivre(u)
        if u.actif is None or u.perdu:
            return                          # on ne photographie pas une épave
        if self.photos and (u.t - self.photos[-1][0] < PAS_PHOTO or
                            maintenant - self.dernier_reel < PAS_PHOTO_REEL):
            return
        from . import sauvegarde
        donnees = zlib.compress(json.dumps(sauvegarde.univers_vers_dict(u)).encode("utf-8"), 1)
        self.photos.append((u.t, donnees))
        self.dernier_reel = maintenant
        del self.photos[:-NB_PHOTOS]

    def photo_avant(self, t):
        """La photo la plus récente prise au plus tard à t (à défaut, la plus ancienne)."""
        avant = [p for p in self.photos if p[0] <= t]
        return avant[-1] if avant else (self.photos[0] if self.photos else None)

    def revenir(self, u, secondes=RECUL):
        """Un univers neuf, tel qu'il était `secondes` plus tôt (None si aucune photo)."""
        photo = self.photo_avant(u.t - secondes)
        if photo is None:
            return None
        from . import sauvegarde
        nouveau = sauvegarde.dict_vers_univers(json.loads(zlib.decompress(photo[1]).decode("utf-8")))
        # le rembobinage défait le vol, pas la carrière : ni missions refaites ni primes en double
        nouveau.missions_faites |= u.missions_faites
        nouveau.fonds = max(nouveau.fonds, u.fonds)
        self.photos = [p for p in self.photos if p[0] <= photo[0]]
        self.univers = nouveau
        return nouveau


def faire_le_plein(v):
    """Tous les réservoirs du vaisseau (boosters compris) pleins de carburant et de monergol."""
    for p in v.pieces:
        for q in [p] + list(p.laterales):
            q.carburant, q.mono = q.m.carburant, q.m.mono


def mettre_en_orbite(u, v):
    """Le vaisseau passe sur une orbite ronde au-dessus de l'atmosphère du corps où il se trouve."""
    c = v.corps
    altitude = max(c.atm_h + 5000.0, 0.12 * c.R)
    x, y, _, _ = u.etat(v)
    angle = atan2(y, x)
    r = c.R + altitude
    vit = sqrt(c.mu / r)
    v.x, v.y = r * cos(angle), r * sin(angle)
    v.vx, v.vy = -vit * sin(angle), vit * cos(angle)
    v.angle, v.omega, v.gaz = atan2(v.vy, v.vx), 0.0, 0.0
    v.mode = "rails"
    v.orbite = Orbite(v.x, v.y, v.vx, v.vy, c.mu, u.t)
    u._predire(v)                                     # trajectoire prête (sinon : plus d'événements SOI/impact)
    v.cache_etat = (None, None)
    u.accel = 0
