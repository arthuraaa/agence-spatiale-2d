# -*- coding: utf-8 -*-
"""Boosters latéraux : étages en parallèle, largage, sauvegarde, construction dans le hangar."""
import os, sys, tempfile
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
from math import hypot, log, sin, cos
from jeu.univers import Univers
from jeu.vaisseau import statistiques_etages, pieces_depuis_plan, prix_plan, toutes_les_cles
from jeu.pieces import CATALOGUE
from jeu.constantes import G0
from jeu import sauvegarde
from test_vol import modele, mise_en_orbite, DT


def test_statistiques():
    """La phase « boosters + moteur central » suit la formule des moteurs en parallèle."""
    plan = modele("Hercule")
    et = statistiques_etages(pieces_depuis_plan(plan))
    assert et[0]["boosters"] and not et[1]["boosters"], et
    mistral = CATALOGUE["mistral"]
    q1 = mistral.poussee / (mistral.isp_vide * G0)            # débit d'un Mistral
    m0 = sum(CATALOGUE[c].masse + CATALOGUE[c].carburant + CATALOGUE[c].mono for c in toutes_les_cles(plan))
    duree = 4000.0 / q1                                       # un réservoir L par booster
    brule = 3 * q1 * duree                                    # 3 moteurs identiques
    dv_attendu = mistral.isp_vide * G0 * log(m0 / (m0 - brule))
    print("   phase boosters : Δv %.1f m/s (attendu %.1f), durée %.1f s" % (et[0]["dv"], dv_attendu, et[0]["duree"]))
    assert abs(et[0]["dv"] - dv_attendu) < 0.5 and abs(et[0]["duree"] - duree) < 0.01
    sans = [e if isinstance(e, str) else e[0] for e in plan]
    total_avec = sum(e["dv"] for e in et)
    total_sans = sum(e["dv"] for e in statistiques_etages(pieces_depuis_plan(sans)))
    print("   Δv total : %.0f m/s avec boosters, %.0f sans" % (total_avec, total_sans))
    assert total_avec > total_sans + 300


def test_largage():
    """ÉTAGE largue d'abord les deux boosters, qui deviennent deux débris symétriques."""
    u = Univers(bac_a_sable=True)
    v = u.lancer("Hercule", modele("Hercule"))
    m0 = v.masse()
    v.gaz, v.sas = 1.0, "stab"
    for _ in range(60 * 30):
        u.avancer(DT)
        if v.etage_epuise():
            break
    assert v.etage_epuise() and v.carburant_boosters()[0] <= 0.0
    assert v.carburant_actif()[0] > 0.0, "le cœur doit encore avoir du carburant"
    x, y, vx, vy = u.etat(v)
    alt, n0 = hypot(x, y) - v.corps.R, len(u.vaisseaux)
    m_avant = v.masse()
    u.separer_etage()
    debris = u.vaisseaux[n0:]
    assert len(debris) == 2 and all(d.nom.startswith("Booster") for d in debris), [d.nom for d in debris]
    assert all(not p.laterales for p in v.pieces), "les boosters doivent avoir quitté le cœur"
    m_b = sum(d.masse() for d in debris)
    print("   largage à %.0f m : 2 débris de %.0f kg chacun, cœur %.0f -> %.0f kg" % (
        alt, m_b / 2, m_avant, v.masse()))
    assert abs(m_avant - v.masse() - m_b) < 1.0
    e1, e2 = u.etat(debris[0]), u.etat(debris[1])
    xc, yc, _, _ = u.etat(v)
    d1 = hypot(e1[0] - xc, e1[1] - yc)
    lx, ly = -sin(v.angle), cos(v.angle)                      # axe latéral du vaisseau
    lat1 = (e1[0] - xc) * lx + (e1[1] - yc) * ly
    lat2 = (e2[0] - xc) * lx + (e2[1] - yc) * ly
    print("   position des débris : %.2f m et %.2f m sur les côtés (symétriques)" % (lat1, lat2))
    assert abs(lat1 + lat2) < 0.05 and 1.0 < abs(lat1) < 3.0
    for _ in range(60 * 5):                                   # ils s'écartent du cœur
        u.avancer(DT)
    e1, e2 = u.etat(debris[0]), u.etat(debris[1])
    assert hypot(e1[0] - e2[0], e1[1] - e2[1]) > 2 * d1
    # deuxième appui : cette fois c'est le découpleur du cœur
    n1 = len(u.vaisseaux)
    u.separer_etage()
    assert len(u.vaisseaux) == n1 + 1 and not u.vaisseaux[-1].nom.startswith("Booster")


def test_orbite_et_sauvegarde():
    """Mise en orbite d'Hercule, et sauvegarde avec des boosters encore accrochés."""
    u = Univers(bac_a_sable=True)
    v = u.lancer("Hercule", modele("Hercule"))
    v.gaz = 1.0
    for _ in range(60 * 8):
        u.avancer(DT)
    chemin = os.path.join(tempfile.gettempdir(), "test_boosters_as2d.json")
    sauvegarde.sauvegarder(u, chemin)
    u2 = sauvegarde.charger(chemin)
    os.remove(chemin)
    a, b = u.actif, u2.actif
    assert [len(p.laterales) for p in a.pieces] == [len(p.laterales) for p in b.pieces]
    assert abs(a.carburant_boosters()[0] - b.carburant_boosters()[0]) < 1e-6
    assert abs(a.masse() - b.masse()) < 1e-6
    print("   sauvegarde en vol : boosters et carburant restitués (%.0f kg)" % b.carburant_boosters()[0])
    u = Univers(bac_a_sable=True)
    v = u.lancer("Hercule", modele("Hercule"))
    assert mise_en_orbite(u, v, verbose=True)


def test_hangar():
    """Construire des boosters à la main dans le hangar, puis lancer."""
    import pygame
    import main as jeu_main
    app = jeu_main.Application(tactile=False)
    app.nouvelle_partie(True)
    sc = app.scene
    sc._vider()
    for cle in ("capsule", "decoupleur", "reservoir_l", "mistral"):
        sc.ajouter(cle)
    sc.selection = 2                                          # le réservoir L
    sc.ajouter("decoupleur_radial")
    assert sc.selection == (2, 0) and sc.cles[2] == ["reservoir_l", ["decoupleur_radial"]]
    sc.ajouter("capsule")                                     # refusé dans un booster
    assert "ne prend que" in sc.message
    for cle in ("coiffe", "reservoir_m", "mistral"):
        sc.ajouter(cle)
    assert sc.cles[2][1] == ["decoupleur_radial", "coiffe", "reservoir_m", "mistral"]
    sc.selection = (2, 2)                                     # réservoir M : on le descend puis le remonte
    sc.deplacer(+1)
    assert sc.cles[2][1][2:] == ["mistral", "reservoir_m"] and sc.selection == (2, 3)
    sc.deplacer(-1)
    assert not sc.peut_deplacer(-1) or sc.selection != (2, 1)
    sc.selection = (2, 1)
    assert not sc.peut_deplacer(-1), "le découpleur radial reste en tête"
    for _ in range(3):
        sc.maj(1 / 60)
        sc.dessiner(app.ecran)
    zones = [z for r, z in sc.zones_pile if isinstance(z, tuple)]
    assert len(zones) == 2 * 4, zones                          # 4 pièces, deux côtés
    rect = next(r for r, z in sc.zones_pile if z == (2, 2))
    sc.evenement(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=rect.center, button=1))
    assert sc.selection == (2, 2), sc.selection
    pygame.image.save(app.ecran, os.path.join(tempfile.gettempdir(), "hangar_boosters.png"))
    # le modèle d'origine n'a pas été modifié en éditant
    sc.charger_modele(next(k for k, m in enumerate(__import__("jeu.pieces", fromlist=["x"]).MODELES)
                           if m[0] == "Hercule"))
    sc.selection = (6, 3)
    sc.supprimer()
    assert modele("Hercule")[6][1] == ["decoupleur_radial", "coiffe", "reservoir_l", "mistral"]
    sc.selection = (6, 0)
    sc.supprimer()                                            # le découpleur radial emporte la paire
    assert sc.cles[6] == "reservoir_l" and sc.selection == 6
    sc.charger_modele(4)
    prix = prix_plan(sc.cles)
    sc.lancer()
    v = app.univers.actif
    assert v is not None and any(p.laterales for p in v.pieces)
    assert abs(v.prix() - prix) < 1e-6
    for _ in range(3):
        app.scene.maj(1 / 60)
        app.scene.dessiner(app.ecran)
    print("   hangar : paire de boosters construite, réordonnée, sélectionnée à la souris, lancée")


if __name__ == "__main__":
    test_statistiques()
    test_largage()
    test_orbite_et_sauvegarde()
    test_hangar()
    print("--- boosters : OK")
