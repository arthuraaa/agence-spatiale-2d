# -*- coding: utf-8 -*-
"""Scène de vol : lit les commandes du joueur, fait avancer l'univers et affiche tout."""
from math import hypot, inf
import time
import pygame
from .constantes import (BLANC, GRIS, CYAN, VERT, ROUGE, JAUNE, ORANGE, ACCEL_MAX_PHYSIQUE,
                         NOEUD_CLIC, NOEUD_SENSIBILITE, NOEUD_PAS_MOLETTE,
                         NOEUD_RAYON_POIGNEE_TACTILE, NOEUD_CLIC_TACTILE, TOLERANCE_DOIGT)
from .rendu import Camera, dessiner_monde, objet_sous_souris
from .hud import Hud
from .hud_tactile import HudTactile
from .tactile import Doigts
from . import plateforme, reglages, sons, triche, album
from .corps import Corps
from .interface import fmt_masse, texte, texte_multiligne, panneau, Bouton, fmt_nombre
from .missions import MISSIONS
from .univers import REFERENCES
from . import sauvegarde
from .textes import t

def aide():
    """Lignes de l'aide clavier, dans la langue active."""
    return [
        (t("PILOTAGE"), [(t("← →  ou  Q D"), t("tourner")), (t("↑ ↓  ou  Z S"), t("gaz + / -")),
                         (t("W / X"), t("plein gaz / couper")), (t("ESPACE"), t("séparer l'étage")),
                         (t("T"), t("SAS marche / arrêt")),
                         (t("1 … 8"), t("SAS : stab, pro, rétro, rad+, rad-, cible, anti, manœuvre")),
                         (t("R  puis  I K J L"), t("RCS : translation (amarrage)")), (t("P"), t("parachute")),
                         (t("B"), t("planter un drapeau (posé)")),
                         (t("U"), t("désamarrer")), (t("V"), t("référence de vitesse"))]),
        (t("MANŒUVRES"), [(t("A  ou  clic sur l'orbite"), t("poser un nœud de manœuvre")),
                          (t("Glisser une poignée"), t("régler le Δv (Maj : fin, Ctrl : rapide)")),
                          (t("Molette sur une poignée"), t("régler le Δv au m/s près")),
                          (t("Glisser le centre du nœud"), t("déplacer le nœud sur l'orbite")),
                          (t("8"), t("SAS : pointer la manœuvre")), (t("Suppr"), t("effacer le nœud")),
                          (t("G"), t("pilote automatique (option « Aides »)"))]),
        (t("VUE ET TEMPS"), [(t("Molette / PgPréc PgSuiv"), t("zoom")),
                             (t("Clic sur un objet"), t("cibler, centrer, contrôler")),
                             (t("F"), t("recentrer sur le vaisseau")),
                             (t("C"), t("caméra : auto / horizon / nord")),
                             (t(",  et  ;  (ou .)"), t("ralentir / accélérer le temps")),
                             (t("Entrée"), t("temps normal (x1)")),
                             (t("N"), t("vaisseau suivant")), (t("Retour arrière"), t("effacer la cible")),
                             (t("M / H / Échap"), t("missions / aide / menu")),
                             (t("F5 / F9"), t("sauvegarder / charger"))]),
    ]


def conseils():
    return t("CONSEILS_ORBITE")


def aide_tactile():
    """Lignes de l'aide tactile, dans la langue active."""
    return [
        (t("COMMANDES"), [(t("Manette à gauche"), t("gaz : pose le doigt et glisse")),
                          (t("⟲  ⟳  (maintenir)"), t("tourner le vaisseau")),
                          (t("ÉTAGE"), t("larguer l'étage vide")),
                          (t("Drapeau"), t("planter un drapeau (posé)")),
                          (t("Boutons du bas"), t("SAS : stab, pro, rétro, radial...")),
                          (t("RCS  puis  ▲ ▼ ◀ ▶"), t("translation fine (amarrage)")),
                          (t("◀  x1  ▶"), t("temps (tape au centre = x1)")),
                          (t("Pilote"), t("orbite auto, exécuter, transfert (aides)")),
                          (t("☰"), t("menu : missions, sauvegarde..."))]),
        (t("GESTES"), [(t("Tape sur un objet"), t("cibler, centrer, contrôler")),
                       (t("Tape sur l'orbite"), t("poser un nœud de manœuvre")),
                       (t("Glisser une poignée"), t("régler le Δv du nœud")),
                       (t("Tape sur une poignée"), t("± 1 m/s (réglage fin)")),
                       (t("Glisser le centre du nœud"), t("le déplacer sur l'orbite")),
                       (t("Deux doigts"), t("pincer pour zoomer")),
                       (t("Vaisseau"), t("revenir au vaisseau"))]),
    ]


def conseils_tactile():
    return t("CONSEILS_ORBITE_TACTILE")


class SceneVol:
    def __init__(self, app):
        self.app = app
        self.u = app.univers
        self.cam = Camera()
        self.tactile = plateforme.TACTILE
        self.hud = HudTactile(self) if self.tactile else Hud(self)
        self.doigts = Doigts()
        self.pince = None              # écart entre deux doigts qui pincent la vue (zoom)
        self.panoramique = None        # dernière position de la souris quand on fait glisser la vue
        self.appui_horloge = None      # (doigt, instant) : appui long sur l'horloge = menu secret
        self.tolerance_clic = NOEUD_CLIC_TACTILE if self.tactile else NOEUD_CLIC
        if self.tactile:
            self.cam.rayon_poignee = NOEUD_RAYON_POIGNEE_TACTILE
        self.panneau = None            # None | "missions" | "aide" | "pause"
        self.boutons = []              # boutons du panneau ouvert
        self.glisse = None             # poignée de nœud en cours de déplacement
        self.temps_reel = 0.0
        a = self.u.actif
        if a is None:
            self.u.vaisseau_suivant()
            a = self.u.actif
        self.cam.zoom = 5.0 if (a is not None and a.mode == "pose") else 2.0

    # ---------------------------------------------------------------- actions
    def ouvrir(self, nom):
        self.panneau = None if self.panneau == nom else nom

    def basculer_rcs(self):
        a = self.u.actif
        if a is not None:
            a.rcs = not a.rcs

    def changer_reference(self):
        a = self.u.actif
        if a is not None:
            refs = [r for r in REFERENCES if r != "cible" or self.u.cible is not None]
            a.ref_vitesse = refs[(refs.index(a.ref_vitesse) + 1) % len(refs)] if a.ref_vitesse in refs else refs[0]

    def changer_camera(self):
        modes = ["auto", "horizon", "nord"]
        self.cam.mode = modes[(modes.index(self.cam.mode) + 1) % 3]

    def centrer_sur(self, obj):
        self.cam.focus = None if obj is self.u.actif else obj
        self.cam.dx = self.cam.dy = 0.0
        self.cam.retour = False
        if isinstance(obj, Corps) and obj.R * self.cam.zoom > 300:
            self.cam.zoom = 300.0 / obj.R

    def controler(self, v):
        if self.u.controler(v):
            self.cam.focus = None
            self.cam.dx = self.cam.dy = 0.0

    def recuperer(self):
        if self.u.recuperer(self.u.actif):
            self.app.aller_hangar()

    def _sons(self, dt):
        """Bruitages demandés par la simulation, et volume des boucles (moteur, vent, RCS)."""
        u, a = self.u, self.u.actif
        for nom in u.bruits:
            sons.jouer(nom)
        u.bruits.clear()
        if getattr(self.hud, "alerte", False):            # « Freinage : MAINTENANT »
            sons.jouer("alerte", 0.7)
        moteur = vent = rcs = rentree = 0.0
        dans_l_air = False
        if a is not None and self.panneau != "pause" and a.mode == "physique":
            c = a.corps
            alt = u.altitude(a)
            rho = c.densite(alt) if alt < c.atm_h else 0.0
            dans_l_air = rho > 0.02
            if a.poussee_et_debit(rho / 1.225)[0] > 0.0:
                moteur = (0.3 + 0.7 * a.gaz) * (1.0 if dans_l_air else 0.5)   # étouffé dans le vide
            cmd = u.commandes
            if a.rcs and (cmd.avant or cmd.cote) and a.mono() > 0.0:
                rcs = 0.5
            if rho > 0.0:
                x, y, vx, vy = u.etat(a)
                w = c.vitesse_rotation
                pression = 0.5 * rho * ((vx + w * y) ** 2 + (vy - w * x) ** 2)
                vent = min(0.8, pression / 25000.0)
                # même formule que le plasma (rendu) : la coque rougeoye, ça gronde et ça vibre
                chaleur = min(1.0, 2.0 * pression / 2000000.0)
                rentree = min(0.9, 1.1 * chaleur) if chaleur > 0.12 else 0.0
                self.cam.tremble = chaleur
            else:
                self.cam.tremble = 0.0
        else:
            self.cam.tremble = 0.0
        sons.regler_boucle("moteur", moteur, dt)
        sons.regler_boucle("vent", vent, dt)
        sons.regler_boucle("rcs", rcs, dt)
        sons.regler_boucle("rentree", rentree, dt)
        sons.regler_boucle("ambiance", 0.15 if dans_l_air else 0.35, dt)

    def changer_son(self):
        reglages.changer_son()
        self.u.dire(t("son", mode=t("son_" + reglages.SON)), CYAN, 3)

    def basculer_aides(self):
        reglages.basculer_aides()
        if not reglages.AIDES:
            self.u.arreter_pilote()
            self.hud.menu_pilote = False

    def temps_normal(self):
        self.u.accel = 0

    def recentrer(self):
        """Revient sur le vaisseau (animation), en rezoomant s'il n'était plus qu'un point."""
        self.cam.revenir(self.u)

    # ------------------------------------------------- nœud de manœuvre
    def _facteur_reglage(self):
        """Maj = réglage fin (x0.1), Ctrl = réglage rapide (x10)."""
        mods = pygame.key.get_mods()
        if mods & pygame.KMOD_SHIFT:
            return 0.1
        if mods & pygame.KMOD_CTRL:
            return 10.0
        return 1.0

    def poignee_sous_souris(self, pos):
        """Poignée du nœud sous le pointeur : (nom, (x, y), (dx, dy)) ou None."""
        for p in self.cam.poignees:
            if hypot(p[1][0] - pos[0], p[1][1] - pos[1]) < self.tolerance_clic:
                return p
        return None

    def temps_sur_trajectoire(self, pos):
        """Instant correspondant au point de la trajectoire le plus proche du pointeur."""
        meilleur, dmin = None, self.tolerance_clic * 1.5
        for px, py, instant in self.cam.echantillons:
            d = hypot(px - pos[0], py - pos[1])
            if d < dmin:
                dmin, meilleur = d, instant
        return meilleur

    def noeud_par_defaut(self):
        """Touche A : pose un nœud à l'apoapside (ou 2 min plus tard)."""
        u, a = self.u, self.u.actif
        if a is None:
            return
        if a.noeud is not None:
            return u.dire(t("Il y a déjà un nœud de manœuvre (Suppr pour l'effacer)"), ORANGE, 3)
        if a.mode == "pose" or not a.troncons:
            return u.dire(t("Il faut être en vol pour planifier une manœuvre"), ORANGE, 3)
        tr = a.troncons[0]
        instant = u.t + 120.0
        if tr.orbite.elliptique:
            d = tr.orbite.delai_apoapside(u.t)
            if d is not None and u.t + d < tr.t1:
                instant = u.t + d
        if tr.t1 < inf:
            instant = min(instant, u.t + 0.9 * (tr.t1 - u.t))
        u.placer_noeud(instant)
        u.dire(t("Nœud posé : tire les poignées pour régler le Δv"), CYAN, 4)

    def _glisser(self, pos):
        """Déplacement d'une poignée (ou du nœud lui-même) à la souris."""
        nom, (pro0, rad0), depart, direction = self.glisse
        u = self.u
        if nom == "centre":
            instant = self.temps_sur_trajectoire(pos)
            if instant is not None:
                u.regler_noeud(t=instant)
            return
        d = (pos[0] - depart[0]) * direction[0] + (pos[1] - depart[1]) * direction[1]
        k = d * NOEUD_SENSIBILITE * self._facteur_reglage()
        if nom == "pro":
            u.regler_noeud(pro=pro0 + k)
        elif nom == "retro":
            u.regler_noeud(pro=pro0 - k)
        elif nom == "rad+":
            u.regler_noeud(rad=rad0 + k)
        elif nom == "rad-":
            u.regler_noeud(rad=rad0 - k)

    def _molette_noeud(self, pos, sens):
        """Molette sur une poignée : réglage précis du Δv. Renvoie True si consommé."""
        a = self.u.actif
        p = self.poignee_sous_souris(pos)
        if p is None or a is None or a.noeud is None or p[0] == "centre":
            return False
        self._pas_poignee(p[0], sens * NOEUD_PAS_MOLETTE * self._facteur_reglage())
        return True

    def _pas_poignee(self, nom, pas):
        """Pousse le nœud de `pas` m/s dans la direction de la poignée `nom`."""
        n = self.u.actif.noeud
        if nom == "pro":
            self.u.regler_noeud(pro=n.pro + pas)
        elif nom == "retro":
            self.u.regler_noeud(pro=n.pro - pas)
        elif nom == "rad+":
            self.u.regler_noeud(rad=n.rad + pas)
        elif nom == "rad-":
            self.u.regler_noeud(rad=n.rad - pas)

    def sauvegarder(self):
        if self.u.tutoriel:
            self.u.dire(t("Pas de sauvegarde pendant un tutoriel"), ORANGE, 3)
            return
        try:
            sauvegarde.sauvegarder(self.u)
            self.u.dire(t("Partie sauvegardée"), VERT, 3)
        except OSError as e:
            self.u.dire(t("Sauvegarde impossible : {err}", err=e), ROUGE)

    # ------------------------------------------------------------- événements
    # ------------------------------------------------------ écran tactile
    def commandes_tenues(self):
        """Commandes maintenues par un doigt : "gaz", ("rot", ±1), ("rcs", avant, côté)."""
        return {d.prise for d in self.doigts.actifs.values()
                if d.prise == "gaz" or (isinstance(d.prise, tuple) and d.prise[0] in ("rot", "rcs"))}

    def _evenement_tactile(self, ev):
        if ev.type == pygame.KEYDOWN:                 # bouton « retour » d'Android, clavier Bluetooth
            return self._touche(ev)
        if ev.type == pygame.MOUSEWHEEL:              # molette (essais sur PC)
            pos = getattr(ev, "pos", None) or pygame.mouse.get_pos()
            if not self._molette_noeud(pos, ev.y):
                self.cam.zoomer(1.2 ** ev.y)
            return
        r = self.doigts.lire(ev, self.app.ecran.get_size())
        if r is not None:
            geste, doigt = r
            {"appui": self._appui, "glisse": self._glisse, "relache": self._relache}[geste](doigt)

    def _appui(self, d):
        """Un doigt se pose : on retient ce qu'il attrape."""
        u, a = self.u, self.u.actif
        horloge = getattr(self.hud, "rect_temps", None)
        if self.panneau is None and horloge is not None and horloge.collidepoint(d.pos):
            self.appui_horloge = (d.ident, time.monotonic())
        if self.panneau is not None or (u.perdu and a is None):
            for b in self.boutons:
                if b.clic(d.pos):
                    break
            d.prise = "panneau"
            return
        commande = self.hud.zone(d.pos)                # manette des gaz, rotation, RCS
        if commande is not None:
            d.prise = commande
            if commande == "gaz" or commande[0] in ("rot", "rcs"):
                u.arreter_pilote()                     # le joueur reprend la main
            if commande == "gaz" and a is not None:
                a.gaz = self.hud.gaz_depuis(d.pos[1])
            return
        if self.hud.clic(d.pos):                       # boutons (et menu contextuel)
            d.prise = "bouton"
            return
        p = self.poignee_sous_souris(d.pos)            # poignée du nœud de manœuvre
        if p is not None and a is not None and a.noeud is not None and not a.noeud.commencee:
            d.prise = ("poignee", p[0], (a.noeud.pro, a.noeud.rad), p[2])
            return
        d.prise = "monde"
        mondes = self.doigts.tenant("monde")
        if len(mondes) == 2:                           # deuxième doigt sur la vue : pincement
            (x1, y1), (x2, y2) = mondes[0].pos, mondes[1].pos
            self.pince = max(1.0, hypot(x2 - x1, y2 - y1))
            for m in mondes:
                m.bouge = True                         # un pincement n'est jamais une tape

    def _glisse(self, d):
        a = self.u.actif
        if d.prise == "gaz" and a is not None:
            a.gaz = self.hud.gaz_depuis(d.pos[1])
        elif isinstance(d.prise, tuple) and d.prise[0] in ("rot", "rcs"):
            nouvelle = self.hud.zone(d.pos)            # le pouce peut glisser d'un bouton à l'autre
            if nouvelle is not None and nouvelle != "gaz":
                d.prise = nouvelle
        elif isinstance(d.prise, tuple) and d.prise[0] == "poignee" and d.bouge:
            _, nom, valeurs, direction = d.prise
            self.glisse = (nom, valeurs, d.depart, direction)
            self._glisser(d.pos)
        elif d.prise == "monde":
            mondes = self.doigts.tenant("monde")
            if len(mondes) == 2 and self.pince is not None:
                (x1, y1), (x2, y2) = mondes[0].pos, mondes[1].pos
                ecart = max(1.0, hypot(x2 - x1, y2 - y1))
                self.cam.zoomer(ecart / self.pince)
                self.pince = ecart
                for m in mondes:
                    m.pan = m.pos                      # pour repartir sans saut après le pincement
            elif len(mondes) == 1 and d.bouge:         # un seul doigt qui glisse : on déplace la vue
                self.cam.glisser(getattr(d, "pan", d.depart), d.pos)
                d.pan = d.pos

    def _relache(self, d):
        u, a = self.u, self.u.actif
        if isinstance(d.prise, tuple) and d.prise[0] == "poignee":
            self.glisse = None
            if not d.bouge and d.prise[1] != "centre" and a is not None and a.noeud is not None:
                self._pas_poignee(d.prise[1], NOEUD_PAS_MOLETTE)      # simple tape : 1 m/s
        elif d.prise == "monde":
            if len(self.doigts.tenant("monde")) < 2:
                self.pince = None
            if not d.bouge:
                self._tape_monde(d.pos)

    def _tape_monde(self, pos):
        """Tape sur la vue : menu de l'objet touché, sinon nœud de manœuvre sur l'orbite."""
        u, a = self.u, self.u.actif
        obj = objet_sous_souris(u, self.cam, pos, TOLERANCE_DOIGT)
        if obj is not None:
            self.hud.ouvrir_popup(obj, pos)
        elif a is not None and a.noeud is None:
            instant = self.temps_sur_trajectoire(pos)
            if instant is not None:
                u.placer_noeud(instant)
                u.dire(t("Nœud posé : tire les poignées pour régler le Δv"), CYAN, 4)

    # ------------------------------------------------------ clavier et souris
    def evenement(self, ev):
        if self.tactile:
            return self._evenement_tactile(ev)
        u, a = self.u, self.u.actif
        if ev.type == pygame.MOUSEWHEEL:
            pos = getattr(ev, "pos", None) or pygame.mouse.get_pos()
            if not self._molette_noeud(pos, ev.y):
                self.cam.zoomer(1.2 ** ev.y)
        elif ev.type == pygame.MOUSEMOTION:
            if self.glisse is not None:
                self._glisser(ev.pos)
            elif self.panoramique is not None:         # on fait glisser la vue
                self.cam.glisser(self.panoramique, ev.pos)
                self.panoramique = ev.pos
        elif ev.type == pygame.MOUSEBUTTONUP:
            if ev.button == 1:
                self.glisse = None
            self.panoramique = None
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button in (2, 3):
            self.panoramique = ev.pos                  # clic droit (ou molette) : glisser la vue
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if self.panneau is not None or (u.perdu and u.actif is None):
                for b in self.boutons:
                    if b.clic(ev.pos):
                        break
                return
            if self.hud.clic(ev.pos):
                return
            p = self.poignee_sous_souris(ev.pos)        # régler la manœuvre
            if p is not None and a is not None and a.noeud is not None:
                if not a.noeud.commencee:
                    self.glisse = (p[0], (a.noeud.pro, a.noeud.rad), ev.pos, p[2])
                return
            obj = objet_sous_souris(u, self.cam, ev.pos)
            instant = None
            if obj is None and a is not None and a.noeud is None:
                instant = self.temps_sur_trajectoire(ev.pos)
            if obj is not None:
                self.hud.ouvrir_popup(obj, ev.pos)
            elif instant is not None:                   # clic sur l'orbite : nouveau nœud
                u.placer_noeud(instant)
                u.dire(t("Nœud posé : tire les poignées pour régler le Δv"), CYAN, 4)
            else:                                       # clic dans le vide : on fait glisser la vue
                self.panoramique = ev.pos
        elif ev.type == pygame.KEYDOWN:
            self._touche(ev)

    def _touche(self, ev):
        if self.u.pilote is not None and ev.key in (pygame.K_w, pygame.K_x, pygame.K_z, pygame.K_s,
                                                    pygame.K_UP, pygame.K_DOWN, pygame.K_t):
            self.u.arreter_pilote()                    # le joueur reprend la main
        u, a, k = self.u, self.u.actif, ev.key
        if k == pygame.K_ESCAPE:
            self.panneau = None if self.panneau else "pause"
            return
        if k in (pygame.K_m,):
            return self.ouvrir("missions")
        if k in (pygame.K_h, pygame.K_F1):
            return self.ouvrir("aide")
        if self.panneau is not None:
            return
        if k == pygame.K_F5:
            return self.sauvegarder()
        if k == pygame.K_F9:
            if self.u.tutoriel:                      # même garde que la sauvegarde (F5)
                self.u.dire(t("Pas de chargement pendant un tutoriel"), ORANGE, 3)
                return
            return self.app.continuer()
        if k == pygame.K_COMMA:
            return u.changer_acceleration(-1)
        if k in (pygame.K_SEMICOLON, pygame.K_PERIOD):
            return u.changer_acceleration(+1)
        if k in (pygame.K_RETURN, pygame.K_KP_ENTER):
            u.accel = 0
            return
        if k == pygame.K_f:
            self.recentrer()
            return
        if k == pygame.K_F12:                          # raccourci : options et triche
            self.ouvrir("options")
            return
        if k == pygame.K_c:
            return self.changer_camera()
        if k == pygame.K_n:
            u.vaisseau_suivant()
            self.cam.focus = None
            return
        if k == pygame.K_BACKSPACE:
            return u.cibler(None)
        if a is None:
            return
        # chiffres du haut du clavier, repérés par position (marche en AZERTY sans Maj)
        sc = getattr(ev, "scancode", -1)
        modes = ["stab", "pro", "retro", "rad+", "rad-", "cible", "anti", "manoeuvre"]
        if pygame.KSCAN_1 <= sc <= pygame.KSCAN_1 + 7:
            mode = modes[sc - pygame.KSCAN_1]
            if mode != "manoeuvre" or a.noeud is not None:
                u.arreter_pilote()                   # comme les boutons SAS à l'écran
                a.sas = mode
        elif k == pygame.K_SPACE:
            u.separer_etage()
        elif k == pygame.K_t:
            a.sas = "off" if a.sas != "off" else "stab"
        elif k == pygame.K_r:
            self.basculer_rcs()
        elif k == pygame.K_p:
            u.ouvrir_parachute()
        elif k == pygame.K_b:
            u.planter_drapeau()
        elif k == pygame.K_u:
            u.desamarrer()
        elif k == pygame.K_v:
            self.changer_reference()
        elif k == pygame.K_x:
            a.gaz = 0.0
        elif k == pygame.K_w:
            a.gaz = 1.0
        elif k == pygame.K_a:
            self.noeud_par_defaut()
        elif k == pygame.K_g and reglages.AIDES:
            self.hud.basculer_menu_pilote()
        elif k == pygame.K_DELETE:
            u.supprimer_noeud()

    # ------------------------------------------------------------ mise à jour
    def maj(self, dt):
        self._sons(dt)
        self.app.historique.enregistrer(self.u, time.monotonic())    # pour « revenir en arrière »
        if self.appui_horloge is not None:           # appui long sur l'horloge : menu secret
            ident, debut = self.appui_horloge
            d = self.doigts.actifs.get(ident)
            if self.panneau is not None or d is None or d.bouge:
                self.appui_horloge = None            # un panneau s'est ouvert, ou le doigt a bougé
            elif time.monotonic() - debut >= triche.APPUI_LONG:
                self.appui_horloge = None
                self.panneau = "options"
        if self.app.tuto is not None:
            self.app.tuto.maj(self)
        u = self.u
        self.temps_reel += dt
        touches = pygame.key.get_pressed()
        cmd = u.commandes
        cmd.rotation = cmd.avant = cmd.cote = 0
        a = u.actif
        if self.panneau is None and a is not None:
            gauche = touches[pygame.K_LEFT] or touches[pygame.K_q]
            droite = touches[pygame.K_RIGHT] or touches[pygame.K_d]
            cmd.rotation = int(bool(gauche)) - int(bool(droite))
            if cmd.rotation and u.pilote is not None:
                u.arreter_pilote()
            if touches[pygame.K_UP] or touches[pygame.K_z]:
                a.gaz = min(1.0, a.gaz + 0.9 * dt)
            if touches[pygame.K_DOWN] or touches[pygame.K_s]:
                a.gaz = max(0.0, a.gaz - 0.9 * dt)
            if a.rcs:
                cmd.avant = int(bool(touches[pygame.K_i])) - int(bool(touches[pygame.K_k]))
                cmd.cote = int(bool(touches[pygame.K_l])) - int(bool(touches[pygame.K_j]))
                if (cmd.avant or cmd.cote) and u.pilote is not None:
                    u.arreter_pilote()                 # le joueur reprend la main
            if self.tactile:                          # doigts posés sur les commandes à l'écran
                for c in self.commandes_tenues():
                    if c[0] == "rot":
                        cmd.rotation += c[1]
                    elif c[0] == "rcs" and a.rcs:
                        cmd.avant += c[1]
                        cmd.cote += c[2]
                cmd.rotation = max(-1, min(1, cmd.rotation))
                cmd.avant = max(-1, min(1, cmd.avant))
                cmd.cote = max(-1, min(1, cmd.cote))
        if touches[pygame.K_PAGEUP]:
            self.cam.zoomer(1.0 + 1.5 * dt)
        if touches[pygame.K_PAGEDOWN]:
            self.cam.zoomer(1.0 / (1.0 + 1.5 * dt))
        if self.panneau is None:
            u.avancer(dt)
        self.cam.suivre(u, dt)

    # ----------------------------------------------------------------- dessin
    def dessiner(self, surf):
        l, h = surf.get_size()
        self.cam.taille(l, h)
        dessiner_monde(surf, self.u, self.cam, self.temps_reel)
        while self.u.photos_demandees:           # photo APRÈS le monde, AVANT le HUD
            genre, corps = self.u.photos_demandees.pop(0)
            album.prendre(surf, genre, corps)
        self.hud.dessiner(surf, self.u, self.cam)
        self.boutons = []
        if self.panneau == "missions":
            self._panneau_missions(surf, l, h)
        elif self.panneau == "aide":
            self._panneau_aide(surf, l, h)
        elif self.panneau == "pause":
            self._panneau_pause(surf, l, h)
        elif self.panneau == "carburant":
            self._panneau_carburant(surf, l, h)
        elif self.panneau == "options":
            self._panneau_options(surf, l, h)
        elif self.u.perdu and self.u.actif is None and self.app.tuto is None:
            self._panneau_perdu(surf, l, h)
        if self.app.tuto is not None and self.panneau is None:     # bulle du tutoriel
            perdu = self.u.perdu and self.u.actif is None
            # après un crash, l'écran n'écoute plus que ses propres boutons : « Réessayer » y va
            self.app.tuto.dessiner(surf, self, self.boutons if perdu else self.hud.boutons,
                                   self.hud.boutons + self.hud.boutons_popup)
        souris = pygame.mouse.get_pos()
        for b in self.boutons:
            b.dessiner(surf, souris)

    def _panneau_missions(self, surf, l, h):
        if h < 80 + 27 * len(MISSIONS) + 40:
            return self._panneau_missions_2_colonnes(surf, l, h)
        u = self.u
        larg, haut = 760, min(h - 40, 80 + 27 * len(MISSIONS))
        x, y = (l - larg) // 2, (h - haut) // 2
        panneau(surf, (x, y, larg, haut), alpha=240)
        texte(surf, t("MISSIONS"), (x + 20, y + 14), 20, BLANC, gras=True)
        texte(surf, t("{fait} / {total} accomplies", fait=len(u.missions_faites), total=len(MISSIONS)),
              (x + larg - 20, y + 18), 14, GRIS, ancre="hd")
        yy = y + 50
        for m in MISSIONS:
            if yy > y + haut - 30:
                break
            fait = m.ident in u.missions_faites
            if fait:                                   # coche dessinée (pas besoin de police spéciale)
                pygame.draw.lines(surf, VERT, False, [(x + 22, yy + 10), (x + 27, yy + 15), (x + 36, yy + 4)], 2)
            else:
                pygame.draw.circle(surf, GRIS, (x + 29, yy + 10), 2)
            texte(surf, t(m.titre), (x + 44, yy), 15, VERT if fait else BLANC, gras=not fait)
            texte(surf, t(m.description), (x + 230, yy + 1), 13, GRIS)
            if not u.bac_a_sable:
                texte(surf, fmt_nombre(m.prime), (x + larg - 20, yy), 14, JAUNE, ancre="hd")
            yy += 27
        self.boutons = [Bouton((x + larg - 130, y + haut - 38, 110, 28), t("Fermer"), lambda: self.ouvrir("missions"))]

    def _panneau_missions_2_colonnes(self, surf, l, h):
        """Liste des missions sur deux colonnes : titre, puis description en petit."""
        u = self.u
        larg, haut = min(l - 20, 1100), h - 20
        x, y = (l - larg) // 2, 10
        panneau(surf, (x, y, larg, haut), alpha=245)
        texte(surf, t("MISSIONS"), (x + 20, y + 12), 20, BLANC, gras=True)
        texte(surf, t("{fait} / {total} accomplies", fait=len(u.missions_faites), total=len(MISSIONS)),
              (x + 160, y + 17), 14, GRIS)
        moitie = (len(MISSIONS) + 1) // 2
        col_l = (larg - 40) // 2
        pas = (haut - 110) // moitie
        for k, m in enumerate(MISSIONS):
            xx = x + 20 + (k // moitie) * (col_l + 10)
            yy = y + 50 + (k % moitie) * pas
            fait = m.ident in u.missions_faites
            if fait:
                pygame.draw.lines(surf, VERT, False, [(xx + 2, yy + 9), (xx + 7, yy + 14), (xx + 16, yy + 3)], 2)
            else:
                pygame.draw.circle(surf, GRIS, (xx + 9, yy + 9), 2)
            texte(surf, t(m.titre), (xx + 24, yy), 15, VERT if fait else BLANC, gras=not fait)
            if not u.bac_a_sable:
                texte(surf, fmt_nombre(m.prime), (xx + col_l - 10, yy), 13, JAUNE, ancre="hd")
            desc = t(m.description)
            if len(desc) > 62:
                desc = desc[:60] + "…"
            texte(surf, desc, (xx + 24, yy + 18), 12, GRIS)
        self.boutons = [Bouton((x + larg - 150, y + haut - 54, 130, 44), t("Fermer"),
                               lambda: self.ouvrir("missions"), 17)]

    def _panneau_aide(self, surf, l, h):
        if self.tactile:
            return self._panneau_aide_tactile(surf, l, h)
        larg, haut = 860, 520
        x, y = (l - larg) // 2, (h - haut) // 2
        panneau(surf, (x, y, larg, haut), alpha=240)
        texte(surf, t("AIDE"), (x + 20, y + 14), 20, BLANC, gras=True)
        for col, (titre, lignes) in enumerate(aide()):
            xx, yy = x + 20 + col * 420, y + 52
            texte(surf, titre, (xx, yy), 14, CYAN, gras=True)
            yy += 26
            for touche, role in lignes:
                texte(surf, touche, (xx, yy), 14, JAUNE)
                texte(surf, role, (xx + 190, yy), 14, BLANC)
                yy += 24
        texte_multiligne(surf, conseils(), (x + 20, y + 350), larg - 40, 14, GRIS)
        texte(surf, t("Échelle 1/100 : vitesses et durées ÷ 10. Le temps accéléré (> x4) exige moteurs coupés, hors atmosphère."),
              (x + 20, y + haut - 66), 13, ORANGE)
        self.boutons = [Bouton((x + larg - 130, y + haut - 38, 110, 28), t("Fermer"), lambda: self.ouvrir("aide"))]

    def _panneau_aide_tactile(self, surf, l, h):
        larg, haut = min(l - 20, 1000), h - 20
        x, y = (l - larg) // 2, 10
        panneau(surf, (x, y, larg, haut), alpha=245)
        texte(surf, t("AIDE"), (x + 20, y + 12), 20, BLANC, gras=True)
        col_l = (larg - 40) // 2
        for col, (titre, lignes) in enumerate(aide_tactile()):
            xx, yy = x + 20 + col * (col_l + 10), y + 48
            texte(surf, titre, (xx, yy), 14, CYAN, gras=True)
            yy += 24
            for geste, role in lignes:
                texte(surf, geste, (xx, yy), 14, JAUNE)
                texte(surf, role, (xx, yy + 17), 13, BLANC)
                yy += 40
        texte_multiligne(surf, conseils_tactile(), (x + 20, y + haut - 128), larg - 190, 13, GRIS, interligne=2)
        self.boutons = [Bouton((x + larg - 150, y + haut - 54, 130, 44), t("Fermer"),
                               lambda: self.ouvrir("aide"), 17)]

    def _menu_boutons(self, surf, titre, sous_titre, entrees, l, h, couleur=BLANC):
        if self.tactile:                          # gros boutons, sur deux colonnes si besoin
            colonnes = 1 if len(entrees) <= 4 else 2
            par_col = (len(entrees) + colonnes - 1) // colonnes
            larg_b, haut_b, pas = 300, 46, 54
            larg = colonnes * larg_b + (colonnes - 1) * 16 + 60
            haut = 96 + pas * par_col
            x, y = (l - larg) // 2, (h - haut) // 2
            panneau(surf, (x, y, larg, haut), alpha=245)
            texte(surf, titre, (l // 2, y + 16), 22, couleur, gras=True, ancre="hc")
            texte(surf, sous_titre, (l // 2, y + 50), 14, GRIS, ancre="hc")
            self.boutons = [Bouton((x + 30 + (k // par_col) * (larg_b + 16), y + 80 + pas * (k % par_col),
                                    larg_b, haut_b), lib, act, 18, actif=ok)
                            for k, (lib, act, ok) in enumerate(entrees)]
            return
        larg, haut = 360, 90 + 40 * len(entrees)
        x, y = (l - larg) // 2, (h - haut) // 2
        panneau(surf, (x, y, larg, haut), alpha=240)
        texte(surf, titre, (l // 2, y + 16), 20, couleur, gras=True, ancre="hc")
        texte(surf, sous_titre, (l // 2, y + 46), 13, GRIS, ancre="hc")
        self.boutons = [Bouton((x + 30, y + 74 + 40 * k, larg - 60, 32), lib, act, actif=ok)
                        for k, (lib, act, ok) in enumerate(entrees)]

    # ------------------------------------------------------------- triche
    def revenir_en_arriere(self):
        """Recharge la photo de la partie prise environ 30 s plus tôt."""
        app, u = self.app, self.u
        nouveau = app.historique.revenir(u)
        if nouveau is None:
            u.dire(t("Rien à rembobiner pour l'instant"), ORANGE, 3)
            return
        recul = u.t - nouveau.t
        nouveau.tutoriel = getattr(u, "tutoriel", None)
        app.univers = nouveau
        if app.tuto is not None:
            app.tuto.echec = False                  # le crash n'a jamais eu lieu
        app.aller_vol()
        nouveau.dire(t("Retour de {n} s en arrière", n=round(recul)), CYAN, 4)

    def basculer_triche(self, option):
        u = self.u
        u.triche[option] = not u.triche.get(option)
        noms = {"carburant": t("Carburant infini"), "indestructible": t("Indestructible")}
        etat = t("oui") if u.triche[option] else t("non")
        u.dire(t("{nom} : {etat}", nom=noms[option], etat=etat), CYAN, 3)

    def _triche_plein(self):
        triche.faire_le_plein(self.u.actif)
        self.u.dire(t("Plein fait !"), CYAN, 3)

    def _triche_orbite(self):
        triche.mettre_en_orbite(self.u, self.u.actif)
        self.panneau = None
        self.u.dire(t("Te voilà en orbite"), CYAN, 3)

    def _triche_fonds(self):
        self.u.fonds += triche.FONDS
        self.u.dire(t("+{montant} de fonds", montant=fmt_nombre(triche.FONDS)), CYAN, 3)

    def _triche_pieces(self):
        self.u.triche["pieces"] = True
        self.u.dire(t("Toutes les pièces sont débloquées"), CYAN, 3)

    def _panneau_options(self, surf, l, h):
        """Options en vol : réglages à gauche, triche à droite (si elle est autorisée)."""
        u, a = self.u, self.u.actif
        oui = lambda x: t("oui") if x else t("non")
        carriere = not u.bac_a_sable
        regl = [(t("son", mode=t("son_" + reglages.SON)), self.changer_son, True),
                (t("aides_pilotage", etat=oui(reglages.AIDES)), self.basculer_aides, True)]
        tri = []
        if reglages.TRICHE:
            tri = [(t("Revenir 30 s en arrière"), self.revenir_en_arriere, bool(self.app.historique.photos)),
                   (t("Faire le plein"), self._triche_plein, a is not None),
                   (t("Carburant infini : {etat}", etat=oui(u.triche.get("carburant"))),
                    lambda: self.basculer_triche("carburant"), True),
                   (t("Indestructible : {etat}", etat=oui(u.triche.get("indestructible"))),
                    lambda: self.basculer_triche("indestructible"), True),
                   (t("Mettre en orbite"), self._triche_orbite, a is not None),
                   (t("+{montant} de fonds", montant=fmt_nombre(triche.FONDS)), self._triche_fonds, carriere),
                   (t("Tout débloquer"), self._triche_pieces, carriere and not u.triche.get("pieces"))]
        tactile = self.tactile
        lb, hb, pas, taille = (300, 44, 50, 17) if tactile else (240, 30, 38, 14)
        colonnes = 2 if tri else 1
        rangs = max(len(regl) + 1, len(tri))              # +1 : « Fermer » en bas des réglages
        larg = colonnes * lb + (colonnes - 1) * 24 + 60
        haut = 104 + pas * rangs
        x, y = (l - larg) // 2, max(4, (h - haut) // 2)
        panneau(surf, (x, y, larg, haut), alpha=245)
        texte(surf, t("options_titre"), (l // 2, y + 14), 22 if tactile else 20, BLANC, gras=True, ancre="hc")
        sous = t("Appui long sur l'horloge : ouvre ce menu") if tactile else t("F12 : ouvre ce menu")
        texte(surf, sous, (l // 2, y + 44), 13, GRIS, ancre="hc")
        self.boutons = []
        for c, (titre, entrees, coul) in enumerate(((t("RÉGLAGES"), regl, CYAN), (t("TRICHE"), tri, ORANGE))):
            if not entrees:
                continue
            cx = x + 30 + c * (lb + 24)
            texte(surf, titre, (cx, y + 70), 14, coul, gras=True)
            for k, (lib, act, ok) in enumerate(entrees):
                self.boutons.append(Bouton((cx, y + 92 + pas * k, lb, hb), lib, act, taille, actif=ok))
        self.boutons.append(Bouton((x + 30, y + 92 + pas * (rangs - 1), lb, hb), t("Fermer"),
                                   lambda: self.ouvrir("options"), taille))

    def remplir_section(self, k):
        from .vaisseau import nom_section
        a = self.u.actif
        sections = a.sections_reservoirs()
        carb, mono = a.remplir(k)
        nom = nom_section(sections[k])
        if carb + mono < 0.5:
            self.u.dire(t("Rien à transférer vers {nom} (plein, ou le reste est vide)", nom=nom), ORANGE, 4)
        else:
            self.u.dire(t("Transfert vers {nom} : {carb} de carburant, {mono} de monergol", nom=nom,
                          carb=fmt_masse(carb), mono=fmt_masse(mono)), VERT, 5)

    def _panneau_carburant(self, surf, l, h):
        """Transfert de carburant entre les parties du vaisseau (vaisseaux amarrés, étages)."""
        from .vaisseau import nom_section
        a = self.u.actif
        sections = a.sections_reservoirs() if a is not None else []
        if len(sections) < 2:
            self.panneau = None
            return
        tactile = self.tactile
        hl = 66 if tactile else 56
        n = max(1, min(len(sections), (h - 150) // hl))
        larg = min(640, l - 40)
        haut = 84 + hl * n + (62 if tactile else 50)
        x, y = (l - larg) // 2, max(8, (h - haut) // 2)
        panneau(surf, (x, y, larg, haut), alpha=245)
        texte(surf, t("TRANSFERT DE CARBURANT"), (x + 16, y + 14), 18, BLANC, gras=True)
        texte(surf, t("« Remplir » puise le carburant et le monergol dans toutes les autres parties."),
              (x + 16, y + 44), 13, GRIS)
        yy = y + 74
        lb = 110 if tactile else 96
        lj = larg - 48 - lb
        for k, sec in enumerate(sections[:n]):
            carb, cap = sum(p.carburant for p in sec), sum(p.m.carburant for p in sec)
            mono, capm = sum(p.mono for p in sec), sum(p.m.mono for p in sec)
            texte(surf, nom_section(sec), (x + 16, yy), 14, BLANC, gras=True)
            for j, (val, maxi, coul, nom) in enumerate(((carb, cap, VERT, t("Carburant")), (mono, capm, CYAN, t("Monergol")))):
                if maxi <= 0:
                    continue
                by = yy + 22 + j * 16
                pygame.draw.rect(surf, (40, 46, 60), (x + 16, by + 4, lj // 2, 7), border_radius=3)
                pygame.draw.rect(surf, coul, (x + 16, by + 4, int(lj // 2 * val / maxi), 7), border_radius=3)
                texte(surf, t("{nom} {val} / {maxi}", nom=nom, val=fmt_masse(val), maxi=fmt_masse(maxi)), (x + 24 + lj // 2, by), 12, GRIS)
            plein = carb >= cap - 0.5 and mono >= capm - 0.5
            self.boutons.append(Bouton((x + larg - 16 - lb, yy + 2, lb, hl - 16), t("Remplir"),
                                       lambda k=k: self.remplir_section(k), 16 if tactile else 14, actif=not plein))
            yy += hl
        self.boutons.append(Bouton((x + larg // 2 - 70, y + haut - (54 if tactile else 42), 140, 44 if tactile else 32),
                                   t("Fermer"), lambda: self.ouvrir("carburant"), 16 if tactile else 14))

    def _panneau_pause(self, surf, l, h):
        app, u = self.app, self.u
        if self.tactile:                          # pas de touches M / H / F9 sur un téléphone
            return self._menu_boutons(surf, t("PAUSE"), t("La simulation est arrêtée"), [
                (t("Reprendre"), lambda: self.ouvrir("pause"), True),
                (t("Missions"), lambda: self.ouvrir("missions"), True),
                (t("Aide"), lambda: self.ouvrir("aide"), True),
                (t("Sauvegarder"), self.sauvegarder, True),
                (t("Transfert de carburant"), lambda: self.ouvrir("carburant"),
                 u.actif is not None and len(u.actif.sections_reservoirs()) >= 2),
                (t("Options"), lambda: self.ouvrir("options"), True),
                (t("Hangar (nouveau vaisseau)"), app.aller_hangar, True),
                (t("Revenir au lancement"), app.revenir_au_lancement, u.instantane is not None),
                (t("Menu principal"), app.aller_menu, True),
                (t("Quitter le jeu"), app.quitter, True)], l, h)
        self._menu_boutons(surf, t("PAUSE"), t("La simulation est arrêtée"), [
            (t("Reprendre"), lambda: self.ouvrir("pause"), True),
            (t("Hangar (nouveau vaisseau)"), app.aller_hangar, True),
            (t("Revenir au lancement"), app.revenir_au_lancement, u.instantane is not None),
            (t("Sauvegarder (F5)"), self.sauvegarder, True),
            (t("Transfert de carburant"), lambda: self.ouvrir("carburant"),
             u.actif is not None and len(u.actif.sections_reservoirs()) >= 2),
            (t("Options"), lambda: self.ouvrir("options"), True),
            (t("Menu principal"), app.aller_menu, True),
            (t("Quitter le jeu"), app.quitter, True)], l, h)

    def _panneau_perdu(self, surf, l, h):
        app, u = self.app, self.u

        def suivant():
            u.vaisseau_suivant()
            self.cam.focus = None

        self._menu_boutons(surf, t("VAISSEAU PERDU"), t("Ça arrive aux meilleurs."), [
            (t("Revenir au lancement"), app.revenir_au_lancement, u.instantane is not None),
            (t("Retour au hangar"), app.aller_hangar, True),
            (t("Contrôler un autre vaisseau"), suivant, any(v.controlable() for v in u.vaisseaux))], l, h, ROUGE)
