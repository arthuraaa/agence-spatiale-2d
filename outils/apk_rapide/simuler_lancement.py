# -*- coding: utf-8 -*-
"""Lance le main.pyc extrait de l APK comme python-for-android (start.c), avec des doigts simulés.
Utilisé par verifier.py --lancer (Python 3.10 + pygame 2.1.0). Argument : le dossier extrait."""
import marshal, os, sys
app_dir = sys.argv[1]
os.environ.update(ANDROID_ARGUMENT=app_dir, ANDROID_PRIVATE=app_dir, ANDROID_APP_PATH=app_dir,
                  SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy", AGENCE_ECRAN="2400x1080")
os.chdir(app_dir)
import pygame
etapes = {20: "Bac à sable (tout débloqué)", 45: "LANCER"}
compteur, journal = [0], []
vraie_get = pygame.event.get

def doigt(app, pos, bas=True):
    L, H = app.ecran.get_size()
    return pygame.event.Event(pygame.FINGERDOWN if bas else pygame.FINGERUP, finger_id=1, touch_id=0,
                              x=pos[0] / L, y=pos[1] / H, dx=0.0, dy=0.0)

def get(*a, **k):
    compteur[0] += 1
    n = compteur[0]
    evs = vraie_get(*a, **k)
    app = sys._getframe(1).f_locals.get("self")           # l'Application qui tourne dans main.pyc
    sc = app.scene
    if n in etapes:
        boutons = list(getattr(getattr(sc, "hud", None), "boutons", [])) + list(sc.boutons)
        b = next(b for b in boutons if b.libelle == etapes[n])
        evs += [doigt(app, b.rect.center), doigt(app, b.rect.center, False)]
        journal.append("tape « %s » (%s)" % (etapes[n], type(sc).__name__))
    elif n in (10, 200):                                   # l'appli passe en arrière-plan...
        evs.append(pygame.event.Event(getattr(pygame, "WINDOWFOCUSLOST", pygame.USEREVENT)))
        journal.append("arrière-plan simulé (%s)" % type(sc).__name__)
    elif n in (12, 202):                                   # ... puis revient
        evs.append(pygame.event.Event(getattr(pygame, "WINDOWFOCUSGAINED", pygame.USEREVENT)))
    elif n == 70:                                          # doigt posé en haut de la manette : plein gaz
        r = sc.hud.rect_gaz
        evs.append(doigt(app, (r.centerx, r.y + 50)))
        journal.append("doigt sur la manette des gaz")
    elif n == 400:
        v = app.univers.actif
        x, y, vx, vy = app.univers.etat(v)
        journal.append("en vol : %s, altitude %.0f m, gaz %.0f %%, écran logique %s, tactile=%s" % (
            v.nom, (x * x + y * y) ** 0.5 - v.corps.R, 100 * v.gaz, app.ecran.get_size(), app.tactile))
        evs.append(pygame.event.Event(pygame.QUIT))
    return evs

pygame.event.get = get
code = marshal.loads(open("main.pyc", "rb").read()[16:])      # comme start.c : en-tête sauté, puis exécution
try:
    exec(code, {"__name__": "__main__", "__builtins__": __builtins__})
except SystemExit:
    pass
print("\n".join(journal))
print("sauvegarde :", [f for f in os.listdir(app_dir) if f.endswith(".json")])
if os.path.exists(os.path.join(app_dir, "erreur.txt")):
    print("PLANTAGE :", open(os.path.join(app_dir, "erreur.txt"), encoding="utf-8").read().strip().splitlines()[-1])
else:
    print("aucun plantage")
