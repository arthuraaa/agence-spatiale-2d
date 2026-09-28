# -*- coding: utf-8 -*-
"""
Garde-fous contre les plantages qu'on ne voit que sur téléphone.

1. Chaque « module.attribut » écrit dans le code doit exister vraiment. Python ne le vérifie
   qu'au moment où la ligne s'exécute : dans la version 1.3, `plateforme.ANDROID` (qui
   n'existait pas) ne plantait qu'au passage en arrière-plan d'Android. Lancé avec le Python
   et le pygame de l'APK (3.10 / 2.1.0), ce test repère aussi ce que cette version n'a pas.
2. Les événements d'arrière-plan (perte puis retour du focus) passent sans erreur,
   sur PC comme sur un Android simulé.
"""
import ast, importlib, os, sys
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
RACINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, RACINE)
import pygame


def _fichiers():
    yield os.path.join(RACINE, "main.py"), "main"
    for f in sorted(os.listdir(os.path.join(RACINE, "jeu"))):
        if f.endswith(".py"):
            yield os.path.join(RACINE, "jeu", f), "jeu." + f[:-3]


def _alias_de_modules(arbre, nom_module):
    """Noms locaux qui désignent un module (import x, from . import x, from jeu import x as y)."""
    paquet = nom_module.rsplit(".", 1)[0] if "." in nom_module else ""
    alias = {"pygame": pygame}
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            for n in noeud.names:
                if n.name.split(".")[0] in ("jeu", "pygame") and n.asname:
                    alias[n.asname] = importlib.import_module(n.name)
        elif isinstance(noeud, ast.ImportFrom):
            base = noeud.module or ""
            if noeud.level:
                base = paquet + ("." + base if base else "")
            if base.split(".")[0] not in ("jeu", "pygame"):
                continue
            for n in noeud.names:
                try:
                    alias[n.asname or n.name] = importlib.import_module(base + "." + n.name)
                except ImportError:
                    pass                                   # un nom (classe, fonction), pas un module
    return alias


def test_attributs_de_modules():
    manquants, vus = [], 0
    for chemin, nom in _fichiers():
        arbre = ast.parse(open(chemin, encoding="utf-8").read(), chemin)
        alias = _alias_de_modules(arbre, nom)
        for noeud in ast.walk(arbre):
            if not (isinstance(noeud, ast.Attribute) and isinstance(noeud.ctx, ast.Load)):
                continue
            chaine, n = [], noeud                          # a.b.c -> racine a, attributs [b, c]
            while isinstance(n, ast.Attribute):
                chaine.insert(0, n.attr)
                n = n.value
            if not isinstance(n, ast.Name) or n.id not in alias or len(chaine) != _profondeur(noeud):
                continue
            obj = alias[n.id]
            for attr in chaine:                            # on descend tant qu'on reste sur des modules
                if not hasattr(obj, attr):
                    manquants.append("%s:%d  %s.%s" % (os.path.basename(chemin), noeud.lineno, n.id, ".".join(chaine)))
                    break
                vus += 1
                obj = getattr(obj, attr)
                if not isinstance(obj, type(pygame)):
                    break
    print("   %d attributs de modules vérifiés (pygame %s)" % (vus, pygame.version.ver))
    assert not manquants, "attributs inexistants :\n" + "\n".join(manquants)


def _profondeur(noeud):
    """Longueur de la chaîne a.b.c complète (pour ne tester chaque chaîne qu'une fois, en entier)."""
    k, n = 0, noeud
    while isinstance(n, ast.Attribute):
        k += 1
        n = n.value
    return k


def test_arriere_plan():
    """Perte puis retour du focus : sur PC, et sur un Android simulé (où le son est suspendu)."""
    import main as jeu_main
    from jeu import plateforme
    perdu = getattr(pygame, "WINDOWFOCUSLOST", None)
    retrouve = getattr(pygame, "WINDOWFOCUSGAINED", None)
    if perdu is None:
        print("   (pygame sans événements de focus : rien à tester)")
        return
    vraie = plateforme.sur_android
    for android in (False, True):
        app = jeu_main.Application(tactile=True)
        plateforme.sur_android = (lambda: True) if android else vraie
        try:
            for scene in ("menu", "vol"):
                if scene == "vol":
                    app.nouvelle_partie(True)
                    app.scene.lancer()
                app.traiter(pygame.event.Event(perdu))
                app.traiter(pygame.event.Event(retrouve))
                app.scene.maj(1 / 60)
                app.scene.dessiner(app.ecran)
        finally:
            plateforme.sur_android = vraie
    for f in ("sauvegarde.json", "reglages.json"):
        chemin = os.path.join(RACINE, f)
        if os.path.exists(chemin):
            os.remove(chemin)
    print("   arrière-plan puis retour (menu et vol, PC et Android simulé) : OK")


if __name__ == "__main__":
    test_attributs_de_modules()
    test_arriere_plan()
    print("--- garde-fous : OK")
