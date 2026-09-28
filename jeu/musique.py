# -*- coding: utf-8 -*-
"""
Musique d'ambiance, fabriquée par le code comme les sons.

Un petit compositeur joue, mesure après mesure, des notes fabriquées une seule fois :
une nappe (des accords tenus), une basse douce et des cloches (des arpèges tirés au
hasard sur une gamme pentatonique, où aucune note ne sonne faux). Il suit l'humeur du
moment : calme au menu, entraînante au décollage, rêveuse en orbite, mystérieuse autour
de la Lune et des planètes. La musique ne se répète donc jamais tout à fait.

Tout est en la, comme la nappe d'ambiance des sons (55 Hz = la).
Au premier lancement, les notes sont fabriquées en arrière-plan (fichiers .wav gardés en
cache) : le jeu démarre tout de suite, la musique arrive quelques secondes plus tard.
"""
import os
import random
import threading
import wave
from array import array
from math import sin, pi, exp

from . import reglages, sons

VERSION = 1                     # à augmenter quand une recette change : le cache est refait
FREQ_GRAVE = 11025              # nappes et basse : pas d'aigus, fréquence réduite
FREQ_CLOCHE = 22050
CANAL0 = len(sons.BOUCLES)      # canaux réservés juste après ceux des boucles de sons
NB_CANAUX = sons.CANAUX_MUSIQUE  # 2 nappes (fondu enchaîné), 1 basse, 3 cloches
VOLUME = 0.55                   # volume général de la musique (les humeurs le modulent)

# ------------------------------------------------------------------ l'écriture musicale
# Notes en numéros MIDI (69 = la 440 Hz).
GAMMES = {
    "clair": [69, 71, 73, 76, 78, 81, 83, 85, 88, 90],     # la majeur pentatonique (la si do# mi fa#)
    "sombre": [69, 72, 74, 76, 79, 81, 84, 86, 88, 91],    # la mineur pentatonique (la do ré mi sol)
}
ACCORDS = {                     # voix de la nappe ; la basse joue la première note une octave plus bas
    "A9": [57, 61, 64, 71], "F#m7": [54, 57, 61, 64], "Dmaj9": [50, 57, 61, 64], "Esus": [52, 57, 59, 64],
    "Am9": [57, 60, 64, 71], "Fmaj7": [53, 57, 60, 64], "Cadd9": [48, 55, 62, 64],
    "G6": [55, 59, 62, 64], "Dm9": [50, 57, 60, 64],
}
ENCHAINEMENTS = {               # accord -> accords qui peuvent suivre (tirés au hasard)
    "A9": ["F#m7", "Dmaj9", "Esus", "Dmaj9"], "F#m7": ["Dmaj9", "Esus", "A9"],
    "Dmaj9": ["A9", "Esus", "F#m7"], "Esus": ["A9", "F#m7", "A9"],
    "Am9": ["Fmaj7", "Dm9", "G6", "Cadd9"], "Fmaj7": ["G6", "Am9", "Cadd9"],
    "Cadd9": ["G6", "Am9", "Fmaj7"], "G6": ["Am9", "Fmaj7", "Am9"], "Dm9": ["Am9", "G6", "Fmaj7"],
}
HUMEURS = {                     # tempo : secondes par temps ; densité : chance d'une note de cloche
    "menu":      {"gamme": "clair",  "depart": "A9",  "tempo": 1.25, "densite": 0.34, "volume": 0.80, "octave": 0},
    "hangar":    {"gamme": "clair",  "depart": "A9",  "tempo": 1.05, "densite": 0.40, "volume": 0.70, "octave": 0},
    "decollage": {"gamme": "clair",  "depart": "Dmaj9", "tempo": 0.78, "densite": 0.50, "volume": 0.75, "octave": 0},
    "espace":    {"gamme": "clair",  "depart": "A9",  "tempo": 1.50, "densite": 0.28, "volume": 0.80, "octave": 1},
    "mystere":   {"gamme": "sombre", "depart": "Am9", "tempo": 1.40, "densite": 0.30, "volume": 0.80, "octave": 0},
}


def _frequence(note):
    return 440.0 * 2.0 ** ((note - 69) / 12.0)


def _notes_de_cloche():
    return sorted(set(GAMMES["clair"] + GAMMES["sombre"]))


def _basses():
    return sorted(set(voix[0] - 12 for voix in ACCORDS.values()))


# ------------------------------------------------------------------ fabrication des notes
TABLE = 2048                    # une période d'onde, relue à la bonne vitesse pour chaque note


def _table(harmoniques):
    t = [sum(a * sin(2.0 * pi * k * i / TABLE) for k, a in harmoniques) for i in range(TABLE)]
    m = max(abs(x) for x in t)
    return [x / m for x in t]


def _cloche(note):
    """Note de cloche : attaque franche, harmoniques qui s'éteignent, léger scintillement."""
    freq, duree = FREQ_CLOCHE, 2.4
    corps, eclat = _table([(1, 1.0), (2, 0.45), (3, 0.18), (5, 0.06)]), _table([(1, 1.0)])
    n = int(duree * freq)
    f = _frequence(note)
    pas, pas2 = f * TABLE / freq, f * 4.2 * TABLE / freq      # 4,2 : l'éclat « métallique »
    d1, d2 = exp(-1.0 / (0.85 * freq)), exp(-1.0 / (0.10 * freq))
    attaque, fin = int(0.004 * freq), int(0.25 * freq)
    out = array("h", [0]) * n
    phase = phase2 = 0.0
    env, env2 = 1.0, 0.35
    for i in range(n):
        x = corps[int(phase) & 2047] * env + eclat[int(phase2) & 2047] * env2
        if i < attaque:
            x *= i / attaque
        elif i > n - fin:
            x *= (n - i) / fin
        out[i] = int(x * 8500)
        phase += pas
        phase2 += pas2
        env *= d1
        env2 *= d2
    return out, freq


def _nappe(accord):
    """Accord tenu : montée lente, léger mouvement, extinction lente (6,5 s)."""
    freq, duree = FREQ_GRAVE, 6.5
    onde = _table([(1, 1.0), (2, 0.22), (3, 0.08)])
    n = int(duree * freq)
    voix = [(_frequence(note) * TABLE / freq, 0.0, k * 1.7) for k, note in enumerate(ACCORDS[accord])]
    out = array("h", [0]) * n
    montee, fin = int(1.4 * freq), int(2.2 * freq)
    lfo = 2.0 * pi * 0.23 / freq
    for k, (pas, _, decal) in enumerate(voix):
        phase = 0.0
        for i in range(n):
            a = 1.0 if montee <= i <= n - fin else (i / montee if i < montee else (n - i) / fin)
            vib = 0.85 + 0.15 * sin(lfo * i + decal)          # chaque voix respire à son rythme
            out[i] += int(onde[int(phase) & 2047] * a * vib * 2300)
            phase += pas
    return out, freq


def _basse(note):
    """Basse douce : un sinus rond qui s'éteint en 3 s."""
    freq, duree = FREQ_GRAVE, 3.0
    onde = _table([(1, 1.0), (2, 0.3)])
    n = int(duree * freq)
    pas = _frequence(note) * TABLE / freq
    d = exp(-1.0 / (1.1 * freq))
    attaque, fin = int(0.02 * freq), int(0.3 * freq)
    out = array("h", [0]) * n
    phase, env = 0.0, 1.0
    for i in range(n):
        x = onde[int(phase) & 2047] * env
        if i < attaque:
            x *= i / attaque
        elif i > n - fin:
            x *= (n - i) / fin
        out[i] = int(x * 9000)
        phase += pas
        env *= d
    return out, freq


def recettes():
    """Toutes les notes à fabriquer : nom -> fonction qui renvoie (échantillons, fréquence)."""
    r = {}
    for note in _notes_de_cloche():
        r["cloche_%d" % note] = (lambda n=note: _cloche(n))
    for accord in ACCORDS:
        r["nappe_%s" % accord.replace("#", "d")] = (lambda a=accord: _nappe(a))
    for note in _basses():
        r["basse_%d" % note] = (lambda n=note: _basse(n))
    return r


def _dossier():
    try:
        from .sauvegarde import chemin_sauvegarde
        dossier = os.path.join(os.path.dirname(chemin_sauvegarde()), "cache_sons", "musique_v%d" % VERSION)
        os.makedirs(dossier, exist_ok=True)
        return dossier
    except OSError:
        return None


def _ecrire(chemin, echantillons, freq):
    provisoire = chemin + ".tmp"
    with wave.open(provisoire, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(freq)
        w.writeframes(echantillons.tobytes())
    os.replace(provisoire, chemin)                  # jamais de fichier à moitié écrit


def fabriquer_tout(dossier=None):
    """Fabrique les notes qui manquent dans le cache. Renvoie le nombre de notes fabriquées."""
    dossier = dossier or _dossier()
    if dossier is None:
        return 0
    faites = 0
    for nom, recette in recettes().items():
        chemin = os.path.join(dossier, nom + ".wav")
        if not os.path.exists(chemin):
            echantillons, freq = recette()
            _ecrire(chemin, echantillons, freq)
            faites += 1
    return faites


# ------------------------------------------------------------------ le compositeur
class Compositeur:
    def __init__(self):
        self.pret = False               # notes fabriquées (en arrière-plan) ?
        self.sons = {}                  # nom -> pygame.mixer.Sound, chargés une fois prêts
        self.humeur = None
        self.suivante = None            # changement d'humeur, appliqué à la mesure suivante
        self.attente = 0.0              # temps restant avant le prochain demi-temps
        self.demi = 0                   # demi-temps dans la mesure (0 à 7)
        self.mesure = 0
        self.accord = None
        self.degre = 4                  # position de la dernière note de cloche dans la gamme
        self.nappe = 0                  # canal de nappe utilisé (on alterne pour les fondus)
        self.cloche = 0
        self.joue = False
        self.notes_jouees = 0           # pour les tests

    # -- préparation
    def preparer(self):
        """Lance la fabrication des notes en arrière-plan (rien à faire si le cache est complet)."""
        if not sons.ACTIF:
            return
        dossier = _dossier()
        if dossier is None:
            return

        def travail():
            try:
                fabriquer_tout(dossier)
                self.dossier = dossier
                self.pret = True
            except (OSError, ValueError, MemoryError):
                pass
        threading.Thread(target=travail, daemon=True).start()

    def _charger(self):
        import pygame
        for nom in recettes():
            try:
                self.sons[nom] = pygame.mixer.Sound(os.path.join(self.dossier, nom + ".wav"))
            except (pygame.error, OSError, FileNotFoundError):
                pass

    # -- à chaque image
    def maj(self, dt, humeur):
        if not sons.ACTIF or not self.pret:
            return
        if reglages.SON != "tout":
            self.taire()
            return
        if not self.sons:
            self._charger()
        if humeur not in HUMEURS:
            humeur = "menu"
        if self.humeur is None:
            self.humeur, self.attente, self.demi = humeur, 0.0, 0
        elif humeur != self.humeur:
            self.suivante = humeur
        self.joue = True
        self.attente -= min(dt, 0.25)
        while self.attente <= 0.0:
            self.attente += HUMEURS[self.humeur]["tempo"] / 2.0
            self._demi_temps()

    def taire(self, fondu_ms=1200):
        if not self.joue:
            return
        import pygame
        for k in range(NB_CANAUX):
            try:
                pygame.mixer.Channel(CANAL0 + k).fadeout(fondu_ms)
            except pygame.error:
                pass
        self.joue = False
        self.humeur = None

    # -- l'écriture en temps réel
    def _demi_temps(self):
        if self.demi == 0:                              # début de mesure
            if self.suivante is not None:
                self.humeur, self.suivante, self.accord = self.suivante, None, None
            self.mesure += 1
            h = HUMEURS[self.humeur]
            self.accord = h["depart"] if self.accord is None or self.accord not in ENCHAINEMENTS \
                or ACCORDS_DE[self.accord] != h["gamme"] else random.choice(ENCHAINEMENTS[self.accord])
            self._nappe(h)
            self._jouer("basse_%d" % (ACCORDS[self.accord][0] - 12), 2, h["volume"] * 0.55)
        h = HUMEURS[self.humeur]
        respire = self.mesure % 8 == 0                  # une mesure sans cloches toutes les huit
        chance = h["densite"] * (1.0 if self.demi % 2 == 0 else 0.55)
        if not respire and random.random() < chance:
            self._cloche(h)
        if self.demi == 4 and random.random() < 0.3:    # parfois, la basse revient à mi-mesure
            self._jouer("basse_%d" % (ACCORDS[self.accord][0] - 12), 2, h["volume"] * 0.35)
        self.demi = (self.demi + 1) % 8

    def _nappe(self, h):
        import pygame
        ancien = pygame.mixer.Channel(CANAL0 + self.nappe)
        ancien.fadeout(1800)                            # fondu enchaîné d'un accord à l'autre
        self.nappe = 1 - self.nappe
        self._jouer("nappe_%s" % self.accord.replace("#", "d"), self.nappe, h["volume"] * 0.5, fondu=1400)

    def _cloche(self, h):
        gamme = GAMMES[h["gamme"]]
        pas = random.choice((-2, -1, -1, 0, 1, 1, 2))   # de petits pas : une mélodie qui chante
        self.degre = max(0, min(len(gamme) - 1, self.degre + pas))
        if h["octave"] and self.degre < 3:
            self.degre += 2                             # en orbite, un peu plus aigu
        note = gamme[self.degre]
        if self.demi == 0:                              # temps fort : on préfère une note de l'accord
            classes = set(n % 12 for n in ACCORDS[self.accord])
            if note % 12 not in classes:
                proches = [k for k, n in enumerate(gamme) if n % 12 in classes]
                if proches:
                    self.degre = min(proches, key=lambda k: abs(k - self.degre))
                    note = gamme[self.degre]
        self._jouer("cloche_%d" % note, 3 + self.cloche, h["volume"] * random.uniform(0.35, 0.8))
        self.cloche = (self.cloche + 1) % 3

    def _jouer(self, nom, canal, volume, fondu=0):
        son = self.sons.get(nom)
        if son is None:
            return
        import pygame
        try:
            c = pygame.mixer.Channel(CANAL0 + canal)
            c.set_volume(max(0.0, min(1.0, volume * VOLUME)))
            c.play(son, fade_ms=fondu)
            self.notes_jouees += 1
        except pygame.error:
            pass


ACCORDS_DE = {a: ("clair" if a in ("A9", "F#m7", "Dmaj9", "Esus") else "sombre") for a in ACCORDS}

COMPOSITEUR = Compositeur()


def preparer():
    COMPOSITEUR.preparer()


def maj(dt, humeur):
    COMPOSITEUR.maj(dt, humeur)


def taire():
    COMPOSITEUR.taire()
