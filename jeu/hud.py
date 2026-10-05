# -*- coding: utf-8 -*-
"""Affichage tête haute (HUD) de la scène de vol."""
from math import cos, sin, atan2, hypot, pi, log10, floor
import pygame
from .constantes import (ACCELERATIONS, BLANC, GRIS, GRIS_FONCE, CYAN, ORANGE, VERT, ROUGE, JAUNE,
                         MAGENTA, BLEU_PLAN)
from . import manoeuvre as mod_manoeuvre
from . import pilote as mod_pilote
from . import reglages
from .corps import Corps
from .orbite import INFINI
from .interface import (police, texte, panneau, Bouton, fmt_distance, fmt_vitesse, fmt_duree, fmt_date,
                        fmt_nombre)
from .missions import mission_suggeree
from .textes import t

LIBELLES_SAS = [("off", "OFF"), ("stab", "STAB"), ("pro", "PRO"), ("retro", "RETRO"),
                ("rad+", "RAD+"), ("rad-", "RAD-"), ("cible", "CIBLE"), ("anti", "ANTI")]
NOEUD_RECT = (10, 256, 270)          # panneau du nœud de manœuvre : x, y, largeur


def compte_a_rebours(s):
    """Durée signée : T− avant l'événement, T+ après."""
    return ("T+ " if s < 0 else "T− ") + fmt_duree(abs(s))


def infos_noeud(u, v):
    """Lignes du panneau « nœud de manœuvre » et hauteur du panneau."""
    n = v.noeud
    dv = n.dv()
    duree, assez = mod_manoeuvre.duree_combustion(v, dv)
    lignes = [(t("Δv restant") if n.commencee else t("Δv"), fmt_vitesse(dv), BLEU_PLAN)]
    if not n.commencee:
        lignes.append((t("   prograde"), "%+.1f m/s" % n.pro, VERT))
        lignes.append((t("   radial"), "%+.1f m/s" % n.rad, CYAN))
    lignes.append((t("Combustion"), fmt_duree(duree) if assez else t("Δv insuffisant"),
                   BLANC if assez else ROUGE))
    # une poussée longue perd de l'efficacité : la direction du nœud est figée, pas la vitesse
    periode = mod_manoeuvre.periode_au_noeud(v, n)
    if assez and periode is not None and duree > 0.06 * periode:
        lignes.append((t("Combustion longue"), t("surveille l'orbite"), ORANGE))
    lignes.append((t("Allumage"), compte_a_rebours(n.t - duree / 2.0 - u.t), JAUNE))
    lignes.append((t("Nœud"), compte_a_rebours(n.t - u.t), GRIS))
    if v.plan:
        o, c = v.plan[0].orbite, v.plan[0].corps
        lignes.append((t("Après : Pe"), fmt_distance(o.rp - c.R), BLEU_PLAN))
        lignes.append((t("Après : Ap"), fmt_distance(o.ra - c.R) if o.elliptique else t("évasion"), BLEU_PLAN))
        for tr in v.plan[1:]:
            if tr.entree:
                lignes.append((t("Rencontre"), t(tr.corps.nom), VERT))
                break
    if u.approche_plan is not None and u.cible is not None:
        d = u.approche_plan[1] - (u.cible.R if isinstance(u.cible, Corps) else 0.0)
        lignes.append((t("Approche prévue"), fmt_distance(max(0.0, d)), BLEU_PLAN))
    return lignes, 46 + 19 * len(lignes) + 36


class Hud:
    POPUP = dict(largeur=180, h_bouton=26, pas=30, police=16)     # menu contextuel (clic sur un objet)

    def decalage_tuto(self):
        """Hauteur de la bulle du tutoriel : les messages du jeu passent dessous."""
        tuto = getattr(getattr(self.scene, "app", None), "tuto", None)
        return tuto.hauteur if tuto is not None else 0

    def basculer_menu_pilote(self):
        self.menu_pilote = not self.menu_pilote
        self.popup = None

    def __init__(self, scene):
        self.scene = scene
        self.boutons = []
        self.popup = None              # (objet cliqué, position)
        self.boutons_popup = []
        self.menu_pilote = False

    # ------------------------------------------------------------------ clics
    def clic(self, pos):
        """Renvoie True si le clic a touché un élément du HUD."""
        for b in self.boutons_popup + self.boutons:
            if b.clic(pos):
                self.popup = None
                return True
        if self.popup is not None:
            self.popup = None
        self.menu_pilote = False
        return False

    def ouvrir_popup(self, objet, pos):
        self.popup = (objet, pos)

    # --------------------------------------------------------------- boutons
    def _construire_boutons(self, u, l, h):
        sc = self.scene
        a = u.actif
        b = [Bouton((l // 2 - 100, 8, 28, 24), "<", lambda: u.changer_acceleration(-1)),
             Bouton((l // 2 + 72, 8, 28, 24), ">", lambda: u.changer_acceleration(+1))]
        x, y = l - 160, h - 38
        for libelle, action in ((t("Menu (Échap)"), lambda: sc.ouvrir("pause")),
                                (t("Aide (H)"), lambda: sc.ouvrir("aide")),
                                (t("Missions (M)"), lambda: sc.ouvrir("missions"))):
            b.append(Bouton((x, y, 150, 28), libelle, action))
            y -= 32
        if a is not None:
            y -= 6
            if u.peut_recuperer(a):
                b.append(Bouton((x, y, 150, 28), t("Récupérer"), sc.recuperer))
                y -= 32
            if a.jonctions():
                b.append(Bouton((x, y, 150, 28), t("Désamarrer (U)"), u.desamarrer))
                y -= 32
                b.append(Bouton((x, y, 150, 28), t("Carburant"), lambda: sc.ouvrir("carburant")))
                y -= 32
            if any(p.parachute == "plie" for p in a.pieces) and a.corps.atm_h > 0 and a.mode != "pose":
                b.append(Bouton((x, y, 150, 28), t("Parachute (P)"), u.ouvrir_parachute))
                y -= 32
            if sc.cam.hors_vaisseau(u):
                b.append(Bouton((x, y, 150, 28), t("◎ Vaisseau (F)"), sc.recentrer, 13))
                y -= 32
            if reglages.AIDES:
                lib = t("Pilote : {nom}", nom=u.pilote.nom) if u.pilote is not None else t("Pilote auto (G)")
                b.append(Bouton((x, y, 150, 28), lib, self.basculer_menu_pilote, 13,
                                allume=u.pilote is not None or self.menu_pilote))
                self.ancre_pilote = (x + 150, y)
                y -= 32
            # SAS et modes
            x0, y0 = l // 2 - 56, h - 124
            for k, (mode, lib) in enumerate(LIBELLES_SAS):
                def choisir(m=mode):
                    u.arreter_pilote()
                    a.sas = m
                b.append(Bouton((x0 + (k % 4) * 66, y0 + (k // 4) * 30, 62, 26), lib, choisir, 13,
                                allume=(a.sas == mode)))
            def sas_manoeuvre():
                a.sas = "manoeuvre"
            b.append(Bouton((x0, y0 + 62, 62, 26), t("MAN"), sas_manoeuvre, 13,
                            actif=a.noeud is not None, allume=(a.sas == "manoeuvre")))
            b.append(Bouton((x0 + 66, y0 + 62, 62, 26), t("RCS (R)"), sc.basculer_rcs, 13, allume=a.rcs))
            b.append(Bouton((x0 + 132, y0 + 62, 128, 26), t("Vit. : {ref} (V)", ref=a.ref_vitesse),
                            sc.changer_reference, 13))
            b.append(Bouton((x0 + 264, y0 + 62, 62, 26), t({"auto": "Cam. auto", "horizon": "Horizon",
                                                          "nord": "Nord"}[sc.cam.mode]), sc.changer_camera, 12))
            if a.noeud is not None:                       # boutons du panneau de manœuvre
                nx, ny, nl = NOEUD_RECT
                yb = ny + infos_noeud(u, a)[1] - 32
                for dx, larg, lib, act in ((0, 56, t("− tour"), lambda: u.decaler_noeud(-1)),
                                           (60, 56, t("+ tour"), lambda: u.decaler_noeud(+1)),
                                           (120, 74, t("Exécuter") if reglages.AIDES else t("Filer"),
                                            (lambda: u.lancer_pilote(mod_pilote.ExecuterNoeud()))
                                            if reglages.AIDES else u.filer_au_noeud),
                                           (198, 52, t("Effacer"), u.supprimer_noeud)):
                    b.append(Bouton((nx + 10 + dx, yb, larg, 26), lib, act, 12))
            from .vaisseau import indice_decoupleur_bas
            if indice_decoupleur_bas(a.pieces):
                b.append(Bouton((150, h - 40, 120, 28), t("Étage (Espace)"), u.separer_etage, 13))
        self.boutons = b

    # ----------------------------------------------------------------- dessin
    def dessiner(self, surf, u, cam):
        l, h = surf.get_size()
        souris = pygame.mouse.get_pos()
        self._construire_boutons(u, l, h)
        a = u.actif
        if a is not None:
            self._vol(surf, u, a)
            if a.noeud is not None:
                self._noeud(surf, u, a)
            elif reglages.AIDES:
                self._atterrissage(surf, u, a, NOEUD_RECT)
            self._jauges(surf, u, a, h)
            self._cadran(surf, u, cam, a, l // 2 - 124, h - 72)
        self._temps(surf, u, l)
        self._cible(surf, u, a, l)
        self._messages(surf, u, l, y0=64 + self.decalage_tuto())
        self._echelle(surf, cam, l, h)
        for b in self.boutons:
            b.dessiner(surf, souris)
        self._popup(surf, u, souris, l, h)
        self._menu_pilote(surf, u, souris, l, h)

    def _vol(self, surf, u, a):
        c = a.corps
        x, y, vx, vy = u.etat(a)
        r = hypot(x, y)
        panneau(surf, (10, 10, 270, 188))
        texte(surf, a.nom, (20, 16), 17, BLANC, gras=True)
        texte(surf, "%s · %s" % (t(c.nom), u.situation(a)), (20, 38), 13, CYAN)
        rvx, rvy = u.vitesse_reference(a)
        w = c.vitesse_rotation
        v_vert = ((vx + w * y) * x + (vy - w * x) * y) / r
        o = a.orbite if a.mode != "pose" else None
        lignes = [(t("Altitude"), fmt_distance(r - c.R - a.geometrie().bas if a.mode != "pose" else 0.0)),
                  (t("Vitesse ({ref})", ref=a.ref_vitesse), fmt_vitesse(hypot(rvx, rvy))),
                  (t("Vit. verticale"), fmt_vitesse(v_vert))]
        if o is not None and not o.degeneree:
            lignes.append((t("Apoapside"), fmt_distance(o.ra - c.R) if o.elliptique else t("évasion")))
            lignes.append((t("Périapside"), fmt_distance(o.rp - c.R)))
            if o.elliptique:
                lignes.append((t("Temps → Ap"), fmt_duree(o.delai_apoapside(u.t))))
            lignes.append((t("Temps → Pe"), fmt_duree(o.delai_periapside(u.t))))
        yy = 60
        for nom, val in lignes:
            texte(surf, nom, (20, yy), 14, GRIS)
            texte(surf, val, (270, yy), 14, BLANC, ancre="hd")
            yy += 19
        m = None if u.tutoriel else mission_suggeree(u)       # pas d'objectif pendant un tutoriel
        if m is not None:
            panneau(surf, (10, 204, 270, 44), alpha=170)
            texte(surf, t("Objectif : ") + t(m.titre), (20, 208), 13, JAUNE, gras=True)
            desc = t(m.description)
            texte(surf, desc[:44] + ("…" if len(desc) > 44 else ""), (20, 226), 12, GRIS)

    def _menu_pilote(self, surf, u, souris, l, h):
        """Liste des aides utilisables maintenant (bouton PILOTE, ou touche G)."""
        if not self.menu_pilote or not reglages.AIDES or u.actif is None:
            self.menu_pilote = False
            return
        cfg = self.POPUP
        larg, hb, pas = cfg["largeur"] + 70, cfg["h_bouton"], cfg["pas"]
        actions = mod_pilote.actions(u, u.actif)
        haut = 40 + pas * max(1, len(actions))
        ax, ay = getattr(self, "ancre_pilote", (l - 10, 60))
        x = min(max(ax - larg, 4), l - larg - 4)
        y = min(max(ay - haut - 6 if ay > h / 2 else ay + 50, 4), h - haut - 4)
        panneau(surf, (x, y, larg, haut), alpha=240)
        texte(surf, t("PILOTE AUTOMATIQUE"), (x + 10, y + 8), cfg["police"] - 2, CYAN, gras=True)
        if not actions:
            texte(surf, t("Rien à faire d'automatique ici"), (x + 10, y + 38), cfg["police"] - 3, GRIS)
        for k, (lib, act) in enumerate(actions):
            def faire(act=act):
                act()
                self.menu_pilote = False
            b = Bouton((x + 8, y + 34 + pas * k, larg - 16, hb), lib, faire, cfg["police"] - 3)
            b.dessiner(surf, souris)
            self.boutons_popup.append(b)

    def _atterrissage(self, surf, u, a, rect, amarrage=True):
        """Panneau d'aide à l'atterrissage (en descente), ou au docking (cible proche)."""
        self.alerte = False
        titre, lignes = t("ATTERRISSAGE"), lignes_atterrissage(u, a)
        if not lignes and amarrage:
            titre, lignes = t("AMARRAGE"), lignes_amarrage(u, a)
        if not lignes:
            return
        self.alerte = any(v == t("MAINTENANT") for _, v, _ in lignes)      # bip d'alerte (écran de vol)
        x, y, larg = rect
        petit = larg < 260
        panneau(surf, (x, y, larg, 40 + 20 * len(lignes)))
        texte(surf, titre, (x + 10, y + 10), 14 if not petit else 15, ORANGE, gras=True)
        yy = y + 36
        for nom, val, coul in lignes:
            texte(surf, nom, (x + 10, yy), 13 if not petit else 14, GRIS)
            texte(surf, val, (x + larg - 10, yy), 13 if not petit else 14, coul, ancre="hd")
            yy += 20

    def _noeud(self, surf, u, a):
        """Panneau récapitulatif de la manœuvre planifiée."""
        lignes, haut = infos_noeud(u, a)
        x, y, larg = NOEUD_RECT
        panneau(surf, (x, y, larg, haut))
        texte(surf, t("NŒUD DE MANŒUVRE"), (x + 10, y + 12), 14, BLEU_PLAN, gras=True)
        yy = y + 40
        for nom, val, coul in lignes:
            texte(surf, nom, (x + 10, yy), 13, GRIS)
            texte(surf, val, (x + larg - 10, yy), 13, coul, ancre="hd")
            yy += 19

    def _jauges(self, surf, u, a, h):
        panneau(surf, (10, h - 132, 270, 122))
        # manette des gaz
        pygame.draw.rect(surf, GRIS_FONCE, (22, h - 122, 16, 100), 1)
        hg = int(98 * a.gaz)
        pygame.draw.rect(surf, ORANGE, (23, h - 23 - hg, 14, hg))
        texte(surf, t("GAZ"), (30, h - 20), 10, GRIS, ancre="hc")
        # carburant de l'étage, monergol
        carb, cap = a.carburant_actif()
        titre = t("Carburant (étage)")
        if a.carburant_boosters()[1] > 0:                  # les boosters brûlent : leur jauge d'abord
            (carb, cap), titre = a.carburant_boosters(), t("Carburant (boosters)")
        for k, (nom, val, maxi, coul) in enumerate(((titre, carb, cap, VERT),
                                                    (t("Monergol RCS"), a.mono(), sum(p.m.mono for p in a.pieces), CYAN))):
            yy = h - 124 + k * 34
            texte(surf, nom, (52, yy), 12, GRIS)
            texte(surf, "%s kg" % fmt_nombre(val), (268, yy), 12, BLANC, ancre="hd")
            pygame.draw.rect(surf, GRIS_FONCE, (52, yy + 17, 216, 8), 1)
            if maxi > 0:
                pygame.draw.rect(surf, coul, (53, yy + 18, int(214 * val / maxi), 6))
        etages = a_etages = None
        from .vaisseau import statistiques_etages
        etages = statistiques_etages(a.pieces)
        texte(surf, t("Δv étage {etage}   total {total} m/s", etage=fmt_nombre(etages[0]["dv"]) if etages else "0",
                                                     total=fmt_nombre(sum(e["dv"] for e in etages))),
              (52, h - 56), 13, BLANC)

    def _cadran(self, surf, u, cam, a, cx, cy, R=54, legende=True):
        """Cadran des directions, orienté comme l'écran : cap, prograde, radial, cible."""
        pygame.draw.circle(surf, (10, 16, 28), (cx, cy), R + 6)
        pygame.draw.circle(surf, (60, 80, 120), (cx, cy), R + 6, 1)
        for k in range(24):
            ang = k * pi / 12
            r0 = R - (8 if k % 6 == 0 else 4)
            pygame.draw.line(surf, GRIS_FONCE, (cx + r0 * cos(ang), cy + r0 * sin(ang)),
                             (cx + R * cos(ang), cy + R * sin(ang)))

        def point(dx, dy):
            n = hypot(dx, dy)
            if n < 1e-9:
                return None
            ex, ey = cam.direction_ecran(dx / n, dy / n)
            return cx + ex * (R - 10), cy + ey * (R - 10)

        x, y, vx, vy = u.etat(a)
        p = point(x, y)                                   # radial (vers le haut local)
        if p:
            pygame.draw.circle(surf, CYAN, (int(p[0]), int(p[1])), 3)
        rvx, rvy = u.vitesse_reference(a)
        if hypot(rvx, rvy) > 0.05:
            p = point(rvx, rvy)                           # prograde
            pygame.draw.circle(surf, VERT, (int(p[0]), int(p[1])), 6, 2)
            pygame.draw.circle(surf, VERT, (int(p[0]), int(p[1])), 1)
            p = point(-rvx, -rvy)                         # rétrograde
            pygame.draw.circle(surf, VERT, (int(p[0]), int(p[1])), 6, 1)
            pygame.draw.line(surf, VERT, (p[0] - 4, p[1] - 4), (p[0] + 4, p[1] + 4))
            pygame.draw.line(surf, VERT, (p[0] - 4, p[1] + 4), (p[0] + 4, p[1] - 4))
        if u.cible is not None:
            ax, ay = u.position_absolue(a)
            tx, ty = u.position_absolue(u.cible)
            p = point(tx - ax, ty - ay)
            if p:
                pygame.draw.rect(surf, MAGENTA, (int(p[0]) - 5, int(p[1]) - 5, 10, 10), 2)
        if a.noeud is not None:                           # direction de la manœuvre
            dv = mod_manoeuvre.impulsion(a, a.noeud)
            p = point(dv[0], dv[1]) if dv and hypot(dv[0], dv[1]) > 1e-6 else None
            if p:
                pygame.draw.polygon(surf, BLEU_PLAN, [(p[0], p[1] - 6), (p[0] + 6, p[1]),
                                                      (p[0], p[1] + 6), (p[0] - 6, p[1])], 2)
        ex, ey = cam.direction_ecran(cos(a.angle), sin(a.angle))   # cap du vaisseau
        bout = (cx + ex * (R - 2), cy + ey * (R - 2))
        pygame.draw.line(surf, BLANC, (cx - ex * 12, cy - ey * 12), bout, 3)
        pygame.draw.polygon(surf, BLANC, [bout, (bout[0] - ex * 12 - ey * 6, bout[1] - ey * 12 + ex * 6),
                                          (bout[0] - ex * 12 + ey * 6, bout[1] - ey * 12 - ex * 6)])
        if legende:
            texte(surf, t("SAS"), (cx, cy + R + 8), 10, GRIS, ancre="hc")

    def _temps(self, surf, u, l):
        panneau(surf, (l // 2 - 110, 4, 220, 50))
        acc = ACCELERATIONS[u.accel]
        texte(surf, "x %s" % fmt_nombre(acc), (l // 2, 20), 17, JAUNE if acc > 1 else BLANC, gras=True, ancre="c")
        texte(surf, fmt_date(u.t), (l // 2, 43), 12, GRIS, ancre="c")

    def _cible(self, surf, u, a, l):
        lignes = lignes_cible(u, a)
        if not lignes:
            return
        panneau(surf, (l - 250, 10, 240, 12 + 19 * len(lignes)))
        yy = 16
        for nom, val, coul in lignes:
            texte(surf, nom, (l - 240, yy), 14, GRIS)
            texte(surf, val, (l - 20, yy), 14, coul, ancre="hd")
            yy += 19

    def _messages(self, surf, u, l, y0=64, taille=16, pas=22, largeur=None):
        """Messages du jeu, centrés et coupés en lignes pour ne pas passer sur les panneaux."""
        largeur = largeur or max(260, l - 600)
        f = police(taille)
        yy = y0
        for txt, reste, coul in u.messages[-5:]:
            lignes, ligne = [], ""
            for mot in txt.split(" "):
                essai = (ligne + " " + mot).strip()
                if ligne and f.size(essai)[0] > largeur:
                    lignes.append(ligne)
                    ligne = mot
                else:
                    ligne = essai
            for ligne in lignes + [ligne]:
                w = f.size(ligne)[0] + 14
                fond = pygame.Surface((w, pas), pygame.SRCALPHA)
                fond.fill((8, 12, 22, 150))                 # lisible même sur le ciel bleu
                surf.blit(fond, (l // 2 - w // 2, yy - 2))
                texte(surf, ligne, (l // 2, yy), taille, coul, ancre="hc")
                yy += pas

    def _echelle(self, surf, cam, l, h, x1=None, y=None):
        """Barre d'échelle (la vue va de quelques mètres à des milliards de km)."""
        cible = 120.0 / cam.zoom
        p = 10.0 ** floor(log10(cible))
        longueur = max(k * p for k in (1, 2, 5) if k * p <= cible)
        px = longueur * cam.zoom
        x1 = l - 176 if x1 is None else x1
        y = h - 148 if y is None else y
        pygame.draw.line(surf, GRIS, (x1 - px, y), (x1, y))
        pygame.draw.line(surf, GRIS, (x1 - px, y - 4), (x1 - px, y + 4))
        pygame.draw.line(surf, GRIS, (x1, y - 4), (x1, y + 4))
        texte(surf, fmt_distance(longueur), (x1 - px / 2, y - 18), 12, GRIS, ancre="hc")

    def _popup(self, surf, u, souris, l, h):
        self.boutons_popup = []
        if self.popup is None:
            return
        obj, (px, py) = self.popup
        if not isinstance(obj, Corps) and (obj.detruit or obj not in u.vaisseaux):
            self.popup = None
            return
        sc = self.scene
        actions = []
        if obj is not u.actif:
            actions.append((t("Cibler"), lambda: u.cibler(obj)))
        if obj is u.cible:
            actions.append((t("Ne plus cibler"), lambda: u.cibler(None)))
        actions.append((t("Centrer la vue"), lambda: sc.centrer_sur(obj)))
        if not isinstance(obj, Corps) and obj is not u.actif and obj.controlable():
            actions.append((t("Contrôler"), lambda: sc.controler(obj)))
        if obj is u.actif and obj.noeud is None and obj.mode != "pose":
            actions.append((t("Nœud de manœuvre"), sc.noeud_par_defaut))
        cfg = self.POPUP
        larg, hb, pas = cfg["largeur"], cfg["h_bouton"], cfg["pas"]
        haut = 50 + pas * len(actions)
        px = min(max(px + 12, 4), l - larg - 4)
        py = min(max(py - 10, 4), h - haut - 4)
        panneau(surf, (px, py, larg, haut), alpha=235)
        texte(surf, t(obj.nom), (px + 10, py + 6), cfg["police"], BLANC, gras=True)
        if isinstance(obj, Corps):
            info = "g %.2f m/s² · R %s" % (obj.g, fmt_distance(obj.R))
        else:
            info = "%s · %s" % (t(obj.type()), t(obj.corps.nom))
        texte(surf, info, (px + 10, py + 27), 12, GRIS)
        for k, (lib, act) in enumerate(actions):
            b = Bouton((px + 8, py + 46 + pas * k, larg - 16, hb), lib, act, cfg["police"] - 3)
            b.dessiner(surf, souris)
            self.boutons_popup.append(b)


def lignes_cible(u, a):
    """Lignes (nom, valeur, couleur) du panneau de droite : fonds, cible, rencontre."""
    lignes = []
    if not u.bac_a_sable:
        lignes.append((t("Fonds"), fmt_nombre(u.fonds), JAUNE))
    c = u.cible
    if c is not None:
        lignes.append((t("Cible"), t(c.nom), MAGENTA))
        if a is not None:
            ax, ay = u.position_absolue(a)
            cx, cy = u.position_absolue(c)
            avx, avy = u.vitesse_absolue(a)
            cvx, cvy = u.vitesse_absolue(c)
            d = hypot(cx - ax, cy - ay) - (c.R if isinstance(c, Corps) else 0.0)
            lignes.append((t("Distance"), fmt_distance(d), BLANC))
            lignes.append((t("Vit. relative"), fmt_vitesse(hypot(cvx - avx, cvy - avy)), BLANC))
            if d > 1:
                rapp = -((cx - ax) * (cvx - avx) + (cy - ay) * (cvy - avy)) / hypot(cx - ax, cy - ay)
                lignes.append((t("Rapprochement"), fmt_vitesse(rapp), VERT if rapp >= 0 else ORANGE))
        if u.approche is not None:
            tm, d = u.approche[0], u.approche[1]
            d -= c.R if isinstance(c, Corps) else 0.0
            lignes.append((t("Approche mini"), fmt_distance(max(0.0, d)), MAGENTA))
            lignes.append((t("   dans"), fmt_duree(tm - u.t), GRIS))
    if a is not None and a.troncons:
        for tr in a.troncons[1:]:
            if tr.entree:
                lignes.append((t("Rencontre"), t(tr.corps.nom), VERT))
                lignes.append((t("   dans"), fmt_duree(tr.t0 - u.t), GRIS))
                lignes.append((t("   périapside"), fmt_distance(tr.orbite.rp - tr.corps.R), VERT))
                break
    return lignes


def lignes_atterrissage(u, v):
    """Aide à l'atterrissage mise en forme : [(nom, texte, couleur)] ou None."""
    infos = mod_pilote.infos_atterrissage(u, v)
    if not infos:
        return None
    out = []
    for nom, val, alerte in infos:
        if isinstance(val, str):
            txt = t(val)
        elif nom == "Altitude":
            txt = fmt_distance(max(0.0, val))
        elif nom.startswith("Vit"):
            txt = fmt_vitesse(val)
        elif nom == "Inclinaison":
            txt = "%.0f°" % val
        elif nom == "Inclinaison":
            txt = "%.0f°" % val
        elif nom == "Freinage dans" and val <= 1.0:
            txt = t("MAINTENANT")
        else:
            txt = fmt_duree(val)
        out.append((t(nom), txt, ROUGE if alerte else (JAUNE if nom == "Freinage dans" else BLANC)))
    return out


def lignes_amarrage(u, v):
    """Aide au docking mise en forme : [(nom, texte, couleur)] ou None."""
    infos = mod_pilote.infos_amarrage(u, v)
    if not infos:
        return None
    out = []
    for nom, val, alerte in infos:
        if isinstance(val, str):
            txt = t(val)
        elif nom.startswith("Distance"):
            txt = fmt_distance(val)
        elif nom == "Alignement":
            txt = "%.1f°" % val
        elif nom.startswith("Écart"):
            txt = "%+.1f m" % val
        else:
            txt = fmt_vitesse(val)
        out.append((t(nom), txt, ROUGE if alerte else BLANC))
    return out
