# -*- coding: utf-8 -*-
"""
La simulation : le temps, les vaisseaux, la physique et les règles du jeu.

Chaque vaisseau est dans l'un des trois modes :
  "pose"     : fixé au sol d'un corps (il tourne avec lui) ;
  "rails"    : en vol balistique dans le vide -> orbite képlérienne exacte,
               stable même en accélérant le temps un million de fois ;
  "physique" : poussée, RCS ou atmosphère -> intégration numérique (RK4),
               accélération du temps limitée à x4.
Le passage d'un mode à l'autre est automatique et invisible pour le joueur.
"""
from math import hypot, cos, sin, atan2, sqrt, exp, ceil, pi, copysign, radians
from .constantes import (ACCELERATIONS, ACCEL_MAX_PHYSIQUE, PAS_PHYSIQUE, MIROIR_X, CARDAN,
                         ALPHA_MIN, OMEGA_MAX, ISP_RCS, PLAFOND_TRAINEE, POSE_V_MAX,
                         POSE_V_MAX_TRAIN, POSE_H_MAX, POSE_H_MAX_TRAIN, POSE_INCLINAISON, POSE_INCLINAISON_TRAIN,
                         AMARRAGE_DISTANCE, AMARRAGE_VITESSE, AMARRAGE_COS, PORTEE_PHYSIQUE,
                         FONDS_DEPART, TAUX_RECUPERATION, LONGITUDE_PAS_DE_TIR, NOM_STATION,
                         PLAFOND_DRAPEAUX,
                         G0, BLANC, VERT, ROUGE, JAUNE, CYAN, ORANGE)
from .orbite import Orbite, angle_pi
from .corps import creer_systeme_solaire, Corps
from .vaisseau import Vaisseau, construire, inverser
from .pieces import Piece, CATALOGUE
from .trajectoire import predire, approche_minimale
from . import manoeuvre as mod_manoeuvre
from . import plateforme, reglages
from . import missions as mod_missions
from . import jalons
from .textes import t

MODES_SAS = ["stab", "pro", "retro", "rad+", "rad-", "cible", "anti", "manoeuvre"]
REFERENCES = ["orbite", "surface", "cible"]


LIMITE_RETRO_SOL = radians(75)   # RÉTRO près du sol : jamais plus penché que ça
HAUTEUR_REDRESSEMENT = 300.0     # m : en dessous, RÉTRO se redresse peu à peu...
INCLINAISON_CONTACT = radians(10)  # ... jusqu'à 10° au plus au moment de toucher le sol


class Commandes:
    """Ce que le joueur demande au vaisseau actif (mis à jour à chaque image)."""

    def __init__(self):
        self.rotation = 0     # +1 = tourner vers la gauche de l'écran, -1 = vers la droite
        self.avant = 0        # RCS : +1 avant, -1 arrière
        self.cote = 0         # RCS : +1 vers la droite, -1 vers la gauche


class Univers:
    def __init__(self, bac_a_sable=False, avec_station=True):
        self.corps, self.par_nom = creer_systeme_solaire()
        self.soleil = self.par_nom["Soleil"]
        self.terre = self.par_nom["Terre"]
        self.t = 0.0                      # temps de jeu (s)
        self.vaisseaux = []
        self.actif = None                 # vaisseau piloté
        self.cible = None                 # Vaisseau ou Corps
        self.accel = 0                    # index dans ACCELERATIONS
        self.bac_a_sable = bac_a_sable
        self.fonds = FONDS_DEPART
        self.missions_faites = set()
        self.messages = []                # [texte, durée restante, couleur]
        self.bruits = []                  # bruitages à jouer (l'écran de vol les consomme)
        self.tutoriel = None              # identifiant du tutoriel joué dans cet univers (jamais sauvegardé)
        self.effets = []                  # explosions
        self.drapeaux_sol = []            # drapeaux plantés : [{"corps", "longitude", "t"}]
        self.photos_demandees = []        # photos à prendre au prochain dessin (pose, amarrage)
        self.commandes = Commandes()
        self.instantane = None            # état sauvegardé juste avant le dernier lancement
        self.approche = None              # plus courte approche de la cible
        self.approche_plan = None         # ... sur la trajectoire prévue après la manœuvre
        self.pilote = None                # programme du pilote automatique en cours (pilote.py)
        self.triche = {}                  # options du menu secret : carburant, indestructible, pieces
        self.perdu = False                # le vaisseau actif vient d'être détruit
        self._chrono_prediction = 0.0
        self._chrono_lent = 0.0
        self._cache_abs = (None, {})
        if avec_station:
            self._creer_station()

    # ======================================================================
    # Petits outils
    # ======================================================================
    def dire(self, texte, couleur=BLANC, duree=5.0):
        self.messages.append([texte, duree, couleur])
        del self.messages[:-6]

    def stat(self, cle):
        """Compte un événement de carrière (lancement, crash...) ; rien pendant un tutoriel."""
        if not self.tutoriel:
            reglages.stat(cle)

    def piece_debloquee(self, cle):
        m = CATALOGUE[cle]
        return self.bac_a_sable or self.triche.get("pieces") or m.debloque_par is None \
            or m.debloque_par in self.missions_faites

    def nom_unique(self, nom):
        noms = {v.nom for v in self.vaisseaux}
        if nom not in noms:
            return nom
        k = 2
        while "%s %d" % (nom, k) in noms:
            k += 1
        return "%s %d" % (nom, k)

    def position_corps(self, corps):
        """Position absolue (repère du Soleil) d'un corps à l'instant courant, avec cache."""
        t, cache = self._cache_abs
        if t != self.t:
            cache = {}
            self._cache_abs = (self.t, cache)
        p = cache.get(corps)
        if p is None:
            p = cache[corps] = corps.position_absolue(self.t)
        return p

    def vitesse_corps(self, corps):
        vx = vy = 0.0
        while corps.parent is not None:
            e = corps.etat_relatif(self.t)
            vx += e[2]
            vy += e[3]
            corps = corps.parent
        return vx, vy

    def etat_pose(self, v, t=None):
        """État d'un vaisseau posé : il tourne avec le sol, posé sur le terrain."""
        c = v.corps
        t = self.t if t is None else t
        r = c.R + c.relief(v.longitude) + v.geometrie().bas
        ang = v.longitude + c.angle_rotation(t)
        w = c.vitesse_rotation
        return r * cos(ang), r * sin(ang), -w * r * sin(ang), w * r * cos(ang)

    def etat(self, v):
        """(x, y, vx, vy) du vaisseau par rapport à son corps, maintenant."""
        if v.mode == "physique":
            return v.x, v.y, v.vx, v.vy
        t, e = v.cache_etat
        if t == self.t:
            return e
        e = v.orbite.etat(self.t) if v.mode == "rails" else self.etat_pose(v)
        v.cache_etat = (self.t, e)
        return e

    def position_absolue(self, obj):
        if isinstance(obj, Corps):
            return self.position_corps(obj)
        cx, cy = self.position_corps(obj.corps)
        e = self.etat(obj)
        return cx + e[0], cy + e[1]

    def vitesse_absolue(self, obj):
        if isinstance(obj, Corps):
            return self.vitesse_corps(obj)
        vx, vy = self.vitesse_corps(obj.corps)
        e = self.etat(obj)
        return vx + e[2], vy + e[3]

    def altitude(self, v):
        """Hauteur au-dessus du terrain (et non de la sphère de rayon R)."""
        e = self.etat(v)
        c = v.corps
        return hypot(e[0], e[1]) - c.R \
            - c.relief(atan2(e[1], e[0]) - c.angle_rotation(self.t))

    def vitesse_reference(self, v):
        """Vecteur vitesse selon la référence choisie (orbite / surface / cible)."""
        x, y, vx, vy = self.etat(v)
        if v.ref_vitesse == "cible" and self.cible is not None:
            ax, ay = self.vitesse_absolue(v)
            cx, cy = self.vitesse_absolue(self.cible)
            return ax - cx, ay - cy
        if v.ref_vitesse == "surface":
            w = v.corps.vitesse_rotation
            return vx + w * y, vy - w * x
        return vx, vy

    def situation(self, v):
        if v.mode == "pose":
            return t("Posé")
        alt = self.altitude(v)
        if alt < v.corps.atm_h:
            return t("Vol atmosphérique")
        o = v.orbite
        if o is None:
            return t("En vol")
        if not o.elliptique or o.ra > v.corps.soi:
            return t("Trajectoire d'évasion")
        if o.rp < v.corps.R + v.corps.atm_h:
            return t("Vol suborbital")
        return t("En orbite")

    # ======================================================================
    # Création / lancement / récupération
    # ======================================================================
    def _creer_station(self):
        s = construire(NOM_STATION, ["port", "module", "panneaux", "module", "port"], self.terre)
        r = self.terre.R + 15_000.0
        vit = sqrt(self.terre.mu / r)
        ang = 2.2
        s.angle = 0.0
        s.corps = self.terre
        self.vaisseaux.append(s)
        self._mettre_sur_rails(s, (r * cos(ang), r * sin(ang), -vit * sin(ang), vit * cos(ang)))

    def lancer(self, nom, cles):
        """Pose un vaisseau neuf sur le pas de tir et en donne le contrôle au joueur."""
        from .sauvegarde import univers_vers_dict
        self.instantane = univers_vers_dict(self)
        for v in list(self.vaisseaux):                  # libère le pas de tir
            if v.mode == "pose" and v.corps is self.terre and \
                    abs(angle_pi(v.longitude - LONGITUDE_PAS_DE_TIR)) * self.terre.R < 80.0:
                self.recuperer(v, silencieux=True)
        if not self.bac_a_sable:
            from .vaisseau import prix_plan
            self.fonds -= prix_plan(cles)
        v = construire(self.nom_unique(nom), cles, self.terre)
        v.mode = "pose"
        v.longitude = LONGITUDE_PAS_DE_TIR
        v.cache_etat = (None, None)
        self.vaisseaux.append(v)
        self.actif = v
        self.perdu = False
        self.accel = 0
        self.stat("lancements")
        conseil = t("Pousse la manette des gaz vers le haut") if plateforme.TACTILE else t("Mets les gaz (Z ou W)")
        if not self.tutoriel:                            # pendant un tutoriel, la bulle explique
            self.dire(t("{nom} est sur le pas de tir. {conseil} pour décoller !", nom=v.nom, conseil=conseil), CYAN, 8)
        return v

    def peut_recuperer(self, v):
        return v is not None and v.mode == "pose" and v.corps is self.terre

    def recuperer(self, v, silencieux=False):
        if not self.peut_recuperer(v):
            return False
        gain = int(v.prix() * TAUX_RECUPERATION)
        if not self.bac_a_sable:
            self.fonds += gain
        self._retirer(v)
        if not silencieux:
            self.dire(t("{nom} récupéré (+{gain})", nom=v.nom, gain=gain), VERT)
        return True

    def _retirer(self, v):
        if v in self.vaisseaux:
            self.vaisseaux.remove(v)
        if self.cible is v:
            self.cible = None
        if self.actif is v:
            self.actif = None

    def _message_destruction(self, v, raison):
        """« {nom} détruit : {raison} », dans la langue active."""
        return t("{nom} détruit{raison}", nom=v.nom,
                 raison=t(" : {raison}", raison=raison) if raison else "")

    def _detruire(self, v, raison="", silencieux=False):
        if v.detruit:
            return
        v.detruit = True
        if not silencieux:                             # les débris nettoyés sans bruit ne comptent pas
            self.stat("crashs")
        e = self.etat(v)
        a = self.actif
        if not silencieux and a is not None and (a is v or (a.corps is v.corps and
                                                          hypot(*[p - q for p, q in zip(self.etat(a)[:2], e[:2])]) < 5000.0)):
            self.bruit("explosion")
        c = v.corps
        self.effets.append({"corps": c, "r": hypot(e[0], e[1]),
                            "lon": atan2(e[1], e[0]) - c.angle_rotation(self.t),
                            "age": 0.0, "taille": max(6.0, v.geometrie().longueur)})
        etait_actif = v is self.actif
        self._retirer(v)
        if etait_actif:
            self.perdu = True
            self.accel = 0
            self.dire(self._message_destruction(v, raison), ROUGE, 8)
        elif not silencieux and v.controlable():
            self.dire(self._message_destruction(v, raison), ORANGE)

    # ======================================================================
    # Actions du joueur
    # ======================================================================
    def controler(self, v):
        self.arreter_pilote(fin=True)
        a = self.actif
        if v is a or not v.controlable():
            return False
        if a is not None and a.mode == "physique" and self.altitude(a) < a.corps.atm_h:
            self.dire(t("Impossible de changer de vaisseau en vol atmosphérique"), ORANGE)
            return False
        if a is not None:
            a.gaz = 0.0
        self.actif = v
        self.perdu = False
        if self.cible is v:
            self.cible = None
        self.accel = min(self.accel, ACCEL_MAX_PHYSIQUE)
        if v.mode == "rails":
            self._predire(v)
        self.recalculer_plan()
        self.dire(t("Contrôle : {nom}", nom=v.nom), CYAN)
        return True

    def vaisseau_suivant(self):
        liste = [v for v in self.vaisseaux if v.controlable()]
        if not liste:
            return
        i = liste.index(self.actif) if self.actif in liste else -1
        self.controler(liste[(i + 1) % len(liste)])

    def cibler(self, obj):
        if obj is self.actif:
            return
        self.cible = obj
        self._calculer_approche()
        self.recalculer_plan()
        if obj is not None:
            self.dire(t("Cible : {nom}", nom=t(obj.nom)), CYAN, 3)

    def changer_acceleration(self, delta):
        self.accel = max(0, min(len(ACCELERATIONS) - 1, self.accel + delta))
        avant = self.accel
        self._limiter_acceleration()
        if self.accel < avant and delta > 0:
            a = self.actif
            if a is not None and a.mode == "physique":
                self.dire(t("Accélération limitée à x4 (poussée ou atmosphère)"), ORANGE, 3)

    def separer_etage(self):
        v = self.actif
        if v is None:
            return
        from .vaisseau import indice_decoupleur_bas, porteurs_actifs
        if porteurs_actifs(v.pieces):                  # les boosters partent en premier
            self._larguer_boosters(v)
            self.bruit("separation")
            self.dire(t("Boosters largués"), JAUNE, 3)
            self.stat("etages")
            return
        i = indice_decoupleur_bas(v.pieces)
        if i is None or i == 0:
            self.dire(t("Aucun étage à séparer"), ORANGE, 3)
            return
        self._scinder(v, i, 1.2)
        self.stat("etages")
        self.bruit("separation")
        self.dire(t("Séparation de l'étage"), JAUNE, 3)

    def desamarrer(self):
        v = self.actif
        if v is None:
            return
        k = v.pieces.index(v.racine) if v.racine in v.pieces else 0
        js = [(min(abs(i - k), abs(i - 1 - k)), "jonction", i) for i in v.jonctions()]
        ks = [(min(abs(kk - k), abs(kk + 1 - k)), "annexe", kk)
              for kk, p in enumerate(v.pieces)
              if p.laterales and p.laterales[0].m.cle == "port_radial" and len(p.laterales) > 1]
        if not js and not ks:
            self.dire(t("Aucun port amarré à séparer"), ORANGE, 3)
            return
        _, genre, i = min(js + ks)
        if genre == "jonction":
            autre = self._scinder(v, i, 0.4)
        else:
            autre = self._separer_annexe(v, i)
        v.separe_de, autre.separe_de = autre.id, v.id
        self.dire(t("Désamarrage de {nom}", nom=autre.nom), JAUNE, 4)
        self.bruit("amarrage")

    def _separer_annexe(self, v, k):
        """Détache l'annexe amarrée sur le port latéral de la pièce k. Renvoie le nouveau vaisseau."""
        g = v.geometrie()
        pile = v.pieces[k].laterales
        pieces = pile[1:]
        m_a = sum(q.masse() for q in pieces)
        y_a = 0.0
        for kk, p2, ec, sg, _, _ in g.laterales:
            if kk == k:
                ecart, segs = ec, sg
        for q, (yh, yb) in zip(pile[1:], segs[1:]):
            y_a += q.masse() * 0.5 * (yh + yb)
        y_annexe = y_a / m_a
        # centre du vaisseau restant (toutes les pièces + les autres piles latérales)
        morceaux = [(p.masse(), 0.5 * (s[0] + s[1])) for p, s in zip(v.pieces, g.segments)]
        for kk, p2, _, sg, _, n in g.laterales:
            if kk != k:
                morceaux += [(n * q.masse(), 0.5 * (s[0] + s[1])) for q, s in zip(p2, sg)]
        m_r = sum(m0 for m0, _ in morceaux)
        y_reste = sum(m0 * yy for m0, yy in morceaux) / m_r
        x, y, vx, vy = self.etat(v)
        ca, sa = cos(v.angle), sin(v.angle)
        px, py = sa, -ca                                   # côté droit, comme point_port_radial
        mode_avant = v.mode
        v.pieces[k].laterales = pile[:1]
        impulsion = 0.4                                    # l'annexe part du flanc
        total = m_a + m_r
        dv_r = impulsion * m_a / total                     # et le vaisseau restant recule d'autant
        etat_annexe = (x + ca * y_annexe + px * ecart, y + sa * y_annexe + py * ecart,
                       vx + px * impulsion, vy + py * impulsion)
        etat_reste = (x + ca * y_reste, y + sa * y_reste, vx - px * dv_r, vy - py * dv_r)
        nouveau = Vaisseau("", pieces, v.corps)
        nouveau.angle, nouveau.omega = v.angle, 0.0
        nouveau.drapeaux = set(v.drapeaux)
        nouveau.sas = "stab"
        for vs, e in ((v, etat_reste), (nouveau, etat_annexe)):
            vs.cache_etat = (None, None)
            vs.orbite = None
            vs.troncons = []
            if mode_avant == "pose":
                vs.mode, vs.longitude = "pose", v.longitude
            else:
                vs.x, vs.y, vs.vx, vs.vy = e
                vs.mode = "physique"
                vs.orbite = Orbite(e[0], e[1], e[2], e[3], v.corps.mu, self.t)
            vs.normaliser()
        if nouveau.racine is None:
            nouveau.nom = self.nom_unique(t("Débris de {nom}", nom=v.nom))
        else:
            nouveau.nom = self.nom_unique(nouveau.proprietaire_majoritaire())
        self.vaisseaux.append(nouveau)
        return nouveau

    def ouvrir_parachute(self):
        v = self.actif
        if v is None:
            return
        plies = [p for p in v.parachutes() if p.parachute == "plie"]
        if not plies:
            self.dire(t("Pas de parachute disponible"), ORANGE, 3)
            return
        if v.corps.densite(self.altitude(v)) <= 0.0:
            self.dire(t("Pas d'atmosphère ici : le parachute est inutile"), ORANGE, 3)
            return
        x, y, vx, vy = self.etat(v)
        w = v.corps.vitesse_rotation
        if hypot(vx + w * y, vy - w * x) > 250.0:
            self.dire(t("Trop rapide pour ouvrir le parachute (max 250 m/s)"), ORANGE, 3)
            return
        for p in plies:
            p.parachute = "ouvert"
            p.ouverture = 0.05
        self.dire(t("Parachute déployé"), VERT, 3)
        self.bruit("parachute")

    def planter_drapeau(self):
        """Plante un drapeau à l'endroit où le vaisseau actif est posé (il reste après le départ)."""
        v = self.actif
        if v is None:
            return
        if v.mode != "pose":
            self.dire(t("Il faut être posé pour planter un drapeau"), ORANGE, 3)
            return
        c = v.corps
        if c.gazeux:                         # géante gazeuse ou étoile : pas de surface
            self.dire(t("{corps} n'a pas de surface où planter un drapeau", corps=t(c.nom)), ORANGE, 3)
            return
        if sum(1 for d in self.drapeaux_sol if d["corps"] == c.nom) >= PLAFOND_DRAPEAUX:
            self.dire(t("Trop de drapeaux sur {corps}", corps=t(c.nom)), ORANGE, 3)
            return
        self.drapeaux_sol.append({"corps": c.nom, "longitude": v.longitude, "t": self.t})
        v.drapeaux.add("drapeau:" + c.nom)   # copié aux séparations : il suit la capsule
        self.dire(t("Drapeau planté sur {corps}", corps=t(c.nom)), VERT, 3)
        self.bruit("pose")

    # ======================================================================
    # Nœud de manœuvre
    # ======================================================================
    def bruit(self, nom):
        """Demande un bruitage (la simulation ne joue rien elle-même)."""
        self.bruits.append(nom)
        del self.bruits[:-20]

    def placer_noeud(self, instant, pro=0.0, rad=0.0):
        """Crée (ou remplace) le nœud du vaisseau actif à l'instant t."""
        v = self.actif
        if v is None or v.mode == "pose" or not v.troncons:
            self.dire(t("Il faut être en vol pour planifier une manœuvre"), ORANGE, 3)
            return None
        v.noeud = mod_manoeuvre.Manoeuvre(max(instant, self.t), pro, rad)
        self.recalculer_plan()
        self.bruit("bip")
        return v.noeud

    def regler_noeud(self, pro=None, rad=None, t=None):
        """Modifie le nœud (sans effet si la combustion a commencé)."""
        v = self.actif
        n = None if v is None else v.noeud
        if n is None or n.commencee:
            return
        if pro is not None:
            n.pro = pro
        if rad is not None:
            n.rad = rad
        if t is not None:
            n.t = max(t, self.t)
        self.recalculer_plan()

    def decaler_noeud(self, tours):
        """Avance ou recule le nœud d'un tour d'orbite entier."""
        v = self.actif
        n = None if v is None else v.noeud
        if n is None or n.commencee:
            return
        p = mod_manoeuvre.periode_au_noeud(v, n)
        if p is None:
            self.dire(t("Orbite non fermée : impossible de décaler d'un tour"), ORANGE, 3)
            return
        self.regler_noeud(t=n.t + tours * p)

    def supprimer_noeud(self):
        v = self.actif
        if v is None or v.noeud is None:
            return
        v.noeud, v.plan = None, []
        self.approche_plan = None
        if v.sas == "manoeuvre":
            v.sas = "stab"

    def filer_au_noeud(self):
        """Accélère le temps au maximum : le limiteur s'arrêtera tout seul avant l'allumage."""
        v = self.actif
        if v is None or v.noeud is None:
            return
        self.accel = len(ACCELERATIONS) - 1
        self._limiter_acceleration()

    def recalculer_plan(self):
        """Recalcule la trajectoire prévue après la manœuvre du vaisseau actif."""
        v = self.actif
        self.approche_plan = None
        if v is None:
            return
        if v.noeud is None or not v.troncons:
            v.plan = []
            return
        v.plan = mod_manoeuvre.plan(v, v.noeud, v.geometrie().bas, 4)
        self.approche_plan = self._approche_sur(v.plan)

    def _consommer_noeud(self, v, dvx, dvy):
        """Retranche du nœud le Δv réellement donné pendant un pas de temps."""
        n = v.noeud
        if not n.commencee:
            duree = mod_manoeuvre.duree_combustion(v, n.dv())[0]
            if abs(self.t - n.t) > 0.5 * duree + mod_manoeuvre.FENETRE:
                return                        # poussée sans rapport avec le nœud (trop loin)
            vec = mod_manoeuvre.impulsion(v, n)
            if vec is None:
                return
            n.commencer(vec)
            fini = hypot(vec[0], vec[1]) < mod_manoeuvre.FIN_MANOEUVRE
            if fini:
                n.consommer(0.0, 0.0)                  # nœud à Δv nul : rien à brûler, déjà fini
        else:
            fini = False
        if (fini or n.consommer(dvx, dvy)) and not getattr(n, "pilote_energie", False):
            ecart = n.dv()
            self.supprimer_noeud()
            v.drapeaux.add("noeud")                    # un jalon marque la première manœuvre exécutée
            if self.pilote is not None:                # exécution automatique : on coupe net
                v.gaz = 0.0
            self.dire(t("Manœuvre terminée (écart {ecart} m/s)", ecart="%.2f" % ecart), VERT, 4)

    # ======================================================================
    # Boucle de simulation
    # ======================================================================
    def lancer_pilote(self, programme):
        """Confie le vaisseau actif à un programme du pilote automatique."""
        if not reglages.AIDES or self.actif is None:
            return
        self.pilote = programme
        self.commandes.avant = self.commandes.cote = 0   # pas d'ordre RCS résiduel (amarrage auto)
        self.dire(t("Pilote automatique : {nom}", nom=t(programme.nom)), CYAN, 4)

    def arreter_pilote(self, fin=False):
        if self.pilote is None:
            return
        self.pilote = None
        self.commandes.avant = self.commandes.cote = 0
        v = self.actif
        if v is not None and (v.sas == "pilote" or (v.sas == "manoeuvre" and v.noeud is None)):
            v.sas = "stab"
        if not fin:
            self.dire(t("Pilote automatique désactivé"), ORANGE, 3)

    def avancer(self, dt_reel):
        dt_reel = min(dt_reel, 0.05)
        if self.pilote is not None:                 # le pilote agit comme un joueur, avant la physique
            a = self.actif
            if a is None or a.detruit or not self.pilote.piloter(self, a):
                self.arreter_pilote(fin=True)
        self._limiter_acceleration()
        dt = dt_reel * ACCELERATIONS[self.accel]
        a = self.actif
        # Changement de sphère d'influence du vaisseau piloté : l'image s'arrête pile sur
        # l'événement (sinon, à x1 000 000, on traverserait toute la SOI d'un coup).
        if a is not None and a.mode == "rails" and a.troncons \
                and a.troncons[0].fin in ("entree", "sortie"):
            dt = min(dt, max(a.troncons[0].t1 - self.t, 0.0) + 1e-3)
        # ... et pile sur l'allumage d'une manœuvre planifiée
        if a is not None and a.noeud is not None and not a.noeud.commencee:
            debut = mod_manoeuvre.instant_allumage(a, a.noeud)
            if debut > self.t:
                dt = min(dt, debut - self.t + 1e-3)
        for v in list(self.vaisseaux):
            if v.mode == "physique" and v is not a:
                self._surveiller_non_actif(v)
        physiques = [v for v in self.vaisseaux if v.mode == "physique"]
        t_fin = self.t + dt
        if physiques:
            n = max(1, int(ceil(dt / PAS_PHYSIQUE - 1e-9)))
            h = dt / n
            for _ in range(n):
                for v in physiques:
                    if v.mode == "physique" and not v.detruit:
                        self._pas_physique(v, h, v is a)
                self.t += h
        self.t = t_fin
        for v in list(self.vaisseaux):
            if v.mode == "rails" and not v.detruit:
                self._avancer_rails(v)
                if v.mode == "rails":
                    self._rotation_sur_rails(v, dt, v is self.actif)
        self._gerer_modes()
        self._verifier_amarrage()
        self._periodique(dt_reel)
        if self.triche.get("carburant") and self.actif is not None:
            from .triche import faire_le_plein        # triche : réservoirs toujours pleins
            faire_le_plein(self.actif)

    def _limiter_acceleration(self):
        maxi = len(ACCELERATIONS) - 1
        a = self.actif
        if a is not None and not a.detruit:
            if a.mode == "physique":
                maxi = ACCEL_MAX_PHYSIQUE
            elif a.mode == "rails" and a.troncons:
                tr = a.troncons[0]
                # avant une rentrée ou un impact on ralentit : le joueur garde 3 s (réelles) pour réagir
                if tr.fin in ("atmo", "impact"):
                    reste = tr.t1 - self.t
                    while maxi > 0 and ACCELERATIONS[maxi] * 3.0 > reste:
                        maxi -= 1
            n = a.noeud
            if n is not None and not n.commencee:
                duree = mod_manoeuvre.duree_combustion(a, n.dv())[0]
                reste = n.t - duree / 2.0 - self.t
                if reste > 0.0:                      # on ne saute pas par-dessus l'allumage
                    while maxi > 0 and ACCELERATIONS[maxi] * 3.0 > reste:
                        maxi -= 1
                elif self.t < n.t + duree:           # pendant la fenêtre de tir : temps réel
                    maxi = min(maxi, ACCEL_MAX_PHYSIQUE)
        if self.accel > maxi:
            self.accel = maxi

    # ----------------------------------------------------------- mode physique
    def _pas_physique(self, v, h, actif):
        """Avance un vaisseau d'un petit pas h (s) par intégration RK4."""
        c = v.corps
        g = v.geometrie()
        m = g.masse
        x, y, vx, vy = v.x, v.y, v.vx, v.vy
        r = hypot(x, y)
        rho = c.densite(r - c.R)
        if not actif:
            v.gaz = 0.0
        poussee, debit = v.poussee_et_debit(rho / 1.225)
        if debit > 0.0:
            v.bruler(h)                                # chaque moteur puise dans ses réservoirs
        self._pas_rotation(v, h, actif, poussee, g, rho)
        ca, sa = cos(v.angle), sin(v.angle)
        tx, ty = poussee / m * ca, poussee / m * sa
        cmd = self.commandes
        if actif and v.rcs and (cmd.avant or cmd.cote) and v.mono() > 0.0:
            f = v.poussee_rcs()
            norme = hypot(cmd.avant, cmd.cote)
            f *= min(1.0, norme)                   # le pilote automatique dose ; le clavier pousse à fond
            fa = f * cmd.avant / norme
            fc = f * cmd.cote / norme * (1.0 if MIROIR_X else -1.0)
            tx += (fa * ca - fc * sa) / m
            ty += (fa * sa + fc * ca) / m
            v.consommer_mono(f / (ISP_RCS * G0) * h)
        if actif and v.noeud is not None and (tx != 0.0 or ty != 0.0):
            self._consommer_noeud(v, tx * h, ty * h)
        w = c.vitesse_rotation
        kd = 0.0
        if rho > 0.0:
            rvx, rvy = vx + w * y, vy - w * x
            sp = hypot(rvx, rvy)
            ci = (rvx * ca + rvy * sa) / sp if sp > 0.01 else 1.0
            kd = 0.5 * (v.cd_a(ci, sqrt(max(0.0, 1.0 - ci * ci))) + v.surface_parachutes()) / m
            for p in v.pieces:
                if p.parachute == "ouvert" and p.ouverture < 1.0:
                    p.ouverture = min(1.0, p.ouverture + h / 3.0)
        mu, R, atm_h, rho0, H = c.mu, c.R, c.atm_h, c.rho0, c.H

        def acc(x, y, vx, vy):
            r2 = x * x + y * y
            r = sqrt(r2)
            k = -mu / (r2 * r)
            ax, ay = k * x + tx, k * y + ty
            if kd > 0.0 and r - R < atm_h:
                rvx, rvy = vx + w * y, vy - w * x
                sp = sqrt(rvx * rvx + rvy * rvy)
                f = kd * rho0 * exp(-max(0.0, r - R) / H) * sp
                if f * sp > PLAFOND_TRAINEE:
                    f = PLAFOND_TRAINEE / sp
                ax -= f * rvx
                ay -= f * rvy
            return ax, ay

        a1x, a1y = acc(x, y, vx, vy)
        x2, y2, vx2, vy2 = x + vx * h / 2, y + vy * h / 2, vx + a1x * h / 2, vy + a1y * h / 2
        a2x, a2y = acc(x2, y2, vx2, vy2)
        x3, y3, vx3, vy3 = x + vx2 * h / 2, y + vy2 * h / 2, vx + a2x * h / 2, vy + a2y * h / 2
        a3x, a3y = acc(x3, y3, vx3, vy3)
        x4, y4, vx4, vy4 = x + vx3 * h, y + vy3 * h, vx + a3x * h, vy + a3y * h
        a4x, a4y = acc(x4, y4, vx4, vy4)
        v.x = x = x + h * (vx + 2 * vx2 + 2 * vx3 + vx4) / 6
        v.y = y = y + h * (vy + 2 * vy2 + 2 * vy3 + vy4) / 6
        v.vx = vx = vx + h * (a1x + 2 * a2x + 2 * a3x + a4x) / 6
        v.vy = vy = vy + h * (a1y + 2 * a2y + 2 * a3y + a4y) / 6

        # --- contact avec le sol (par le bas ou par le nez) ; le terrain a du relief
        r = hypot(x, y)
        if r - max(g.bas, g.haut) <= c.R + c.relief_max:
            rot = c.angle_rotation(self.t + h)
            rb = hypot(x - ca * g.bas, y - sa * g.bas) \
                - c.R - c.relief(atan2(y - sa * g.bas, x - ca * g.bas) - rot)
            rh = hypot(x + ca * g.haut, y + sa * g.haut) \
                - c.R - c.relief(atan2(y + sa * g.haut, x + ca * g.haut) - rot)
            if min(rb, rh) <= 0.0:
                vr = ((vx + w * y) * x + (vy - w * x) * y) / r
                if vr <= 0.0:
                    self._toucher(v, x, y, vx, vy, self.t + h)
                return
        # --- changement de sphère d'influence
        if r > c.soi:
            self._changer_corps(v, c.parent, (x, y, vx, vy), self.t + h)
        elif c.enfants:
            for e in c.enfants:
                ex, ey = e.position_relative(self.t + h)
                if hypot(x - ex, y - ey) < e.soi * 0.985:
                    self._changer_corps(v, e, (x, y, vx, vy), self.t + h)
                    break

    def _pas_rotation(self, v, h, actif, poussee=0.0, g=None, rho=0.0):
        """Attitude : commandes du joueur, SAS, et effet girouette du parachute."""
        if rho > 0.0 and v.parachute_ouvert():
            w = v.corps.vitesse_rotation
            rvx, rvy = v.vx + w * v.y, v.vy - w * v.x
            q = 0.5 * rho * (rvx * rvx + rvy * rvy)
            err = angle_pi(atan2(-rvy, -rvx) - v.angle)
            # la voile porte le poids de la capsule à toute vitesse : le
            # redressement ne doit pas mourir quand q s'effondre en fin de
            # descente (rentrée plane à sec : le nez restait couché et la
            # capsule touchait « posé de travers » / « impact à 8 m/s »)
            v.omega += (4.0 * err - 2.5 * v.omega) * h * max(min(1.0, q / 50.0), 0.25)
        if actif and v.controlable():
            g = g or v.geometrie()
            couple = v.couple() + poussee * sin(CARDAN) * (g.longueur - g.haut)
            alpha = max(ALPHA_MIN, couple / g.inertie)
            cmd = self.commandes.rotation * (-1.0 if MIROIR_X else 1.0)
            if cmd != 0:
                v.omega += cmd * alpha * h
            elif v.sas != "off" and not (v.sas == "stab" and rho > 0.0 and v.parachute_ouvert()):
                # (sous parachute, STAB laisse la voile redresser la capsule au lieu de la bloquer)
                cible = self.angle_sas(v)
                if cible is None:                       # stabilisation : on freine la rotation
                    d = alpha * h
                    v.omega = 0.0 if abs(v.omega) <= d else v.omega - copysign(d, v.omega)
                else:                                   # maintien d'une direction
                    err = angle_pi(cible - v.angle)
                    voulu = min(OMEGA_MAX, 0.8 * sqrt(2.0 * alpha * abs(err)), 4.0 * abs(err))
                    voulu = copysign(voulu, err)
                    v.omega += max(-alpha * h, min(alpha * h, voulu - v.omega))
        v.omega = max(-3.0, min(3.0, v.omega))
        v.angle = angle_pi(v.angle + v.omega * h)

    def _rotation_sur_rails(self, v, dt, actif):
        if ACCELERATIONS[self.accel] > ACCELERATIONS[ACCEL_MAX_PHYSIQUE]:
            v.omega = 0.0                               # en forte accélération : attitude figée
            if actif and v.sas not in ("off", "stab"):
                cible = self.angle_sas(v)
                if cible is not None:
                    v.angle = angle_pi(cible)
            return
        n = max(1, int(ceil(dt / PAS_PHYSIQUE - 1e-9)))
        for _ in range(n):
            self._pas_rotation(v, dt / n, actif)

    def angle_sas(self, v):
        """Direction que le SAS doit tenir (None = simple stabilisation)."""
        m = v.sas
        if m in ("stab", "off"):
            return None
        if m == "pilote":
            return v.cap_pilote
        if m == "manoeuvre":
            return None if v.noeud is None else mod_manoeuvre.angle_dv(v, v.noeud)
        x, y, vx, vy = self.etat(v)
        if m in ("rad+", "rad-"):
            a = atan2(y, x)
            return a if m == "rad+" else a + pi
        if m in ("cible", "anti"):
            if self.cible is None:
                return None
            ax, ay = self.position_absolue(v)
            cx, cy = self.position_absolue(self.cible)
            a = atan2(cy - ay, cx - ax)
            return a if m == "cible" else a + pi
        rvx, rvy = self.vitesse_reference(v)
        s = hypot(rvx, rvy)
        if v.ref_vitesse == "surface":
            return self._pro_retro_surface(v, m, x, y, rvx, rvy, s)
        if s < 0.05:
            return None
        a = atan2(rvy, rvx)
        return a if m == "pro" else a + pi

    def _pro_retro_surface(self, v, m, x, y, rvx, rvy, s):
        """PRO / RÉTRO par rapport au sol, pensés pour l'atterrissage.

        Quand la vitesse devient faible, sa direction n'a plus de sens : la moindre dérive la fait
        pivoter, et si la poussée fait remonter le vaisseau, RÉTRO viserait le sol. Le SAS suivait
        et le vaisseau tourbillonnait. Désormais :
          - sous 15 m/s, on se redresse peu à peu vers la verticale (tout droit à l'arrêt) ;
          - près du sol, RÉTRO ne pointe jamais le moteur vers le ciel (75° de la verticale au plus) ;
          - dans les 300 derniers mètres, on se redresse pour toucher le sol presque droit
            (10° au plus au contact) : sinon la moindre dérive horizontale fait poser de travers.
        """
        haut = atan2(y, x)
        if s < 0.05:
            return haut
        ecart = angle_pi(atan2(rvy, rvx) + (0.0 if m == "pro" else pi) - haut)
        hauteur = hypot(x, y) - v.corps.R - v.geometrie().bas
        if m == "retro" and hauteur < 5000.0:
            limite = LIMITE_RETRO_SOL
            if hauteur < HAUTEUR_REDRESSEMENT:
                f = max(0.0, hauteur) / HAUTEUR_REDRESSEMENT
                limite = INCLINAISON_CONTACT + (LIMITE_RETRO_SOL - INCLINAISON_CONTACT) * f
            ecart = max(-limite, min(limite, ecart))
        k = max(0.0, min(1.0, (s - 1.0) / 14.0))
        return haut + ecart * k

    def _surveiller_non_actif(self, v):
        """Débris en mode physique : sur rails dès que possible, supprimés s'ils sont trop loin."""
        a = self.actif
        if self.altitude(v) > v.corps.atm_h and self._mettre_sur_rails(v):
            return
        loin = a is None or a.corps is not v.corps
        if not loin:
            ea, ev = self.etat(a), self.etat(v)
            loin = hypot(ea[0] - ev[0], ea[1] - ev[1]) > PORTEE_PHYSIQUE
        if loin or self.accel > ACCEL_MAX_PHYSIQUE:
            self._detruire(v, "rentrée atmosphérique", silencieux=True)

    # -------------------------------------------------------------- mode rails
    def _mettre_sur_rails(self, v, etat=None):
        if etat is None:
            etat = self.etat(v)
        orb = Orbite(etat[0], etat[1], etat[2], etat[3], v.corps.mu, self.t)
        if orb.degeneree:
            return False
        v.orbite = orb
        v.mode = "rails"
        v.cache_etat = (None, None)
        self._predire(v)
        return True

    def _predire(self, v, t=None):
        n = 4 if v is self.actif else 1
        v.troncons = predire(v.orbite, v.corps, self.t if t is None else t, v.geometrie().bas, n)

    def _vers_physique(self, v, etat=None):
        v.x, v.y, v.vx, v.vy = etat or self.etat(v)
        v.mode = "physique"
        v.cache_etat = (None, None)

    def _avancer_rails(self, v):
        """Déclenche les événements datés (SOI, atmosphère, impact) arrivés à échéance."""
        for _ in range(8):
            if v.mode != "rails" or v.detruit or not v.troncons:
                return
            tr = v.troncons[0]
            if tr.fin is None or tr.t1 > self.t:
                return
            if tr.fin == "revoir":
                self._predire(v)
                return
            te = tr.t1
            etat = tr.orbite.etat(te)
            if tr.fin == "sortie":
                self._changer_corps(v, v.corps.parent, etat, te)
            elif tr.fin == "entree":
                self._changer_corps(v, tr.suivant, etat, te)
            elif tr.fin == "atmo":
                proche = v is self.actif
                a = self.actif
                if not proche and a is not None and a.corps is v.corps:
                    ea = self.etat(a)
                    proche = hypot(ea[0] - etat[0], ea[1] - etat[1]) < PORTEE_PHYSIQUE
                if proche:
                    self._vers_physique(v, etat)
                    if v is self.actif:
                        self.dire(t("Entrée dans l'atmosphère de {corps}", corps=t(v.corps.nom)), JAUNE)
                else:
                    self._detruire(v, "désintégré dans l'atmosphère", silencieux=(v.racine is None))
            elif tr.fin == "impact":
                self._toucher(v, etat[0], etat[1], etat[2], etat[3], te)

    def _changer_corps(self, v, nouveau, etat, instant):
        """Passe dans la sphère d'influence d'un autre corps (parent ou satellite)."""
        ancien = v.corps
        x, y, vx, vy = etat
        if nouveau is ancien.parent:
            b = ancien.etat_relatif(instant)
            etat = (x + b[0], y + b[1], vx + b[2], vy + b[3])
        else:
            b = nouveau.etat_relatif(instant)
            etat = (x - b[0], y - b[1], vx - b[2], vy - b[3])
        v.corps = nouveau
        v.drapeaux.add("soi:" + nouveau.nom)
        v.cache_etat = (None, None)
        if v.mode == "rails":
            orb = Orbite(etat[0], etat[1], etat[2], etat[3], nouveau.mu, instant)
            if orb.degeneree:
                self._vers_physique(v, etat)
            else:
                v.orbite = orb
                self._predire(v, instant)
        else:
            v.x, v.y, v.vx, v.vy = etat
        if v is self.actif:
            if nouveau is ancien.parent:
                self.dire(t("Sortie de la sphère d'influence de {corps}", corps=t(ancien.nom)), CYAN)
            else:
                self.dire(t("Entrée dans la sphère d'influence de {corps}", corps=t(nouveau.nom)), CYAN)
                self.accel = 0

    def _toucher(self, v, x, y, vx, vy, instant):
        """Contact avec le sol : atterrissage réussi ou destruction."""
        c = v.corps
        r = hypot(x, y)
        ux, uy = x / r, y / r
        w = c.vitesse_rotation
        rvx, rvy = vx + w * y, vy - w * x
        v_vert = rvx * ux + rvy * uy
        v_horiz = -rvx * uy + rvy * ux
        inclinaison = abs(angle_pi(v.angle - atan2(y, x)))
        train = v.a_un_train()
        v_max = POSE_V_MAX_TRAIN if train else POSE_V_MAX
        h_max = POSE_H_MAX_TRAIN if train else POSE_H_MAX
        incl_max = POSE_INCLINAISON_TRAIN if train else POSE_INCLINAISON
        v.x, v.y, v.vx, v.vy = x, y, vx, vy
        v.cache_etat = (None, None)
        if c.gazeux:
            v.mode = "physique"
            self._detruire(v, t("englouti par {corps}", corps=t(c.nom)))
        elif (-v_vert > v_max or abs(v_horiz) > h_max or inclinaison > incl_max) \
                and not self.triche.get("indestructible"):
            v.mode = "physique"
            if inclinaison > incl_max:
                raison = t("posé de travers")
            elif abs(v_horiz) > h_max:
                raison = t("vitesse horizontale trop forte ({v:.0f} m/s)", v=abs(v_horiz))
            else:
                raison = t("impact à {v:.0f} m/s", v=-v_vert)
            self._detruire(v, raison)
        else:
            if v is self.actif:
                self.bruit("pose")
            if inclinaison > incl_max:                 # triche « indestructible » : on le redresse
                v.angle = atan2(y, x)
            v.mode = "pose"
            v.longitude = angle_pi(atan2(y, x) - c.angle_rotation(instant))
            v.omega = 0.0
            v.gaz = 0.0
            v.orbite = None
            v.troncons = []
            for p in v.parachutes():
                p.parachute, p.ouverture = "plie", 0.0
            v.drapeaux.add("pose:" + c.nom)
            self.stat("poses")
            if not self.tutoriel:                # photo du moment (hors tutoriels/scénarios)
                self.photos_demandees.append(("pose", c.nom))
            if v is self.actif:
                self.dire(t("Posé sur {corps} ({v:.1f} m/s)", corps=t(c.nom), v=-v_vert), VERT)
                self.accel = 0

    # ------------------------------------------------------ gestion des modes
    def _besoin_physique(self, v):
        if self.altitude(v) < v.corps.atm_h:
            return True
        if v.gaz > 0.0 and v.poussee_et_debit(1.0)[0] > 0.0:   # moteur central OU boosters qui brûlent
            return True
        cmd = self.commandes
        return bool(v.rcs and (cmd.avant or cmd.cote) and v.mono() > 0.0)

    def _gerer_modes(self):
        a = self.actif
        for v in self.vaisseaux:
            if v.detruit:
                continue
            if v.mode == "pose":
                e = self.etat_pose(v)
                v.angle = atan2(e[1], e[0])
                v.omega = 0.0
                if v is a and v.gaz > 0.0:              # décollage ?
                    c = v.corps
                    r = hypot(e[0], e[1])
                    poussee, _ = v.poussee_et_debit(c.densite(r - c.R) / 1.225)
                    pesanteur = c.mu / (r * r) - c.vitesse_rotation ** 2 * r
                    if poussee / v.masse() > pesanteur:
                        self._vers_physique(v, e)
                        self.dire(t("Décollage !"), VERT, 3)
            elif v is a:
                besoin = self._besoin_physique(v)
                if v.mode == "rails" and besoin:
                    self._vers_physique(v)
                elif v.mode == "physique" and not besoin:
                    self._mettre_sur_rails(v)

    # -------------------------------------------------- séparation / amarrage
    def _larguer_boosters(self, v):
        """Détache les boosters de la section du bas : chacun devient un débris qui s'écarte."""
        from .vaisseau import porteurs_actifs
        g = v.geometrie()
        x, y, vx, vy = self.etat(v)
        ca, sa = cos(v.angle), sin(v.angle)
        lx, ly = -sa, ca                                   # direction latérale
        porteurs = porteurs_actifs(v.pieces)
        largues = masse_larguee = moment = 0.0
        for k, pile, ecart, segs, demi, n in g.laterales:
            if v.pieces[k] not in porteurs:
                continue                              # une annexe sur port latéral ne se largue pas
            m = sum(q.masse() for q in pile)
            ym = sum(q.masse() * 0.5 * (a + b) for q, (a, b) in zip(pile, segs)) / m if m > 0 else 0.0
            for cote in (-1.0, 1.0):
                copie = [Piece.depuis_dict(q.vers_dict()) for q in pile]
                debris = Vaisseau("", copie, v.corps)
                debris.angle, debris.omega = v.angle, v.omega
                debris.nom = self.nom_unique("Booster de %s" % v.nom)
                debris.cache_etat = (None, None)
                e = (x + ca * ym + lx * ecart * cote, y + sa * ym + ly * ecart * cote,
                     vx + lx * cote * 2.0, vy + ly * cote * 2.0)       # petite poussée vers l'extérieur
                if v.mode == "pose":
                    debris.mode, debris.longitude = "pose", v.longitude
                else:
                    debris.x, debris.y, debris.vx, debris.vy = e
                    debris.mode = "physique"
                    debris.orbite = Orbite(e[0], e[1], e[2], e[3], v.corps.mu, self.t)
                self.vaisseaux.append(debris)
            masse_larguee += 2 * m
            moment += 2 * m * ym
            v.pieces[k].laterales = []
        # le centre de masse du vaisseau se déplace : on recale sa position
        m_reste = g.masse - masse_larguee
        decalage = -moment / m_reste if m_reste > 0 else 0.0
        v.cache_etat = (None, None)
        if v.mode != "pose":
            v.x, v.y, v.vx, v.vy = x + ca * decalage, y + sa * decalage, vx, vy
            v.mode = "physique"
            v.orbite = Orbite(v.x, v.y, v.vx, v.vy, v.corps.mu, self.t)
            v.troncons = []

    def _scinder(self, v, i, impulsion):
        """Coupe la pile de v entre les pièces i-1 et i. Renvoie le nouveau vaisseau."""
        g = v.geometrie()
        x, y, vx, vy = self.etat(v)
        mode_avant = v.mode

        def centre(a, b):
            # masse et centre de la tranche, boosters latéraux compris (comme geometrie()) ;
            # une pile latérale compte n exemplaires (2 : paire miroir, 1 : annexe amarrée)
            morceaux = [(p.masse(), 0.5 * (s[0] + s[1]))
                        for p, s in zip(v.pieces[a:b], g.segments[a:b])]
            for k, pile, _, segs, _, n in g.laterales:
                if a <= k < b:
                    morceaux += [(n * q.masse(), 0.5 * (s[0] + s[1])) for q, s in zip(pile, segs)]
            m = sum(m0 for m0, _ in morceaux)
            ym = sum(m0 * y for m0, y in morceaux) / m
            return m, ym

        m_h, y_h = centre(0, i)
        m_b, y_b = centre(i, len(v.pieces))
        total = m_h + m_b
        ca, sa = cos(v.angle), sin(v.angle)
        dv_h, dv_b = impulsion * m_b / total, -impulsion * m_h / total
        etat_h = (x + ca * y_h, y + sa * y_h, vx + ca * dv_h, vy + sa * dv_h)
        etat_b = (x + ca * y_b, y + sa * y_b, vx + ca * dv_b, vy + sa * dv_b)
        haut, bas = v.pieces[:i], v.pieces[i:]
        racine_en_haut = v.racine is None or any(p is v.racine for p in haut)
        garde, autre = (haut, bas) if racine_en_haut else (bas, haut)
        etat_garde, etat_autre = (etat_h, etat_b) if racine_en_haut else (etat_b, etat_h)

        nouveau = Vaisseau("", autre, v.corps)
        nouveau.angle, nouveau.omega = v.angle, v.omega
        nouveau.drapeaux = set(v.drapeaux)
        nouveau.sas = "stab"
        v.pieces = garde
        for vs, e in ((v, etat_garde), (nouveau, etat_autre)):
            vs.cache_etat = (None, None)
            vs.orbite = None
            vs.troncons = []
            if mode_avant == "pose":
                vs.mode, vs.longitude = "pose", v.longitude
            else:
                vs.x, vs.y, vs.vx, vs.vy = e
                vs.mode = "physique"
                vs.orbite = Orbite(e[0], e[1], e[2], e[3], v.corps.mu, self.t)
            vs.normaliser()
        if v.racine is not None and v.racine.proprietaire:
            v.nom = v.racine.proprietaire
        if nouveau.racine is None:
            nouveau.nom = self.nom_unique(t("Débris de {nom}", nom=v.nom))
        else:
            nouveau.nom = self.nom_unique(nouveau.proprietaire_majoritaire())
        self.vaisseaux.append(nouveau)
        return nouveau

    def _verifier_amarrage(self):
        a = self.actif
        if a is None or a.mode == "pose" or self.accel > ACCEL_MAX_PHYSIQUE:
            return
        ports_a = a.ports_libres()
        radiaux_a = a.ports_radiaux()
        if not ports_a and not radiaux_a:
            return
        ea = self.etat(a)
        for b in self.vaisseaux:
            if b is a or b.corps is not a.corps or b.mode == "pose" or b.detruit:
                continue
            eb = self.etat(b)
            if hypot(ea[0] - eb[0], ea[1] - eb[1]) > 300.0:
                continue
            paires = []
            for pa in ports_a:
                ax, ay, adx, ady = a.point_port(ea, pa)
                for pb in b.ports_libres():
                    bx, by, bdx, bdy = b.point_port(eb, pb)
                    paires.append((hypot(ax - bx, ay - by), adx * bdx + ady * bdy, pa, pb))
                for k in b.ports_radiaux():       # notre extrémité sur le port latéral de l'autre
                    bx, by, bdx, bdy = b.point_port_radial(eb, k)
                    paires.append((hypot(ax - bx, ay - by), adx * bdx + ady * bdy, pa, ("lat", k)))
            for k in radiaux_a:                   # ou notre port latéral qui reçoit l'autre
                ax, ay, adx, ady = a.point_port_radial(ea, k)
                for pb in b.ports_libres():
                    bx, by, bdx, bdy = b.point_port(eb, pb)
                    paires.append((hypot(ax - bx, ay - by), adx * bdx + ady * bdy, ("lat", k), pb))
            if not paires:
                continue
            d, alignement, pa, pb = min(paires, key=lambda p: (p[0], p[1]))
            if a.separe_de == b.id:                     # on vient de se séparer : attendre
                if d > 3.0:
                    a.separe_de = b.separe_de = None
                continue
            if d < AMARRAGE_DISTANCE and alignement < -AMARRAGE_COS \
                    and hypot(ea[2] - eb[2], ea[3] - eb[3]) < AMARRAGE_VITESSE:
                self._amarrer(a, b, pa, pb, ea, eb)
                return

    def _amarrer(self, a, b, pa, pb, ea, eb):
        """Fusionne b dans a (la pile reste dans le repère du vaisseau actif).
        Un port « ("lat", k) » désigne le port latéral de la pièce k : l'autre vaisseau
        devient une annexe accrochée sur le flanc, qui se détache avec U."""
        ma, mb = a.masse(), b.masse()
        m = ma + mb
        if isinstance(pa, tuple):                 # le port latéral de a reçoit b
            recepteur, annexe, extremite, k = a, b, pb, pa[1]
        elif isinstance(pb, tuple):               # le port latéral de b reçoit a
            recepteur, annexe, extremite, k = b, a, pa, pb[1]
        elif pa == "haut":
            recepteur, annexe, extremite, k = a, b, pb, None
            a.pieces = (b.pieces if pb == "bas" else inverser(b.pieces)) + a.pieces
        else:
            recepteur, annexe, extremite, k = a, b, pb, None
            a.pieces = a.pieces + (b.pieces if pb == "haut" else inverser(b.pieces))
        if k is not None:                         # l'annexe part du flanc vers l'extérieur :
            port = recepteur.pieces[k].laterales[0]   # la pièce amarrée est collée au port
            recepteur.pieces[k].laterales = [port] + \
                (inverser(annexe.pieces) if extremite == "bas" else annexe.pieces)
        etat = tuple((ma * ea[i] + mb * eb[i]) / m for i in range(4))
        recepteur.omega = 0.0
        recepteur.drapeaux |= annexe.drapeaux
        recepteur.drapeaux.add("amarre:" + annexe.nom)
        self.stat("amarrages")
        if annexe.contient_proprietaire(NOM_STATION):
            recepteur.drapeaux.add("amarre:" + NOM_STATION)
        nom_b = annexe.nom
        etait_actif = self.actif is annexe
        self._retirer(annexe)
        annexe.detruit = True
        if etait_actif:
            self.actif = recepteur                # on garde le contrôle du vaisseau qui reste
        self._vers_physique(recepteur, etat)
        recepteur.gaz = 0.0
        self.dire(t("Amarrage réussi avec {nom} !", nom=nom_b), VERT, 6)
        self.bruit("amarrage")
        if not self.tutoriel:                    # photo du moment (hors tutoriels/scénarios)
            self.photos_demandees.append(("amarrage", recepteur.corps.nom))

    # ------------------------------------------------------ tâches périodiques
    def _periodique(self, dt_reel):
        for m in self.messages:
            m[1] -= dt_reel
        self.messages = [m for m in self.messages if m[1] > 0.0]
        for e in self.effets:
            e["age"] += dt_reel
        self.effets = [e for e in self.effets if e["age"] < 1.6]
        a = self.actif
        self._chrono_prediction += dt_reel
        if a is not None and a.mode == "physique" and self._chrono_prediction > 0.15:
            self._chrono_prediction = 0.0
            orb = Orbite(a.x, a.y, a.vx, a.vy, a.corps.mu, self.t)
            a.orbite = orb
            a.troncons = [] if orb.degeneree else predire(orb, a.corps, self.t, a.geometrie().bas, 4)
        self._chrono_lent += dt_reel
        if self._chrono_lent > 0.5:
            self._chrono_lent = 0.0
            self._calculer_approche()
            self.recalculer_plan()
            self._maj_drapeaux()
            if not self.tutoriel:                      # pas de missions ni de jalons pendant un tutoriel
                mod_missions.verifier(self)
                jalons.verifier(self)
        if a is not None and a.noeud is not None and not a.noeud.commencee:
            duree = mod_manoeuvre.duree_combustion(a, a.noeud.dv())[0]
            if self.t > a.noeud.t + max(60.0, duree):          # nœud jamais exécuté : on l'efface
                self.supprimer_noeud()
                self.dire(t("Nœud de manœuvre dépassé"), ORANGE, 4)
        if a is not None:                               # référence de vitesse automatique
            seuil = max(a.corps.atm_h, 2500.0)
            auto = "surface" if (a.mode == "pose" or self.altitude(a) < seuil) else "orbite"
            if auto != a.ref_auto:
                a.ref_auto = a.ref_vitesse = auto

    def _maj_drapeaux(self):
        for v in self.vaisseaux:
            if v.mode == "rails" and v.orbite.elliptique:
                c = v.corps
                if v.orbite.rp > c.R + max(c.atm_h, 1000.0) and v.orbite.ra < c.soi:
                    v.drapeaux.add("orbite:" + c.nom)

    def _approche_sur(self, troncons):
        """Plus courte approche de la cible le long d'une trajectoire (ou None)."""
        c = self.cible
        if c is None or not troncons:
            return None
        if isinstance(c, Vaisseau):
            parent = c.corps
            if c.mode == "rails":
                f = c.orbite.position
            elif c.mode == "pose":
                f = lambda t: self.etat_pose(c, t)[:2]
            else:
                return None
        else:
            parent = c.parent
            f = c.position_relative
            if parent is None:
                return None
        r = approche_minimale(troncons, f, parent, self.t)
        return None if r is None else r + (parent,)

    def _calculer_approche(self):
        a = self.actif
        self.approche = None if a is None else self._approche_sur(a.troncons)
