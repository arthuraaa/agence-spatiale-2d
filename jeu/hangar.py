# -*- coding: utf-8 -*-
"""Hangar : on assemble la fusée pièce par pièce, du nez vers le moteur."""
import base64
import binascii
import json
import pygame
from .missions import MISSIONS
from .constantes import BLANC, GRIS, GRIS_FONCE, CYAN, ORANGE, VERT, ROUGE, JAUNE, NOIR
from .pieces import CATALOGUE, CATEGORIES, MODELES, Piece
from .vaisseau import (Vaisseau, orienter_ports, statistiques_etages, indice_moteur, pieces_depuis_plan,
                       toutes_les_cles, prix_plan, copie_plan, moteur_et_reservoirs, est_paire_boosters)
from .rendu import dessiner_pile, formes_piece
from .interface import (texte, texte_multiligne, panneau, Bouton, fmt_nombre, fmt_masse,
                        fmt_duree, police)
from .tactile import Doigts
from . import sons, plateforme
from .textes import t

HORS_ECRAN = (-100, -100)          # « position de la souris » sur écran tactile : pas de survol

L_GAUCHE, L_DROITE = 300, 330
H_LIGNE, H_TITRE = 40, 26

MARQUE_CODE = "AGS1."              # tout code de partage de fusée commence par ça


def code_de_plan(nom, cles):
    """Code court pour partager la fusée : un texte à coller dans une messagerie."""
    brut = json.dumps([nom, cles], ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return MARQUE_CODE + base64.urlsafe_b64encode(brut).decode("ascii").rstrip("=")


def plan_de_code(code):
    """Décode un code de partage, ou None s'il est illisible (clé inconnue, forme fausse...)."""
    try:
        code = code.strip().strip('"')
        if not code.startswith(MARQUE_CODE):
            return None
        brut = base64.urlsafe_b64decode(code[len(MARQUE_CODE):] + "==")
        nom, cles = json.loads(brut.decode("utf-8"))
        if not isinstance(nom, str) or not isinstance(cles, list) or len(toutes_les_cles(cles)) > 40:
            return None
        if any(c not in CATALOGUE for c in toutes_les_cles(cles)):
            return None
        return nom, copie_plan(cles)
    except Exception:                                 # binascii, JSON, structure inattendue...
        return None


def copier_dans_presse_papiers(brut):
    """Met le texte dans le presse-papiers ; False si l'appareil ne le permet pas."""
    try:
        pygame.scrap.init()
        brut = brut.encode("utf-8")
        pygame.scrap.put("UTF8_STRING", brut)
        pygame.scrap.put("text/plain;charset=utf-8", brut)
        return True
    except (pygame.error, NotImplementedError):
        return False


def lire_presse_papiers():
    """Le texte du presse-papiers, ou None s'il est inaccessible."""
    try:
        pygame.scrap.init()
        for typ in ("text/plain;charset=utf-8", "UTF8_STRING"):
            brut = pygame.scrap.get(typ)
            if brut:
                return brut.decode("utf-8")
        return ""
    except (pygame.error, NotImplementedError):
        return None


class SceneHangar:
    def __init__(self, app):
        self.app = app
        self.u = app.univers
        self.cles = copie_plan(app.modele)    # la fusée en cours (plan : clés du haut vers le bas)
        self.nom = t(app.nom_modele)
        self.selection = None                 # indice de la pièce, ou (indice, rang dans son booster)
        self.defilement = 0
        self.edition_nom = False
        self.menu_modeles = False
        self.boutons = []
        self.zones_catalogue = []             # (rect, clé)
        self.zones_pile = []                  # (rect, indice)
        self.message = ""
        self.zone_nom = pygame.Rect(0, 0, 0, 0)
        self.tactile = plateforme.TACTILE
        self.doigts = Doigts()
        self.defilement_depart = 0            # défilement du catalogue quand le doigt s'est posé
        self.lg, self.ld = L_GAUCHE, L_DROITE  # largeurs du catalogue et du panneau de droite

    # ---------------------------------------------------------------- édition
    def ajouter(self, cle):
        if not self.u.piece_debloquee(cle):
            ident = CATALOGUE[cle].debloque_par
            titre = next((m.titre for m in MISSIONS if m.ident == ident), ident)
            self.message = t("Pièce verrouillée : accomplis la mission « {titre} ».", titre=titre)
            return
        if len(self.cles) >= 40:
            return
        sel = self.selection
        if cle == "decoupleur_radial":                   # accroche une paire de boosters
            if not isinstance(sel, int):
                self.message = t("Choisis d'abord la pièce de la fusée qui portera les boosters.")
                return
            if self._booster(sel) is not None:
                self.message = t("Cette pièce porte déjà une paire de boosters.")
                return
            self.cles[sel] = [self.cles[sel], ["decoupleur_radial"]]
            self.selection = (sel, 0)
            self.message = t("Boosters accrochés : ajoute-leur un réservoir, puis un moteur.")
            return
        if cle == "port_radial":                         # accroche un port latéral
            if not isinstance(sel, int):
                self.message = t("Choisis d'abord la pièce qui portera le port latéral.")
                return
            if self._booster(sel) is not None:
                self.message = t("Cette pièce porte déjà quelque chose sur le côté.")
                return
            self.cles[sel] = [self.cles[sel], ["port_radial"]]
            self.selection = (sel, 0)
            self.message = t("Port latéral accroché : en vol, amarre-toi dessus avec un port d'extrémité.")
            return
        if isinstance(sel, tuple):                       # on remplit la pile latérale sélectionnée
            i, j = sel
            pile = self._booster(i)
            annexe = bool(pile) and pile[0] == "port_radial"     # annexe : toutes les pièces
            if not annexe and CATALOGUE[cle].forme not in ("reservoir", "moteur", "coiffe"):
                self.message = t("Un booster ne prend que des réservoirs, des moteurs et une coiffe.")
                return
            self._booster(i).insert(j + 1, cle)
            self.selection = (i, j + 1)
            self.message = ""
            return
        i = len(self.cles) if sel is None else sel + 1
        self.cles.insert(i, cle)
        self.selection = i
        self.message = ""

    def _booster(self, i):
        """Pile (liste de clés) du booster accroché à la pièce i, ou None."""
        e = self.cles[i]
        return None if isinstance(e, str) else e[1]

    def supprimer(self):
        sel = self.selection
        if isinstance(sel, tuple):
            i, j = sel
            if j == 0:                                   # le découpleur radial : la paire s'en va
                self.cles[i] = self.cles[i][0]
                self.selection = i
            else:
                del self._booster(i)[j]
                self.selection = (i, j - 1)
        elif sel is not None and self.cles:
            del self.cles[sel]
            self.selection = min(sel, len(self.cles) - 1) if self.cles else None

    def peut_deplacer(self, sens):
        sel = self.selection
        if isinstance(sel, tuple):                       # le découpleur radial reste en tête du booster
            i, j = sel
            return j >= 1 and 1 <= j + sens < len(self._booster(i))
        return sel is not None and 0 <= sel + sens < len(self.cles)

    def deplacer(self, sens):
        if not self.peut_deplacer(sens):
            return
        sel = self.selection
        if isinstance(sel, tuple):
            i, j = sel
            pile = self._booster(i)
            pile[j], pile[j + sens] = pile[j + sens], pile[j]
            self.selection = (i, j + sens)
        else:
            self.cles[sel], self.cles[sel + sens] = self.cles[sel + sens], self.cles[sel]
            self.selection = sel + sens

    def _piece_selectionnee(self, pieces):
        sel = self.selection
        if isinstance(sel, tuple):
            i, j = sel
            if i < len(pieces) and j < len(pieces[i].laterales):
                return pieces[i].laterales[j]
        elif sel is not None and sel < len(pieces):
            return pieces[sel]
        return None

    def charger_modele(self, k):
        nom, _, cles = MODELES[k]
        self.cles, self.nom = copie_plan(cles), t(nom)
        self.selection, self.menu_modeles, self.message = None, False, ""

    # ------------------------------------------------------------- partage de fusées
    def copier_code(self):
        """Mets le plan de la fusée dans le presse-papiers, sous forme de code court."""
        if copier_dans_presse_papiers(code_de_plan(self.nom or "", self.cles)):
            self.menu_modeles = False
            self.message = t("code_copie", nom=self.nom or t("Vaisseau"))
        else:
            self.message = t("code_indisponible")

    def coller_code(self):
        """Charge la fusée décrite par le code du presse-papiers."""
        brut = lire_presse_papiers()
        resultat = plan_de_code(brut) if brut else None
        if resultat is None:
            self.message = t("code_illisible")
            return
        nom, cles = resultat
        verrouillees = [c for c in toutes_les_cles(cles) if not self.u.piece_debloquee(c)]
        self.cles, self.nom = cles, nom or t("Vaisseau")
        self.selection, self.menu_modeles = None, False
        self.message = t("code_importee_verrouillee", nom=self.nom) if verrouillees \
            else t("code_importee", nom=self.nom)

    def problemes(self):
        """Liste (texte, bloquant) des problèmes de la fusée."""
        out = []
        pieces = pieces_depuis_plan(self.cles)
        if not any(p.m.commande for p in pieces):
            out.append((t("Il faut une pièce de commande (capsule, sonde...)"), True))
        if any(not self.u.piece_debloquee(c) for c in toutes_les_cles(self.cles)):
            out.append((t("Contient des pièces pas encore débloquées"), True))
        if any(est_paire_boosters(p) and moteur_et_reservoirs(p.laterales)[0] is None for p in pieces):
            out.append((t("Un booster n'a pas de moteur tout en bas"), False))
        prix = prix_plan(self.cles)
        if not self.u.bac_a_sable and prix > self.u.fonds:
            out.append((t("Fonds insuffisants ({prix})", prix=fmt_nombre(prix)), True))
        if pieces:
            et = statistiques_etages(pieces)
            if indice_moteur(pieces) is None:
                out.append((t("Aucun moteur actif tout en bas de la pile"), False))
            elif et[0]["twr"] < 1.0:
                out.append((t("Poussée trop faible pour décoller (TWR {twr})", twr=et[0]["twr"]), False))
        return out

    def editer_nom(self, oui):
        """Commence ou termine la saisie du nom (affiche le clavier sur téléphone)."""
        if oui == self.edition_nom:
            return
        self.edition_nom = oui
        if self.tactile:
            if oui:
                pygame.key.set_text_input_rect(self.zone_nom)
                pygame.key.start_text_input()
            else:
                pygame.key.stop_text_input()

    def lancer(self):
        if self.cles and not any(b for _, b in self.problemes()):
            self.app.modele, self.app.nom_modele = copie_plan(self.cles), self.nom
            self.app.lancer(self.nom or t("Vaisseau"), self.cles)

    def quitter_hangar(self):
        self.app.modele, self.app.nom_modele = copie_plan(self.cles), self.nom
        self.app.aller_vol()

    # ------------------------------------------------------------- événements
    def evenement(self, ev):
        if self.tactile:
            return self._evenement_tactile(ev)
        if ev.type == pygame.MOUSEWHEEL:
            if pygame.mouse.get_pos()[0] < self.lg:
                self.defilement -= ev.y * 40
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            self.edition_nom = False
            for b in self.boutons:
                if b.clic(ev.pos):
                    return
            self.menu_modeles = False
            for rect, cle in self.zones_catalogue:
                if rect.collidepoint(ev.pos):
                    return self.ajouter(cle)
            for rect, i in self.zones_pile:
                if rect.collidepoint(ev.pos):
                    self.selection = i
                    return
            if self.zone_nom.collidepoint(ev.pos):
                self.edition_nom = True
            elif ev.pos[0] > self.lg and ev.pos[0] < pygame.display.get_surface().get_width() - self.ld:
                self.selection = None
        elif ev.type == pygame.KEYDOWN:
            if self.edition_nom:
                if ev.key in (pygame.K_RETURN, pygame.K_ESCAPE, pygame.K_KP_ENTER):
                    self.edition_nom = False
                elif ev.key == pygame.K_BACKSPACE:
                    self.nom = self.nom[:-1]
                elif ev.unicode and ev.unicode.isprintable() and len(self.nom) < 22:
                    self.nom += ev.unicode
            elif ev.key in (pygame.K_DELETE, pygame.K_BACKSPACE):
                self.supprimer()
            elif ev.key == pygame.K_UP:
                self.deplacer(-1)
            elif ev.key == pygame.K_DOWN:
                self.deplacer(+1)
            elif ev.key == pygame.K_ESCAPE:
                self.quitter_hangar()

    def _evenement_tactile(self, ev):
        """Au doigt : tape = ajouter / sélectionner, glisser dans le catalogue = le faire défiler."""
        if ev.type == pygame.TEXTINPUT:                   # lettres du clavier Android
            if self.edition_nom:
                self.nom = (self.nom + ev.text)[:22]
            return
        if ev.type == pygame.KEYDOWN:
            if self.edition_nom:
                if ev.key == pygame.K_BACKSPACE:
                    self.nom = self.nom[:-1]
                elif ev.key in (pygame.K_RETURN, pygame.K_ESCAPE, pygame.K_KP_ENTER):
                    self.editer_nom(False)
            elif ev.key == pygame.K_ESCAPE:               # bouton « retour » d'Android
                if self.menu_modeles:
                    self.menu_modeles = False
                else:
                    self.quitter_hangar()
            return
        if ev.type == pygame.MOUSEWHEEL:                  # molette (essais sur PC)
            self.defilement -= ev.y * 40
            return
        r = self.doigts.lire(ev, pygame.display.get_surface().get_size())
        if r is None:
            return
        geste, d = r
        if geste == "appui":
            for b in self.boutons:                        # boutons : déclenchés dès l'appui
                if b.clic(d.pos):
                    d.prise = "bouton"
                    return
            if self.zone_nom.collidepoint(d.pos):
                d.prise = "bouton"
                return self.editer_nom(True)
            self.editer_nom(False)
            self.menu_modeles = False
            d.prise = "catalogue" if d.pos[0] < self.lg else "pile"
            self.defilement_depart = self.defilement
        elif geste == "glisse" and d.prise == "catalogue" and d.bouge:
            self.defilement = self.defilement_depart - (d.pos[1] - d.depart[1])
        elif geste == "relache" and not d.bouge:          # une tape (le doigt n'a pas glissé)
            if d.prise == "catalogue":
                for rect, cle in self.zones_catalogue:
                    if rect.collidepoint(d.pos):
                        return self.ajouter(cle)
            elif d.prise == "pile":
                for rect, i in self.zones_pile:
                    if rect.collidepoint(d.pos):
                        self.selection = i
                        return
                if d.pos[0] < pygame.display.get_surface().get_width() - self.ld:
                    self.selection = None

    def maj(self, dt):
        if self.app.tuto is not None:
            self.app.tuto.maj(self)
        sons.silence_boucles()
        sons.regler_boucle("ambiance", 0.25, dt)

    # ----------------------------------------------------------------- dessin
    def dessiner(self, surf):
        l, h = surf.get_size()
        # sur un écran étroit (tablette 4:3, petite fenêtre), les panneaux latéraux rétrécissent
        self.lg, self.ld = (self.lg, self.ld) if l >= 1100 else (250, 280)
        surf.fill((18, 22, 32))
        for x in range(self.lg, l - self.ld, 40):          # quadrillage du hangar
            pygame.draw.line(surf, (24, 30, 44), (x, 0), (x, h))
        for y in range(0, h, 40):
            pygame.draw.line(surf, (24, 30, 44), (self.lg, y), (l - self.ld, y))
        pygame.draw.rect(surf, (40, 44, 54), (self.lg, h - 30, l - self.lg - self.ld, 30))
        self.boutons = []
        self._pile(surf, l, h)
        self._catalogue(surf, h)
        self._stats(surf, l, h)
        self._outils_selection(surf, l, h)
        souris = HORS_ECRAN if self.tactile else pygame.mouse.get_pos()
        for b in self.boutons:
            b.dessiner(surf, souris)
        if self.app.tuto is not None:                  # bulle du tutoriel
            self.app.tuto.dessiner(surf, self, self.boutons, list(self.boutons))
        dessiner_libelles_modeles(self, surf)

    def _catalogue(self, surf, h):
        panneau(surf, (0, 0, self.lg, h), alpha=255, bord=False)
        total = len(CATEGORIES) * H_TITRE + len(CATALOGUE) * H_LIGNE + 60
        self.defilement = max(0, min(self.defilement, total - h))
        y = 50 - self.defilement
        self.zones_catalogue = []
        souris = HORS_ECRAN if self.tactile else pygame.mouse.get_pos()
        for cat in CATEGORIES:
            texte(surf, t(cat).upper(), (14, y + 6), 13, CYAN, gras=True)
            y += H_TITRE
            for m in CATALOGUE.values():
                if m.categorie != cat:
                    continue
                rect = pygame.Rect(6, y, self.lg - 12, H_LIGNE - 4)
                ok = self.u.piece_debloquee(m.cle)
                if rect.collidepoint(souris) and souris[1] > 44:
                    pygame.draw.rect(surf, (34, 48, 78), rect, border_radius=4)
                # mini dessin de la pièce
                zone = pygame.Rect(10, y + 2, 44, H_LIGNE - 8)
                ech = min(30.0 / max(m.h, 0.8), 40.0 / m.l)
                ancien = surf.get_clip()
                surf.set_clip(zone.clip(pygame.Rect(0, 44, self.lg, h)))
                p = Piece(m.cle)
                if m.forme == "radial":                        # icône : deux boosters de part et d'autre
                    for dx in (-13, 9):
                        pygame.draw.rect(surf, (225, 228, 235) if ok else (60, 64, 74), (zone.centerx + dx, zone.y + 6, 5, 22))
                    pygame.draw.rect(surf, (90, 94, 104), (zone.centerx - 8, zone.y + 10, 16, 3))
                    pygame.draw.rect(surf, (90, 94, 104), (zone.centerx - 8, zone.y + 22, 16, 3))
                for couleur, pts in formes_piece(p, m.l, m.h):
                    if not ok:
                        couleur = (60, 64, 74)
                    pygame.draw.polygon(surf, couleur, [(zone.centerx + x * ech, zone.bottom - 1 - yy * ech)
                                                        for x, yy in pts])
                surf.set_clip(ancien)
                texte(surf, t(m.nom), (62, y + 2), 14, BLANC if ok else GRIS_FONCE)
                detail = ("%s · %s" % (fmt_masse(m.masse + m.carburant + m.mono),
                                        fmt_nombre(m.prix)) if ok else t("verrouillée"))
                texte(surf, detail, (62, y + 19), 11, GRIS if ok else GRIS_FONCE)
                if y > 44:
                    self.zones_catalogue.append((rect, m.cle))
                y += H_LIGNE
        panneau(surf, (0, 0, self.lg, 44), alpha=255, bord=False, couleur=(10, 14, 24))
        texte(surf, t("PIÈCES"), (14, 12), 17, BLANC, gras=True)
        aide = t("tape = ajouter · glisse = défiler") if self.tactile else t("clic = ajouter sous la sélection")
        if self.lg >= 300:
            texte(surf, aide, (self.lg - 10, 17), 11, GRIS, ancre="hd")

    def _pile(self, surf, l, h):
        self.zones_pile = []
        self.gauche_etiquette = None
        cx = (self.lg + l - self.ld) // 2
        if not self.cles:
            texte(surf, t("Clique sur une pièce à gauche pour commencer"), (cx, h // 2), 16, GRIS, ancre="c")
            texte(surf, t("(on construit du nez vers le moteur)"), (cx, h // 2 + 24), 13, GRIS_FONCE, ancre="c")
            return
        pieces = pieces_depuis_plan(self.cles)
        v = Vaisseau(self.nom, pieces, None)
        g = v.geometrie()
        ech = min(18.0, (h - 120) / (g.longueur + 1.0))
        haut_ecran = h - 34 - (g.longueur + (0.5 if g.train else 0.0)) * ech
        oy = haut_ecran + g.haut * ech
        sel = self._piece_selectionnee(pieces)
        dessiner_pile(surf, v, g, (cx, oy), (0.0, -ech), (ech, 0.0), selection=sel)
        # zones cliquables : les boosters d'abord (ils sont prioritaires là où ils se trouvent)
        etages = statistiques_etages(pieces)
        for k, pile, ecart, segs, demi, n in g.laterales:
            l_b = max(q.m.l for q in pile)
            for j, (q, (yh, yb)) in enumerate(zip(pile, segs)):
                for cote in ((-1, 1) if n == 2 else (1,)):
                    if q.m.forme == "radial":                  # l'attache du haut, entre cœur et booster
                        x0 = cx + cote * demi * ech
                        x1 = cx + cote * (ecart - l_b / 2) * ech
                        rect = pygame.Rect(min(x0, x1) - 4, oy - (segs[0][0] - 0.7) * ech - 8, abs(x1 - x0) + 8, 16)
                    else:
                        w = max(q.m.l * ech, 18)
                        rect = pygame.Rect(cx + cote * ecart * ech - w / 2, oy - yh * ech, w, max(6, (yh - yb) * ech))
                    self.zones_pile.append((rect, (k, j)))
            phase = next((n for n, e in enumerate(etages) if e.get("boosters")), None)
            if phase is not None and est_paire_boosters(pieces[k]) and \
                    pieces[k] is next((p for p in pieces[::-1] if est_paire_boosters(p)), None):
                e = etages[phase]
                xg = cx - (ecart + l_b / 2) * ech - 8
                etiq = t("boosters · Δv {dv}", dv=fmt_nombre(e["dv"]))
                self.gauche_etiquette = xg - police(12).size(etiq)[0]
                ym = oy - 0.5 * (segs[0][0] + segs[-1][1]) * ech
                texte(surf, t("Étage {n}", n=phase + 1), (xg, ym - 16), 13, ORANGE if phase == 0 else GRIS,
                      gras=True, ancre="hd")
                texte(surf, etiq, (xg, ym + 1), 12, BLANC, ancre="hd")
        for i, ((yh, yb), larg) in enumerate(zip(g.segments, g.largeurs)):
            self.zones_pile.append((pygame.Rect(cx - 70, oy - yh * ech, 140, max(4, (yh - yb) * ech)), i))
        # accolades des étages (la phase des boosters est notée à côté d'eux)
        for k, e in enumerate(etages):
            if e.get("boosters"):
                continue
            y0 = oy - g.segments[e["debut"]][0] * ech
            y1 = oy - g.segments[e["fin"] - 1][1] * ech
            x = min(cx + 135, l - self.ld - 60)
            place = l - self.ld - x - 12                   # largeur disponible pour le texte
            coul = ORANGE if k == 0 else GRIS
            pygame.draw.lines(surf, coul, False, [(x - 6, y0 + 2), (x, y0 + 2), (x, y1 - 2), (x - 6, y1 - 2)])
            complet = t("Δv {dv} m/s · TWR {twr}", dv=fmt_nombre(e["dv"]), twr=e["twr"] if k == 0 else e["twr_vide"])
            court = t("Δv {dv}", dv=fmt_nombre(e["dv"]))
            texte(surf, t("Étage {n}", n=k + 1) if place >= 60 else str(k + 1), (x + 8, (y0 + y1) / 2 - 16), 13,
                  coul, gras=True)
            if e["moteur"] and place >= 44:
                texte(surf, complet if place >= police(12).size(complet)[0] else court,
                      (x + 8, (y0 + y1) / 2 + 1), 12, BLANC)

    def _stats(self, surf, l, h):
        x = l - self.ld
        panneau(surf, (x, 0, self.ld, h), alpha=255, bord=False)
        texte(surf, t("HANGAR"), (x + 16, 12), 17, BLANC, gras=True)
        if not self.u.bac_a_sable:
            texte(surf, t("Fonds : {v}", v=fmt_nombre(self.u.fonds)), (l - 14, 15), 14, JAUNE, ancre="hd")
        else:
            texte(surf, t("Bac à sable"), (l - 14, 15), 14, GRIS, ancre="hd")
        self.zone_nom = pygame.Rect(x + 14, 50, self.ld - 28, 30)
        pygame.draw.rect(surf, (10, 14, 24), self.zone_nom, border_radius=4)
        pygame.draw.rect(surf, CYAN if self.edition_nom else GRIS_FONCE, self.zone_nom, 1, border_radius=4)
        curseur = "|" if self.edition_nom and pygame.time.get_ticks() % 900 < 450 else ""
        texte(surf, (self.nom or t("Nom du vaisseau")) + curseur, (x + 22, 56), 15, BLANC if self.nom else GRIS_FONCE)
        pieces = pieces_depuis_plan(self.cles)
        masse = Vaisseau("", pieces, None).masse()
        etages = statistiques_etages(pieces) if pieces else []
        lignes = [(t("Pièces"), str(len(toutes_les_cles(self.cles)))), (t("Masse au décollage"), fmt_masse(masse)),
                  (t("Hauteur"), "%.1f m" % sum(p.m.h for p in pieces)),
                  (t("Prix"), fmt_nombre(prix_plan(self.cles))),
                  (t("Δv total (vide)"), "%s m/s" % fmt_nombre(sum(e["dv"] for e in etages)))]
        y = 94
        for nom, val in lignes:
            texte(surf, nom, (x + 16, y), 14, GRIS)
            texte(surf, val, (l - 16, y), 14, BLANC, ancre="hd")
            y += 21
        y += 6
        texte(surf, t("ÉTAGES (ordre d'allumage)"), (x + 16, y), 12, CYAN, gras=True)
        y += 20
        for k, e in enumerate(etages[:5 if self.tactile else 7]):
            if e["moteur"]:
                txt = "%d · %s   Δv %s   TWR %.2f" % (k + 1, e["moteur"], fmt_nombre(e["dv"]),
                                                     e["twr"] if k == 0 else e["twr_vide"])
                if self.ld >= L_DROITE:                    # la durée de combustion, si la place le permet
                    txt += "   " + fmt_duree(e["duree"])
            else:
                txt = t("{n} · (sans moteur)", n=k + 1)
            texte(surf, txt, (x + 16, y), 12, BLANC if e["moteur"] else GRIS)
            y += 18
        y += 4
        if not self.tactile:
            texte(surf, t("Repères : orbite ≈ 1 050 m/s"), (x + 16, y), 11, GRIS)
            texte(surf, t("Lune aller-retour ≈ 2 000 m/s"), (x + 16, y + 15), 11, GRIS)
            y += 34
        pbs = self.problemes() if pieces else []
        for txt, bloquant in pbs:
            y = texte_multiligne(surf, "! " + txt, (x + 16, y), self.ld - 32, 13,
                                 ROUGE if bloquant else ORANGE)
        if self.message:
            y = texte_multiligne(surf, self.message, (x + 16, y), self.ld - 32, 13, ORANGE)
        if self._piece_selectionnee(pieces) is not None and not self.tactile:
            m = self._piece_selectionnee(pieces).m
            y += 6
            texte(surf, t(m.nom), (x + 16, y), 14, CYAN, gras=True)
            y += 20
            infos = []
            if m.poussee:
                infos.append(t("Poussée {kn} kN · Isp {ispv} s (vide) / {isps} s (sol)",
                               kn=m.poussee / 1000, ispv=m.isp_vide, isps=m.isp_sol))
            if m.carburant:
                infos.append(t("Carburant {v} kg", v=fmt_nombre(m.carburant)))
            if m.description:
                infos.append(m.description)
            infos.append(t("Suppr ou ✕ = retirer · ↑ ↓ ou ▲ ▼ = déplacer"))
            for info in infos:
                y = texte_multiligne(surf, info, (x + 16, y), self.ld - 32, 12, GRIS)
        # boutons
        peut_lancer = bool(pieces) and not any(b for _, b in pbs)
        grand, petit = (46, 40) if self.tactile else (38, 28)
        by = h - 12 - grand
        self.boutons.append(Bouton((x + 14, by, self.ld - 28, grand), t("LANCER"), self.lancer, 18,
                                   actif=peut_lancer))
        by -= petit + 8
        demi = (self.ld - 36) // 2
        self.boutons.append(Bouton((x + 14, by, demi, petit), t("Modèles…"), self._basculer_modeles, 15))
        self.boutons.append(Bouton((x + 22 + demi, by, demi, petit), t("Tout vider"), self._vider, 15))
        by -= petit + 6
        self.boutons.append(Bouton((x + 14, by, self.ld - 28, petit),
                                   t("Suivi des vols") if self.tactile else t("Suivi des vols (Échap)"),
                                   self.quitter_hangar, 15))
        if self.menu_modeles:
            hm = 16 + 44 * (len(MODELES) + 2)          # la liste des modèles + copier/coller
            mx, my = x - 330, h - 60 - hm
            panneau(surf, (mx, my, 320, hm), alpha=250)
            for k, (nom, desc, cles) in enumerate(MODELES):
                ok = all(self.u.piece_debloquee(c) for c in toutes_les_cles(cles))
                prix = prix_plan(cles)
                b = Bouton((mx + 8, my + 8 + 44 * k, 304, 40), "", lambda k=k: self.charger_modele(k), actif=ok)
                self.boutons.insert(0, b)
            self.boutons.insert(0, Bouton((mx + 8, my + 8 + 44 * len(MODELES), 304, 40), "",
                                          self.copier_code))
            self.boutons.insert(0, Bouton((mx + 8, my + 8 + 44 * (len(MODELES) + 1), 304, 40), "",
                                          self.coller_code))

    def _outils_selection(self, surf, l, h):
        """Boutons ✕ ▲ ▼ juste à gauche de la pièce sélectionnée (retirer, monter, descendre)."""
        rect = next((r for r, i in self.zones_pile if i == self.selection), None)
        if rect is None:
            return
        taille = 44 if self.tactile else 32
        x = max(self.lg + 4, rect.x - taille - 16)
        if isinstance(self.selection, tuple) and self.gauche_etiquette is not None:
            x = max(self.lg + 4, min(x, self.gauche_etiquette - taille - 10))   # pas sur l'étiquette
        y = max(10, min(rect.centery - (3 * taille + 12) // 2, h - 3 * taille - 50))
        for k, (lib, act, ok) in enumerate((("✕", self.supprimer, True),
                                            ("▲", lambda: self.deplacer(-1), self.peut_deplacer(-1)),
                                            ("▼", lambda: self.deplacer(+1), self.peut_deplacer(+1)))):
            self.boutons.append(Bouton((x, y + k * (taille + 6), taille, taille), lib, act,
                                       20 if self.tactile else 16, actif=ok))

    def _basculer_modeles(self):
        self.menu_modeles = not self.menu_modeles

    def _vider(self):
        self.cles, self.selection = [], None


def dessiner_libelles_modeles(scene, surf):
    """Textes des boutons du menu « Modèles » (dessinés par-dessus les boutons)."""
    if not scene.menu_modeles:
        return
    l, h = surf.get_size()
    x = l - scene.ld
    hm = 16 + 44 * (len(MODELES) + 2)
    mx, my = x - 330, h - 60 - hm
    for k, (nom, desc, cles) in enumerate(MODELES):
        ok = all(scene.u.piece_debloquee(c) for c in toutes_les_cles(cles))
        prix = prix_plan(cles)
        texte(surf, "%s  (%s)" % (t(nom), fmt_nombre(prix)), (mx + 18, my + 11 + 44 * k), 14,
              BLANC if ok else GRIS_FONCE, gras=True)
        texte(surf, t(desc) if ok else t("pièces pas encore débloquées"), (mx + 18, my + 29 + 44 * k), 11,
              GRIS if ok else GRIS_FONCE)
    texte(surf, t("copier_code"), (mx + 18, my + 11 + 44 * len(MODELES)), 14, CYAN, gras=True)
    texte(surf, t("coller_code"), (mx + 18, my + 11 + 44 * (len(MODELES) + 1)), 14, CYAN, gras=True)
