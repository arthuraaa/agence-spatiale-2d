# -*- coding: utf-8 -*-
"""
Lance tous les tests, un fichier après l'autre, et résume.

    python tests/tout.py              tous les tests (2 à 3 minutes)
    python tests/tout.py --rapide     sans les plus longs (missions jouées en entier...)
    python tests/tout.py aides boost  seulement les fichiers dont le nom contient ces mots

Sans écran : l'affichage et le son passent par les pilotes « dummy » de SDL.
Code de sortie 1 si un test échoue (utile aux scripts, comme outils/android/construire.sh).
"""
import os
import subprocess
import sys
import time

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.dirname(ICI)
LONGS = {"test_scenarios", "test_aides", "test_amarrage_auto", "test_atterrissage", "test_tutoriel"}


def main():
    mots = [a for a in sys.argv[1:] if not a.startswith("--")]
    fichiers = sorted(f[:-3] for f in os.listdir(ICI) if f.startswith("test_") and f.endswith(".py"))
    if mots:
        fichiers = [f for f in fichiers if any(m in f for m in mots)]
    if "--rapide" in sys.argv:
        fichiers = [f for f in fichiers if f not in LONGS]
    env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
    echecs, debut = [], time.time()
    for nom in fichiers:
        t = time.time()
        r = subprocess.run([sys.executable, os.path.join(ICI, nom + ".py")], cwd=RACINE, env=env,
                           capture_output=True, text=True)
        print("%s %-24s %6.1f s" % ("OK   " if r.returncode == 0 else "ÉCHEC", nom, time.time() - t), flush=True)
        if r.returncode != 0:
            echecs.append(nom)
            print("    " + "\n    ".join((r.stdout + r.stderr).strip().splitlines()[-20:]))
    for f in ("sauvegarde.json", "reglages.json", "erreur.txt"):     # ce que les tests ont pu laisser
        if os.path.exists(os.path.join(RACINE, f)):
            os.remove(os.path.join(RACINE, f))
    print("%d fichiers de tests, %d échec(s), %.0f s" % (len(fichiers), len(echecs), time.time() - debut))
    sys.exit(1 if echecs else 0)


if __name__ == "__main__":
    main()
