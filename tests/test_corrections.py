# -*- coding: utf-8 -*-
"""Corrections de l'audit de novembre 2026 : un test par bug corrigé.

    python tests/test_corrections.py

Chaque test reproduit la situation qui faisait planter (ou mentir) le jeu avant
la correction : ils doivent rester verts, ils gardent les bugs enterrés.
"""
import json
import os
import sys
import tempfile

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ["AGENCE_LANGUE"] = "fr"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from math import hypot, sqrt
import pygame

import main as jeu_main
from jeu import hud, pilote, reglages, sauvegarde, textes, triche
from jeu import manoeuvre as mod_manoeuvre
from jeu.orbite import Orbite
from jeu.pieces import MODELES
from jeu.rendu import disque, _ombre_nuit
from jeu.tutoriel import PAR_ID, Tutoriel
from jeu.univers import Univers

DT = 1 / 60.0

_APP = {}


def app_():
    if "app" not in _APP:
        _APP["app"] = jeu_main.Application(tactile=False)
    return _APP["app"]


def modele(nom):
    return next(c for n, d, c in MODELES if n == nom)


def sur_orbite(u, v, alt=200_000.0):
    """Téléporte le vaisseau sur une orbite ronde, sur rails."""
    c = v.corps
    r = c.R + alt
    vit = sqrt(c.mu / r)
    v.x, v.y, v.vx, v.vy = r, 0.0, 0.0, vit
    v.mode = "rails"
    v.gaz = 0.0
    v.orbite = Orbite(v.x, v.y, v.vx, v.vy, c.mu, u.t)
    v.cache_etat = (None, None)
    u._predire(v)
    return v


def univers_(plan=None, nom="Hermès"):
    u = Univers(bac_a_sable=True)
    u.actif = u.lancer(nom, plan if plan is not None else modele("Hermès"))
    return u


# ------------------------------------------------------------------ pilote
def test_pilote_noeud_deja_commence():
    """Un nœud dont la combustion a commencé à la main ne fait plus planter le pilote."""
    u = univers_()
    v = u.actif
    sur_orbite(u, v)
    assert pilote.planifier_circularisation(u, v, silencieux=True) and v.noeud is not None
    n = v.noeud
    n.commencer(mod_manoeuvre.impulsion(v, n))     # burn lancé à la main, puis pilote branché
    u.lancer_pilote(pilote.ExecuterNoeud())
    for _ in range(120):                           # plantait en TypeError avant la correction
        u.avancer(DT)


def test_lancer_pilote_zero_rcs():
    """Brancher le pilote efface l'ordre RCS résiduel (sinon l'amarrage auto dérive)."""
    u = univers_()
    u.commandes.avant = 1.0                        # le joueur tenait une touche de translation
    u.commandes.cote = -0.5
    u.lancer_pilote(pilote.ExecuterNoeud())
    assert u.commandes.avant == 0.0 and u.commandes.cote == 0.0


def test_noeud_delta_v_nul():
    """Un nœud réglé à Δv nul disparaît dès que le moteur pousse, au lieu de rester à vie."""
    u = univers_()
    v = u.actif
    sur_orbite(u, v)
    v.noeud = mod_manoeuvre.Manoeuvre(u.t, 0.0, 0.0)
    v.gaz = 1.0                                    # n'importe quelle poussée déclenche le nœud
    for _ in range(60):
        u.avancer(DT)
        if v.noeud is None:
            break
    assert v.noeud is None, "le nœud à Δv nul n'a jamais été consommé"


# ------------------------------------------------------------------ triche
def test_triche_orbite_re_predire():
    """« Mise en orbite » sur rails relance la prédiction : trajectoire et événements reviennent."""
    u = univers_()
    v = u.actif
    sur_orbite(u, v)
    triche.mettre_en_orbite(u, v)
    for _ in range(120):
        u.avancer(DT)
    assert v.troncons, "plus de trajectoire après la mise en orbite (troncons vides)"
    assert v.mode == "rails"


def test_rembobinage_garde_carriere():
    """Revenir 30 s en arrière ne rejoue pas les missions (primes en double) et garde les fonds."""
    u = univers_()
    u.missions_faites.add("premier_vol")
    u.fonds = 12345.0
    h = triche.Historique()
    h.enregistrer(u, 0.0)                          # une photo de la partie
    u.avancer(DT * 60)
    u.missions_faites = set()                      # le rembobinage repart d'un univers plus ancien
    u.fonds = 0.0
    nouveau = h.revenir(u)
    assert nouveau is not None
    assert "premier_vol" in nouveau.missions_faites, "mission refaite après un retour 30 s"
    assert nouveau.fonds >= 12345.0, "fonds perdus après un retour 30 s"


# ------------------------------------------------------------------ univers
def test_rails_pendant_boosters():
    """Réservoir central vide + boosters allumés : le vol reste en physique (boosters actifs)."""
    u = Univers(bac_a_sable=True)
    v = u.lancer("Repro", ["capsule", "decoupleur",
                           ["reservoir_m", ["decoupleur_radial", "coiffe", "reservoir_xxl", "titan"]],
                           "mistral"])
    sur_orbite(u, v, alt=400_000.0)
    v.mode = "physique"
    v.gaz = 1.0
    for p in v.reservoirs_actifs():
        p.carburant = 0.0                          # seul le carburant des boosters reste
    restant = v.carburant_boosters()[0]
    for _ in range(30):
        u.avancer(DT)
    assert v.mode == "physique", "bascule sur rails alors que les boosters brûlent"
    assert v.carburant_boosters()[0] < restant, "boosters figés (plus de consommation)"


def test_separation_masses_boosters():
    """Séparation d'étage avec boosters : la masse se conserve, sans « téléportation »."""
    u = Univers(bac_a_sable=True)
    v = u.lancer("Repro", ["capsule", "decoupleur",
                           ["reservoir_l", ["decoupleur_radial", "coiffe", "reservoir_l", "mistral"]],
                           "mistral"])
    sur_orbite(u, v)
    m_totale = v.geometrie().masse
    x0, y0, vx0, vy0 = u.etat(v)
    autre = u._scinder(v, 2, 1.2)                  # coupe entre le découpleur et l'étage à boosters
    assert autre is not None
    morceaux = [v, autre]
    m_separee = sum(w.geometrie().masse for w in morceaux)
    assert abs(m_separee - m_totale) < 1.0, \
        "séparation : %.0f kg après coup au lieu de %.0f kg (boosters mal comptés)" % (m_separee, m_totale)
    g = sum(w.geometrie().masse for w in morceaux)
    bx = sum(w.geometrie().masse * w.x for w in morceaux) / g
    by = sum(w.geometrie().masse * w.y for w in morceaux) / g
    assert hypot(bx - x0, by - y0) < 1.0, "le barycentre a sauté à la séparation"
    # quantité de mouvement conservée : l'impulsion de séparation est interne,
    # elle ne doit pas créer de recul d'ensemble
    px = sum(w.geometrie().masse * w.vx for w in morceaux)
    py = sum(w.geometrie().masse * w.vy for w in morceaux)
    assert hypot(px - vx0 * m_totale, py - vy0 * m_totale) < 1.0, \
        "la séparation a créé du recul d'ensemble (boosters mal pesés)"


# ------------------------------------------------------------------ interface
def test_hangar_quitte_tuto_de_vol():
    """La bulle d'un tuto de vol ne suit pas le joueur au hangar (celle du hangar, oui)."""
    a = app_()
    a.tuto = Tutoriel(PAR_ID["lune"])
    a.aller_hangar()
    assert a.tuto is None, "le tuto de vol continue au hangar"
    a.tuto = Tutoriel(PAR_ID["hangar"])
    a.aller_hangar()
    assert a.tuto is not None, "le tuto du hangar a été perdu en y allant"
    a.tuto = None


def test_amarrage_cles_brutes():
    """lignes_amarrage renvoie des clés non traduites : le filtre tactile peut les reconnaître."""
    u = univers_(["port", "capsule"], "Nous")
    v = u.actif
    sur_orbite(u, v, alt=100_000.0)
    v.mode = "physique"
    cible = u.lancer("Cible", ["port", "capsule"])
    cible.x, cible.y = v.x + 50.0, v.y
    cible.vx = cible.vy = 0.0
    cible.mode = "physique"
    cible.cache_etat = (None, None)
    u.cible = cible
    lignes = hud.lignes_amarrage(u, v)
    assert lignes, "aucune ligne d'amarrage affichée (aide au docking)"
    cles = {nom for nom, _, _ in lignes}
    attendues = {"Distance au port", "Écart latéral", "Alignement"}
    assert attendues <= cles, "clés d'amarrage introuvables pour le filtre tactile : %s" % (attendues - cles)
    assert cles <= set(textes.TOUT), "clé d'amarrage absente du dictionnaire : %s" % (cles - set(textes.TOUT))


def test_boutons_sas_petit_ecran():
    """Les boutons SAS restent dans la fenêtre, même en 400 px de large."""

    class Cam:
        mode = "auto"

        def hors_vaisseau(self, u):
            return False

    class Scene:                                   # le minimum requis par Hud
        cam = Cam()

        def ouvrir(self, quoi):
            pass
        basculer_rcs = changer_reference = changer_camera = recuperer = recentrer = prendre_photo = ouvrir

    u = univers_()
    scene = Scene()
    h = hud.Hud(scene)
    h._construire_boutons(u, 400, 300)             # remplit h.boutons
    for b in h.boutons:
        x, y, l, hb = b.rect
        assert x >= 0 and y >= 0 and x + l <= 400 and y + hb <= 300, \
            "bouton hors écran en 400x300 : %s (%d, %d, %d, %d)" % (b.libelle, x, y, l, hb)


def test_disque_immense():
    """disque() ne divise plus par zéro sur les grands écrans (r ≈ demi-diagonale)."""
    surf = pygame.Surface((2560, 1600))
    L, H = surf.get_size()
    demi = hypot(L, H) / 2
    disque(surf, (255, 0, 0), L / 2, H / 2, demi)          # r = demi : cas limite exact
    disque(surf, (0, 255, 0), L / 2 + 1e-9, H / 2, demi + 1e-9)


def test_ombre_grande_planete():
    """L'ombre de nuit couvre tout le limbe, même pour un corps affiché en 1000 px de rayon."""
    surf = pygame.Surface((1600, 900))
    _ombre_nuit(surf, 800, 450, 1000.0, 0.0)               # rognait avant la correction
    # le cache d'ombres respecte son budget mémoire (les grosses ombres sont chères)
    from jeu.rendu import _OMBRES, RAYON_GRAND_CERCLE
    for k in range(30):
        _ombre_nuit(surf, 800, 450, 1000.0, 0.7 * k)
    pixels = sum(o.get_width() * o.get_height() for o in _OMBRES.values())
    plafond = 12_000_000 + 4 * (2 * RAYON_GRAND_CERCLE + 32) ** 2
    assert pixels <= plafond, "cache d'ombres hors budget : %d px" % pixels
    assert len(_OMBRES) < 30, "aucune éviction du cache d'ombres"


def test_reglages_corrompus():
    """Un reglages.json faux (types inattendus) ne fait pas boucler le jeu au démarrage."""
    with tempfile.TemporaryDirectory() as tmp:
        chemin = os.path.join(tmp, "reglages.json")
        with open(chemin, "w", encoding="utf-8") as f:
            f.write('{"aides": "oui", "son": 42, "langue": ["fr"], "tutos": "x", "triche": []}')
        sauve_chemin = reglages._chemin
        reglages._chemin = lambda: chemin
        try:
            reglages.charger()
            assert reglages.SON == "tout", "son corrompu accepté tel quel"
            assert isinstance(reglages.TUTOS_FAITS, (list, set, tuple))
        finally:
            reglages._chemin = sauve_chemin


def test_ecriture_reglages_atomique():
    """Écrire les réglages ne laisse rien traîner (pas de .tmp à moitié écrit)."""
    with tempfile.TemporaryDirectory() as tmp:
        chemin = os.path.join(tmp, "reglages.json")
        sauve_chemin = reglages._chemin
        reglages._chemin = lambda: chemin
        try:
            reglages.changer_langue("en")                  # passe par l'écriture
        finally:
            reglages._chemin = sauve_chemin
        with open(chemin, encoding="utf-8") as f:
            assert json.load(f)["langue"] == "en"
        restes = [f for f in os.listdir(tmp) if f != "reglages.json"]
        assert not restes, "fichiers résiduels après écriture des réglages : %s" % restes


def test_sauvegarde_illisible():
    """Une sauvegarde fausse (JSON lisible, champ d'un mauvais type) est refusée comme ValueError."""
    u = univers_()
    d = sauvegarde.univers_vers_dict(u)
    d["vaisseaux"] = 3                             # une liste remplacée par un entier
    with tempfile.TemporaryDirectory() as tmp:
        chemin = os.path.join(tmp, "partie.json")
        with open(chemin, "w", encoding="utf-8") as f:
            json.dump(d, f)
        try:
            sauvegarde.charger(chemin)
        except ValueError:
            pass                                   # refus propre attendu
        # (avant la correction : TypeError, non attrapé par le menu « Continuer »)


def test_separe_de_sauvegarde():
    """Le lien de séparation récente passe le tour de la sauvegarde sans erreur."""
    u = univers_(["capsule", "decoupleur", "reservoir_m", "alize"])
    v = u.actif
    sur_orbite(u, v)
    v.mode = "physique"
    v.gaz = 1.0
    u.separer_etage()
    autre = next(w for w in u.vaisseaux if w is not v)
    v.separe_de, autre.separe_de = autre.id, v.id
    d = sauvegarde.univers_vers_dict(u)
    w = sauvegarde.dict_vers_univers(d)
    paire = {x.id for x in w.vaisseaux}
    liens = [x.separe_de for x in w.vaisseaux if x.separe_de is not None]
    assert liens, "separe_de perdu dans la sauvegarde"
    assert all(i in paire for i in liens), "separe_de pointe sur un id inexistant après le tour"


def test_verifier_paquet_tri_versions():
    """Les dossiers build-tools « 9.0.0 » et « 36.0.0 » se trient numériquement."""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "outils"))
    from verifier_paquet import cle_version_buildtools
    assert cle_version_buildtools("/sdk/build-tools/36.0.0/aapt2") > \
        cle_version_buildtools("/sdk/build-tools/9.0.0/aapt2")
    assert cle_version_buildtools("/sdk/build-tools/10.0.0/aapt2") > \
        cle_version_buildtools("/sdk/build-tools/9.0.0/aapt2")


def test_apollo13_transfert_sms():
    """Apollo 13 : le module de service vidé peut être rempli depuis Aquarius (panneau Transfert)."""
    from jeu.vaisseau import nom_section
    import main as jeu_main2
    app13 = jeu_main2.Application(tactile=False)
    from jeu import tutoriel as tut
    tut.demarrer(app13, "apollo13")
    u13 = app13.univers
    a = u13.actif
    sections = a.sections_reservoirs()
    # la section du module de service d'Odyssey est vidée par le scénario mais listée
    i_sms = next(i for i, s in enumerate(sections)
                 if any(p.proprietaire == "Odyssey" for p in s) and any(p.m.carburant > 0 for p in s))
    assert sum(p.carburant for p in sections[i_sms]) == 0.0, "l'explosion n'a pas vidé le module de service"
    carb, mono = a.remplir(i_sms)
    assert carb > 1000.0, "« Remplir » n'a pas puisé dans les réservoirs d'Aquarius (%.0f kg)" % carb
    assert sum(p.carburant for p in sections[i_sms]) > 1000.0, "le module de service est resté vide"
    assert nom_section(sections[i_sms]).startswith("Odyssey"), "la section trouvée n'est pas celle d'Odyssey"


def test_drapeaux_fusionnes_amarrage():
    """L'amarrage fusionne les drapeaux : un seul vaisseau peut porter tout le Grand Tour."""
    u = univers_()
    v = u.actif
    sur_orbite(u, v)
    autre = u.lancer("Compagnon", ["capsule", "reservoir_m", "alize"])
    autre.x, autre.y = v.x + 5.0, v.y
    autre.vx = autre.vy = 0.0
    autre.mode = "physique"
    autre.cache_etat = (None, None)
    autre.drapeaux |= {"soi:Jupiter", "orbite:Mars"}
    u.cible = autre
    u._amarrer(v, autre, "haut", "haut", u.etat(v), u.etat(autre))
    assert "soi:Jupiter" in v.drapeaux and "orbite:Mars" in v.drapeaux, \
        "les drapeaux de l'amarré n'ont pas été fusionnés"
    from jeu.missions import _grand_tour
    v.drapeaux |= {"soi:Saturne", "soi:Uranus", "soi:Neptune"}
    assert _grand_tour(u, v), "le Grand Tour ne reconnaît pas les drapeaux fusionnés"
    # la séparation garde les drapeaux sur les deux moitiés (pas de perte)
    morceau = u._scinder(v, 1, 0.4)
    assert "soi:Jupiter" in morceau.drapeaux, "les drapeaux sont perdus à la séparation"


def test_barre_temps_43():
    """En 4:3 (720 px), la barre du temps ne couvre pas le panneau de vol."""
    class Cam:
        mode = "auto"
        def hors_vaisseau(self, u):
            return False

    class Scene:
        cam = Cam()
        def ouvrir(self, quoi):
            pass
        basculer_rcs = changer_reference = changer_camera = recuperer = recentrer = temps_normal = prendre_photo = ouvrir

    u = univers_()
    scene = Scene()
    from jeu.hud_tactile import HudTactile
    h = HudTactile(scene)
    h._construire_boutons(u, 720, 540)
    assert h.rect_temps.left >= 30 + 250, \
        "la barre du temps commence à %d, dans le panneau de vol" % h.rect_temps.left


def test_pas_de_cles_dupliquees():
    """Le dictionnaire de textes n'a plus de clé écrite deux fois (la deuxième écrasait la première)."""
    import ast
    chemin = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "jeu", "textes.py")
    arbre = ast.parse(open(chemin, encoding="utf-8").read())
    # le dict de premier niveau de « TOUT = { ... } » : une clé écrite deux fois s'y écrasait
    for noeud in arbre.body:
        if isinstance(noeud, ast.Assign) and any(getattr(t, "id", None) == "TOUT" for t in noeud.targets):
            vues = set()
            for k in noeud.value.keys:
                if isinstance(k, ast.Constant) and isinstance(k.value, str):
                    assert k.value not in vues, "clé de texte dupliquée dans textes.py : %r" % k.value
                    vues.add(k.value)
            break
    assert "conseil_prefixe" in textes.TOUT, "la clé conseil_prefixe a disparu"
    assert "Pas de chargement pendant un tutoriel" in textes.TOUT


# ------------------------------------------------------------------ lancement
if __name__ == "__main__":
    echecs = []
    for nom, f in sorted(globals().items()):
        if nom.startswith("test_") and callable(f):
            try:
                f()
                print("   ok   %s" % nom)
            except Exception as e:
                echecs.append(nom)
                print("   ÉCHEC %s : %r" % (nom, e))
    if echecs:
        print("--- corrections : %d échec(s) : %s" % (len(echecs), ", ".join(echecs)))
        sys.exit(1)
    print("--- corrections : OK")
