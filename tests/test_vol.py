# -*- coding: utf-8 -*-
"""Tests de la simulation sans affichage : mise en orbite automatique, Lune, amarrage, sauvegarde."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from math import atan2, hypot, pi, cos, sin, sqrt
from jeu.univers import Univers
from jeu.pieces import MODELES
from jeu.vaisseau import construire
from jeu import sauvegarde

DT = 1 / 60.0


def modele(nom):
    return next(c for n, d, c in MODELES if n == nom)


def mise_en_orbite(u, v, ap_vise=13_000.0, verbose=False):
    """Pilote automatique très simple : virage gravitationnel puis circularisation à l'apoapside."""
    u.accel = 3
    v.sas = "off"
    phase = "montee"
    for k in range(200_000):
        if u.actif is not v or v.detruit:
            return False
        x, y, vx, vy = u.etat(v)
        alt = hypot(x, y) - v.corps.R
        haut = atan2(y, x)
        if v.etage_epuise() and v.gaz > 0:          # boosters vides ou étage à sec : ÉTAGE
            u.separer_etage()
        if phase == "montee":
            v.gaz = 1.0
            inclinaison = min(pi / 2, (pi / 2) * max(0.0, (alt - 150.0) / 5500.0) ** 0.55)
            v.angle, v.omega = haut + inclinaison, 0.0
            if v.orbite is not None and v.orbite.elliptique and v.orbite.ra - v.corps.R > ap_vise:
                v.gaz = 0.0
                phase = "croisiere"
        elif phase == "croisiere":
            v.angle, v.omega = atan2(vy, vx), 0.0
            if v.mode == "rails":
                d = v.orbite.delai_apoapside(u.t)
                u.accel = 4 if d > 40 else 0
                if d < 12.0 or d > v.orbite.periode - 2:
                    phase = "circularisation"
                    u.accel = 3
            elif alt < 3000 and vx * x + vy * y < 0:
                return False
        else:
            v.angle, v.omega = atan2(vy, vx), 0.0
            v.gaz = 1.0
            o = v.orbite
            if o is not None and o.elliptique and o.rp - v.corps.R > 9_000:
                v.gaz = 0.0
                u.avancer(DT)
                break
            if v.delta_v() < 1:
                return False
        u.avancer(DT)
    o = v.orbite
    if verbose:
        print("   t=%.0f s  Pe=%.1f km  Ap=%.1f km  dv restant=%.0f m/s  mode=%s" % (
            u.t, (o.rp - v.corps.R) / 1e3, (o.ra - v.corps.R) / 1e3, v.delta_v(), v.mode))
    return v.mode == "rails" and o.rp - v.corps.R > 7_000


def test_orbite_modeles():
    for nom in ("Pionnier", "Hermès", "Cargo", "Hercule", "Sélène", "Spoutnik", "Arès"):
        u = Univers(bac_a_sable=True)
        v = u.lancer(nom, modele(nom))
        print(nom)
        assert mise_en_orbite(u, v, verbose=True), nom
        u._maj_drapeaux()
        assert "orbite:Terre" in v.drapeaux


def test_lune():
    """Depuis l'orbite basse : on cherche un instant de départ qui donne une rencontre avec la Lune."""
    u = Univers(bac_a_sable=True)
    v = u.lancer("Sélène", modele("Sélène"))
    assert mise_en_orbite(u, v)
    from jeu.orbite import Orbite
    from jeu.trajectoire import predire
    lune = u.par_nom["Lune"]
    trouve = None
    for k in range(0, 120):
        t = u.t + k * v.orbite.periode / 40
        x, y, vx, vy = v.orbite.etat(t)
        sp = hypot(vx, vy)
        dv = 306.0
        o = Orbite(x, y, vx * (1 + dv / sp), vy * (1 + dv / sp), v.corps.mu, t)
        trs = predire(o, v.corps, t, 0.0, 4)
        if len(trs) > 1 and trs[0].fin == "entree" and trs[1].orbite.rp > lune.R + 5_000:
            trouve = (t, dv, trs)
            break
    assert trouve, "aucune rencontre lunaire trouvée"
    t, dv, trs = trouve
    print("Lune : départ dans %.0f s, dv=%.0f, entrée SOI à t+%.0f s, Pe lunaire %.1f km, %d tronçons (%s)" % (
        t - u.t, dv, trs[0].t1 - t, (trs[1].orbite.rp - lune.R) / 1e3, len(trs), [x.fin for x in trs]))
    # on exécute : attente sur rails, poussée réelle prograde, puis croisière accélérée
    u.accel = 6
    while u.t < t - 8:
        if t - u.t < 600: u.accel = 4
        if t - u.t < 60: u.accel = 0
        u.avancer(DT)
    u.accel = 0
    for _ in range(40_000):
        x, y, vx, vy = u.etat(v)
        v.angle, v.omega, v.gaz = atan2(vy, vx), 0.0, 1.0
        if v.moteur_actif() is not None and v.carburant_actif()[0] <= 0:
            u.separer_etage()
        u.avancer(DT)
        if v.orbite is not None and v.orbite.elliptique and v.orbite.ra > lune.a - 0.3 * lune.soi:
            break
        if v.orbite is not None and not v.orbite.elliptique:
            break
    v.gaz = 0.0
    u.avancer(DT)
    print("   après la poussée : Ap=%.0f km, tronçons=%s" % ((v.orbite.ra - v.corps.R) / 1e3, [x.fin for x in v.troncons]))
    # croisière à forte accélération : le limiteur doit ralentir avant l'entrée dans la SOI
    u.accel = 8
    for _ in range(200_000):
        u.avancer(DT)
        if v.corps is lune:
            break
        if u.accel < 8 and (not v.troncons or v.troncons[0].fin != "entree"):
            u.accel = 8
        elif u.accel < 2:
            u.accel = min(8, u.accel + 1) if v.troncons[0].t1 - u.t > 60 else u.accel
    print("   SOI lunaire atteinte : corps=%s, altitude=%.0f km, Pe=%.1f km, t=%.0f s" % (
        v.corps.nom, u.altitude(v) / 1e3, (v.orbite.rp - lune.R) / 1e3, u.t))
    assert v.corps is lune and "soi:Lune" in v.drapeaux
    # freinage au périapside pour se mettre en orbite lunaire
    while v.orbite.delai_periapside(u.t) > 30:
        u.accel = 6 if v.orbite.delai_periapside(u.t) > 2000 else 3
        u.avancer(DT)
    u.accel = 0
    for _ in range(40_000):
        if v.orbite.elliptique and v.orbite.ra < 0.9 * lune.soi:
            break
        x, y, vx, vy = u.etat(v)
        v.angle, v.omega, v.gaz = atan2(-vy, -vx), 0.0, 1.0
        if v.moteur_actif() is not None and v.carburant_actif()[0] <= 0:
            u.separer_etage()
        u.avancer(DT)
    v.gaz = 0.0
    u.avancer(DT); u._maj_drapeaux()
    print("   orbite lunaire : Pe=%.1f km Ap=%.1f km, dv restant %.0f m/s, drapeaux=%s" % (
        (v.orbite.rp - lune.R) / 1e3, (v.orbite.ra - lune.R) / 1e3, v.delta_v(), sorted(v.drapeaux)))
    assert "orbite:Lune" in v.drapeaux
    return u, v


def test_alunissage(u, v):
    """Descente automatique : on annule la vitesse horizontale puis descente freinée."""
    lune = v.corps
    # désorbitation au-dessus du point courant : rétrograde jusqu'à Pe < -5 km
    u.accel = 0
    for _ in range(40_000):
        if v.orbite.rp < lune.R - 8_000:
            break
        x, y, vx, vy = u.etat(v)
        v.angle, v.omega, v.gaz = atan2(-vy, -vx), 0.0, 1.0
        u.avancer(DT)
    v.gaz = 0.0
    u.accel = 3
    for _ in range(400_000):
        if v.mode == "pose" or v.detruit:
            break
        x, y, vx, vy = u.etat(v)
        r = hypot(x, y)
        alt = u.altitude(v) - v.geometrie().bas      # jusqu'au terrain (il y a du relief)
        w = lune.vitesse_rotation
        rvx, rvy = vx + w * y, vy - w * x
        sp = hypot(rvx, rvy)
        vr = (rvx * x + rvy * y) / r
        m = v.masse()
        a_max = 18_000 / m - lune.g
        # vitesse autorisée en fonction de l'altitude (profil de freinage avec marge)
        v_ok = sqrt(max(0.0, 2 * 0.7 * a_max * max(alt - 3.0, 0.0))) + 1.5
        ux, uy = x / r, y / r
        vh = -rvx * uy + rvy * ux
        if v.moteur_actif() is not None and v.carburant_actif()[0] <= 0:
            u.separer_etage()
        if alt < 600 and abs(vh) < 1.5:
            # phase finale : vaisseau vertical, on règle la vitesse de descente
            v.angle, v.omega = atan2(y, x), 0.0
            v.gaz = 1.0 if vr < -(1.5 + 0.06 * alt) else 0.0
        else:
            v.angle, v.omega = atan2(-rvy, -rvx), 0.0
            v.gaz = 1.0 if sp > v_ok else 0.0
        if alt < 2500: u.accel = 0 if alt < 300 else 1
        if v.mode == "rails" and alt > 6000: u.accel = 4
        u.avancer(DT)
    print("   alunissage : mode=%s detruit=%s dv restant=%.0f, messages=%s" % (v.mode, v.detruit, v.delta_v(), [m[0] for m in u.messages][-2:]))
    assert v.mode == "pose" and "pose:Lune" in v.drapeaux


def test_amarrage_et_sauvegarde():
    u = Univers(bac_a_sable=True)
    station = u.vaisseaux[0]
    es = u.etat(station)
    # un vaisseau avec un port en haut, placé 30 m devant le port "haut" de la station, face à lui
    v = construire("Navette", ["port", "capsule", "reservoir_s", "moustique"], u.terre)
    px, py, dx, dy = station.point_port(es, "haut")
    g = v.geometrie()
    v.angle = atan2(-dy, -dx)
    dist = 6.0 + g.haut
    v.x, v.y = px + dx * dist, py + dy * dist
    v.vx, v.vy = es[2] - dx * 1.0, es[3] - dy * 1.0          # approche à 1 m/s
    v.mode = "physique"
    u.vaisseaux.append(v)
    u.actif = v
    u.cibler(station)
    n0 = len(station.pieces)
    for _ in range(60 * 60):
        u.avancer(DT)
        if len(u.vaisseaux) == 1:
            break
    assert len(u.vaisseaux) == 1 and u.actif is v, "pas d'amarrage"
    assert len(v.pieces) == n0 + 4 and "amarre:Station Alpha" in v.drapeaux
    print("Amarrage OK :", [p.m.cle + ("*" if p.retournee else "") for p in v.pieces], "jonctions", v.jonctions())
    from jeu import missions
    missions.verifier(u)
    assert "amarrage" in u.missions_faites
    # sauvegarde / rechargement
    d = sauvegarde.univers_vers_dict(u)
    u2 = sauvegarde.dict_vers_univers(d)
    a, b = u.etat(u.actif), u2.etat(u2.actif)
    assert hypot(a[0] - b[0], a[1] - b[1]) < 1e-3 and u2.actif.nom == "Navette"
    # désamarrage
    u.desamarrer()
    assert len(u.vaisseaux) == 2
    autre = [x for x in u.vaisseaux if x is not v][0]
    print("Désamarrage OK :", v.nom, [p.m.cle for p in v.pieces], "|", autre.nom, [p.m.cle + ("*" if p.retournee else "") for p in autre.pieces], autre.type())
    assert autre.nom == "Station Alpha" and len(autre.pieces) == n0 and not autre.pieces[0].retournee
    for _ in range(600):
        u.avancer(DT)
    assert len(u.vaisseaux) == 2, "ré-amarrage immédiat"
    print("   modes après 10 s :", v.mode, autre.mode, " distance %.1f m" % hypot(u.etat(v)[0] - u.etat(autre)[0], u.etat(v)[1] - u.etat(autre)[1]))


if __name__ == "__main__":
    import time
    t0 = time.time()
    if "--rapide" not in sys.argv:
        test_orbite_modeles()
    print("--- orbites OK (%.1f s)" % (time.time() - t0))
    u, v = test_lune()
    test_alunissage(u, v)
    print("--- Lune OK (%.1f s)" % (time.time() - t0))
    test_amarrage_et_sauvegarde()
    print("--- tout est OK (%.1f s)" % (time.time() - t0))
