# -*- coding: utf-8 -*-
"""
Mode tactile (Android), testé sans écran avec des doigts simulés.

Le pilote de ce fichier n'a droit qu'aux événements de doigts (FINGERDOWN, FINGERMOTION,
FINGERUP) posés sur les commandes réellement dessinées à l'écran : si une commande
manque ou tombe à côté, le vol échoue.
"""
import os, sys, random, subprocess, tempfile
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("AGENCE_ECRAN", "2400x1080")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from math import atan2, hypot, pi, cos, sin
import pygame
import main as jeu_main
from jeu.orbite import angle_pi
from jeu.constantes import ACCELERATIONS

DT = 1 / 60.0


class Main:
    """Des doigts simulés sur l'écran tactile."""

    def __init__(self, app):
        self.app = app
        self.poses = {}

    def _ev(self, typ, ident, pos):
        L, H = self.app.ecran.get_size()
        self.app.traiter(pygame.event.Event(typ, finger_id=ident, touch_id=0, x=pos[0] / L, y=pos[1] / H,
                                            dx=0.0, dy=0.0))

    def poser(self, ident, pos):
        self._ev(pygame.FINGERDOWN, ident, pos)
        self.poses[ident] = pos

    def glisser(self, ident, pos):
        self._ev(pygame.FINGERMOTION, ident, pos)
        self.poses[ident] = pos

    def lever(self, ident):
        if ident in self.poses:
            self._ev(pygame.FINGERUP, ident, self.poses.pop(ident))

    def taper(self, pos, ident=99):
        self.poser(ident, pos)
        self.lever(ident)

    def boutons(self):
        sc = self.app.scene
        return list(getattr(getattr(sc, "hud", None), "boutons", [])) + list(getattr(sc, "boutons", []))

    def bouton(self, libelle):
        """Tape sur le bouton affiché qui porte ce libellé (échec si absent)."""
        for b in self.boutons():
            if b.libelle == libelle:
                self.taper(b.rect.center)
                return
        raise AssertionError("bouton « %s » introuvable : %s" % (libelle, [b.libelle for b in self.boutons()]))

    def commande(self, commande):
        """Centre de la commande maintenue (manette, rotation, RCS) à l'écran."""
        for rect, c, _ in self.app.scene.hud.maintenus:
            if c == commande:
                return rect.center
        raise AssertionError("commande %r absente" % (commande,))


def image(app, n=1):
    for _ in range(n):
        app.scene.maj(DT)
        app.scene.dessiner(app.ecran)


def nouvelle_app():
    return jeu_main.Application(tactile=True)


# =============================================================================
def test_orbite_au_doigt():
    """Du menu principal à l'orbite, uniquement avec des doigts sur l'écran."""
    app = nouvelle_app()
    main = Main(app)
    image(app)
    main.bouton("Bac à sable (tout débloqué)")
    image(app)
    main.bouton("Modèles…")
    image(app)
    # une des fusées modèles (les boutons du menu « Modèles » sont insérés en tête de liste)
    boutons_modeles = [b for b in main.boutons() if b.libelle == ""]
    main.taper(boutons_modeles[-3].rect.center)          # insérés au début, dans l'ordre inverse
    image(app)
    main.bouton("LANCER")
    image(app, 2)
    u = app.univers
    v = u.actif
    assert type(app.scene).__name__ == "SceneVol", type(app.scene)
    print("   lancé : %s (%d pièces), écran logique %s" % (v.nom, len(v.pieces), app.ecran.get_size()))
    sc = app.scene
    hud = sc.hud
    main.bouton("STAB")
    for _ in range(3):
        main.bouton("▶")                                  # temps x4 pendant la montée
    # gaz à fond : un doigt posé en haut de la manette
    r = hud.rect_gaz
    main.poser(1, (r.centerx, r.y + 30))
    image(app)
    assert v.gaz == 1.0, v.gaz
    ROT_G, ROT_D = main.commande(("rot", 1)), main.commande(("rot", -1))
    sens = None                         # signe de la rotation obtenue avec ⟲ (mesuré en vol)
    phase, tenu, etages = "montee", None, 0
    for k in range(60 * 2000):
        if v.detruit or u.actif is not v:
            raise AssertionError("vaisseau perdu en phase %s" % phase)
        x, y, vx, vy = u.etat(v)
        alt = hypot(x, y) - v.corps.R
        haut = atan2(y, x)
        # étage vide : on tape ÉTAGE
        if v.moteur_actif() is not None and v.carburant_actif()[0] <= 0 and v.gaz > 0:
            main.bouton("ÉTAGE")
            etages += 1
        if phase == "montee":
            if sens is None and alt > 60:
                # on mesure une fois ce que fait ⟲ : il doit tourner le vaisseau vers la GAUCHE de l'écran
                ex0, ey0 = sc.cam.direction_ecran(cos(v.angle), sin(v.angle))
                a0 = v.angle
                main.poser(2, ROT_G)
                image(app, 20)
                main.lever(2)
                ex1, ey1 = sc.cam.direction_ecran(cos(v.angle), sin(v.angle))
                sens = 1 if angle_pi(v.angle - a0) > 0 else -1
                ecran = atan2(-ey1, ex1) - atan2(-ey0, ex0)   # angle à l'écran, y vers le haut
                assert angle_pi(ecran) > 0, "⟲ doit tourner dans le sens inverse des aiguilles à l'écran"
                image(app, 60)
                continue
            if sens is not None:
                incl = min(pi / 2, (pi / 2) * max(0.0, (alt - 150.0) / 5500.0) ** 0.55)
                err = angle_pi(haut + incl - (v.angle + v.omega * 0.8))
                voulu = None if abs(err) < 0.02 else (2 if err * sens > 0 else 3)
                if voulu != tenu:
                    if tenu is not None:
                        main.lever(tenu)
                    if voulu is not None:
                        main.poser(voulu, ROT_G if voulu == 2 else ROT_D)
                    tenu = voulu
            if v.orbite is not None and v.orbite.elliptique and v.orbite.ra - v.corps.R > 13_000:
                main.glisser(1, (r.centerx, r.bottom - 4))   # manette tout en bas : gaz coupés
                main.lever(1)
                if tenu is not None:
                    main.lever(tenu)
                    tenu = None
                image(app)
                assert v.gaz == 0.0, v.gaz
                main.bouton("PRO")
                phase = "croisiere"
        elif phase == "croisiere":
            if v.mode == "rails":
                d = v.orbite.delai_apoapside(u.t)
                if d > 60 and u.accel < len(ACCELERATIONS) - 1:
                    main.bouton("▶")
                elif d < 14:
                    main.taper(hud.rect_temps.center)        # tape au centre : retour à x1
                    phase = "circularisation"
        else:
            if v.gaz == 0.0:
                main.poser(1, (r.centerx, r.y + 30))
            o = v.orbite
            if o is not None and o.elliptique and o.rp - v.corps.R > 9_000:
                main.glisser(1, (r.centerx, r.bottom - 4))
                main.lever(1)
                image(app, 30)
                break
        image(app)
    o = v.orbite
    print("   orbite au doigt : Pe %.1f km, Ap %.1f km, %d étage(s) largué(s), t = %.0f s de jeu" % (
        (o.rp - v.corps.R) / 1e3, (o.ra - v.corps.R) / 1e3, etages, u.t))
    assert v.mode == "rails" and o.rp - v.corps.R > 7_000
    return app, main


def test_gestes(app, main):
    """Pincement pour zoomer, nœud posé d'une tape, poignée glissée puis tapée, menu, retour Android."""
    sc, u = app.scene, app.univers
    v = u.actif
    sc.cam.zoom = 0.004
    image(app)
    # --- pincement : deux doigts sur la vue qui s'écartent
    z0 = sc.cam.zoom
    cx, cy = app.ecran.get_width() // 2, 120
    main.poser(11, (cx - 40, cy))
    main.poser(12, (cx + 40, cy))
    for k in range(1, 11):
        main.glisser(11, (cx - 40 - 6 * k, cy))
        main.glisser(12, (cx + 40 + 6 * k, cy))
    main.lever(11)
    main.lever(12)
    image(app)
    print("   pincement : zoom x%.2f (écart des doigts x%.2f)" % (sc.cam.zoom / z0, 200 / 80))
    assert abs(sc.cam.zoom / z0 - 200 / 80) < 0.05
    assert v.noeud is None, "un pincement ne doit pas poser de nœud"
    sc.cam.zoom = z0
    image(app)
    # --- tape sur l'orbite : un nœud apparaît
    ech = [e for e in sc.cam.echantillons if 330 < e[0] < 900 and 70 < e[1] < 300]
    assert ech, "aucun point d'orbite à portée de doigt"
    x, y, t = ech[len(ech) // 2]
    main.taper((x, y))
    assert v.noeud is not None, "la tape sur l'orbite doit poser un nœud"
    image(app)
    # --- glisser la poignée prograde (grande sur écran tactile)
    nom, (hx, hy), (dx, dy) = next(p for p in sc.cam.poignees if p[0] == "pro")
    main.poser(5, (hx, hy))
    for k in range(1, 9):
        main.glisser(5, (hx + dx * 10 * k, hy + dy * 10 * k))
    main.lever(5)
    image(app)
    print("   poignée glissée de 80 px : Δv prograde %.1f m/s" % v.noeud.pro)
    assert 70 < v.noeud.pro < 90, v.noeud.pro
    # --- une simple tape sur « radial + » : +1 m/s
    hx, hy = next(p[1] for p in sc.cam.poignees if p[0] == "rad+")
    main.taper((hx, hy))
    main.taper((hx, hy))
    assert abs(v.noeud.rad - 2.0) < 1e-9, v.noeud.rad
    # --- bouton ✕ du panneau de manœuvre
    main.bouton("✕")
    assert v.noeud is None
    # --- menu ☰ puis bouton « retour » d'Android (Échap)
    image(app)
    main.bouton("☰")
    image(app)
    assert sc.panneau == "pause"
    main.bouton("Missions")
    image(app)
    assert sc.panneau == "missions"
    app.traiter(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_AC_BACK, scancode=0, unicode="", mod=0))
    assert sc.panneau is None, sc.panneau
    # --- RCS : la croix apparaît et pousse le vaisseau
    main.bouton("RCS")
    image(app)
    mono0 = v.mono()
    main.poser(6, main.commande(("rcs", 1, 0)))
    image(app, 60)
    main.lever(6)
    image(app)
    assert v.mono() < mono0, "la croix RCS doit consommer du monergol"
    print("   gestes OK (pincement, nœud, poignées, menu, retour Android, RCS)")


def test_hangar_au_doigt():
    app = nouvelle_app()
    main = Main(app)
    app.nouvelle_partie(True)
    image(app)
    sc = app.scene
    main.bouton("Tout vider")
    image(app)
    assert sc.cles == []

    def taper_piece(cle):
        rect = next(r for r, c in sc.zones_catalogue if c == cle)
        main.taper(rect.center)
        image(app)

    for cle in ("capsule", "decoupleur", "reservoir_m", "alize"):
        taper_piece(cle)
    assert sc.cles == ["capsule", "decoupleur", "reservoir_m", "alize"], sc.cles
    # glisser dans le catalogue : il défile, et aucune pièce n'est ajoutée
    d0 = sc.defilement
    main.poser(7, (150, 420))
    for k in range(1, 11):
        main.glisser(7, (150, 420 - 25 * k))
    main.lever(7)
    image(app)
    assert sc.defilement > d0 + 200 and len(sc.cles) == 4, (sc.defilement, sc.cles)
    # sélection d'une pièce dans la pile, puis ▲ et ✕
    rect = next(r for r, i in sc.zones_pile if i == 3)
    main.taper(rect.center)
    image(app)
    assert sc.selection == 3
    main.bouton("▲")
    image(app)
    assert sc.cles == ["capsule", "decoupleur", "alize", "reservoir_m"], sc.cles
    main.bouton("✕")
    image(app)
    assert sc.cles == ["capsule", "decoupleur", "reservoir_m"], sc.cles
    # renommer avec le clavier du téléphone (événements TEXTINPUT)
    main.taper(sc.zone_nom.center)
    assert sc.edition_nom
    for _ in range(30):
        app.traiter(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_BACKSPACE, scancode=0, unicode="", mod=0))
    for lettre in "Ariane":
        app.traiter(pygame.event.Event(pygame.TEXTINPUT, text=lettre))
    app.traiter(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, scancode=0, unicode="", mod=0))
    assert sc.nom == "Ariane" and not sc.edition_nom, sc.nom
    # retour Android dans le hangar : vers le suivi des vols
    main.bouton("Modèles…")
    image(app)
    assert sc.menu_modeles
    app.traiter(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_AC_BACK, scancode=0, unicode="", mod=0))
    assert not sc.menu_modeles
    print("   hangar au doigt OK : ajout, défilement, ▲, ✕, nom « %s »" % sc.nom)


def test_singe_multi_doigts():
    """Doigts au hasard (jusqu'à 3 à la fois), sur trois formats d'écran : aucune exception."""
    formats = ("2400x1080", "1920x1080", "2048x1536")
    for f in formats:
        os.environ["AGENCE_ECRAN"] = f
        for graine in range(2):
            rnd = random.Random(graine)
            app = nouvelle_app()
            app.quitter = lambda: None
            main = Main(app)
            app.nouvelle_partie(rnd.random() < 0.5)
            image(app)
            scenes = set()
            for k in range(1500):
                L, H = app.ecran.get_size()
                r = rnd.random()
                cibles = [b.rect.center for b in main.boutons()]
                hud = getattr(app.scene, "hud", None)
                if hud is not None and hasattr(hud, "maintenus"):
                    cibles += [rect.center for rect, _, _ in hud.maintenus]
                if r < 0.25:
                    pos = rnd.choice(cibles) if cibles and rnd.random() < 0.7 else (rnd.randrange(L), rnd.randrange(H))
                    ident = rnd.randrange(3)
                    if ident in main.poses:
                        main.lever(ident)
                    else:
                        main.poser(ident, pos)
                elif r < 0.45 and main.poses:
                    ident = rnd.choice(list(main.poses))
                    px, py = main.poses[ident]
                    main.glisser(ident, (min(L - 1, max(0, px + rnd.randrange(-80, 81))),
                                         min(H - 1, max(0, py + rnd.randrange(-80, 81)))))
                elif r < 0.47:
                    app.traiter(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_AC_BACK, scancode=0,
                                                   unicode="", mod=0))
                elif r < 0.48:
                    app.traiter(pygame.event.Event(pygame.TEXTINPUT, text=rnd.choice("aZé9 ")))
                elif r < 0.49:
                    app.traiter(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=rnd.choice((-1, 1))))
                image(app)
                scenes.add(type(app.scene).__name__)
            for ident in list(main.poses):
                main.lever(ident)
            print("   écran %-9s → logique %-10s graine %d : OK %s" % (f, "%dx%d" % app.ecran.get_size(),
                                                                       graine, sorted(scenes)))
    os.environ["AGENCE_ECRAN"] = "2400x1080"


def test_android_simule():
    """Dans un processus qui se croit sur Android : mode tactile automatique, sauvegarde privée."""
    dossier = tempfile.mkdtemp(prefix="android_prive_")
    code = r'''
import os, sys
sys.path.insert(0, %r)
import pygame, main as m
from jeu import plateforme, sauvegarde
app = m.Application()
assert plateforme.TACTILE, "Android non détecté"
print("tactile", app.ecran.get_size())
app.nouvelle_partie(True)
app.scene.lancer()
app.sauvegarde_auto()
print("sauvegarde", sauvegarde.chemin_sauvegarde())
''' % os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    env = dict(os.environ, ANDROID_PRIVATE=dossier, AGENCE_ECRAN="2400x1080")
    env.pop("AGENCE_TACTILE", None)
    r = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=120)
    sortie = r.stdout + r.stderr
    assert r.returncode == 0, sortie
    assert "tactile (1200, 540)" in sortie, sortie
    assert os.path.exists(os.path.join(dossier, "sauvegarde.json")), sortie
    print("   Android simulé : mode tactile auto, écran 1200x540, sauvegarde dans le dossier privé")


if __name__ == "__main__":
    app, main = test_orbite_au_doigt()
    test_gestes(app, main)
    test_hangar_au_doigt()
    test_singe_multi_doigts()
    test_android_simule()
    from jeu import sauvegarde as _s                  # les tapes au hasard ont pu changer les réglages
    _f = os.path.join(os.path.dirname(_s.chemin_sauvegarde()), "reglages.json")
    if os.path.exists(_f):
        os.remove(_f)
    print("--- tactile : OK")
