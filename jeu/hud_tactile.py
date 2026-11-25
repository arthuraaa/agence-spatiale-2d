# -*- coding: utf-8 -*-
"""
Affichage tête haute pour écran tactile (téléphone, tablette).

Même contenu que le HUD du PC, rangé pour les pouces :
    à gauche : la manette des gaz (on pose le doigt et on glisse de haut en bas) ;
    à droite : rotation (à maintenir), étage, parachute, désamarrage, RCS... ;
    en bas   : les modes du SAS, avec le cadran juste au-dessus ;
    en haut  : infos de vol, accélération du temps, menu, cible.

Les commandes qu'on MAINTIENT (gaz, rotation, translation RCS) ne sont pas des
boutons : la scène demande à zone() ce qu'il y a sous chaque doigt, puis agit tant
que le doigt reste posé. Les autres sont des Bouton ordinaires, déclenchés à l'appui.
Toutes les tailles sont en pixels « logiques » : l'écran fait 540 px de haut.
"""
from math import hypot
import pygame
from .constantes import (ACCELERATIONS, BLANC, GRIS, GRIS_FONCE, CYAN, ORANGE, VERT, JAUNE,
                         BLEU_PLAN, BORD_PANNEAU)
from .hud import Hud, infos_noeud, lignes_cible, lignes_amarrage
from . import pilote as mod_pilote
from . import reglages
from .interface import texte, panneau, Bouton, fmt_distance, fmt_vitesse, fmt_date, fmt_nombre
from .missions import mission_suggeree
from .textes import t
from .plateforme import MARGE_BORD as MX
from .vaisseau import indice_decoupleur_bas, statistiques_etages

M = 12                 # marge en haut et en bas de l'écran
L_GAZ = 64             # largeur de la manette des gaz
L_COLONNE = 190        # largeur de la colonne de boutons de droite
L_PANNEAU = 250        # largeur des panneaux d'information
H_INFOS = 192          # hauteur du panneau de vol (en haut à gauche)
H_SAS, PAS_SAS = 46, 62
R_CADRAN = 40
SAS = [("off", "OFF"), ("stab", "STAB"), ("pro", "PRO"), ("retro", "RÉTRO"), ("rad+", "RAD+"),
       ("rad-", "RAD−"), ("cible", "CIBLE"), ("anti", "ANTI"), ("manoeuvre", "MAN")]
LIBELLES_REF = {"surface": "Surf.", "orbite": "Orb.", "cible": "Cible"}   # clés -> textes
LIBELLES_CAM = {"auto": "Auto", "horizon": "Horiz.", "nord": "Nord"}


class HudTactile(Hud):
    POPUP = dict(largeur=250, h_bouton=44, pas=50, police=17)

    def __init__(self, scene):
        super().__init__(scene)
        self.maintenus = []                   # [(rect, commande, symbole)]
        self.rect_gaz = pygame.Rect(0, 0, 0, 0)
        self.rect_temps = pygame.Rect(0, 0, 0, 0)
        self.cadran = None                    # (cx, cy) ou None s'il n'y a pas la place
        self.noeud_visible = False
        self.y_haut_sas = 0
        self.rect_croix = None                # zone de la croix RCS (elle a priorité sur les panneaux)
        self.sas_etendu = False               # « … » déplie les modes SAS moins utilisés
        self.contexte_etendu = False          # « … » déplie les actions rares de la colonne

    # ------------------------------------------------------------ doigts
    def derouler_sas(self):
        """Le bouton « … » déplie les modes SAS moins utilisés (RAD+, RAD−, CIBLE, ANTI, MAN)."""
        self.sas_etendu = not self.sas_etendu

    def derouler_contexte(self):
        """Le bouton « … » déplie les actions rares (Récupérer, Désamarrer, Carburant, Drapeau)."""
        self.contexte_etendu = not self.contexte_etendu

    def zone(self, pos):
        """Commande à maintenir sous le doigt : "gaz", ("rot", ±1), ("rcs", avant, côté) ou None."""
        for rect, commande, _ in self.maintenus:
            if rect.collidepoint(pos):
                return commande
        return None

    def gaz_depuis(self, y):
        """Hauteur du doigt sur la manette -> gaz entre 0 et 1 (les bouts sont « collants »)."""
        r = self.rect_gaz
        bas, haut = r.bottom - 12, r.y + 46
        f = (bas - y) / max(1.0, bas - haut)
        return 0.0 if f < 0.04 else 1.0 if f > 0.96 else f

    # ----------------------------------------------------------- disposition
    def _construire_boutons(self, u, l, h):
        sc, a = self.scene, u.actif
        b, maintenus = [], []
        # en haut à droite : menu, et un bouton « Vaisseau » bien lisible (pas un symbole)
        # quand la vue s'est perdue ailleurs
        b.append(Bouton((l - MX - 56, M, 56, 44), "☰", lambda: sc.ouvrir("pause"), 24))
        hors = sc.cam.hors_vaisseau(u)
        x_droite = l - MX - 62
        if hors:                                        # revenir (et rezoomer) sur la fusée
            b.append(Bouton((x_droite - 104, M, 104, 44), t("Vaisseau"), sc.recentrer, 16))
            x_droite -= 110
        x_pilote = x_droite
        if reglages.AIDES and a is not None:                 # pilote automatique
            b.append(Bouton((x_pilote - 96, M, 96, 44), t("Pilote"), self.basculer_menu_pilote, 16,
                            allume=u.pilote is not None or self.menu_pilote))
            self.ancre_pilote = (x_pilote, M)
        # en haut au centre : accélération du temps (la case du milieu remet le temps à x1) ;
        # sur écran étroit, décalée à droite pour ne pas couvrir le panneau de vol, et
        # compacte (44/92/44) si « Vaisseau » et « Pilote » lui laissent moins de la place
        gauche_panneau = MX + L_PANNEAU + 4
        droite_boutons = (x_pilote - 96) if (reglages.AIDES and a is not None) else \
            (x_droite if hors else l - MX - 56)
        if l // 2 + 124 <= droite_boutons - 4:
            xc = max(l // 2, gauche_panneau + 124)
            b.append(Bouton((xc - 124, M, 52, 44), "◀", lambda: u.changer_acceleration(-1), 20))
            b.append(Bouton((xc + 72, M, 52, 44), "▶", lambda: u.changer_acceleration(+1), 20))
            self.rect_temps = pygame.Rect(xc - 66, M, 132, 44)
        else:
            xc = gauche_panneau + 92
            b.append(Bouton((xc - 92, M, 44, 44), "◀", lambda: u.changer_acceleration(-1), 20))
            b.append(Bouton((xc + 48, M, 44, 44), "▶", lambda: u.changer_acceleration(+1), 20))
            self.rect_temps = pygame.Rect(xc - 46, M, 92, 44)
        b.append(Bouton(self.rect_temps, "", sc.temps_normal))
        self.cadran = None
        if a is None:
            self.boutons, self.maintenus = b, maintenus
            return
        # ---- colonne de droite, de bas en haut
        x0 = l - MX - L_COLONNE
        y = h - M - 84
        maintenus.append((pygame.Rect(x0, y, 92, 84), ("rot", 1), "⟲"))
        maintenus.append((pygame.Rect(x0 + 98, y, 92, 84), ("rot", -1), "⟳"))
        y -= 8 + 56
        if indice_decoupleur_bas(a.pieces):          # la place reste réservée : rien ne bouge
            b.append(Bouton((x0, y, L_COLONNE, 56), t("ÉTAGE"), u.separer_etage, 20))
        # Le parachute reste visible (décision urgentée) ; les actions plus rares se
        # déplient via « … », comme les modes SAS, pour ne pas encombrer la colonne.
        if any(p.parachute == "plie" for p in a.pieces) and a.corps.atm_h > 0 and a.mode != "pose":
            y -= 6 + 44
            b.append(Bouton((x0, y, L_COLONNE, 44), t("Parachute"), u.ouvrir_parachute, 17))
        rare = []
        if u.peut_recuperer(a):
            rare.append((t("Récupérer"), sc.recuperer))
        if a.jonctions():
            rare.append((t("Désamarrer"), u.desamarrer))
            rare.append((t("Carburant"), lambda: sc.ouvrir("carburant")))
        if a.mode == "pose" and not a.corps.gazeux:
            rare.append((t("Drapeau"), u.planter_drapeau))
        if rare:
            y -= 6 + 44
            b.append(Bouton((x0, y, L_COLONNE, 44), "…", self.derouler_contexte, 18,
                            allume=self.contexte_etendu))
            if self.contexte_etendu:
                for lib, act in rare:
                    y -= 6 + 44
                    b.append(Bouton((x0, y, L_COLONNE, 44), lib, act, 17))
        y -= 8 + 40
        b.append(Bouton((x0, y, L_COLONNE, 40), t("RCS"), sc.basculer_rcs, 14, allume=a.rcs))
        # ---- manette des gaz, à gauche sous le panneau de vol
        self.rect_gaz = pygame.Rect(MX, M + H_INFOS + 12, L_GAZ, h - 2 * M - H_INFOS - 12)
        maintenus.append((self.rect_gaz, "gaz", ""))
        # ---- SAS en bas, entre la manette et la colonne de droite ; cadran au-dessus.
        # Allégé : OFF STAB PRO RÉTRO sont toujours là, les modes plus rares (RAD+, RAD−,
        # CIBLE, ANTI, MAN) se déplient via « … » pour ne pas encombrer le bas de l'écran.
        gauche, droite = MX + L_GAZ + 14, x0 - 14
        base, extra = SAS[:4], SAS[4:]
        # le mode SAS courant doit toujours rester visible, même rangée rare
        montre_extra = self.sas_etendu or a.sas in [m for m, _ in extra]
        rangs = ([extra] if montre_extra else []) + [base]
        larg = max(len(r) for r in rangs) * PAS_SAS - 6
        xs = gauche + (droite - gauche - larg) // 2
        for r, rang in enumerate(rangs):
            ys = h - M - H_SAS - (len(rangs) - 1 - r) * (H_SAS + 6)
            for k, (mode, lib) in enumerate(rang):
                def choisir(m=mode):
                    u.arreter_pilote()
                    a.sas = m
                b.append(Bouton((xs + k * PAS_SAS, ys, PAS_SAS - 6, H_SAS), lib, choisir, 14,
                                actif=(mode != "manoeuvre" or a.noeud is not None),
                                allume=(a.sas == mode)))
            if r == len(rangs) - 1:                    # « … » sur la rangée du bas : déplie/replie
                b.append(Bouton((xs + len(rang) * PAS_SAS, ys, PAS_SAS - 6, H_SAS), "…",
                                self.derouler_sas, 18, allume=montre_extra))
        self.y_haut_sas = h - M - H_SAS - (len(rangs) - 1) * (H_SAS + 6)
        if larg >= 2 * R_CADRAN + 20:
            self.cadran = (xs + larg // 2, self.y_haut_sas - R_CADRAN - 14)
        # ---- croix de translation RCS (seulement quand le RCS est allumé)
        self.rect_croix = None
        if a.rcs:                          # une manette ronde au lieu des quatre flèches
            cx, cy = x0 - 110, h - 230
            self.rect_croix = pygame.Rect(cx - 95, cy - 95, 190, 190)
            maintenus.append((self.rect_croix, ("rcs_joy", cx, cy), "⊕"))
        # ---- boutons du panneau de manœuvre (sur écran étroit, la croix RCS a la priorité)
        self.noeud_visible = a.noeud is not None and not (a.rcs and l < 900)
        obstacles = [rect for rect, commande, _ in maintenus if commande != "gaz"]
        if self.noeud_visible:
            nx, ny, haut, _ = self._geometrie_noeud(u, a, l)
            obstacles.append(pygame.Rect(nx, ny, L_PANNEAU, haut))
        if self.cadran is not None:
            zone = pygame.Rect(0, 0, 2 * R_CADRAN + 14, 2 * R_CADRAN + 14)
            zone.center = self.cadran
            if zone.collidelist(obstacles) >= 0:
                self.cadran = None                     # pas la place : le cadran s'efface
        if self.noeud_visible:
            nx, ny, haut, _ = self._geometrie_noeud(u, a, l)
            xb, yb = nx + 8, ny + haut - 50
            for larg_b, lib, act in ((54, t("− tour"), lambda: u.decaler_noeud(-1)),
                                     (54, t("+ tour"), lambda: u.decaler_noeud(+1)),
                                     (64, t("Exécuter") if reglages.AIDES else t("Filer"),
                                      (lambda: u.lancer_pilote(mod_pilote.ExecuterNoeud()))
                                      if reglages.AIDES else u.filer_au_noeud),
                                     (44, "✕", u.supprimer_noeud)):
                b.append(Bouton((xb, yb, larg_b, 44), lib, act, 15))
                xb += larg_b + 6
        self.boutons, self.maintenus = b, maintenus

    def _geometrie_noeud(self, u, a, l):
        """Position, hauteur et lignes du panneau de manœuvre (à droite de la manette)."""
        lignes, _ = infos_noeud(u, a)
        longue = any(nom == t("Combustion longue") for nom, _, _ in lignes)
        propres = []
        for nom, val, coul in lignes:
            if nom in (t("Nœud"), t("Combustion longue")):
                continue
            if nom == t("Combustion") and longue:
                coul = ORANGE                              # combustion longue : valeur en orange
            propres.append((nom.strip(), val, coul))
        propres = propres[:8 if l >= 900 else 5]
        return MX + L_GAZ + 12, M + H_INFOS + 12, 46 + 20 * len(propres) + 54, propres

    # ----------------------------------------------------------------- dessin
    def dessiner(self, surf, u, cam):
        l, h = surf.get_size()
        self._construire_boutons(u, l, h)
        a = u.actif
        souris = (-100, -100)                              # pas de survol sur un écran tactile
        if a is not None:
            self._infos(surf, u, a)
            self._gaz(surf, a)
            if self.noeud_visible:
                self._noeud_tactile(surf, u, a, l)
            elif reglages.AIDES:
                x_at, larg_at = MX + L_GAZ + 12, L_PANNEAU
                if self.rect_croix is not None:            # sur écran étroit, la croix RCS gagne
                    larg_at = min(larg_at, self.rect_croix.left - x_at - 8)
                self._atterrissage(surf, u, a, (x_at, M + H_INFOS + 12, larg_at), amarrage=False)
            if self.cadran is not None:
                self._cadran(surf, u, cam, a, self.cadran[0], self.cadran[1], R=R_CADRAN, legende=False)
        m = None if u.tutoriel else mission_suggeree(u)       # pas d'objectif pendant un tutoriel
        if m is not None:
            texte(surf, t("Objectif : ") + t(m.titre), (l // 2, M + 50), 13, JAUNE, ancre="hc")
        self._messages(surf, u, l, y0=M + 70 + self.decalage_tuto(), taille=15, pas=20,
                       largeur=max(300, l - 2 * (MX + L_PANNEAU + 16)))
        lignes = lignes_cible(u, a)[:8]
        amarrage = lignes_amarrage(u, a) if reglages.AIDES and lignes else None
        # sur écran étroit avec le RCS allumé : le panneau s'arrête au-dessus de la croix
        n_max = 8
        if self.rect_croix is not None and self.rect_croix.right > l - MX - L_PANNEAU:
            n_max = max(4, (self.rect_croix.top - M - 64 - 12) // 19)
        if amarrage:            # docking : dans le panneau de la cible (la croix RCS occupe la gauche)
            # filtre sur les CLÉS (lignes_amarrage ne traduit pas) : marche dans les deux langues
            garder = max(3, n_max - 3)             # la place reste aux lignes d'amarrage
            lignes = lignes[:garder] + [(t("Au port") if cle == "Distance au port" else t(cle), v, c)
                                        for cle, v, c in amarrage
                                        if cle in ("Distance au port", "Écart latéral", "Alignement")]
        lignes = lignes[:n_max]
        if lignes:
            x = l - MX - L_PANNEAU
            panneau(surf, (x, M + 52, L_PANNEAU, 12 + 19 * len(lignes)))
            yy = M + 58
            for nom, val, coul in lignes:
                texte(surf, nom.strip(), (x + 10, yy), 14, GRIS)
                texte(surf, val, (x + L_PANNEAU - 10, yy), 14, coul, ancre="hd")
                yy += 19
        if a is not None:
            self._echelle(surf, cam, l, h, x1=l - MX - L_COLONNE - 16, y=self.y_haut_sas - 22)
        for bouton in self.boutons:
            bouton.dessiner(surf, souris)
        self._temps_tactile(surf, u)
        tenues = self.scene.commandes_tenues()
        for rect, commande, symbole in self.maintenus:
            if commande == "gaz":
                continue
            if commande[0] == "rcs_joy":                   # la manette RCS se dessine ronde
                self._joystick(surf, rect, commande)
                continue
            allume = commande in tenues
            pygame.draw.rect(surf, (30, 90, 130) if allume else (24, 34, 56), rect, border_radius=8)
            pygame.draw.rect(surf, CYAN if allume else BORD_PANNEAU, rect, 1, border_radius=8)
            texte(surf, symbole, rect.center, 34 if commande[0] == "rot" else 24, BLANC, ancre="c")
        self._popup(surf, u, souris, l, h)
        self._menu_pilote(surf, u, souris, l, h)

    def _infos(self, surf, u, a):
        """Panneau de vol : altitude, vitesse, apoapside, périapside, carburant."""
        c = a.corps
        x, y, vx, vy = u.etat(a)
        r = hypot(x, y)
        w = c.vitesse_rotation
        v_vert = ((vx + w * y) * x + (vy - w * x) * y) / r
        rvx, rvy = u.vitesse_reference(a)
        o = a.orbite if a.mode != "pose" else None
        valide = o is not None and not o.degeneree
        lignes = [(t("Altitude"), fmt_distance(u.altitude(a) - a.geometrie().bas
                                               if a.mode != "pose" else 0.0)),
                  (t("Vit. %s" % a.ref_vitesse), fmt_vitesse(hypot(rvx, rvy))),
                  (t("Vit. verticale"), fmt_vitesse(v_vert)),
                  (t("Apoapside"), (fmt_distance(o.ra - c.R) if o.elliptique else t("évasion")) if valide else "—"),
                  (t("Périapside"), fmt_distance(o.rp - c.R) if valide else "—")]
        panneau(surf, (MX, M, L_PANNEAU, H_INFOS))
        texte(surf, a.nom, (MX + 10, M + 6), 17, BLANC, gras=True)
        texte(surf, "%s · %s" % (t(c.nom), u.situation(a)), (MX + 10, M + 29), 13, CYAN)
        yy = M + 50
        for nom, val in lignes:
            texte(surf, nom, (MX + 10, yy), 15, GRIS)
            texte(surf, val, (MX + L_PANNEAU - 10, yy), 15, BLANC, ancre="hd")
            yy += 21
        carb, cap = a.carburant_actif()
        if a.carburant_boosters()[1] > 0:                  # les boosters brûlent : leur jauge d'abord
            carb, cap = a.carburant_boosters()
        pygame.draw.rect(surf, GRIS_FONCE, (MX + 10, M + 160, L_PANNEAU - 20, 8), 1)
        if cap > 0:
            pygame.draw.rect(surf, VERT, (MX + 11, M + 161, int((L_PANNEAU - 22) * carb / cap), 6))
        etages = statistiques_etages(a.pieces)
        texte(surf, t("Δv étage {dv} m/s", dv=fmt_nombre(etages[0]["dv"]) if etages else "0"),
              (MX + 10, M + 172), 13, BLANC)

    def _joystick(self, surf, rect, commande):
        """Manette de translation RCS : le doigt s'écarte du centre, la poussée suit."""
        tenue = commande in self.scene.commandes_tenues()
        cx, cy = rect.center
        pygame.draw.circle(surf, (24, 34, 56), (cx, cy), rect.width // 2)
        pygame.draw.circle(surf, CYAN if tenue else BORD_PANNEAU, (cx, cy), rect.width // 2, 1)
        for d in self.scene.doigts.actifs.values():    # le point suit le doigt (borné au bord)
            if d.prise == commande:
                dx, dy = d.pos[0] - cx, d.pos[1] - cy
                n = hypot(dx, dy)
                if n > 78.0:
                    dx, dy = dx * 78.0 / n, dy * 78.0 / n
                pygame.draw.circle(surf, CYAN, (int(cx + dx), int(cy + dy)), 18)
                break

    def _gaz(self, surf, a):
        """Manette des gaz : une jauge verticale qu'on règle en y glissant le doigt."""
        r = self.rect_gaz
        tenue = "gaz" in self.scene.commandes_tenues()
        pygame.draw.rect(surf, (16, 22, 36), r, border_radius=10)
        pygame.draw.rect(surf, CYAN if tenue else BORD_PANNEAU, r, 1, border_radius=10)
        interieur = pygame.Rect(r.x + 12, r.y + 46, r.width - 24, r.height - 58)
        hauteur = int(interieur.height * a.gaz)
        if hauteur > 0:
            pygame.draw.rect(surf, ORANGE, (interieur.x, interieur.bottom - hauteur, interieur.width, hauteur),
                             border_radius=4)
        for f in (0.25, 0.5, 0.75):
            yy = interieur.bottom - int(interieur.height * f)
            pygame.draw.line(surf, GRIS_FONCE, (interieur.x - 6, yy), (interieur.x, yy))
        yy = interieur.bottom - hauteur
        pygame.draw.line(surf, BLANC, (r.x + 4, yy), (r.right - 4, yy), 3)
        texte(surf, t("GAZ"), (r.centerx, r.y + 7), 12, GRIS, ancre="hc")
        texte(surf, "%d %%" % round(100 * a.gaz), (r.centerx, r.y + 23), 14,
              ORANGE if a.gaz > 0 else GRIS, gras=True, ancre="hc")

    def _temps_tactile(self, surf, u):
        acc = ACCELERATIONS[u.accel]
        cx = self.rect_temps.centerx
        texte(surf, "x %s" % fmt_nombre(acc), (cx, M + 15), 17, JAUNE if acc > 1 else BLANC,
              gras=True, ancre="c")
        texte(surf, fmt_date(u.t), (cx, M + 34), 11, GRIS, ancre="c")

    def _noeud_tactile(self, surf, u, a, l):
        x, y, haut, lignes = self._geometrie_noeud(u, a, l)
        panneau(surf, (x, y, L_PANNEAU, haut))
        texte(surf, t("MANŒUVRE"), (x + 10, y + 8), 15, BLEU_PLAN, gras=True)
        texte(surf, t("glisse une poignée, ou tape-la : 1 m/s"), (x + 10, y + 28), 11, GRIS)
        yy = y + 46
        for nom, val, coul in lignes:
            texte(surf, nom, (x + 10, yy), 14, GRIS)
            texte(surf, val, (x + L_PANNEAU - 10, yy), 14, coul, ancre="hd")
            yy += 20
