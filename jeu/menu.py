# -*- coding: utf-8 -*-
"""Menu principal."""
import random
from math import sin
import pygame
from .constantes import TITRE, BLANC, GRIS, CYAN, NOIR
from .interface import texte, Bouton
from .rendu import disque, melange
from .tactile import Doigts
from .version import __version__
from . import sauvegarde, plateforme, reglages, sons


class SceneMenu:
    def __init__(self, app, vue="principal"):
        self.app = app
        self.vue = vue                    # "principal" ou "tutos" (liste des tutoriels)
        self.boutons = []
        self.doigts = Doigts()            # sur téléphone, les doigts remplacent la souris
        self.t = 0.0
        rng = random.Random(3)
        self.etoiles = [(rng.random(), rng.random(), rng.choice((110, 150, 200, 255))) for _ in range(220)]

    def evenement(self, ev):
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
            if self.vue in ("tutos", "options", "scenarios"):
                self.vue = "principal"
            else:
                self.app.quitter()
            return
        if plateforme.TACTILE:
            r = self.doigts.lire(ev, pygame.display.get_surface().get_size())
            pos = r[1].pos if r is not None and r[0] == "appui" else None
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            pos = ev.pos
        else:
            pos = None
        if pos is not None:
            for b in self.boutons:
                if b.clic(pos):
                    return

    def maj(self, dt):
        sons.silence_boucles()
        sons.regler_boucle("ambiance", 0.45, dt)
        self.t += dt

    def dessiner(self, surf):
        l, h = surf.get_size()
        surf.fill(NOIR)
        for x, y, lum in self.etoiles:
            surf.fill((lum, lum, lum), (int(x * l), int(y * h), 2, 2))
        # une planète bleue et son halo, en bas de l'écran
        cx, cy, r = l * 0.5, h + 2600, 2900
        for k, f in enumerate((0.08, 0.16, 0.3, 0.5)):
            disque(surf, melange(NOIR, (110, 170, 255), f), cx, cy, r + 60 - 14 * k)
        disque(surf, (40, 90, 170), cx, cy, r)
        if self.vue == "principal":             # petite fusée stylisée qui monte doucement
            fx, fy = l * 0.76, h * 0.52 + 8 * sin(self.t * 1.3)
            pygame.draw.polygon(surf, (255, 170, 60), [(fx - 7, fy + 46), (fx + 7, fy + 46), (fx, fy + 80 + 10 * sin(self.t * 23))])
            pygame.draw.rect(surf, (230, 232, 240), (fx - 9, fy - 20, 18, 60))
            pygame.draw.polygon(surf, (200, 70, 60), [(fx - 9, fy - 20), (fx + 9, fy - 20), (fx, fy - 46)])
            pygame.draw.polygon(surf, (90, 94, 104), [(fx - 9, fy + 40), (fx - 20, fy + 50), (fx - 9, fy + 20)])
            pygame.draw.polygon(surf, (90, 94, 104), [(fx + 9, fy + 40), (fx + 20, fy + 50), (fx + 9, fy + 20)])

        texte(surf, TITRE.upper(), (l // 2, h * 0.17), 46, BLANC, gras=True, ancre="c")
        texte(surf, "Construis, lance, mets en orbite, amarre, explore le système solaire",
              (l // 2, h * 0.17 + 44), 16, CYAN, ancre="c")
        app = self.app
        souris = pygame.mouse.get_pos()
        if self.vue == "tutos":
            self._liste_tutos(surf, l, h, souris)
        elif self.vue == "options":
            self._page_options(surf, l, h, souris)
        elif self.vue == "scenarios":
            self._liste_tutos(surf, l, h, souris, genre="mission")
        else:
            entrees = [("Continuer la partie", app.continuer, sauvegarde.sauvegarde_existe()),
                       ("Nouvelle carrière", lambda: app.nouvelle_partie(False), True),
                       ("Bac à sable (tout débloqué)", lambda: app.nouvelle_partie(True), True),
                       (None, None, True),                          # Tutoriels | Scénarios (côte à côte)
                       ("Options", lambda: setattr(self, "vue", "options"), True),
                       ("Quitter", app.quitter, True)]
            y0 = int(h * 0.36)
            self.boutons = [Bouton((l // 2 - 160, y0 + 52 * k, 320, 42), lib, act, 17, actif=ok)
                            for k, (lib, act, ok) in enumerate(entrees) if lib is not None]
            k = [e[0] for e in entrees].index(None)
            self.boutons.append(Bouton((l // 2 - 160, y0 + 52 * k, 156, 42), "Tutoriels",
                                       lambda: setattr(self, "vue", "tutos"), 17))
            self.boutons.append(Bouton((l // 2 + 4, y0 + 52 * k, 156, 42), "Scénarios",
                                       lambda: setattr(self, "vue", "scenarios"), 17))
            for b in self.boutons:
                b.dessiner(surf, souris)
        pied = ("Échelle 1/100 · en vol, ☰ ouvre le menu (missions, aide, sauvegarde) · v%s" % __version__ if plateforme.TACTILE
                else "Échelle 1/100 · H = aide en vol · F5 = sauvegarder")
        texte(surf, pied, (l // 2, h - 28), 13, GRIS, ancre="c")

    def _page_options(self, surf, l, h, souris):
        """Son, aides au pilotage et triche. La triche elle-même s'utilise en vol."""
        texte(surf, "OPTIONS", (l // 2, int(h * 0.30)), 20, BLANC, gras=True, ancre="c")
        y0 = int(h * 0.30) + 26
        entrees = [("Son : %s" % reglages.NOMS_SON[reglages.SON], reglages.changer_son),
                   ("Aides au pilotage : %s" % ("oui" if reglages.AIDES else "non"), reglages.basculer_aides),
                   ("Triche en vol : %s" % ("autorisée" if reglages.TRICHE else "désactivée"),
                    reglages.basculer_triche)]
        self.boutons = [Bouton((l // 2 - 170, y0 + 50 * k, 340, 42), lib, act, 16)
                        for k, (lib, act) in enumerate(entrees)]
        yt = y0 + 50 * len(entrees) + 6
        ou = "☰ puis Options, ou appui long sur l'horloge" if plateforme.TACTILE else "Échap puis Options, ou F12"
        texte(surf, "La triche (revenir 30 s en arrière, plein, indestructible...) s'ouvre en vol :",
              (l // 2, yt), 13, GRIS, ancre="hc")
        texte(surf, ou + ".", (l // 2, yt + 18), 13, GRIS, ancre="hc")
        self.boutons.append(Bouton((l // 2 - 90, yt + 44, 180, 40), "Retour",
                                   lambda: setattr(self, "vue", "principal"), 16))
        for b in self.boutons:
            b.dessiner(surf, souris)

    def _liste_tutos(self, surf, l, h, souris, genre="tuto"):
        """Tutoriels (ou missions historiques), sur deux colonnes, cochés quand ils sont faits."""
        from .tutoriel import PAR_ID, demarrer
        SCENARIOS = [s for s in PAR_ID.values() if s.genre == genre]
        titre = ("TUTORIELS : une mécanique à la fois" if genre == "tuto"
                 else "SCÉNARIOS : rejoue les grandes missions")
        texte(surf, titre, (l // 2, int(h * 0.30)), 20, BLANC, gras=True, ancre="c")
        cols = 2 if l >= 640 else 1
        lignes = (len(SCENARIOS) + cols - 1) // cols
        lb, hb = min(380, (l - 60) // cols - 6), 50
        x0 = (l - cols * lb - (cols - 1) * 12) // 2
        y0 = int(h * 0.30) + 24
        self.boutons = []
        for i, s in enumerate(SCENARIOS):
            c, r = i // lignes, i % lignes                # on lit la première colonne, puis la seconde
            x, y = x0 + c * (lb + 12), y0 + r * (hb + 8)
            b = Bouton((x, y, lb, hb), "", lambda ident=s.ident: demarrer(self.app, ident), 15)
            b.dessiner(surf, souris)
            self.boutons.append(b)
            nom = ("%d · %s" % (s.annee, s.titre)) if s.annee else ("%d. %s" % (i + 1, s.titre))
            texte(surf, nom, (x + 12, y + 7), 15, BLANC, gras=True)
            texte(surf, s.resume, (x + 12, y + 28), 12, GRIS)
            if s.ident in reglages.TUTOS_FAITS:
                texte(surf, "✓", (x + lb - 12, y + 12), 20, (120, 230, 140), gras=True, ancre="hd")
        b = Bouton((l // 2 - 90, y0 + lignes * (hb + 8) + 4, 180, 40), "Retour",
                   lambda: setattr(self, "vue", "principal"), 16)
        b.dessiner(surf, souris)
        self.boutons.append(b)
