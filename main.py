# -*- coding: utf-8 -*-
"""
Agence Spatiale 2D - point d'entrée.

    pip install pygame
    python main.py              (PC : clavier + souris)
    python main.py --tactile    (essayer sur PC l'interface tactile du téléphone)

Sur Android, le mode tactile s'active tout seul (voir jeu/plateforme.py).
"""
import os
import sys

# Sur Android, python-for-android lance ce fichier depuis le dossier de l'application :
# on s'assure que ce dossier est bien dans le chemin d'import (pour « import jeu »).
_DOSSIER = os.environ.get("ANDROID_ARGUMENT") or os.path.dirname(os.path.abspath(__file__))
if _DOSSIER not in sys.path:
    sys.path.insert(0, _DOSSIER)

import pygame

# Si le jeu lui-même ne se charge pas (fichier manquant...), on le dira à l'écran plutôt que
# de laisser l'application se fermer sans un mot (voir ecran_erreur, en bas du fichier).
try:
    from jeu.constantes import TITRE, LARGEUR, HAUTEUR, FPS
    from jeu.pieces import MODELES
    from jeu.univers import Univers
    from jeu import sauvegarde, plateforme, reglages, sons, musique, triche
    ERREUR_AU_CHARGEMENT = None
except Exception:
    import traceback
    ERREUR_AU_CHARGEMENT = traceback.format_exc()

SAUVEGARDE_AUTO_TACTILE = 60.0     # s : sur téléphone, l'appli peut être tuée à tout moment


class Application:
    """Gère la fenêtre, la boucle principale et le passage d'une scène à l'autre."""

    def __init__(self, tactile=None):
        if tactile is None:
            plateforme.configurer(sys.argv)               # avant pygame.init() : réglages SDL
        else:
            plateforme.configurer(["--tactile"] if tactile else [])
            plateforme.TACTILE = bool(tactile)
        pygame.mixer.pre_init(sons.FREQ, -16, 2, 1024)    # son : fréquence modeste, faible latence
        pygame.init()
        pygame.display.set_caption(TITRE)
        self.ecran = plateforme.ouvrir_fenetre(pygame, LARGEUR, HAUTEUR)
        self.tactile = plateforme.TACTILE
        reglages.charger()
        if not sons.cache_complet():                     # premier lancement : on fabrique les sons
            self.ecran.fill((0, 0, 0))
            from jeu.interface import texte
            l, h = self.ecran.get_size()
            texte(self.ecran, "Préparation des sons…", (l // 2, h // 2), 20, (200, 210, 230), ancre="c")
            pygame.display.flip()
        sons.initialiser()
        musique.preparer()                          # notes fabriquées en arrière-plan (la 1re fois)
        self.historique = triche.Historique()       # photos de la partie, pour revenir en arrière
        self.tuto = None                                 # tutoriel en cours (tutoriel.py)
        self.horloge = pygame.time.Clock()
        self.chrono_sauvegarde = 0.0
        self.univers = None
        self.nom_modele, _, cles = MODELES[0]          # fusée proposée par défaut dans le hangar
        self.modele = [e if isinstance(e, str) else [e[0], list(e[1])] for e in cles]
        self.en_marche = True
        self.scene = None
        self.aller_menu()

    # ------------------------------------------------------------ navigation
    def aller_menu(self, vue="principal"):
        from jeu.menu import SceneMenu
        self.sauvegarde_auto()                           # (jamais pendant un tutoriel)
        self.tuto = None
        self.scene = SceneMenu(self, vue)

    def aller_hangar(self):
        from jeu.hangar import SceneHangar
        self.scene = SceneHangar(self)

    def humeur_musique(self):
        """L'ambiance musicale selon l'écran et la situation du vaisseau."""
        nom = type(self.scene).__name__
        if nom == "SceneMenu":
            return "menu"
        if nom == "SceneHangar":
            return "hangar"
        u = getattr(self.scene, "u", None)
        a = u.actif if u is not None else None
        if a is None:
            return "espace"
        if a.corps is not u.terre:
            return "mystere"                        # la Lune, les planètes...
        if a.mode == "pose" or u.altitude(a) < a.corps.atm_h:
            return "decollage"
        return "espace"

    def aller_vol(self):
        from jeu.vol import SceneVol
        self.scene = SceneVol(self)

    def nouvelle_partie(self, bac_a_sable):
        self.tuto = None
        self.univers = Univers(bac_a_sable)
        self.aller_hangar()

    def continuer(self):
        self.tuto = None
        try:
            self.univers = sauvegarde.charger()
        except (OSError, ValueError, KeyError) as e:
            print("Chargement impossible :", e)
            return
        self.aller_vol()
        self.univers.dire("Partie chargée")

    def lancer(self, nom, cles):
        self.univers.lancer(nom, cles)
        self.aller_vol()

    def revenir_au_lancement(self):
        """Annule le vol en cours : on retrouve l'état d'avant le lancement, dans le hangar."""
        if self.univers is not None and self.univers.instantane is not None:
            self.univers = sauvegarde.dict_vers_univers(self.univers.instantane)
            self.aller_hangar()

    def sauvegarde_auto(self):
        if self.univers is not None:
            try:
                sauvegarde.sauvegarder(self.univers)
            except OSError:
                pass

    def quitter(self):
        self.sauvegarde_auto()
        self.en_marche = False

    # ---------------------------------------------------------------- boucle
    def boucle(self):
        while self.en_marche:
            # au plus 0,1 s par image : après une mise en veille (téléphone en poche, fenêtre
            # déplacée...), on ne cherche pas à rattraper le temps perdu d'un coup
            dt = min(self.horloge.tick(FPS) / 1000.0, 0.1)
            for ev in pygame.event.get():
                self.traiter(ev)
            if self.tactile and self.univers is not None:
                self.chrono_sauvegarde += dt
                if self.chrono_sauvegarde > SAUVEGARDE_AUTO_TACTILE:
                    self.chrono_sauvegarde = 0.0
                    self.sauvegarde_auto()
            self.scene.maj(dt)
            musique.maj(dt, self.humeur_musique())
            self.scene.dessiner(self.ecran)
            pygame.display.flip()
        pygame.quit()

    def traiter(self, ev):
        """Événements communs à toutes les scènes, puis ceux de la scène en cours."""
        if ev.type == pygame.QUIT:
            self.quitter()
        elif ev.type == pygame.VIDEORESIZE:
            self.ecran = pygame.display.get_surface()
        elif ev.type == getattr(pygame, "WINDOWFOCUSLOST", -1):
            self.sauvegarde_auto()                        # l'appli passe en arrière-plan
            if plateforme.sur_android():
                sons.suspendre(True)                      # silence tant qu'on ne la voit plus
        elif ev.type == getattr(pygame, "WINDOWFOCUSGAINED", -1):
            if plateforme.sur_android():
                sons.suspendre(False)
        elif ev.type == pygame.KEYDOWN and ev.key == getattr(pygame, "K_AC_BACK", -1):
            # bouton « retour » d'Android = touche Échap (menu de pause, fermer un panneau)
            self.scene.evenement(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE,
                                                    scancode=0, unicode="", mod=0))
        else:
            self.scene.evenement(ev)


def ecran_erreur(trace):
    """Dernier recours si le jeu plante : l'erreur s'affiche à l'écran (un téléphone n'a pas
    de console), et elle est aussi écrite dans erreur.txt et dans le journal (adb logcat)."""
    print(trace)
    try:
        with open(os.path.join(os.environ.get("ANDROID_PRIVATE") or _DOSSIER, "erreur.txt"), "w",
                  encoding="utf-8") as f:
            f.write(trace)
    except OSError:
        pass
    try:
        import textwrap
        pygame.display.init()
        pygame.font.init()
        ecran = pygame.display.get_surface() or pygame.display.set_mode((1200, 540))
        largeur, hauteur = ecran.get_size()
        try:            # la police du jeu (pygame n'a pas la sienne dans l'APK Android)
            police = pygame.font.Font(os.path.join(_DOSSIER, "jeu", "polices", "DejaVuSans.ttf"), 14)
        except Exception:
            police = pygame.font.Font(None, 20)
        lignes = ["Le jeu a planté. Touche l'écran (ou une touche) pour quitter.", ""]
        for ligne in trace.splitlines()[-24:]:
            lignes += textwrap.wrap(ligne, max(20, largeur // 8)) or [""]
        while True:
            for ev in pygame.event.get():
                if ev.type in (pygame.QUIT, pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN, pygame.FINGERDOWN):
                    return
            ecran.fill((40, 10, 16))
            y = 12
            for k, ligne in enumerate(lignes[-(hauteur - 20) // 19:]):
                ecran.blit(police.render(ligne, True, (255, 200, 120) if k == 0 else (235, 235, 240)), (14, y))
                y += 19
            pygame.display.flip()
            pygame.time.wait(50)
    except Exception:
        pass


if __name__ == "__main__":
    if ERREUR_AU_CHARGEMENT:
        ecran_erreur(ERREUR_AU_CHARGEMENT)
        sys.exit(1)
    try:
        Application().boucle()
    except SystemExit:
        raise
    except Exception:
        import traceback
        ecran_erreur(traceback.format_exc())
    sys.exit(0)
