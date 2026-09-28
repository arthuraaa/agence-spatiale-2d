# -*- coding: utf-8 -*-
"""
Sons du jeu, entièrement fabriqués par le code : aucun fichier audio à fournir.

    - boucles : moteur, vent (dans l'atmosphère), RCS, et une nappe d'ambiance ;
    - bruitages : séparation, explosion, amarrage, parachute, atterrissage, bip,
      alerte, mission réussie, clic des boutons.

Chaque son est une « recette » : du bruit filtré, des sinus, une enveloppe (attaque puis
déclin). La synthèse prend un moment : au premier lancement, les sons sont écrits en .wav
dans un dossier de cache (à côté de la sauvegarde), puis simplement relus ensuite.
Sans carte son, ou si le mixeur refuse de démarrer, tout reste silencieux, sans erreur.
"""
import io
import math
import os
import random
import time
import wave
from array import array

from . import reglages

VERSION = 1             # à augmenter quand une recette change : le cache est alors refait
FREQ = 22050            # échantillons par seconde (largement assez pour ces sons)
BOUCLES = ("moteur", "vent", "rcs", "ambiance")   # sons joués en continu, chacun sur son canal
ANTI_RAFALE = {"clic": 0.04, "alerte": 1.2, "explosion": 0.3, "bip": 0.08}   # délai mini (s)

ACTIF = False
_sons = {}              # nom -> pygame.mixer.Sound
_canaux = {}            # boucle -> canal réservé
_volumes = {}           # boucle -> volume actuel (lissé)
_dernier = {}           # bruitage -> instant du dernier déclenchement


# =============================================================================
# Petits outils de synthèse (listes de nombres entre -1 et 1)
# =============================================================================
def _duree(secondes):
    return int(secondes * FREQ)


def _bruit(n, graine):
    r = random.Random(graine)
    return [r.uniform(-1.0, 1.0) for _ in range(n)]


def _passe_bas(x, a):
    """Filtre passe-bas simple (a petit = plus sourd)."""
    y, s = [0.0] * len(x), 0.0
    for i, v in enumerate(x):
        s += a * (v - s)
        y[i] = s
    return y


def _passe_haut(x, a):
    return [v - p for v, p in zip(x, _passe_bas(x, a))]


def _sinus(freq, n, phase=0.0):
    w = 2.0 * math.pi * freq / FREQ
    return [math.sin(w * i + phase) for i in range(n)]


def _declin(n, tau, attaque=0.004):
    """Enveloppe : montée rapide puis décroissance exponentielle (tau en secondes)."""
    na = max(1, _duree(attaque))
    d = math.exp(-1.0 / (tau * FREQ))
    env, e = [0.0] * n, 1.0
    for i in range(n):
        env[i] = (i / na if i < na else 1.0) * e
        e *= d
    return env


def _mul(*signaux):
    out = list(signaux[0])
    for s in signaux[1:]:
        out = [a * b for a, b in zip(out, s)]
    return out


def _somme(*termes):
    """Somme pondérée : _somme((0.8, x), (0.3, y))."""
    n = max(len(s) for _, s in termes)
    out = [0.0] * n
    for k, s in termes:
        for i, v in enumerate(s):
            out[i] += k * v
    return out


def _normaliser(x, niveau):
    m = max(1e-9, max(abs(v) for v in x))
    return [v * niveau / m for v in x]


def _boucler(x, fondu):
    """Raccorde la fin au début (fondu enchaîné) : la boucle tourne sans claquer."""
    n = len(x) - fondu
    out = x[:n]
    for i in range(fondu):
        f = i / fondu
        out[i] = x[i] * f + x[n + i] * (1.0 - f)
    return out


# =============================================================================
# Recettes
# =============================================================================
def _moteur():
    fondu = _duree(0.2)
    b = _bruit(_duree(1.2) + fondu, 1)
    grave = _normaliser(_passe_bas(_passe_bas(b, 0.02), 0.05), 1.0)     # grondement
    crepite = _normaliser(_passe_bas(b, 0.3), 1.0)                         # crépitement
    return _normaliser(_boucler(_somme((0.85, grave), (0.25, crepite)), fondu), 0.9)


def _vent():
    fondu = _duree(0.3)
    n = _duree(2.0) + fondu
    b = _bruit(n, 2)
    souffle = _normaliser([p - q for p, q in zip(_passe_bas(b, 0.12), _passe_bas(b, 0.015))], 1.0)
    houle = [0.65 + 0.35 * math.sin(2.0 * math.pi * i / _duree(2.0)) for i in range(n)]
    return _normaliser(_boucler(_mul(souffle, houle), fondu), 0.7)


def _rcs():
    fondu = _duree(0.1)
    return _normaliser(_boucler(_passe_haut(_bruit(_duree(0.5) + fondu, 3), 0.35), fondu), 0.6)


def _ambiance():
    """Nappe grave et lente. Toutes les fréquences sont des multiples de 1/4 Hz : sur une
    boucle de 4 s, chaque sinus retombe exactement sur ses pieds."""
    n = _duree(4.0)
    t = [i / FREQ for i in range(n)]
    nappe = [0.0] * n
    for f, amp, lfo in ((55.0, 1.0, 4.0), (55.25, 0.7, 2.0), (82.5, 0.55, 4.0 / 3.0),
                        (110.0, 0.4, 4.0), (165.0, 0.18, 2.0), (247.5, 0.08, 1.0)):
        w, wl = 2.0 * math.pi * f, 2.0 * math.pi / lfo
        for i, ti in enumerate(t):
            nappe[i] += amp * math.sin(w * ti) * (0.6 + 0.4 * math.sin(wl * ti))
    souffle = _normaliser(_passe_bas(_passe_bas(_bruit(n + _duree(0.5), 4), 0.03), 0.1), 0.12)
    souffle = _boucler(souffle, _duree(0.5))
    return _normaliser(_somme((1.0, nappe), (1.0, souffle)), 0.8)


def _separation():
    n = _duree(0.6)
    coup = _mul(_sinus(65.0, n), _declin(n, 0.09))
    souffle = _mul(_normaliser(_passe_bas(_bruit(n, 5), 0.08), 1.0), _declin(n, 0.05))
    clac = _mul(_sinus(1400.0, n), _declin(n, 0.008, 0.001))
    return _normaliser(_somme((0.9, coup), (0.6, souffle), (0.25, clac)), 0.95)


def _explosion():
    n = _duree(2.0)
    boum = _mul(_normaliser(_passe_bas(_bruit(n, 6), 0.06), 1.0), _declin(n, 0.45, 0.005))
    grave = _mul(_sinus(35.0, n), _declin(n, 0.5))
    eclats = _mul(_normaliser(_passe_bas(_bruit(n, 7), 0.4), 1.0), _declin(n, 0.15))
    return _normaliser(_somme((1.0, boum), (0.6, grave), (0.3, eclats)), 1.0)


def _amarrage():
    n = _duree(0.45)
    metal = _somme((0.8, _mul(_sinus(430.0, n), _declin(n, 0.12, 0.001))),
                   (0.5, _mul(_sinus(1170.0, n), _declin(n, 0.06, 0.001))),
                   (0.3, _mul(_sinus(2010.0, n), _declin(n, 0.03, 0.001))))
    clic = _mul(_bruit(n, 8), _declin(n, 0.004, 0.0005))
    return _normaliser(_somme((1.0, metal), (0.5, clic)), 0.8)


def _parachute():
    n = _duree(0.8)
    b = _bruit(n, 9)
    souffle = _normaliser([p - q for p, q in zip(_passe_bas(b, 0.25), _passe_bas(b, 0.03))], 1.0)
    montee = _duree(0.12)
    env = [min(1.0, i / montee) * math.exp(-max(0, i - montee) / (0.25 * FREQ)) for i in range(n)]
    return _normaliser(_mul(souffle, env), 0.7)


def _pose():
    n = _duree(0.4)
    return _normaliser(_somme((1.0, _mul(_sinus(50.0, n), _declin(n, 0.12))),
                              (0.5, _mul(_normaliser(_passe_bas(_bruit(n, 10), 0.05), 1.0), _declin(n, 0.06)))), 0.8)


def _clic():
    n = _duree(0.035)
    return _normaliser(_mul(_sinus(1900.0, n), _declin(n, 0.006, 0.0005)), 0.3)


def _bip():
    n = _duree(0.12)
    return _normaliser(_mul(_sinus(988.0, n), _declin(n, 0.05, 0.005)), 0.45)


def _alerte():
    n, bip = _duree(0.42), _duree(0.12)
    s = _somme((1.0, _sinus(1250.0, n)), (0.3, _sinus(3750.0, n)))
    env = [1.0 if (i < bip or _duree(0.2) <= i < _duree(0.2) + bip) else 0.0 for i in range(n)]
    return _normaliser(_mul(s, _passe_bas(env, 0.02)), 0.5)


def _succes():
    """Petite fanfare : do, mi, sol, do."""
    n = _duree(1.2)
    out = [0.0] * n
    for debut, f, tau in ((0.0, 523.25, 0.25), (0.12, 659.25, 0.25), (0.24, 783.99, 0.25), (0.40, 1046.5, 0.45)):
        d = _duree(debut)
        m = n - d
        note = _mul(_somme((1.0, _sinus(f, m)), (0.3, _sinus(2 * f, m))), _declin(m, tau, 0.008))
        for i, v in enumerate(note):
            out[d + i] += v
    return _normaliser(out, 0.55)


RECETTES = {"moteur": _moteur, "vent": _vent, "rcs": _rcs, "ambiance": _ambiance,
            "separation": _separation, "explosion": _explosion, "amarrage": _amarrage,
            "parachute": _parachute, "pose": _pose, "clic": _clic, "bip": _bip,
            "alerte": _alerte, "succes": _succes}


def fabriquer_wav(nom):
    """Le son `nom` au format .wav (mono, 16 bits), en mémoire."""
    echantillons = array("h", [int(max(-1.0, min(1.0, v)) * 32767) for v in RECETTES[nom]()])
    tampon = io.BytesIO()
    with wave.open(tampon, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(FREQ)
        w.writeframes(echantillons.tobytes())
    return tampon.getvalue()


# =============================================================================
# Utilisation
# =============================================================================
def _dossier_cache():
    try:
        from .sauvegarde import chemin_sauvegarde
        dossier = os.path.join(os.path.dirname(chemin_sauvegarde()), "cache_sons", "v%d" % VERSION)
        os.makedirs(dossier, exist_ok=True)
        return dossier
    except OSError:
        return None


def cache_complet():
    dossier = _dossier_cache()
    return dossier is not None and all(os.path.exists(os.path.join(dossier, n + ".wav")) for n in RECETTES)


CANAUX_MUSIQUE = 6          # canaux réservés à la musique (musique.py), juste après les boucles


def initialiser():
    """Démarre le mixeur et prépare les sons (depuis le cache s'il existe). Renvoie True si ça marche."""
    global ACTIF
    try:
        import pygame
        if not pygame.mixer.get_init():
            pygame.mixer.init(FREQ, -16, 2, 1024)
        pygame.mixer.set_num_channels(24)
        pygame.mixer.set_reserved(len(BOUCLES) + CANAUX_MUSIQUE)   # boucles, puis musique
    except Exception as e:                             # pas de carte son : on joue en silence
        print("Son désactivé :", e)
        ACTIF = False
        return False
    dossier = _dossier_cache()
    for nom in RECETTES:
        chemin = os.path.join(dossier, nom + ".wav") if dossier else None
        try:
            if chemin and os.path.exists(chemin):
                _sons[nom] = pygame.mixer.Sound(chemin)
                continue
            donnees = fabriquer_wav(nom)
            if chemin:
                with open(chemin, "wb") as f:
                    f.write(donnees)
            _sons[nom] = pygame.mixer.Sound(io.BytesIO(donnees))
        except Exception as e:
            print("Son « %s » indisponible :" % nom, e)
    ACTIF = bool(_sons)
    return ACTIF


def suspendre(oui):
    """Coupe (ou relance) tout le son, par exemple quand l'appli passe en arrière-plan."""
    if not ACTIF:
        return
    import pygame
    try:
        pygame.mixer.pause() if oui else pygame.mixer.unpause()
    except pygame.error:
        pass


def jouer(nom, volume=1.0):
    """Joue un bruitage une fois (sauf si le son est coupé)."""
    if not ACTIF or reglages.SON == "aucun" or nom not in _sons:
        return
    maintenant = time.time()
    if maintenant - _dernier.get(nom, 0.0) < ANTI_RAFALE.get(nom, 0.02):
        return
    _dernier[nom] = maintenant
    canal = _sons[nom].play()
    if canal is not None:
        canal.set_volume(volume)


def regler_boucle(nom, volume, dt=1.0 / 60.0):
    """Volume voulu d'une boucle (0 = silence), atteint en douceur pour éviter les claquements."""
    if not ACTIF or nom not in _sons:
        return
    if reglages.SON == "aucun" or (nom == "ambiance" and reglages.SON not in ("tout", "sans_musique")):
        volume = 0.0
    canal = _canaux.get(nom)
    if canal is None:
        if volume <= 0.0:
            return
        import pygame
        canal = pygame.mixer.Channel(BOUCLES.index(nom))
        canal.play(_sons[nom], loops=-1)
        canal.set_volume(0.0)
        _canaux[nom], _volumes[nom] = canal, 0.0
    v = _volumes[nom] + (volume - _volumes[nom]) * min(1.0, 8.0 * dt)
    _volumes[nom] = v
    canal.set_volume(v)


def silence_boucles(sauf=("ambiance",)):
    """Coupe net les boucles du vol (moteur, vent, RCS) : en quittant l'écran de vol, en pause..."""
    for nom in BOUCLES:
        if nom not in sauf and nom in _canaux:
            _volumes[nom] = 0.0
            _canaux[nom].set_volume(0.0)
