# -*- coding: utf-8 -*-
"""Réussites : jalons cochés d'une partie à l'autre et compteurs de carrière."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
from math import sqrt
from jeu.orbite import Orbite
from jeu.univers import Univers
from jeu import jalons, reglages
from jeu.vaisseau import construire


DT = 1.0 / 30.0


def univers_(plan=None):
    """Un univers bac à sable avec un vaisseau actif, et des réussites vierges."""
    reglages.JALONS_FAITS = []
    reglages.STATS = {}
    u = Univers(bac_a_sable=True)
    u.actif = u.lancer("Pionnier", plan if plan is not None else ["capsule"])
    return u


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


def test_jalon_pose_pas_de_tir_vs_terrain():
    """Être sur le pas de tir (mode « pose ») ne compte pas comme un atterrissage."""
    u = univers_()
    v = u.actif
    assert v.mode == "pose"
    jalons.verifier(u)
    assert "pose_terre" not in reglages.JALONS_FAITS, "le pas de tir n'est pas un posé"
    v.drapeaux.add("pose:Terre")            # un vrai contact pose ce drapeau (univers._toucher)
    jalons.verifier(u)
    assert "pose_terre" in reglages.JALONS_FAITS
    assert any("★" in m[0] for m in u.messages), "le jalon doit être annoncé en vol"
    n = len(u.messages)
    jalons.verifier(u)
    assert len(u.messages) == n, "un jalon déjà fait ne s'annonce pas deux fois"


def test_jalon_haut_et_evasion():
    """Dépasser 10 km puis quitter la sphère terrestre (changement de corps)."""
    u = univers_()
    v = u.actif
    v.mode = "physique"
    v.x, v.y = v.corps.R + 11_000.0, 0.0
    jalons.verifier(u)
    assert "haut" in reglages.JALONS_FAITS
    assert "evasion" not in reglages.JALONS_FAITS
    v.corps = u.par_nom["Lune"]             # changer de corps = sortie de SOI (univers.py)
    jalons.verifier(u)
    assert "evasion" in reglages.JALONS_FAITS


def test_jalon_proche():
    """À moins de 50 m d'un vaisseau ciblé (les missions exigent 200 m de la station)."""
    u = univers_()
    v = u.actif
    autre = construire("Autre", ["capsule"], u.terre)
    autre.mode = "physique"
    u.vaisseaux.append(autre)
    u.cible = autre
    v.mode = "physique"
    v.x, v.y = 100.0, 0.0
    autre.x, autre.y = 130.0, 0.0           # 30 m d'écart
    jalons.verifier(u)
    assert "proche" in reglages.JALONS_FAITS
    u.cible = u.terre                       # un corps ne compte pas
    reglages.JALONS_FAITS.remove("proche")
    jalons.verifier(u)
    assert "proche" not in reglages.JALONS_FAITS


def test_stats_lancement_etage_crash():
    """Un lancement, une séparation et une destruction incrémentent les compteurs."""
    u = univers_(["reservoir_m", "decoupleur", "reservoir_m", "mistral"])
    assert reglages.STATS.get("lancements") == 1
    v = u.actif
    v.mode = "physique"
    u.separer_etage()
    assert reglages.STATS.get("etages") == 1
    u._detruire(v, "essai")
    assert reglages.STATS.get("crashs") == 1


def test_stats_pose_et_amarrage():
    """Un contact doux compte comme un atterrissage, une fusion comme un amarrage."""
    u = univers_()
    v = u.actif
    c = u.terre
    w = c.vitesse_rotation
    v.mode = "physique"
    v.angle = 0.0
    u._toucher(v, c.R, 0.0, 0.0, w * c.R, u.t)      # vitesse nulle par rapport au sol tournant
    assert v.mode == "pose" and "pose:Terre" in v.drapeaux
    assert reglages.STATS.get("poses") == 1

    reglages.STATS = {}
    u2 = Univers(bac_a_sable=True, avec_station=False)
    a = construire("A", ["port", "capsule"], u2.terre)
    b = construire("B", ["port", "capsule"], u2.terre)
    u2.vaisseaux += [a, b]
    u2._amarrer(a, b, "haut", "haut", (0.0, 0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 0.0))
    assert reglages.STATS.get("amarrages") == 1


def test_jalon_noeud_execute():
    """Consommer un nœud de manœuvre (même à Δv nul) coche le jalon."""
    from jeu import manoeuvre as mod_manoeuvre
    u = univers_(["capsule", "reservoir_m", "mistral"])     # il faut un moteur pour brûler
    v = sur_orbite(u, u.actif)
    v.noeud = mod_manoeuvre.Manoeuvre(u.t, 0.0, 0.0)
    v.gaz = 1.0
    for _ in range(60):
        u.avancer(DT)
        if v.noeud is None:
            break
    assert v.noeud is None, "le nœud à Δv nul aurait dû être consommé"
    assert "noeud" in v.drapeaux, "consommer un nœud doit poser le drapeau"
    jalons.verifier(u)
    assert "noeud" in reglages.JALONS_FAITS


def test_jalons_nouveaux():
    """Drapeau planté, photo, poses lointaines, constellation et trois mondes."""
    import jeu.sauvegarde as sauvegarde
    import tempfile
    from jeu import album
    from jeu.menu import SceneMenu
    import pygame

    u = univers_()
    # drapeau : au moins un drapeau planté quelque part
    assert not any(j.ident == "drapeau" and j.test(u, u.actif) for j in jalons.JALONS)
    u.drapeaux_sol.append({"corps": "Lune", "longitude": 0.5, "t": 0.0})
    jalons.verifier(u)
    assert "drapeau" in reglages.JALONS_FAITS
    # photo : une photo dans l'album (dossier de sauvegarde redirigé)
    tmp = tempfile.TemporaryDirectory()
    sauvegarde.chemin_sauvegarde = lambda: os.path.join(tmp.name, "sauvegarde.json")
    surf_photo = pygame.Surface((100, 80))
    surf_photo.fill((10, 10, 40))
    album.prendre(surf_photo, "pose", "Lune")
    jalons.verifier(u)
    assert "photo" in reglages.JALONS_FAITS
    # poses lointaines : Io, Europe, Ganymède, Pluton
    v = u.actif
    for ident, corps in (("io", "Io"), ("europe", "Europe"),
                         ("ganymede", "Ganymède"), ("pluton", "Pluton")):
        reglages.JALONS_FAITS = [j for j in reglages.JALONS_FAITS if j != ident]
        v.drapeaux.add("pose:" + corps)
        jalons.verifier(u)
        assert ident in reglages.JALONS_FAITS, "jalon " + ident + " non coché"
    # constellation : trois satellites (sonde + panneaux) en orbite terrestre
    reglages.JALONS_FAITS = [j for j in reglages.JALONS_FAITS if j != "constellation"]
    for k in range(3):
        s = construire("Sat%d" % k, ["sonde", "panneaux"], u.terre)
        s.corps = u.terre
        u.vaisseaux.append(s)
        sur_orbite(u, s)
    jalons.verifier(u)
    assert "constellation" in reglages.JALONS_FAITS, "3 satellites : constellation attendue"
    # trois_mondes : Mercure + Vénus + Mars visités par le même vaisseau
    v.drapeaux |= {"soi:Mercure", "soi:Vénus", "soi:Mars"}
    jalons.verifier(u)
    assert "trois_mondes" in reglages.JALONS_FAITS


def test_page_reussites_tient_dans_lecran():
    """21 jalons sur 3 colonnes : page Réussites affichée en 4:3 et 20:9, boutons dans l'écran."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    if not pygame.get_init():
        pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((200, 100))
    from jeu.menu import SceneMenu

    class App:
        def quitter(self):
            pass
        def continuer(self):
            pass
        def nouvelle_partie(self, sable):
            pass

    for taille in ((720, 540), (1200, 540)):
        sc = SceneMenu(App(), vue="reussites")
        surf = pygame.Surface(taille).convert()
        sc.dessiner(surf)
        for b in sc.boutons:
            assert b.rect.bottom <= taille[1] and b.rect.top >= 0, \
                "bouton Réussites hors écran en %s : %s" % (taille, b.rect)


def test_reglages_persiste_et_relit():
    """Jalons et stats survivent à un aller-retour reglages.json, avec valeurs sûres."""
    reglages.JALONS_FAITS = ["mercure", 7]
    reglages.STATS = {"lancements": 3, "bete": "x"}
    reglages._ecrire()
    reglages.JALONS_FAITS, reglages.STATS = [], {}
    reglages.charger()
    assert reglages.JALONS_FAITS == ["mercure"]      # le 7 non textuel est écarté
    assert reglages.STATS == {"lancements": 3}       # la valeur non numérique aussi


def test_tutoriel_ne_compte_pas():
    """Pendant un tutoriel, ni stats ni jalons."""
    reglages.JALONS_FAITS, reglages.STATS = [], {}
    u = Univers(bac_a_sable=True)
    u.tutoriel = "orbite"
    u.actif = u.lancer("Pionnier", ["capsule"])      # un tutoriel qui lance : pas de stat
    v = u.actif
    v.mode = "physique"
    v.x, v.y = v.corps.R + 11_000.0, 0.0
    u._detruire(v, "essai")
    jalons.verifier(u)                               # appelé quand même par _periodique :
    assert reglages.STATS == {}, "les stats d'un tutoriel ne doivent pas compter"
    assert "haut" not in reglages.JALONS_FAITS       # le vrai filtrage est dans univers._periodique


if __name__ == "__main__":
    for nom, f in sorted(list(globals().items())):
        if nom.startswith("test_") and callable(f):
            f()
            print("OK  ", nom)
    print("Tous les tests passent.")
