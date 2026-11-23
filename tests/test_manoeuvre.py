# -*- coding: utf-8 -*-
"""Nœuds de manœuvre : planification, exécution automatique, transfert lunaire, sauvegarde."""
import os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
from math import sqrt, hypot
from jeu.univers import Univers
from jeu.orbite import angle_pi
from jeu.constantes import ACCELERATIONS
from jeu import manoeuvre, sauvegarde
from jeu.interface import fmt_duree
from test_vol import mise_en_orbite, modele, DT


def executer(u, v, limite=200_000):
    """Pilote automatique : SAS sur le nœud, plein gaz à l'instant d'allumage."""
    v.sas = "manoeuvre"
    while limite > 0:
        limite -= 1
        if v.noeud is None:
            return True
        allumage = manoeuvre.instant_allumage(v, v.noeud)
        if u.t < allumage - 25.0:                    # on patiente en accélérant le temps
            u.accel = len(ACCELERATIONS) - 1
            v.gaz = 0.0
        else:
            u.accel = 0
            vise = manoeuvre.angle_dv(v, v.noeud)
            aligne = vise is not None and abs(angle_pi(v.angle - vise)) < 0.02
            v.gaz = 1.0 if (u.t >= allumage and aligne) else 0.0
        u.avancer(DT)
    return False


def test_circularisation():
    """Le nœud annonce une orbite circulaire, et l'exécution la donne vraiment."""
    u = Univers(bac_a_sable=True)
    v = u.lancer("Hermès", modele("Hermès"))
    assert mise_en_orbite(u, v)
    u.accel = 0
    o = v.orbite
    ra = o.ra
    # Δv prograde à l'apoapside pour circulariser
    v_ap = sqrt(u.terre.mu * (2.0 / ra - 1.0 / o.a))
    dv = sqrt(u.terre.mu / ra) - v_ap
    n = u.placer_noeud(u.t + o.delai_apoapside(u.t), pro=dv)
    assert v.plan, "aucune trajectoire prévue"
    prevu = v.plan[0].orbite
    print("   avant : Pe %.0f m / Ap %.0f m" % (o.rp - u.terre.R, o.ra - u.terre.R))
    print("   prévu : Pe %.0f m / Ap %.0f m (Δv %.1f m/s, combustion %.1f s)" % (
        prevu.rp - u.terre.R, prevu.ra - u.terre.R, dv, manoeuvre.duree_combustion(v, dv)[0]))
    assert abs(prevu.rp - prevu.ra) < 0.01 * ra, "le plan devrait être circulaire"
    assert executer(u, v), "manœuvre non terminée"
    reel = v.orbite
    print("   réel  : Pe %.0f m / Ap %.0f m   (écart au plan : %.0f m)" % (
        reel.rp - u.terre.R, reel.ra - u.terre.R, abs(reel.rp - prevu.rp)))
    assert v.noeud is None and v.sas == "stab"
    assert abs(reel.rp - prevu.rp) < 0.02 * ra and abs(reel.ra - prevu.ra) < 0.02 * ra


def test_reglages():
    """Déplacement d'un tour, réglage radial, suppression, et le temps s'arrête à l'allumage."""
    u = Univers(bac_a_sable=True)
    v = u.lancer("Hermès", modele("Hermès"))
    assert mise_en_orbite(u, v)
    u.accel = 0
    periode = v.orbite.periode
    n = u.placer_noeud(u.t + 60.0, pro=30.0)
    t0 = n.t
    u.decaler_noeud(+1)
    assert abs(n.t - (t0 + periode)) < 1e-6
    u.decaler_noeud(-1)
    assert abs(n.t - t0) < 1e-6
    u.regler_noeud(rad=-20.0)
    assert v.plan and abs(n.rad + 20.0) < 1e-9
    # l'accélération du temps doit s'arrêter avant l'allumage, sans jamais le dépasser
    allumage = manoeuvre.instant_allumage(v, n)
    u.accel = len(ACCELERATIONS) - 1
    for _ in range(4000):
        u.avancer(DT)
        assert u.t <= allumage + 0.5, "le temps a sauté par-dessus l'allumage"
        if abs(u.t - allumage) < 0.2:
            break
    print("   allumage atteint à %.2f s près, accélération retombée à x%d" % (
        abs(u.t - allumage), ACCELERATIONS[u.accel]))
    assert abs(u.t - allumage) < 0.5 and u.accel <= 3
    u.supprimer_noeud()
    assert v.noeud is None and v.plan == [] and u.approche_plan is None


def _dv_pour_apoapside(v, n, r_vise):
    """Bissection sur le Δv prograde pour que l'apoapside atteigne r_vise."""
    bas, haut = 0.0, 800.0
    for _ in range(46):
        n.pro = 0.5 * (bas + haut)
        r = manoeuvre.orbite_apres(v, n)
        ra = r[0].ra if (r is not None and r[0].elliptique) else float("inf")
        if ra < r_vise:
            bas = n.pro
        else:
            haut = n.pro
    return 0.5 * (bas + haut)


def test_transfert_lunaire():
    """On cherche le nœud (position + Δv) qui donne une rencontre avec la Lune, puis on l'exécute."""
    from jeu.trajectoire import approche_minimale
    u = Univers(bac_a_sable=True)
    v = u.lancer("Sélène", modele("Sélène"))
    assert mise_en_orbite(u, v)
    u.accel = 0
    lune = u.par_nom["Lune"]
    u.cibler(lune)
    periode = v.orbite.periode
    n = u.placer_noeud(u.t + 10.0)

    def rencontre(plan):
        return any(tr.entree and tr.corps is lune for tr in plan)

    # 1) on promène le nœud sur un tour d'orbite, avec le Δv qui amène l'apoapside à la Lune
    trouve, meilleur = None, None
    for k in range(90):
        n.t = u.t + (k + 0.5) * periode / 90.0
        n.pro = _dv_pour_apoapside(v, n, lune.a)
        plan = manoeuvre.plan(v, n, 0.0, 4)
        if rencontre(plan):
            trouve = (n.t, n.pro)
            break
        appr = approche_minimale(plan, lune.position_relative, u.terre, n.t)
        if appr is not None and (meilleur is None or appr[1] < meilleur[0]):
            meilleur = (appr[1], n.t, n.pro)
    # 2) sinon, réglage fin du Δv autour du meilleur emplacement (ce que fait le joueur à la molette)
    if trouve is None:
        assert meilleur is not None
        print("   meilleure approche du 1er balayage : %.0f km" % (meilleur[0] / 1e3))
        n.t = meilleur[1]
        for k in range(-60, 61):
            n.pro = meilleur[2] + k * 0.5
            if rencontre(manoeuvre.plan(v, n, 0.0, 4)):
                trouve = (n.t, n.pro)
                break
    assert trouve is not None, "aucune rencontre trouvée en promenant le nœud"
    u.regler_noeud(pro=trouve[1], t=trouve[0])
    tr = next(t for t in v.plan if t.entree and t.corps is lune)
    print("   nœud à T+%s : Δv %.1f m/s → rencontre Lune dans %.1f h, périapside %.0f km" % (
        fmt_duree(n.t - u.t), n.dv(), (tr.t0 - u.t) / 3600.0, (tr.orbite.rp - lune.R) / 1e3))
    assert u.approche_plan is not None and u.approche_plan[1] < lune.soi
    assert executer(u, v), "manœuvre non terminée"
    v.gaz = 0.0
    for _ in range(60):
        u.avancer(DT)
    ap = v.orbite.ra if v.orbite.elliptique else float("inf")
    print("   après la poussée : Ap %.0f km (visé %.0f km) — une poussée de %s perd un peu"
          % ((ap - u.terre.R) / 1e3, (lune.a - u.terre.R) / 1e3,
             fmt_duree(manoeuvre.duree_combustion(v, trouve[1])[0])))
    assert ap > 0.8 * lune.a, "la manœuvre devrait amener tout près de l'orbite lunaire"

    # 2e temps : comme un vrai joueur, on complète au jugé en regardant la trajectoire
    v.sas, v.gaz = "pro", 1.0
    carb0 = v.carburant_actif()[0]
    for _ in range(60 * 200):
        u.avancer(DT)
        if any(t.entree and t.corps is lune for t in v.troncons):
            break
    v.gaz = 0.0
    reelle = next((t for t in v.troncons if t.entree and t.corps is lune), None)
    assert reelle is not None, [(t.corps.nom, t.fin) for t in v.troncons]
    print("   correction de %.0f kg de carburant : rencontre confirmée, périapside %.0f km dans %.1f h"
          % (carb0 - v.carburant_actif()[0], (reelle.orbite.rp - lune.R) / 1e3,
             (reelle.t0 - u.t) / 3600.0))


def test_sauvegarde_noeud():
    u = Univers(bac_a_sable=True)
    v = u.lancer("Hermès", modele("Hermès"))
    assert mise_en_orbite(u, v)
    u.placer_noeud(u.t + 300.0, pro=120.0, rad=-15.0)
    chemin = os.path.join(tempfile.gettempdir(), "test_noeud_as2d.json")
    sauvegarde.sauvegarder(u, chemin)
    u2 = sauvegarde.charger(chemin)
    os.remove(chemin)
    n2 = u2.actif.noeud
    assert n2 is not None and abs(n2.t - (u.t + 300.0)) < 1e-6
    assert abs(n2.pro - 120.0) < 1e-9 and abs(n2.rad + 15.0) < 1e-9
    assert u2.actif.plan, "le plan doit être recalculé au chargement"
    a, b = v.plan[0].orbite, u2.actif.plan[0].orbite
    assert abs(a.rp - b.rp) < 1.0 and abs(a.ra - b.ra) < 1.0
    print("   sauvegarde/chargement du nœud OK (Pe prévu %.0f m)" % (b.rp - u2.terre.R))


def test_poussee_hors_fenetre():
    """Une poussée sans rapport (loin du nœud) ne doit pas entamer le Δv planifié."""
    u = Univers(bac_a_sable=True)
    v = u.lancer("Hermès", modele("Hermès"))
    assert mise_en_orbite(u, v)
    u.accel = 0
    n = u.placer_noeud(u.t + 3000.0, pro=100.0)
    v.sas = "pro"
    v.gaz = 1.0
    for _ in range(600):
        u.avancer(DT)
    assert v.noeud is n and not n.commencee, "le nœud ne doit pas être entamé de loin"
    print("   poussée hors fenêtre : nœud intact (Δv %.0f m/s)" % n.dv())


def test_souris():
    """Parcours complet à la souris : clic sur l'orbite, glissement des poignées, molette."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    import pygame
    import main as jeu_main
    app = jeu_main.Application()
    app.nouvelle_partie(True)
    app.scene.charger_modele(4)
    app.scene.lancer()
    u, sc = app.univers, app.scene
    v = u.actif
    assert mise_en_orbite(u, v)
    u.accel = 0
    sc.cam.zoom = 0.004
    sc.maj(1 / 60)
    sc.dessiner(app.ecran)

    def clic(pos, bouton=1):
        sc.evenement(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=bouton))
        sc.evenement(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=pos, button=bouton))

    def image():
        sc.maj(1 / 60)
        sc.dessiner(app.ecran)

    # 1) clic sur la trajectoire : un nœud apparaît
    ech = sc.cam.echantillons
    assert ech, "la trajectoire n'a pas été échantillonnée"
    libres = [e for e in ech if 0 < e[0] < app.ecran.get_width() and 0 < e[1] < app.ecran.get_height()
              and not any(b.rect.collidepoint(e[0], e[1]) for b in sc.hud.boutons)]
    touches = [b.libelle for b in sc.hud.boutons if b.rect.collidepoint(ech[len(ech) // 3][:2])]
    print("   (point au tiers de l'orbite sous un bouton : %s)" % (touches or "non"))
    x, y, t = libres[len(libres) // 3]
    clic((int(x), int(y)))
    assert v.noeud is not None, "le clic sur l'orbite doit poser un nœud"
    assert abs(v.noeud.t - t) < 1e-6
    image()
    noms = [p[0] for p in sc.cam.poignees]
    print("   poignées dessinées :", noms)
    assert set(noms) == {"pro", "retro", "rad+", "rad-", "centre"}

    # 2) glisser la poignée prograde
    nom, (hx, hy), (dx, dy) = next(p for p in sc.cam.poignees if p[0] == "pro")
    sc.evenement(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(int(hx), int(hy)), button=1))
    assert sc.glisse is not None
    cible = (int(hx + dx * 80), int(hy + dy * 80))
    sc.evenement(pygame.event.Event(pygame.MOUSEMOTION, pos=cible, rel=(0, 0), buttons=(1, 0, 0)))
    sc.evenement(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=cible, button=1))
    assert sc.glisse is None
    print("   glissement de 80 px sur la poignée prograde : Δv = %.1f m/s" % v.noeud.pro)
    assert 60.0 < v.noeud.pro < 100.0, v.noeud.pro
    assert v.plan and v.plan[0].orbite.ra > v.orbite.ra, "l'orbite prévue doit être plus haute"
    image()

    # 3) molette sur la poignée radiale
    hx, hy = next(p[1] for p in sc.cam.poignees if p[0] == "rad-")
    avant = v.noeud.rad
    for _ in range(3):
        sc.evenement(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=1, pos=(int(hx), int(hy))))
    print("   3 crans de molette sur « radial - » : rad = %.1f m/s" % v.noeud.rad)
    assert abs(v.noeud.rad - (avant - 3.0)) < 1e-6

    # 4) la molette ailleurs zoome toujours
    z = sc.cam.zoom
    sc.evenement(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=1, pos=(10, 10)))
    assert sc.cam.zoom > z

    # 5) touche Suppr : le nœud disparaît
    sc.evenement(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DELETE, scancode=0, unicode="", mod=0))
    assert v.noeud is None and v.plan == []
    image()
    # 6) touche A : nœud par défaut à l'apoapside
    sc.evenement(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a, scancode=0, unicode="a", mod=0))
    assert v.noeud is not None
    print("   touche A : nœud posé dans %s (apoapside dans %s)" % (
        fmt_duree(v.noeud.t - u.t), fmt_duree(v.orbite.delai_apoapside(u.t))))
    assert abs((v.noeud.t - u.t) - v.orbite.delai_apoapside(u.t)) < 1.0


def test_circularisation_lunaire():
    """La circularisation automatique autour d'un petit corps (la Lune) doit donner
    une orbite à peu près ronde. Un arrêt plus serré qu'aujourd'hui (0,4 % d'écart
    au lieu de 2,4 %) paraissait mieux, mais il change la moindre combustion et fait
    dévier les trajectoires de retour — le scénario Apollo 11 (test_scenarios) rate
    alors la Terre : on garde le seuil historique et cette garde anti-dérive."""
    from math import cos, sin, atan2
    from jeu.orbite import Orbite
    from jeu.vaisseau import construire
    from jeu import pilote, reglages
    u = Univers(bac_a_sable=True)
    lune = next(c for c in u.corps if c.nom == "Lune")
    v = construire("Essai", ["capsule", "reservoir_m", "alize"], lune)
    v.corps = lune
    r, ra = lune.R + 20000.0, lune.R + 100000.0
    va = sqrt(lune.mu * (2.0 / r - 1.0 / ra))
    ang = 2.2
    v.x, v.y = r * cos(ang), r * sin(ang)
    v.vx, v.vy = -va * sin(ang), va * cos(ang)
    v.angle, v.omega, v.gaz = atan2(v.vy, v.vx), 0.0, 0.0
    v.mode = "rails"
    v.orbite = Orbite(v.x, v.y, v.vx, v.vy, lune.mu, u.t)
    u.vaisseaux.append(v)
    u.actif = v
    u._predire(v)
    reglages.AIDES = True
    assert pilote.planifier_circularisation(u, v) and v.noeud is not None
    u.lancer_pilote(pilote.ExecuterNoeud())
    for _ in range(60 * 3600):
        u.avancer(DT)
        if u.pilote is None or v.detruit:
            break
    reglages.AIDES = False
    assert not v.detruit and v.noeud is None, [m[0] for m in u.messages][-2:]
    o = v.orbite
    print("   Lune : Pe %.0f m / Ap %.0f m (écart %.1f %%)" % (
        o.rp - lune.R, o.ra - lune.R, 100.0 * (o.ra - o.rp) / o.ra))
    assert (o.ra - o.rp) / o.ra < 0.05, "circularisation lunaire trop ovale"


def test_manoeuvre_a_sec():
    """Étage à sec en pleine manœuvre automatique : après étagement raté (plus de moteur),
    le pilote abandonne en COUPANT les gaz et en prévenant — il laissait la manette à fond
    en silence, et un ravitaillement plus tard aurait rallumé le moteur à 100 %."""
    from math import cos, sin, atan2
    from jeu.orbite import Orbite
    from jeu.vaisseau import construire
    from jeu import pilote, reglages
    u = Univers(bac_a_sable=True)
    c = next(cc for cc in u.corps if cc.nom == "Terre")
    v = construire("Essai", ["capsule", "decoupleur", "reservoir_s", "alize"], c)
    v.corps = c
    r, ra = c.R + 20000.0, c.R + 100000.0
    va = sqrt(c.mu * (2.0 / r - 1.0 / ra))
    ang = 2.2
    v.x, v.y = r * cos(ang), r * sin(ang)
    v.vx, v.vy = -va * sin(ang), va * cos(ang)
    v.angle, v.omega, v.gaz = atan2(v.vy, v.vx), 0.0, 0.0
    v.mode = "rails"
    v.orbite = Orbite(v.x, v.y, v.vx, v.vy, c.mu, u.t)
    u.vaisseaux.append(v)
    u.actif = v
    u._predire(v)
    for p in v.pieces:
        if p.m.cle == "reservoir_s":
            p.carburant = 3.0                    # à peine quelques m/s, bien moins que le Δv
    reglages.AIDES = True
    assert pilote.planifier_circularisation(u, v) and v.noeud is not None
    u.lancer_pilote(pilote.ExecuterNoeud())
    for _ in range(60 * 3600):
        u.avancer(DT)
        if u.pilote is None:
            break
    reglages.AIDES = False
    assert v.gaz == 0.0, "gaz laissé à %.2f après l'abandon de la manœuvre" % v.gaz
    assert any("plus de carburant" in m[0] for m in u.messages), [m[0] for m in u.messages][-3:]
    print("   manœuvre à sec : gaz coupé, message affiché, vaisseau intact")


if __name__ == "__main__":
    test_circularisation()
    test_circularisation_lunaire()
    test_reglages()
    test_manoeuvre_a_sec()
    test_transfert_lunaire()
    test_sauvegarde_noeud()
    test_poussee_hors_fenetre()
    test_souris()
    print("--- manœuvres : OK")
