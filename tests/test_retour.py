# -*- coding: utf-8 -*-
"""Rentrée atmosphérique + parachute + récupération, crash, carrière, haute accélération du temps."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
from math import atan2, hypot
from jeu.univers import Univers
from jeu import missions, sauvegarde
from test_vol import mise_en_orbite, modele, DT


def test_retour_parachute():
    u = Univers(bac_a_sable=False)
    fonds0 = u.fonds
    v = u.lancer("Pionnier", modele("Pionnier"))
    assert u.fonds < fonds0, "le lancement doit coûter"
    assert mise_en_orbite(u, v)
    u._maj_drapeaux()
    missions.verifier(u)
    assert {"decollage", "espace", "orbite"} <= u.missions_faites, u.missions_faites
    # freinage rétrograde jusqu'à Pe = 1 km
    u.accel = 0
    for _ in range(20_000):
        if v.orbite is not None and v.orbite.rp < v.corps.R + 1_000:
            break
        x, y, vx, vy = u.etat(v)
        v.angle, v.omega, v.gaz = atan2(-vy, -vx), 0.0, 1.0
        u.avancer(DT)
    v.gaz = 0.0
    u.avancer(DT)
    assert v.mode == "rails" and v.troncons[0].fin == "atmo", (v.mode, v.troncons[0].fin)
    # on largue tout sauf la capsule
    from jeu.vaisseau import indice_decoupleur_bas
    while indice_decoupleur_bas(v.pieces):
        u.separer_etage()
    assert [p.m.cle for p in v.pieces] == ["capsule"]
    # accélération forte : le limiteur doit nous ramener à x1 avant l'atmosphère
    u.accel = 7
    vmax_decel = 0.0
    ouvert = False
    for k in range(400_000):
        u.avancer(DT)
        if v.detruit or v.mode == "pose":
            break
        if v.mode == "rails":
            u.accel = max(u.accel, 4)
        else:
            u.accel = 3
            x, y, vx, vy = u.etat(v)
            if not ouvert and u.altitude(v) < 2500 and hypot(*u.vitesse_reference(v)[:2]) < 240:
                u.ouvrir_parachute()
                ouvert = v.parachute_ouvert()
    print("   retour : mode=%s detruit=%s pieces=%s, t=%.0f s, messages=%s" % (
        v.mode, v.detruit, [p.m.cle for p in v.pieces], u.t, [m[0] for m in u.messages][-3:]))
    assert v.mode == "pose" and not v.detruit
    missions.verifier(u)
    assert "retour" in u.missions_faites
    assert u.peut_recuperer(v)
    f = u.fonds
    assert u.recuperer(v) and u.fonds > f and v not in u.vaisseaux
    print("   fonds : départ %d -> %d après missions et récupération" % (fonds0, u.fonds))


def test_crash_et_retour_lancement():
    u = Univers(bac_a_sable=True)
    v = u.lancer("Pionnier", modele("Pionnier"))
    assert u.instantane is not None
    v.gaz = 1.0
    for _ in range(60 * 6):
        u.avancer(DT)
    v.gaz = 0.0
    v.sas = "off"
    for _ in range(60 * 60):
        u.avancer(DT)
        if v.detruit:
            break
    assert v.detruit and u.actif is None and u.perdu, (v.detruit, u.actif, u.perdu)
    u2 = sauvegarde.dict_vers_univers(u.instantane)
    assert u2.actif is None or u2.actif.nom != "Pionnier"
    assert all(x.nom != "Pionnier" for x in u2.vaisseaux)
    print("   crash OK, effets=%d, messages=%s" % (len(u.effets), [m[0] for m in u.messages][-2:]))


def test_grande_acceleration():
    """Évasion de la Terre puis 3 ans à x1 000 000 : pas d'exception, énergie solaire conservée."""
    u = Univers(bac_a_sable=True)
    v = u.lancer("Arès", modele("Arès"))
    assert mise_en_orbite(u, v)
    u.accel = 0
    for _ in range(60_000):
        x, y, vx, vy = u.etat(v)
        v.angle, v.omega, v.gaz = atan2(vy, vx), 0.0, 1.0
        if v.moteur_actif() is not None and v.carburant_actif()[0] <= 0:
            u.separer_etage()
        u.avancer(DT)
        if v.orbite is not None and not v.orbite.elliptique and v.orbite.energie > 0.5 * 120.0 ** 2:
            break
    v.gaz = 0.0
    u.avancer(DT)
    print("   évasion : tronçons =", [(t.corps.nom, t.fin) for t in v.troncons])
    assert v.troncons[0].fin == "sortie"
    u.accel = 10
    for _ in range(60 * 30):
        u.avancer(DT)
        if v.detruit:
            break
        if u.accel < 10:
            u.accel += 1
    o = v.orbite
    print("   après %.0f jours : corps=%s, a=%.3g m, e=%.3f, mode=%s, accel=%d, détruit=%s" % (
        u.t / 86400, v.corps.nom, o.a, o.e, v.mode, u.accel, v.detruit))
    assert v.corps.nom == "Soleil" and v.mode == "rails"
    # la station est toujours sur son orbite
    st = u.vaisseaux[0]
    assert st.nom == "Station Alpha" and abs(st.orbite.rp - (u.terre.R + 15_000)) < 50


if __name__ == "__main__":
    test_retour_parachute()
    test_crash_et_retour_lancement()
    test_grande_acceleration()
    print("--- retour / crash / accélération : OK")
