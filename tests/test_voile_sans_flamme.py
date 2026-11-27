# -*- coding: utf-8 -*-
"""Le pilote d'atterrissage n'ouvre jamais le parachute dans la flamme : à
l'ouverture de la voile les gaz sont coupés, et sous voile le moteur ne rallume
que sous 300 m (l'aide de la dernière ligne droite). Le bug : la phase « freinage »
brûlait pendant TOUTE la descente sous voile — parachute déployé dans les flammes.
Même règle en phase « chute » : les branches qui freinent « trop vite pour la
voile » (vitesse > 250) ne doivent pas rallumer sous une voile déjà ouverte — le
gonflage laisse la gravité remonter la vitesse au-dessus de 250 : flammes hautes
au milieu de la descente (v1.9.4).

    python tests/test_voile_sans_flamme.py
"""
import os, sys
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from math import hypot

from jeu.univers import Univers
from jeu.vaisseau import construire
from jeu import pilote


def vaisseau_dans_lair(u, altitude, vitesse, moteur="alize"):
    """Capsule + réservoir + moteur, plongeant à `vitesse` (relative au sol)."""
    v = construire("Essai", ["capsule", "reservoir_m", moteur], u.terre)
    c = u.terre
    v.corps = c
    lon = 0.0
    r = c.R + c.relief(lon) + altitude + v.geometrie().bas
    v.x, v.y = r, 0.0
    w = c.vitesse_rotation
    svx, svy = -vitesse, 0.0            # vitesse voulue : vers le bas local
    v.vx, v.vy = svx, svy + w * r        # (vitesse_surface : vx + w·y, vy − w·x)
    v.angle, v.omega = 1.5 * 3.14159, 0.0
    v.gaz = 1.0                          # le moteur brûle (phase freinage)
    v.mode = "physique"                  # état lu directement (x, y, vx, vy)
    v.troncons = []
    v.cache_etat = (None, None)
    u.vaisseaux.append(v)
    u.actif = v
    return v


def test_voile_sans_flamme():
    u = Univers(bac_a_sable=True)
    v = vaisseau_dans_lair(u, 4000.0, 240.0)     # dans l'air, freinage en cours
    prg = pilote.Atterrissage()
    prg.phase = "freinage"
    prg.piloter(u, v)
    assert v.parachute_ouvert(), "la voile devait s'ouvrir (240 m/s, dans l'air)"
    assert v.gaz == 0.0, "voile ouverte : les gaz doivent être coupés (pas de \
parachute déployé dans la flamme)"


def test_aide_sous_voile_gardee():
    u = Univers(bac_a_sable=True)
    v = vaisseau_dans_lair(u, 12.0, 15.0)        # à hauteur d'arrêt, presque doux
    for p in v.parachutes():
        p.parachute = "ouvert"                   # voile déjà déployée
    prg = pilote.Atterrissage()
    prg.phase = "freinage"
    prg.piloter(u, v)
    assert v.gaz > 0.0, "à hauteur d'arrêt sous voile, l'aide moteur doit rallumer"


def test_voile_descend_seule():
    """Sous voile, dérive tuée et hauteur d'arrêt confortable : le moteur doit
    rester coupé jusqu'au ras du sol. Sinon la formule balistique « plane » à
    ~6 m/s du haut de ses 300 m et brûle tout le carburant en pertes de gravité
    (Pionnier : réservoir vide à 285 m, contact à 8,8 m/s)."""
    u = Univers(bac_a_sable=True)
    v = vaisseau_dans_lair(u, 280.0, 9.0)        # voile ouverte, terminal, haut
    for p in v.parachutes():
        p.parachute = "ouvert"
    prg = pilote.Atterrissage()
    prg.phase = "freinage"
    prg.piloter(u, v)
    assert v.gaz == 0.0, "sous voile, bien au-dessus de la hauteur d'arrêt : couper"


class _Troncon:
    """Faux tronçon de trajectoire : seul l'attribut `fin` est lu par le pilote."""

    def __init__(self, fin):
        self.fin = fin


def test_chute_voile_ouverte_pas_de_flamme():
    """Voile ouverte et vitesse remontée au-dessus de 250 (la gravité gagne
    pendant le gonflage de 3 s) : la branche « trop vite pour la voile » ne doit
    pas rallumer le moteur. Bug v1.9.4 : flammes hautes sous voile, étage encore
    attaché (sans le largage), moteur remis en marche au milieu de la descente."""
    u = Univers(bac_a_sable=True)
    # Mistral : assez fort pour que le seuil « 1,25 × distance d'arrêt » de la
    # branche freinage soit sous 4000 m, et que la branche « trop vite pour la
    # voile » soit la seule à pouvoir allumer.
    v = vaisseau_dans_lair(u, 4000.0, 260.0, moteur="mistral")
    for p in v.parachutes():
        p.parachute = "ouvert"                   # voile déjà déployée
    v.troncons = [_Troncon("impact")]
    prg = pilote.Atterrissage()
    prg.phase = "chute"
    prg.piloter(u, v)
    assert v.gaz == 0.0, "voile ouverte : aucun moteur en phase chute"


def test_chute_brute_voile_pas_de_flamme():
    """Idem pour la branche « brute » (freinage jusqu'à la voile) : le test
    isole la garde, sans tronçon la branche else ne peut pas tirer."""
    u = Univers(bac_a_sable=True)
    v = vaisseau_dans_lair(u, 4000.0, 260.0, moteur="mistral")
    for p in v.parachutes():
        p.parachute = "ouvert"
    prg = pilote.Atterrissage()
    prg.phase = "chute"
    prg.brute_voile = True
    prg.piloter(u, v)
    assert v.gaz == 0.0, "brute ou pas : jamais de moteur sous voile ouverte"


if __name__ == "__main__":
    test_voile_sans_flamme()
    test_aide_sous_voile_gardee()
    test_voile_descend_seule()
    test_chute_voile_ouverte_pas_de_flamme()
    test_chute_brute_voile_pas_de_flamme()
    print("--- voile sans flamme : OK")
