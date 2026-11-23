# -*- coding: utf-8 -*-
"""Menu principal."""
import random
from math import sin
import pygame
from .constantes import BLANC, GRIS, CYAN, NOIR, VERT
from .interface import texte, texte_multiligne, Bouton
from .rendu import disque, melange
from .tactile import Doigts
from .version import __version__
from .textes import t, NOMS_LANGUE
from . import sauvegarde, plateforme, reglages, sons, textes


class SceneMenu:
    def __init__(self, app, vue="principal"):
        self.app = app
        self.vue = vue                    # "principal", "tutos", "options", "reussites", "album"...
        self.photo_index = 0              # photo affichée en grand (vue "photo")
        self.boutons = []
        self.doigts = Doigts()            # sur téléphone, les doigts remplacent la souris
        self.t = 0.0
        rng = random.Random(3)
        self.etoiles = [(rng.random(), rng.random(), rng.choice((110, 150, 200, 255))) for _ in range(220)]

    def evenement(self, ev):
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
            if self.vue in ("tutos", "options", "scenarios", "reussites", "apropos",
                            "album", "photo"):
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

        texte(surf, t("nom_jeu").upper(), (l // 2, h * 0.17), 46, BLANC, gras=True, ancre="c")
        texte(surf, t("sous_titre"), (l // 2, h * 0.17 + 44), 16, CYAN, ancre="c")
        app = self.app
        souris = pygame.mouse.get_pos()
        if self.vue == "tutos":
            self._liste_tutos(surf, l, h, souris)
        elif self.vue == "options":
            self._page_options(surf, l, h, souris)
        elif self.vue == "scenarios":
            self._liste_tutos(surf, l, h, souris, genre="mission")
        elif self.vue == "reussites":
            self._page_reussites(surf, l, h, souris)
        elif self.vue == "album":
            self._page_album(surf, l, h, souris)
        elif self.vue == "photo":
            self._page_photo(surf, l, h, souris)
        elif self.vue == "apropos":
            self._page_apropos(surf, l, h, souris)
        else:
            entrees = [(t("continuer"), app.continuer, sauvegarde.sauvegarde_existe()),
                       (t("nouvelle_carriere"), lambda: app.nouvelle_partie(False), True),
                       (t("bac_a_sable"), lambda: app.nouvelle_partie(True), True),
                       (None, None, True),                          # Tutoriels | Scénarios
                       (None, None, True),                          # Réussites | Album
                       (t("options"), lambda: setattr(self, "vue", "options"), True),
                       (t("quitter"), app.quitter, True)]
            y0 = int(h * 0.30)                      # 8 rangées en 540 px : pas de 46 px
            self.boutons = [Bouton((l // 2 - 160, y0 + 46 * k, 320, 40), lib, act, 17, actif=ok)
                            for k, (lib, act, ok) in enumerate(entrees) if lib is not None]
            k1, k2 = [k for k, e in enumerate(entrees) if e[0] is None]
            self.boutons.append(Bouton((l // 2 - 160, y0 + 46 * k1, 156, 40), t("tutoriels"),
                                       lambda: setattr(self, "vue", "tutos"), 17))
            self.boutons.append(Bouton((l // 2 + 4, y0 + 46 * k1, 156, 40), t("scenarios"),
                                       lambda: setattr(self, "vue", "scenarios"), 17))
            self.boutons.append(Bouton((l // 2 - 160, y0 + 46 * k2, 156, 40), t("reussites_titre"),
                                       lambda: setattr(self, "vue", "reussites"), 17))
            self.boutons.append(Bouton((l // 2 + 4, y0 + 46 * k2, 156, 40), t("album_titre"),
                                       lambda: setattr(self, "vue", "album"), 17))
            for b in self.boutons:
                b.dessiner(surf, souris)
        pied = (t("pied_tactile", version=__version__) if plateforme.TACTILE
                else t("pied_pc"))
        texte(surf, pied, (l // 2, h - 28), 13, GRIS, ancre="c")

    def _page_options(self, surf, l, h, souris):
        """Langue, son, aides au pilotage et triche. La triche elle-même s'utilise en vol."""
        texte(surf, t("options_titre"), (l // 2, int(h * 0.30)), 20, BLANC, gras=True, ancre="c")
        y0 = int(h * 0.30) + 26

        def langue_suivante():
            # auto -> français -> English -> auto
            ordre = list(NOMS_LANGUE)
            reglages.changer_langue(ordre[(ordre.index(reglages.LANGUE) + 1) % len(ordre)])

        nom_langue = NOMS_LANGUE[reglages.LANGUE] if reglages.LANGUE else t("langue_auto")
        entrees = [(t("choix_langue", nom=nom_langue), langue_suivante),
                   (t("son", mode=t("son_" + reglages.SON)), reglages.changer_son),
                   (t("aides_pilotage", etat=t("oui") if reglages.AIDES else t("non")), reglages.basculer_aides),
                   (t("triche_options", etat=t("triche_autorisee") if reglages.TRICHE else t("triche_desactivee")),
                    reglages.basculer_triche),
                   (t("apropos"), lambda: setattr(self, "vue", "apropos"))]
        self.boutons = [Bouton((l // 2 - 170, y0 + 46 * k, 340, 40), lib, act, 16)
                        for k, (lib, act) in enumerate(entrees)]
        yt = y0 + 46 * len(entrees) + 6
        ou = t("triche_ou_tactile") if plateforme.TACTILE else t("triche_ou_pc")
        texte(surf, t("triche_intro"), (l // 2, yt), 13, GRIS, ancre="hc")
        texte(surf, ou + ".", (l // 2, yt + 18), 13, GRIS, ancre="hc")
        self.boutons.append(Bouton((l // 2 - 90, yt + 42, 180, 40), t("retour"),
                                   lambda: setattr(self, "vue", "principal"), 16))
        for b in self.boutons:
            b.dessiner(surf, souris)

    def _page_reussites(self, surf, l, h, souris):
        """Jalons cochés et compteurs de carrière, gardés d'une partie à l'autre."""
        from . import jalons
        texte(surf, t("reussites_titre"), (l // 2, int(h * 0.30)), 20, BLANC, gras=True, ancre="c")
        y0 = int(h * 0.30) + 34
        # la ligne des compteurs, sous le titre
        pieces = [t("stats_" + cle, n=reglages.STATS.get(cle, 0))
                  for cle in ("lancements", "etages", "crashs", "amarrages", "poses")
                  if reglages.STATS.get(cle, 0) > 0]
        texte(surf, " · ".join(pieces) if pieces else t("stats_aucune"),
              (l // 2, y0), 13, CYAN, ancre="hc")
        # les jalons, sur deux colonnes, cochés quand ils sont obtenus
        y0 += 24
        cols = 2 if l >= 640 else 1
        lignes = (len(jalons.JALONS) + cols - 1) // cols
        lb = min(340, (l - 60) // cols - 8)
        x0 = (l - cols * lb - (cols - 1) * 12) // 2
        for i, j in enumerate(jalons.JALONS):
            c, r = i // lignes, i % lignes
            fait = j.ident in reglages.JALONS_FAITS
            texte(surf, ("✓ " if fait else "○ ") + t(j.titre),
                  (x0 + c * (lb + 12), y0 + r * 30), 14, VERT if fait else GRIS, gras=fait)
        b = Bouton((l // 2 - 90, y0 + lignes * 30 + 6, 180, 40), t("retour"),
                   lambda: setattr(self, "vue", "principal"), 16)
        b.dessiner(surf, souris)
        self.boutons = [b]

    def _page_album(self, surf, l, h, souris):
        """Les photos de la partie (pose, amarrage, demande du joueur)."""
        from . import album
        texte(surf, t("album_titre"), (l // 2, int(h * 0.30)), 20, BLANC, gras=True, ancre="c")
        photos = album.lister()
        self.boutons = []
        if not photos:
            texte(surf, t("album_vide"), (l // 2, int(h * 0.52)), 14, GRIS, ancre="c")
        else:
            y0 = int(h * 0.30) + 28
            dispo = (h - 76) - y0                     # place pour la grille, bouton Retour en bas
            ch, cw = 110, 196                         # vignette, réduite si la grille déborde
            from math import ceil
            while ch > 50 and ceil(len(photos) / max(1, (l - 40) // (cw + 10))) * (ch + 8) > dispo:
                ch -= 10
                cw = round(ch * 1.8)
            par_ligne = max(1, (l - 40) // (cw + 10))
            x0 = (l - min(len(photos), par_ligne) * (cw + 10) + 10) // 2
            for i, chemin in enumerate(photos):
                c, r = i % par_ligne, i // par_ligne
                x, y = x0 + c * (cw + 10), y0 + r * (ch + 8)
                v = album.vignette(chemin, ch)
                if v is None:
                    continue
                b = Bouton((x, y, v.get_width(), v.get_height()), "",
                           lambda i=i: self._ouvrir_photo(i), 12)
                b.dessiner(surf, souris)
                surf.blit(v, (x, y))
                self.boutons.append(b)
        b = Bouton((l // 2 - 90, h - 76, 180, 40), t("retour"),
                   lambda: setattr(self, "vue", "principal"), 16)
        b.dessiner(surf, souris)
        self.boutons.append(b)

    def _page_photo(self, surf, l, h, souris):
        """Une photo en grand : légende, boutons Supprimer et Retour."""
        from . import album
        photos = album.lister()
        if not photos or not (0 <= self.photo_index < len(photos)):
            self.vue = "album"
            return self._page_album(surf, l, h, souris)
        chemin = photos[self.photo_index]
        texte(surf, album.libelle(chemin), (l // 2, int(h * 0.30)), 14, CYAN, ancre="c")
        v = album.image(chemin, l - 40, h - 190)
        if v is not None:
            surf.blit(v, (l // 2 - v.get_width() // 2, int(h * 0.30) + 22))
        self.boutons = [Bouton((l // 2 - 190, h - 76, 180, 40), t("supprimer"),
                               lambda: (album.supprimer(chemin), setattr(self, "vue", "album")), 16),
                        Bouton((l // 2 + 10, h - 76, 180, 40), t("retour"),
                               lambda: setattr(self, "vue", "album"), 16)]
        for b in self.boutons:
            b.dessiner(surf, souris)

    def _ouvrir_photo(self, i):
        self.photo_index = i
        self.vue = "photo"

    def _page_apropos(self, surf, l, h, souris):
        """Version, licences (pygame, DejaVu) et confidentialité."""
        texte(surf, t("apropos"), (l // 2, int(h * 0.28)), 20, BLANC, gras=True, ancre="c")
        largeur = min(420, l - 80)
        texte_multiligne(surf, t("apropos_texte", version=__version__),
                         (l // 2 - largeur // 2, int(h * 0.28) + 36), largeur, 14, GRIS)
        b = Bouton((l // 2 - 90, h - 76, 180, 40), t("retour"),
                   lambda: setattr(self, "vue", "options"), 16)
        b.dessiner(surf, souris)
        self.boutons = [b]

    def _liste_tutos(self, surf, l, h, souris, genre="tuto"):
        """Tutoriels (ou missions historiques), sur deux colonnes, cochés quand ils sont faits."""
        from .tutoriel import PAR_ID, demarrer
        SCENARIOS = [s for s in PAR_ID.values() if s.genre == genre]
        titre = t("tutoriels_titre") if genre == "tuto" else t("scenarios_titre")
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
            nom = ("%d · %s" % (s.annee, t(s.titre))) if s.annee else ("%d. %s" % (i + 1, t(s.titre)))
            texte(surf, nom, (x + 12, y + 7), 15, BLANC, gras=True)
            texte(surf, t(s.resume), (x + 12, y + 28), 12, GRIS)
            if s.ident in reglages.TUTOS_FAITS:
                texte(surf, "✓", (x + lb - 12, y + 12), 20, (120, 230, 140), gras=True, ancre="hd")
        b = Bouton((l // 2 - 90, y0 + lignes * (hb + 8) + 4, 180, 40), t("retour"),
                   lambda: setattr(self, "vue", "principal"), 16)
        b.dessiner(surf, souris)
        self.boutons.append(b)
