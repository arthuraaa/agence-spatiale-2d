# -*- coding: utf-8 -*-
"""
PC ou téléphone : tout ce qui dépend de la plateforme est ici.

Sur Android (APK construit avec buildozer, ou Pydroid 3), le jeu passe en « mode
tactile » : commandes à l'écran au lieu du clavier, et affichage à une résolution
logique fixe de 540 pixels de haut, agrandie par SDL pour remplir l'écran. Sans
ça, un texte de 13 pixels ferait à peine un millimètre sur un téléphone.

Pour essayer le mode tactile sur PC (à la souris) :   python main.py --tactile
"""
import os
import sys

HAUTEUR_TACTILE = 540          # hauteur logique de l'écran en mode tactile (px)
MARGE_BORD = 30                # marge gauche/droite : encoches et coins arrondis des téléphones

TACTILE = False                # choisi par configurer(), lu par les scènes


def sur_android():
    """Vrai sur Android (python-for-android, Pydroid 3...)."""
    return hasattr(sys, "getandroidapilevel") or "ANDROID_ARGUMENT" in os.environ \
        or "ANDROID_PRIVATE" in os.environ or os.environ.get("ANDROID_ROOT") == "/system"


def configurer(argv=()):
    """À appeler AVANT pygame.init() : choisit le mode et règle SDL en conséquence."""
    global TACTILE
    TACTILE = sur_android() or "--tactile" in argv or os.environ.get("AGENCE_TACTILE") == "1"
    if TACTILE:
        # les doigts sont lus directement : pas de clics de souris « simulés » en double
        os.environ.setdefault("SDL_TOUCH_MOUSE_EVENTS", "0")
        # paysage uniquement, et le bouton « retour » d'Android ouvre le menu au lieu de quitter
        os.environ.setdefault("SDL_IOS_ORIENTATIONS", "LandscapeLeft LandscapeRight")
        os.environ.setdefault("SDL_ANDROID_TRAP_BACK_BUTTON", "1")
        # agrandissement lissé (l'écran fait rarement un multiple exact de 540 px)
        os.environ.setdefault("SDL_RENDER_SCALE_QUALITY", "linear")
    return TACTILE


def taille_logique(largeur_ecran, hauteur_ecran):
    """Taille de l'image calculée en mode tactile : 540 px de haut, au format de l'écran."""
    grand, petit = max(largeur_ecran, hauteur_ecran), min(largeur_ecran, hauteur_ecran)
    if petit <= 0:
        grand, petit = 2400, 1080                        # format de téléphone courant
    largeur = int(round(HAUTEUR_TACTILE * grand / petit / 2.0)) * 2
    return max(720, min(largeur, 1400)), HAUTEUR_TACTILE


def ouvrir_fenetre(pygame, largeur_pc, hauteur_pc):
    """Crée la fenêtre (PC) ou l'écran plein (téléphone)."""
    if not TACTILE:
        return pygame.display.set_mode((largeur_pc, hauteur_pc), pygame.RESIZABLE)
    info = pygame.display.Info()
    largeur, hauteur = info.current_w, info.current_h
    simule = os.environ.get("AGENCE_ECRAN", "")         # ex. AGENCE_ECRAN=2400x1080 : écran simulé
    if "x" in simule:
        largeur, hauteur = (int(v) for v in simule.lower().split("x"))
    taille = taille_logique(largeur, hauteur)
    options = pygame.SCALED | (pygame.FULLSCREEN if sur_android() else 0)
    try:
        return pygame.display.set_mode(taille, options)
    except pygame.error:                                  # pilote sans agrandissement
        return pygame.display.set_mode(taille)


def dossier_donnees():
    """Dossier privé de l'application sur Android (APK), sinon None."""
    return os.environ.get("ANDROID_PRIVATE")
