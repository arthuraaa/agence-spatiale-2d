# -*- coding: utf-8 -*-
"""
Un vaisseau = une pile de pièces, listée du HAUT (nez) vers le BAS (moteur).

Règles simples :
  - le moteur actif est celui tout en bas de la pile (s'il n'est pas retourné) ;
  - il consomme le carburant des réservoirs situés au-dessus de lui, jusqu'au
    premier découpleur ou port d'amarrage rencontré ;
  - ESPACE sépare la pile au découpleur le plus bas ;
  - deux ports d'amarrage face à face (port retourné au-dessus d'un port normal)
    forment une jonction qu'on peut défaire avec U.

Boosters latéraux : une pièce de la pile peut porter une paire de boosters symétriques
(attribut `laterales` : la pile d'UN booster, doublée à l'affichage et dans les calculs).
Le bas des boosters est aligné sur le bas de leur pièce porteuse. Les boosters de la
section du bas (sous le dernier découpleur) brûlent en même temps que le moteur central,
chacun avec son propre carburant ; ESPACE les largue en premier.
"""
from math import log, pi, cos, sin
from collections import Counter
from .constantes import G0
from .pieces import Piece, CATALOGUE


# --------------------------------------------------------------------------
# Fonctions sur une simple liste de pièces (utilisées aussi par le hangar)
# --------------------------------------------------------------------------
def indice_moteur(pieces):
    """Indice du moteur actif (tout en bas, trains d'atterrissage ignorés) ou None."""
    i = len(pieces) - 1
    while i >= 0 and pieces[i].m.forme == "train":
        i -= 1
    if i >= 0 and pieces[i].m.poussee > 0 and not pieces[i].retournee:
        return i
    return None


def reservoirs_du_moteur(pieces, i):
    """Réservoirs qui alimentent le moteur d'indice i."""
    out = []
    j = i - 1
    while j >= 0 and pieces[j].m.forme not in ("decoupleur", "port"):
        if pieces[j].m.carburant > 0:
            out.append(pieces[j])
        j -= 1
    return out


def indice_decoupleur_bas(pieces):
    """Indice du découpleur le plus bas, ou None."""
    for i in range(len(pieces) - 1, -1, -1):
        if pieces[i].m.forme == "decoupleur":
            return i
    return None


def orienter_ports(pieces):
    """Hangar : un port regarde vers le bas s'il est suivi d'un découpleur, d'un port ou de rien."""
    n = len(pieces)
    for i, p in enumerate(pieces):
        if p.m.forme == "port":
            dessous = pieces[i + 1].m.forme if i + 1 < n else None
            p.retournee = dessous in (None, "decoupleur", "port") and i > 0 \
                and not (pieces[i - 1].m.forme == "port" and pieces[i - 1].retournee)


# --------------------------------------------------------------------------
# Plans : la description d'une fusée (hangar, modèles). Chaque entrée est une clé de
# pièce, ou ["clé", [pile d'un booster]] pour une pièce qui porte une paire de boosters.
# --------------------------------------------------------------------------
def cle_de(entree):
    return entree if isinstance(entree, str) else entree[0]


def boosters_de(entree):
    return [] if isinstance(entree, str) else list(entree[1])


def copie_plan(plan):
    """Copie indépendante d'un plan (on peut modifier les boosters sans toucher l'original)."""
    return [e if isinstance(e, str) else [e[0], list(e[1])] for e in plan]


def toutes_les_cles(plan):
    """Toutes les pièces du plan, boosters compris (chaque booster compte deux fois)."""
    out = []
    for e in plan:
        out.append(cle_de(e))
        out += boosters_de(e) * 2
    return out


def prix_plan(plan):
    return sum(CATALOGUE[c].prix for c in toutes_les_cles(plan))


def pieces_depuis_plan(plan, proprietaire=""):
    """Pièces neuves (avec leurs boosters) à partir d'un plan."""
    pieces = []
    for e in plan:
        p = Piece(cle_de(e), proprietaire)
        p.laterales = [Piece(c, proprietaire) for c in boosters_de(e)]
        pieces.append(p)
    orienter_ports(pieces)
    return pieces


# --------------------------------------------------------------------------
# Boosters
# --------------------------------------------------------------------------
def masse_avec_boosters(p):
    return p.masse() + 2.0 * sum(q.masse() for q in p.laterales)


def moteur_et_reservoirs(pile):
    """(moteur du bas, réservoirs qui l'alimentent) d'une pile, ou (None, [])."""
    i = indice_moteur(pile)
    return (None, []) if i is None else (pile[i], reservoirs_du_moteur(pile, i))


def porteurs_actifs(pieces):
    """Pièces de la section du bas qui portent des boosters : ceux-là brûlent maintenant."""
    d = indice_decoupleur_bas(pieces)
    return [p for p in pieces[(0 if d is None else d + 1):] if p.laterales]


def _moteurs_de_section(pieces):
    """Moteur central et boosters de la section du bas : [(modèle de moteur, carburant, nombre)]."""
    out = []
    i = indice_moteur(pieces)
    if i is not None:
        out.append((pieces[i].m, sum(p.carburant for p in reservoirs_du_moteur(pieces, i)), 1))
    for p in porteurs_actifs(pieces):
        mot, res = moteur_et_reservoirs(p.laterales)
        if mot is not None:
            out.append((mot.m, sum(r.carburant for r in res), 2))
    return out


def statistiques_etages(pieces):
    """
    Une entrée par étage, dans l'ordre où ESPACE les largue :
    debut/fin (indices des pièces larguées avec l'étage), moteur, dv (vide), dv_sol,
    twr (au sol, sur Terre), twr_vide, duree de combustion, masse au début de l'étage,
    boosters (True pour la phase où les boosters brûlent avec le moteur central).

    Avec des boosters, la section du bas compte deux étages : d'abord « boosters + moteur
    central » jusqu'à ce que les boosters soient vides, puis le moteur central seul.
    Plusieurs moteurs qui poussent dans le même sens équivalent à un seul moteur de
    poussée totale F et de débit total q : vitesse d'éjection F / q.
    """
    pieces = list(pieces)
    etages = []
    while pieces:
        i = indice_moteur(pieces)
        d = indice_decoupleur_bas(pieces)
        m0 = sum(masse_avec_boosters(p) for p in pieces)
        porteurs = porteurs_actifs(pieces)
        carb_c = debit_c = 0.0
        if i is not None:
            mc = pieces[i].m
            carb_c = sum(p.carburant for p in reservoirs_du_moteur(pieces, i))
            debit_c = mc.poussee / (mc.isp_vide * G0)
        if porteurs:
            # --- phase 1 : boosters + moteur central
            f_vide = f_sol = debit_b = carb_b = masse_b = 0.0
            for mod, carb, n in _moteurs_de_section(pieces):
                f_vide += n * mod.poussee
                f_sol += n * mod.poussee * mod.isp_sol / mod.isp_vide
            for p in porteurs:
                masse_b += 2.0 * sum(q.masse() for q in p.laterales)
                mot, res = moteur_et_reservoirs(p.laterales)
                if mot is not None:
                    debit_b += 2.0 * mot.m.poussee / (mot.m.isp_vide * G0)
                    carb_b += 2.0 * sum(r.carburant for r in res)
            debit = debit_b + debit_c
            duree = 0.0
            if debit_b > 0.0:
                duree = carb_b / debit_b
                if debit_c > 0.0:
                    duree = min(duree, carb_c / debit_c)
            brule = debit * duree
            nom = "%d boosters" % (2 * len(porteurs))
            etage = {"debut": len(pieces), "fin": len(pieces), "boosters": True, "masse": m0,
                     "moteur": (pieces[i].m.nom + " + " + nom) if i is not None else nom,
                     "dv": 0.0, "dv_sol": 0.0, "twr": f_sol / (m0 * 9.81), "twr_vide": f_vide / (m0 * 9.81),
                     "duree": duree}
            if brule > 0.0 and m0 > brule:
                rapport = log(m0 / (m0 - brule))
                etage["dv"] = f_vide / debit * rapport
                etage["dv_sol"] = f_sol / debit * rapport
            etages.append(etage)
            # --- après le largage : le moteur central continue seul
            m0 = m0 - debit_c * duree - masse_b
            carb_c -= debit_c * duree
        etage = {"debut": 0 if d is None else d, "fin": len(pieces), "boosters": False, "moteur": None,
                 "masse": m0, "dv": 0.0, "dv_sol": 0.0, "twr": 0.0, "twr_vide": 0.0, "duree": 0.0}
        if i is not None:
            mod = pieces[i].m
            etage["moteur"] = mod.nom
            etage["twr"] = mod.poussee * (mod.isp_sol / mod.isp_vide) / (m0 * 9.81)
            etage["twr_vide"] = mod.poussee / (m0 * 9.81)
            if carb_c > 0 and m0 > carb_c:
                rapport = log(m0 / (m0 - carb_c))
                etage["dv"] = mod.isp_vide * G0 * rapport
                etage["dv_sol"] = mod.isp_sol * G0 * rapport
                etage["duree"] = carb_c / debit_c
        etages.append(etage)
        if d is None:
            break
        pieces = pieces[:d]
    return etages


def _vider(reservoirs, quantite):
    """Retire du carburant de ces réservoirs, proportionnellement à leur contenu."""
    total = sum(p.carburant for p in reservoirs)
    if total <= 0.0:
        return
    f = max(0.0, 1.0 - quantite / total)
    for p in reservoirs:
        p.carburant *= f


class Geometrie:
    """Résultat du calcul de géométrie d'une pile (positions le long de l'axe, en m)."""
    __slots__ = ("masse", "longueur", "haut", "bas", "inertie", "largeurs", "segments",
                 "largeur_max", "train", "laterales", "nez", "fond", "surface_frontale", "surface_cote")


class Vaisseau:
    _compteur = 0

    def __init__(self, nom, pieces, corps):
        Vaisseau._compteur += 1
        self.id = Vaisseau._compteur
        self.nom = nom
        self.pieces = pieces
        self.corps = corps              # corps dont on subit la gravité (sphère d'influence)
        self.mode = "pose"              # "pose" | "rails" | "physique"
        self.x = self.y = self.vx = self.vy = 0.0   # état relatif au corps (mode physique)
        self.angle = pi / 2             # direction du nez (rad, repère inertiel)
        self.omega = 0.0                # vitesse de rotation (rad/s)
        self.longitude = 0.0            # position au sol (repère tournant) si posé
        self.gaz = 0.0                  # manette des gaz 0..1
        self.sas = "stab"               # off, stab, pro, retro, rad+, rad-, cible, anti, manoeuvre, pilote
        self.cap_pilote = None          # direction voulue par le pilote automatique (SAS « pilote »)
        self.rcs = False
        self.ref_vitesse = "surface"    # surface | orbite | cible
        self.ref_auto = None
        self.orbite = None              # Orbite courante si sur rails
        self.troncons = []              # trajectoire prédite (liste de Troncon)
        self.noeud = None               # Manoeuvre planifiée (voir manoeuvre.py)
        self.plan = []                  # trajectoire prévue après la manœuvre
        self.racine = self.premiere_commande()   # pièce depuis laquelle on pilote
        self.drapeaux = set()           # historique : "orbite:Terre", "pose:Lune"...
        self.detruit = False
        self.separe_de = None           # id du vaisseau dont on vient de se désamarrer
        self.cache_etat = (None, None)  # (t, état) pour ne pas recalculer dans la même image

    # ------------------------------------------------------------ propriétés
    def premiere_commande(self):
        for p in self.pieces:
            if p.m.commande:
                return p
        return None

    def controlable(self):
        return self.racine is not None

    def type(self):
        """"debris", "station" ou "vaisseau" (pour l'icône)."""
        if self.racine is None:
            return "debris"
        formes = [p.m.forme for p in self.pieces]
        if "module" in formes and "moteur" not in formes:
            return "station"
        return "vaisseau"

    def masse(self):
        return sum(masse_avec_boosters(p) for p in self.pieces)

    def prix(self):
        return sum(p.m.prix + 2 * sum(q.m.prix for q in p.laterales) for p in self.pieces)

    def mono(self):
        return sum(p.mono for p in self.pieces)

    def couple(self):
        return sum(p.m.couple for p in self.pieces)

    def poussee_rcs(self):
        return sum(p.m.rcs for p in self.pieces if p.mono > 0)

    def a_un_train(self):
        return self.geometrie().train

    def compte(self, forme):
        return sum(1 for p in self.pieces if p.m.forme == forme)

    def contient_proprietaire(self, nom):
        return any(p.proprietaire == nom for p in self.pieces)

    # ------------------------------------------------------------ géométrie
    def geometrie(self):
        """Positions des pièces le long de l'axe, par rapport au centre de masse (haut = +)."""
        pieces = self.pieces
        n = len(pieces)
        largeurs = [p.m.l for p in pieces]
        for i, p in enumerate(pieces):             # largeurs automatiques
            if p.m.largeur_auto:
                j = i - 1
                while j >= 0 and pieces[j].m.largeur_auto:
                    j -= 1
                if j < 0:
                    j = i + 1
                    while j < n and pieces[j].m.largeur_auto:
                        j += 1
                largeurs[i] = pieces[j].m.l if 0 <= j < n else 1.5
        # y : distance depuis le nez, vers le bas
        y = 0.0
        masse = moment = 0.0
        hauts = []
        for p in pieces:
            m = p.masse()
            hauts.append(y)
            moment += m * (y + p.m.h / 2)
            masse += m
            y += p.m.h
        longueur_coeur = y
        # boosters : (pièce porteuse, pile, écart latéral, hauts des pièces, demi-largeur du cœur)
        boosters = []
        dessus, dessous = 0.0, longueur_coeur
        for k, p in enumerate(pieces):
            if not p.laterales:
                continue
            l_b = max(q.m.l for q in p.laterales)
            ecart = largeurs[k] / 2 + l_b / 2 + 0.15
            yb = hauts[k] + p.m.h - sum(q.m.h for q in p.laterales)     # haut du booster
            hauts_b = []
            for q in p.laterales:
                hauts_b.append(yb)
                moment += 2.0 * q.masse() * (yb + q.m.h / 2)
                masse += 2.0 * q.masse()
                yb += q.m.h
            dessus, dessous = min(dessus, hauts_b[0]), max(dessous, yb)
            boosters.append((k, p.laterales, ecart, hauts_b, largeurs[k] / 2))
        cdm = moment / masse if masse > 0 else 0.0
        g = Geometrie()
        g.masse = masse
        g.longueur = dessous - dessus
        g.largeurs = largeurs
        g.segments = [(cdm - h, cdm - h - p.m.h) for h, p in zip(hauts, pieces)]
        inertie = 0.0
        for p, (yh, yb), l in zip(pieces, g.segments, largeurs):
            ym = 0.5 * (yh + yb)
            inertie += p.masse() * (ym * ym + (p.m.h ** 2 + l ** 2) / 12.0)
        g.laterales = []
        frontale = 3.14159 * (max(largeurs) / 2) ** 2 if largeurs else 1.0
        cote = longueur_coeur * (max(largeurs) if largeurs else 1.0)
        largeur_max = max(largeurs) if largeurs else 1.0
        for k, pile, ecart, hauts_b, demi in boosters:
            segs = [(cdm - hb, cdm - hb - q.m.h) for hb, q in zip(hauts_b, pile)]
            for q, (yh, yb) in zip(pile, segs):
                ym = 0.5 * (yh + yb)
                inertie += 2.0 * q.masse() * (ym * ym + ecart * ecart + (q.m.h ** 2 + q.m.l ** 2) / 12.0)
            l_b = max(q.m.l for q in pile)
            frontale += 2 * 3.14159 * (l_b / 2) ** 2
            cote += 2 * l_b * sum(q.m.h for q in pile)
            largeur_max = max(largeur_max, 2 * ecart + l_b)
            g.laterales.append((k, pile, ecart, segs, demi))
        g.inertie = max(inertie, 1.0)
        g.largeur_max = largeur_max
        g.surface_frontale, g.surface_cote = frontale, cote
        # un train d'atterrissage n'est utile que s'il est près du bas de la pile
        g.train = any(p.m.forme == "train" and (cdm - longueur_coeur) - yb > -6.0
                      for p, (yh, yb) in zip(pieces, g.segments))
        g.nez, g.fond = cdm, cdm - longueur_coeur       # extrémités de la pile centrale
        g.haut = cdm - dessus
        g.bas = (dessous - cdm) + (0.5 if g.train else 0.0)
        return g

    # -------------------------------------------------------------- moteurs
    def moteur_actif(self):
        i = indice_moteur(self.pieces)
        return None if i is None else self.pieces[i]

    def reservoirs_actifs(self):
        i = indice_moteur(self.pieces)
        return [] if i is None else reservoirs_du_moteur(self.pieces, i)

    def carburant_actif(self):
        """(restant, capacité) des réservoirs du moteur actif."""
        res = self.reservoirs_actifs()
        return sum(p.carburant for p in res), sum(p.m.carburant for p in res)

    def moteurs(self):
        """Moteurs qui poussent : [(moteur, réservoirs, nombre)] — le central, et ceux des
        boosters de la section du bas (nombre = 2 : un de chaque côté)."""
        out = []
        mot, res = moteur_et_reservoirs(self.pieces)
        if mot is not None:
            out.append((mot, res, 1))
        for p in porteurs_actifs(self.pieces):
            mot, res = moteur_et_reservoirs(p.laterales)
            if mot is not None:
                out.append((mot, res, 2))
        return out

    def poussee_et_debit(self, rapport_pression):
        """Poussée (N) et débit (kg/s) actuels selon les gaz et la pression ambiante."""
        if self.gaz <= 0.0:
            return 0.0, 0.0
        poussee = debit_total = 0.0
        for mot, res, n in self.moteurs():
            if sum(r.carburant for r in res) <= 0.0:
                continue
            m = mot.m
            isp = max(10.0, m.isp_vide - (m.isp_vide - m.isp_sol) * min(rapport_pression, 3.0))
            debit = self.gaz * m.poussee / (m.isp_vide * G0)
            poussee += n * debit * isp * G0
            debit_total += n * debit
        return poussee, debit_total

    def bruler(self, duree):
        """Chaque moteur allumé consomme SON carburant pendant `duree` secondes."""
        for mot, res, n in self.moteurs():
            _vider(res, self.gaz * mot.m.poussee / (mot.m.isp_vide * G0) * duree)

    def consommer(self, quantite):
        """Retire du carburant des réservoirs du moteur central."""
        _vider(self.reservoirs_actifs(), quantite)

    def carburant_boosters(self):
        """(restant, capacité) des boosters qui brûlent en ce moment (les deux côtés)."""
        restant = capacite = 0.0
        for p in porteurs_actifs(self.pieces):
            res = moteur_et_reservoirs(p.laterales)[1]
            restant += 2 * sum(r.carburant for r in res)
            capacite += 2 * sum(r.m.carburant for r in res)
        return restant, capacite

    def etage_epuise(self):
        """Vrai quand il est temps d'appuyer sur ÉTAGE : boosters vides, ou moteur central à sec."""
        porteurs = porteurs_actifs(self.pieces)
        if porteurs:
            return all(sum(r.carburant for r in moteur_et_reservoirs(p.laterales)[1]) <= 0.0
                       for p in porteurs)
        return self.moteur_actif() is not None and self.carburant_actif()[0] <= 0.0

    def consommer_mono(self, quantite):
        total = self.mono()
        if total <= 0.0:
            return
        f = max(0.0, 1.0 - quantite / total)
        for p in self.pieces:
            p.mono *= f

    def delta_v(self):
        return sum(e["dv"] for e in statistiques_etages(self.pieces))

    # ------------------------------------------------------------ parachutes
    def parachutes(self):
        return [p for p in self.pieces if p.parachute is not None]

    def parachute_ouvert(self):
        return any(p.parachute == "ouvert" for p in self.pieces)

    def surface_parachutes(self):
        """Cd*A total des parachutes ouverts (m²)."""
        return sum(700.0 * p.ouverture ** 2 for p in self.pieces if p.parachute == "ouvert")

    # ------------------------------------------------------------- traînée
    def cd_a(self, cos_incidence, sin_incidence):
        """Cd*A du corps du vaisseau selon l'incidence (nez face au vent : cos > 0)."""
        g = self.geometrie()
        front, cote = g.surface_frontale, g.surface_cote
        if cos_incidence > 0:
            profile = self.pieces[0].m.forme in ("capsule", "coiffe", "port")
            cd = 0.35 if profile else 0.8
        else:
            cd = 1.0
        return cd * front * abs(cos_incidence) + 1.2 * cote * abs(sin_incidence)

    # -------------------------------------------------- transfert de carburant
    def sections(self):
        """Morceaux de la pile séparés par les découpleurs et les jonctions d'amarrage."""
        coupures = set(self.jonctions())
        out, courant = [], []
        for i, p in enumerate(self.pieces):
            if i in coupures and courant:
                out.append(courant)
                courant = []
            if p.m.forme == "decoupleur":
                if courant:
                    out.append(courant)
                courant = []
                continue
            courant.append(p)
        if courant:
            out.append(courant)
        return out

    def sections_reservoirs(self):
        """Les sections qui ont des réservoirs (carburant ou monergol), du haut vers le bas."""
        return [s for s in self.sections() if any(p.m.carburant > 0 or p.m.mono > 0 for p in s)]

    def remplir(self, k):
        """Remplit la section k avec le carburant et le monergol des autres. Renvoie (kg, kg)."""
        sections = self.sections_reservoirs()
        cible = sections[k]
        autres = [p for j, s in enumerate(sections) if j != k for p in s]
        carb = _transvaser(cible, autres, "carburant", lambda p: p.m.carburant)
        mono = _transvaser(cible, autres, "mono", lambda p: p.m.mono)
        return carb, mono

    # --------------------------------------------------------------- ports
    def ports_libres(self):
        """Extrémités où l'on peut s'amarrer : liste parmi "haut" et "bas"."""
        out = []
        if self.pieces:
            p = self.pieces[0]
            if p.m.forme == "port" and not p.retournee:
                out.append("haut")
            p = self.pieces[-1]
            if p.m.forme == "port" and p.retournee and len(self.pieces) > 1:
                out.append("bas")
        return out

    def jonctions(self):
        """Indices i tels que pieces[i-1] et pieces[i] forment deux ports amarrés."""
        ps = self.pieces
        return [i for i in range(1, len(ps))
                if ps[i - 1].m.forme == "port" and ps[i - 1].retournee
                and ps[i].m.forme == "port" and not ps[i].retournee]

    def point_port(self, etat, extremite):
        """Position (relative au corps) et direction sortante d'un port d'extrémité."""
        g = self.geometrie()
        ca, sa = cos(self.angle), sin(self.angle)
        if extremite == "haut":
            return etat[0] + ca * g.nez, etat[1] + sa * g.nez, ca, sa
        return etat[0] + ca * g.fond, etat[1] + sa * g.fond, -ca, -sa

    # ------------------------------------------------------------ utilitaires
    def proprietaire_majoritaire(self):
        c = Counter()
        for p in self.pieces:
            c[p.proprietaire] += p.masse()
        return c.most_common(1)[0][0] if c else self.nom

    def normaliser(self):
        """Après une séparation : remet la pile à l'endroit (nez en haut). Renvoie True si retournée."""
        if self.racine is not None:
            a_l_envers = self.racine.retournee
        else:
            a_l_envers = sum(1 for p in self.pieces if p.retournee) * 2 > len(self.pieces)
        if a_l_envers:
            self.pieces = inverser(self.pieces)
            self.angle += pi
        return a_l_envers


def _transvaser(destination, sources, attribut, capacite):
    """Verse le contenu des sources dans la place libre de la destination (au prorata). Renvoie la quantité."""
    place = sum(capacite(p) - getattr(p, attribut) for p in destination)
    dispo = sum(getattr(p, attribut) for p in sources)
    quantite = min(place, dispo)
    if quantite <= 1e-6:
        return 0.0
    f = 1.0 - quantite / dispo
    for p in sources:
        setattr(p, attribut, getattr(p, attribut) * f)
    for p in destination:
        libre = capacite(p) - getattr(p, attribut)
        setattr(p, attribut, getattr(p, attribut) + quantite * libre / place)
    return quantite


def nom_section(pieces):
    """Nom lisible d'une section : son vaisseau d'origine et sa pièce principale."""
    proprio = Counter()
    for p in pieces:
        proprio[p.proprietaire] += p.masse()
    nom = proprio.most_common(1)[0][0] if proprio else ""
    chef = next((p for p in pieces if p.m.commande), None) or \
        max(pieces, key=lambda p: p.m.carburant + p.m.mono)
    return ("%s : %s" % (nom, chef.m.nom)) if nom else chef.m.nom


def inverser(pieces):
    """Retourne une pile tête-bêche (ordre inversé, chaque pièce retournée)."""
    out = list(reversed(pieces))
    for p in out:
        p.retournee = not p.retournee
    return out


def construire(nom, plan, corps):
    """Crée un vaisseau neuf à partir d'un plan (clés de pièces, du haut vers le bas)."""
    return Vaisseau(nom, pieces_depuis_plan(plan, nom), corps)
