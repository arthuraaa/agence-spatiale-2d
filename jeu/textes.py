# -*- coding: utf-8 -*-
"""Textes du jeu, en français et en anglais.

Tout texte affiché au joueur passe par t("cle") : le module choisit la langue
dans reglages.LANGUE ("" = langue du système). Chaque entrée de TOUT donne les
deux langues, ce qui permet à tests/test_textes.py de vérifier la couverture.

Les gabarits s'écrivent avec des accolades : t("altitude_sur", corps="Lune")
pour "Altitude au-dessus de {corps}".
"""
import os

# Codes de langue reconnus, avec leur nom affiché (toujours dans sa propre
# langue, convention habituelle des sélecteurs de langue).
NOMS_LANGUE = {"": "auto", "fr": "français", "en": "English"}

TOUT = {
    "nom_jeu": {"fr": "Agence Spatiale 2D", "en": "Space Agency 2D"},
    "langue": {"fr": "Langue", "en": "Language"},
    "langue_auto": {"fr": "langue du système", "en": "system language"},

    # ---- Menu principal
    "sous_titre": {"fr": "Construis, lance, mets en orbite, amarre, explore le système solaire",
                   "en": "Build, launch, reach orbit, dock, explore the solar system"},
    "continuer": {"fr": "Continuer la partie", "en": "Continue game"},
    "nouvelle_carriere": {"fr": "Nouvelle carrière", "en": "New career"},
    "bac_a_sable": {"fr": "Bac à sable (tout débloqué)", "en": "Sandbox (everything unlocked)"},
    "options": {"fr": "Options", "en": "Options"},
    "quitter": {"fr": "Quitter", "en": "Quit"},
    "tutoriels": {"fr": "Tutoriels", "en": "Tutorials"},
    "scenarios": {"fr": "Scénarios", "en": "Scenarios"},
    "pied_tactile": {"fr": "Échelle 1/100 · en vol, ☰ ouvre le menu (missions, aide, sauvegarde) · v{version}",
                     "en": "Scale 1/100 · in flight, ☰ opens the menu (missions, help, save) · v{version}"},
    "pied_pc": {"fr": "Échelle 1/100 · H = aide en vol · F5 = sauvegarder",
                "en": "Scale 1/100 · H = help in flight · F5 = save"},

    # ---- Options
    "options_titre": {"fr": "OPTIONS", "en": "OPTIONS"},
    "son": {"fr": "Son : {mode}", "en": "Sound: {mode}"},
    "aides_pilotage": {"fr": "Aides au pilotage : {etat}", "en": "Flight assists: {etat}"},
    "triche_options": {"fr": "Triche en vol : {etat}", "en": "Cheat menu in flight: {etat}"},
    "oui": {"fr": "oui", "en": "yes"},
    "non": {"fr": "non", "en": "no"},
    "triche_autorisee": {"fr": "autorisée", "en": "allowed"},
    "triche_desactivee": {"fr": "désactivée", "en": "disabled"},
    "triche_intro": {"fr": "La triche (revenir 30 s en arrière, plein, indestructible...) s'ouvre en vol :",
                     "en": "Cheats (rewind 30 s, full fuel, indestructible...) open in flight:"},
    "triche_ou_tactile": {"fr": "☰ puis Options, ou appui long sur l'horloge",
                          "en": "☰ then Options, or long-press the clock"},
    "triche_ou_pc": {"fr": "Échap puis Options, ou F12", "en": "Esc then Options, or F12"},
    "choix_langue": {"fr": "Langue : {nom}", "en": "Language: {nom}"},
    "son_tout": {"fr": "tout", "en": "all"},
    "son_sans_musique": {"fr": "sans musique", "en": "no music"},
    "son_effets": {"fr": "effets seuls", "en": "effects only"},
    "son_aucun": {"fr": "coupé", "en": "off"},
    "retour": {"fr": "Retour", "en": "Back"},

    # ---- Listes tutoriels / scénarios
    "tutoriels_titre": {"fr": "TUTORIELS : une mécanique à la fois",
                        "en": "TUTORIALS: one skill at a time"},
    "scenarios_titre": {"fr": "SCÉNARIOS : rejoue les grandes missions",
                        "en": "SCENARIOS: replay the great missions"},
}

# Langue imposée par la variable d'environnement (tests, captures) — même
# convention que AGENCE_ECRAN. None tant qu'on ne l'a pas lue.
_imposee = None
_detectee = None


def _langue_systeme():
    """Langue du système : "fr" si elle commence par fr, "en" sinon.

    Le jeu naît en français : toute locale inconnue (ou Android sans locale
    lisible) part en anglais, la langue la plus utile pour le monde entier.
    """
    global _detectee
    if _detectee is None:
        brute = os.environ.get("LC_ALL") or os.environ.get("LANG") or ""
        if not brute:
            try:
                import locale
                brute = locale.getdefaultlocale()[0] or ""
            except (ValueError, OSError):
                brute = ""
        _detectee = "fr" if brute.lower().startswith("fr") else "en"
    return _detectee


def langue_active():
    """Le code de langue effectivement utilisé ("fr" ou "en")."""
    global _imposee
    if _imposee is None:
        _imposee = os.environ.get("AGENCE_LANGUE") or ""
    if _imposee in ("fr", "en"):
        return _imposee
    from . import reglages
    return reglages.LANGUE or _langue_systeme()


def definir_langue(code):
    """Change la langue du joueur ("fr", "en" ou "" pour la langue du système)."""
    from . import reglages
    reglages.changer_langue(code)


def t(cle, **params):
    """Texte demandé dans la langue active ; paramètres injectés par nom.

    Une clé absente de TOUT renvoie la clé elle-même : visible en jouant,
    attrapée par tests/test_textes.py.
    """
    entree = TOUT.get(cle)
    if entree is None:
        return cle
    texte = entree.get(langue_active()) or entree["fr"]
    if params:
        texte = texte.format(**params)
    return texte
