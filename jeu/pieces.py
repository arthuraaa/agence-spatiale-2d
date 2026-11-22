# -*- coding: utf-8 -*-
"""
Catalogue des pièces. Pour ajouter une pièce : une ligne dans CATALOGUE suffit.

Remarque sur les moteurs : dans cet univers à l'échelle 1/100, toutes les
vitesses orbitales sont divisées par 10. Pour que la construction par étages
garde de l'intérêt, les impulsions spécifiques (Isp) sont réduites elles aussi
(~100-140 s au lieu de 300-450 s).
"""


class ModelePiece:
    """Définition (immuable) d'un type de pièce."""

    def __init__(self, cle, nom, categorie, forme, masse, l, h, prix, carburant=0.0,
                 mono=0.0, poussee=0.0, isp_vide=0.0, isp_sol=0.0, couple=0.0, rcs=0.0,
                 commande=False, parachute=False, largeur_auto=False, debloque_par=None,
                 couleur=(225, 228, 235), description=""):
        self.cle = cle
        self.nom = nom
        self.categorie = categorie
        self.forme = forme                # sert au dessin et à la logique (moteur, port...)
        self.masse = masse                # masse à vide (kg)
        self.l = l                        # largeur (m)
        self.h = h                        # hauteur (m)
        self.prix = prix
        self.carburant = carburant        # capacité en carburant (kg)
        self.mono = mono                  # monergol pour le RCS (kg)
        self.poussee = poussee            # poussée dans le vide (N)
        self.isp_vide = isp_vide
        self.isp_sol = isp_sol
        self.couple = couple              # couple des roues de réaction (N.m)
        self.rcs = rcs                    # poussée RCS en translation (N)
        self.commande = commande          # permet de piloter le vaisseau
        self.parachute = parachute        # parachute intégré
        self.largeur_auto = largeur_auto  # prend la largeur de la pièce voisine
        self.debloque_par = debloque_par  # identifiant de mission (mode carrière)
        self.couleur = couleur
        self.description = description


CATEGORIES = ["Commande", "Réservoirs", "Moteurs", "Structure", "Station"]

_LISTE = [
    # --- Commande -----------------------------------------------------------
    ModelePiece("capsule", "Capsule Mk1", "Commande", "capsule", 1200, 2.0, 1.9, 600,
                mono=120, couple=15_000, rcs=3_000, commande=True, parachute=True,
                description="Habitée. Parachute et RCS intégrés."),
    ModelePiece("sonde", "Sonde", "Commande", "sonde", 200, 1.2, 0.7, 350,
                mono=25, couple=3_000, rcs=600, commande=True, debloque_par="orbite",
                couleur=(200, 164, 70), description="Cœur de sonde / satellite (non habité)."),
    # --- Réservoirs -----------------------------------------------------------
    ModelePiece("reservoir_s", "Réservoir S", "Réservoirs", "reservoir", 110, 1.5, 1.5, 150,
                carburant=1000),
    ModelePiece("reservoir_m", "Réservoir M", "Réservoirs", "reservoir", 220, 1.5, 3.0, 275,
                carburant=2000),
    ModelePiece("reservoir_l", "Réservoir L", "Réservoirs", "reservoir", 440, 1.5, 6.0, 500,
                carburant=4000),
    ModelePiece("reservoir_xl", "Réservoir XL", "Réservoirs", "reservoir", 1000, 2.5, 5.0, 1000,
                carburant=9000, debloque_par="espace"),
    ModelePiece("reservoir_xxl", "Réservoir XXL", "Réservoirs", "reservoir", 2000, 2.5, 10.0, 1900,
                carburant=18000, debloque_par="lune_soi"),
    # --- Moteurs --------------------------------------------------------------
    ModelePiece("moustique", "Moustique", "Moteurs", "moteur", 150, 1.0, 0.9, 250,
                poussee=18_000, isp_vide=140, isp_sol=60, debloque_par="orbite",
                description="Petit moteur d'atterrisseur."),
    ModelePiece("alize", "Alizé", "Moteurs", "moteur", 450, 1.5, 1.4, 500,
                poussee=60_000, isp_vide=135, isp_sol=90,
                description="Moteur d'étage supérieur."),
    ModelePiece("mistral", "Mistral", "Moteurs", "moteur", 1200, 1.5, 1.8, 900,
                poussee=220_000, isp_vide=115, isp_sol=100,
                description="Moteur principal de décollage."),
    ModelePiece("titan", "Titan", "Moteurs", "moteur", 3500, 2.5, 2.4, 2200,
                poussee=800_000, isp_vide=112, isp_sol=102, debloque_par="orbite",
                description="Gros moteur pour lanceur lourd."),
    ModelePiece("atome", "Atome", "Moteurs", "moteur", 2000, 1.5, 2.6, 4000,
                poussee=40_000, isp_vide=250, isp_sol=80, debloque_par="lune_sol",
                couleur=(120, 150, 120), description="Nucléaire : très économe, peu puissant."),
    # --- Structure ------------------------------------------------------------
    ModelePiece("coiffe", "Coiffe", "Structure", "coiffe", 100, 1.5, 1.8, 100,
                description="Réduit la traînée."),
    ModelePiece("decoupleur", "Découpleur", "Structure", "decoupleur", 100, 1.5, 0.3, 200,
                largeur_auto=True, couleur=(60, 62, 70),
                description="Sépare les étages (ESPACE)."),
    ModelePiece("decoupleur_radial", "Découpleur radial", "Structure", "radial", 60, 0.4, 0.0, 150,
                debloque_par="espace", couleur=(60, 62, 70),
                description="Choisis d'abord une pièce de la fusée : une paire de boosters s'y accroche."),
    ModelePiece("train", "Train d'atterrissage", "Structure", "train", 250, 1.5, 0.4, 350,
                largeur_auto=True, debloque_par="espace", couleur=(90, 94, 104),
                description="À placer juste au-dessus du moteur."),
    # --- Station --------------------------------------------------------------
    ModelePiece("port", "Port d'amarrage", "Station", "port", 100, 1.3, 0.5, 400,
                debloque_par="orbite", couleur=(170, 176, 188),
                description="S'oriente tout seul. Deux ports collés = séparables (U)."),
    ModelePiece("port_radial", "Port latéral", "Station", "port", 90, 1.0, 0.6, 450,
                debloque_par="orbite", couleur=(170, 176, 188),
                description="Accroché sur le côté d'une pièce : un vaisseau s'amarre perpendiculaire."),
    ModelePiece("module", "Module habitat", "Station", "module", 4000, 3.0, 6.0, 3000,
                mono=150, couple=60_000, rcs=6_000, commande=True, debloque_par="orbite",
                description="Élément de station spatiale."),
    ModelePiece("panneaux", "Panneaux solaires", "Station", "panneaux", 300, 1.5, 1.0, 800,
                debloque_par="orbite", couleur=(110, 114, 126),
                description="Pour satellites et stations."),
]

CATALOGUE = {m.cle: m for m in _LISTE}      # dict ordonné : sert aussi à l'affichage


class Piece:
    """Une pièce réelle montée sur un vaisseau (avec son carburant restant...)."""

    __slots__ = ("m", "carburant", "mono", "retournee", "proprietaire", "parachute", "ouverture",
                 "laterales")

    def __init__(self, cle, proprietaire=""):
        self.m = CATALOGUE[cle]               # le modèle
        self.carburant = self.m.carburant
        self.mono = self.m.mono
        self.retournee = False                # pièce montée tête en bas
        self.proprietaire = proprietaire      # nom du vaisseau d'origine
        self.parachute = "plie" if self.m.parachute else None   # plie / ouvert
        self.ouverture = 0.0                  # 0..1 progression de l'ouverture
        # Boosters latéraux accrochés à cette pièce : la pile d'UN booster (du haut vers le bas,
        # en commençant par le découpleur radial). Il y en a toujours deux, symétriques.
        self.laterales = []

    def masse(self):
        return self.m.masse + self.carburant + self.mono

    def vers_dict(self):
        d = {"cle": self.m.cle, "carburant": self.carburant, "mono": self.mono,
             "retournee": self.retournee, "proprietaire": self.proprietaire,
             "parachute": self.parachute, "ouverture": self.ouverture}
        if self.laterales:
            d["laterales"] = [q.vers_dict() for q in self.laterales]
        return d

    @staticmethod
    def depuis_dict(d):
        p = Piece(d["cle"], d.get("proprietaire", ""))
        p.carburant = d.get("carburant", p.carburant)
        p.mono = d.get("mono", p.mono)
        p.retournee = d.get("retournee", False)
        p.parachute = d.get("parachute", p.parachute)
        p.ouverture = d.get("ouverture", 0.0)
        p.laterales = [Piece.depuis_dict(q) for q in d.get("laterales", [])]
        return p


# Modèles prêts à voler : (nom, description, liste de pièces du haut vers le bas).
# Une entrée ["pièce", [pile d'un booster]] accroche une paire de boosters à cette pièce.
MODELES = [
    ("Pionnier", "2 étages pour l'orbite ; largue tout au retour.",
     ["capsule", "decoupleur", "reservoir_m", "alize", "decoupleur", "reservoir_l", "reservoir_l",
      "mistral"]),
    ("Hermès", "Pionnier + port d'amarrage pour la station.",
     ["port", "capsule", "decoupleur", "reservoir_m", "alize", "decoupleur", "reservoir_l",
      "reservoir_l", "mistral"]),
    ("Spoutnik", "Petit satellite (sonde + panneaux) et son lanceur.",
     ["coiffe", "sonde", "panneaux", "reservoir_s", "moustique", "decoupleur", "reservoir_m",
      "alize", "decoupleur", "reservoir_l", "reservoir_l", "mistral"]),
    ("Cargo", "Apporte un module à la station et rentre.",
     ["port", "module", "port", "port", "capsule", "decoupleur", "reservoir_l", "alize",
      "decoupleur", "reservoir_xl", "reservoir_xl", "titan"]),
    ("Hercule", "Boosters latéraux ; ÉTAGE les largue d'abord.",
     ["capsule", "decoupleur", "reservoir_m", "alize", "decoupleur",
      "reservoir_l", ["reservoir_l", ["decoupleur_radial", "coiffe", "reservoir_l", "mistral"]], "mistral"]),
    ("Sélène", "3 étages : aller se poser sur la Lune et revenir.",
     ["capsule", "reservoir_m", "train", "moustique", "decoupleur", "reservoir_l", "alize",
      "decoupleur", "reservoir_xl", "reservoir_xl", "titan"]),
    ("Arès", "Lanceur lourd interplanétaire (Mars, Vénus...).",
     ["capsule", "reservoir_m", "train", "moustique", "decoupleur", "reservoir_l", "reservoir_l",
      "atome", "decoupleur", "reservoir_xxl", "reservoir_xxl", "titan"]),
]
