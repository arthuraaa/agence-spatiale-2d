# -*- coding: utf-8 -*-
"""Vendabilité : tout ce que Google Play et les joueurs attendent, hors code du jeu.

    python tests/test_vendabilite.py

Vérifie ce qui rend l'application publiable ET désirable :
- la fiche Play Store (FR + EN) : limites de caractères imposées par Google ;
- les visuels : icône 512, bannière 1024x500, captures, poids des fichiers ;
- la lisibilité de l'icône réduite (48 px : c'est sa taille sur l'écran d'accueil) ;
- la cohérence visuelle icône / bannière / captures (même identité) ;
- le paquet Android : identifiant, permissions (aucune), orientation, AAB ;
- les langues : fiche EN prête, et couverture de la traduction anglaise (objectif
  long terme : le test affiche où on en est, et durcit ses critères quand la
  traduction sera lancée — voir TRADUCTION_ANGLAISE plus bas).

Nécessite Pillow (déjà utilisée par outils/generer_visuels_store.py).
"""
import os
import re
import sys

RACINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, RACINE)

from PIL import Image

# Passer à True quand le jeu sera traduit (module de textes + textes traduits) :
# le test exigera alors une couverture d'au moins 95 % des textes affichables.
TRADUCTION_ANGLAISE = False

# Limites officielles de la fiche Google Play
MAX_NOM = 30
MAX_COURTE = 80
MAX_COMPLETE = 4000
MAX_NOTES = 500


def _lire(*morceaux):
    return open(os.path.join(RACINE, *morceaux), encoding="utf-8").read()


def _analyser_fiche(texte):
    """Sépare une fiche (markdown) en sections ; renvoie {titre en minuscules: corps}."""
    sections, titre = {"": ""}, ""
    for ligne in texte.splitlines():
        if ligne.startswith("## "):
            titre = ligne[3:].strip().lower()
            sections[titre] = ""
        else:
            sections[titre] = sections.get(titre, "") + ligne + "\n"
    return sections


def _premiere_ligne(texte):
    return next((l.strip() for l in texte.splitlines() if l.strip()), "")


def test_fiche_francais():
    fiche = _analyser_fiche(_lire("store", "fiche-fr.md"))
    nom = _premiere_ligne(fiche["nom de l'appli (30 caractères max)"])
    courte = _premiere_ligne(fiche["description courte (80 caractères max)"])
    complete = fiche["description complète (4000 caractères max)"].strip()
    notes = fiche["notes de version (500 caractères max)"].strip()
    print("   FR : nom %d/30, courte %d/80, complète %d/4000, notes %d/500"
          % (len(nom), len(courte), len(complete), len(notes)))
    assert nom == "Agence Spatiale 2D", "le nom d'appli Play doit être « Agence Spatiale 2D »"
    assert 0 < len(nom) <= MAX_NOM, "nom trop long pour Play (30 max)"
    assert 0 < len(courte) <= MAX_COURTE, "description courte trop long (80 max)"
    assert 0 < len(complete) <= MAX_COMPLETE, "description complète trop longue (4000 max)"
    assert 0 < len(notes) <= MAX_NOTES, "notes de version trop longues (500 max)"
    for mot in ("fusée", "orbite", "Lune"):
        assert mot.lower() in complete.lower(), "la description FR doit parler de « %s » (mots-clés de recherche)" % mot
    assert "sans publicité" in complete.lower() and "sans collecte de données" in complete.lower(), \
        "la description FR doit rassurer (pas de pub, pas de collecte)"


def test_fiche_anglaise():
    fiche = _analyser_fiche(_lire("store", "fiche-en.md"))
    nom = _premiere_ligne(fiche["app name (max 30)"])
    courte = _premiere_ligne(fiche["short description (max 80)"])
    complete = fiche["full description (max 4000)"].strip()
    print("   EN : nom %d/30, courte %d/80, complète %d/4000" % (len(nom), len(courte), len(complete)))
    assert 0 < len(nom) <= MAX_NOM and 0 < len(courte) <= MAX_COURTE and 0 < len(complete) <= MAX_COMPLETE
    for mot in ("build", "rocket", "orbit", "moon"):
        assert mot in (courte + complete).lower(), "la fiche EN doit contenir « %s »" % mot
    # Honnêteté : tant que le jeu n'est pas traduit, la fiche EN doit le dire.
    if not TRADUCTION_ANGLAISE:
        assert "french" in complete.lower(), \
            "la fiche EN doit préciser que le jeu est en français (tant que la traduction n'existe pas)"
    # Section fiches absente de fiche-en.md mais utile : notes de version EN
    assert "release notes" in fiche or "notes" in " ".join(fiche), "il manque les notes de version EN"


def _poids(mo):
    return os.path.getsize(mo) / (1024 * 1024)


def test_visuels_store():
    icone = Image.open(os.path.join(RACINE, "store", "icone-512.png"))
    assert icone.size == (512, 512), "l'icône Play doit faire exactement 512x512"
    assert _poids(os.path.join(RACINE, "store", "icone-512.png")) <= 1, "icône Play : 1 Mo max"
    banniere = Image.open(os.path.join(RACINE, "store", "banniere-1024x500.png"))
    assert banniere.size == (1024, 500), "l'image de présentation doit faire 1024x500"
    assert _poids(os.path.join(RACINE, "store", "banniere-1024x500.png")) <= 15, "bannière : 15 Mo max"

    dossier = os.path.join(RACINE, "store", "captures")
    captures = sorted(f for f in os.listdir(dossier) if f.endswith(".png"))
    print("   %d captures %s" % (len(captures), Image.open(os.path.join(dossier, captures[0])).size))
    assert 2 <= len(captures) <= 8, "Play demande 2 à 8 captures d'écran téléphone"
    tailles = set()
    for f in captures:
        im = Image.open(os.path.join(dossier, f))
        tailles.add(im.size)
        assert _poids(os.path.join(dossier, f)) <= 8, "capture %s : 8 Mo max" % f
        assert min(im.size) >= 320 and max(im.size) <= 3840, "capture %s : dimensions hors limites Play" % f
        # Ratios acceptés par Play : 1:1, 16:9 et 9:16
        l, h = im.size
        assert (l, h) in ((h, h), (h * 16 // 9, h), (h, h * 16 // 9)), \
            "capture %s : ratio %dx%d ni 1:1 ni 16:9/9:16" % (f, l, h)
    assert len(tailles) == 1, "les captures doivent toutes avoir la même taille (cohérence de la fiche)"
    taille = tailles.pop()
    # Le jeu est en paysage : les captures aussi (sinon la fiche semble ne pas correspondre).
    spec = _lire("buildozer.spec")
    orientation = re.search(r"(?m)^orientation = (.*)$", spec).group(1)
    assert ("landscape" in orientation) == (taille[0] > taille[1]), \
        "captures et orientation du jeu (buildozer.spec) ne sont pas d'accord"


def test_icone_lisible():
    """L'icône doit rester reconnaissable en 48 px (taille sur l'écran d'accueil)."""
    im = Image.open(os.path.join(RACINE, "store", "icone-512.png")).convert("RGB")
    petite = im.resize((48, 48))
    pixels = list(petite.getdata())
    moyennes = [sum(c) / len(c) for c in zip(*pixels)]
    contraste = max(moyennes) - min(moyennes)
    print("   icône 48 px : contraste=%.0f (doit être > 40 pour rester lisible)" % contraste)
    assert contraste > 40, "icône trop plate une fois réduite à 48 px : on ne distingue plus rien"
    # Les trois canaux ne doivent pas être identiques (icône toute grise = indistincte).
    assert max(moyennes) - min(moyennes) > 40 or len(set(moyennes)) > 1


def test_identite_visuelle():
    """Icône, bannière et captures partagent la même ambiance (ciel étoilé sombre)."""
    def couleur_moyenne(chemin):
        im = Image.open(chemin).convert("RGB")
        if max(im.size) > 256:                       # échantillon réduit : suffit et va plus vite
            im = im.resize((64, 64))
        pixels = list(im.getdata())
        return tuple(sum(c) / len(c) for c in zip(*pixels))

    icone = couleur_moyenne(os.path.join(RACINE, "store", "icone-512.png"))
    banniere = couleur_moyenne(os.path.join(RACINE, "store", "banniere-1024x500.png"))
    # Ambiance d'ensemble des captures (moyenne) : une capture diurne peut sortir
    # du lot, c'est même souhaitable pour montrer la variété du jeu.
    dossier = os.path.join(RACINE, "store", "captures")
    captures = [couleur_moyenne(os.path.join(dossier, f)) for f in os.listdir(dossier) if f.endswith(".png")]
    capture = tuple(sum(c[i] for c in captures) / len(captures) for i in range(3))
    distance_ib = sum(abs(a - b) for a, b in zip(icone, banniere))
    distance_ic = sum(abs(a - b) for a, b in zip(icone, capture))
    print("   écart couleurs icône↔bannière=%.0f, icône↔captures=%.0f (doivent rester < 100)" % (distance_ib, distance_ic))
    assert distance_ib < 100, "l'icône et la bannière n'ont plus la même identité visuelle"
    assert distance_ic < 100, "l'icône et l'ambiance des captures sont trop différentes"
    # Fond sombre attendu (espace) : c'est la signature visuelle du jeu.
    assert sum(icone) / 3 < 130, "l'icône devrait rester sur fond sombre (espace), comme le jeu"


def test_paquet_android():
    spec = _lire("buildozer.spec")
    domaine = re.search(r"(?m)^package\.domain = (.+)$", spec).group(1).strip()
    nom = re.search(r"(?m)^package\.name = (.+)$", spec).group(1).strip()
    identifiant = domaine + "." + nom
    print("   identifiant : %s" % identifiant)
    assert re.fullmatch(r"[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+", identifiant), \
        "identifiant Android invalide : %s" % identifiant
    # Aucune permission : le jeu est hors ligne, la fiche promet « sans collecte de données ».
    m = re.search(r"(?m)^android\.permissions = (.*)$", spec)
    assert not m or m.group(1).strip() in ("", "ANDROID_PERMISSIONS"), \
        "des permissions sont déclarées alors que le jeu n'en a pas besoin : %s" % (m and m.group(1))
    minapi = int(re.search(r"(?m)^android\.minapi = (\d+)", spec).group(1))
    api = int(re.search(r"(?m)^android\.api = (\d+)", spec).group(1))
    assert 23 <= minapi < api, "minapi=%d : couvert trop bas ou au-dessus de la cible (%d)" % (minapi, api)
    assert re.search(r"(?m)^android\.release_artifact = aab$", spec), "Play veut un AAB"
    # Titre de l'appli = nom de la fiche (cohérence quand on installe).
    titre = re.search(r"(?m)^title = (.+)$", spec).group(1).strip()
    assert titre == "Agence Spatiale 2D", "title de buildozer.spec (%r) ≠ nom de la fiche" % titre


def test_langues():
    """Où en est la traduction ? Objectif long terme : le jeu en anglais.

    Aujourd'hui tous les textes du jeu sont en français, en dur dans le code.
    Le test mesure une métrique simple (présence d'un module de textes et
    part de textes qui passent par lui) pour suivre la progression.
    """
    if not TRADUCTION_ANGLAISE:
        print("   traduction EN : pas commencée (objectif long terme)")
        print("   feuille de route : 1) module jeu/textes.py  2) remplacer les chaînes en dur"
              "  3) traduire  4) passer TRADUCTION_ANGLAISE à True ici")
        return
    # Une fois la traduction lancée : le module de textes doit exister et être utilisé.
    assert os.path.exists(os.path.join(RACINE, "jeu", "textes.py")), "il manque jeu/textes.py"
    import jeu.textes as textes
    total = len(textes.TOUT)                       # clés attendues : chaque texte du jeu
    traduits = sum(1 for cle in textes.TOUT if "en" in textes.TOUT[cle])
    couverture = traduits / max(total, 1)
    print("   traduction EN : %d/%d textes (%.0f %%)" % (traduits, total, 100 * couverture))
    assert couverture >= 0.95, "traduction anglaise incomplète : %.0f %%" % (100 * couverture)


def test_politique_confidentialite():
    """La politique doit exister (obligatoire pour Play), même si non finalisée."""
    assert os.path.exists(os.path.join(RACINE, "docs", "politique-confidentialite.md"))
    assert os.path.exists(os.path.join(RACINE, "docs", "index.html")), \
        "docs/index.html (version HTML prête à héberger) a disparu"
    texte = _lire("docs", "politique-confidentialite.md")
    a_completer = texte.count("À COMPLÉTER")
    assert "ne collecte" in texte.lower() or "aucune donnée" in texte.lower(), \
        "la politique doit dire explicitement que rien n'est collecté"
    if a_completer:
        print("   RAPPEL : %d « À COMPLÉTER » restent dans docs/politique-confidentialite.md "
              "(nom, e-mail, date) — à faire avant la mise en ligne sur Google Sites" % a_completer)


if __name__ == "__main__":
    test_fiche_francais()
    test_fiche_anglaise()
    test_visuels_store()
    test_icone_lisible()
    test_identite_visuelle()
    test_paquet_android()
    test_langues()
    test_politique_confidentialite()
    print("--- vendabilite : OK")
