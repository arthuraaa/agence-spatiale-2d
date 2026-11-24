# -*- coding: utf-8 -*-
"""
Aides au pilotage (activables ou non dans le menu : « Aides au pilotage »).

    - Mise en orbite automatique ;
    - exécution automatique d'un nœud de manœuvre ;
    - assistant : circularisation, transfert vers une lune ou une planète ;
    - informations d'atterrissage (altitude, impact, moment où commencer à freiner).

Un programme de pilotage agit comme un joueur : il règle les gaz, choisit où pointer
(c'est le SAS qui fait tourner le vaisseau, avec le couple disponible) et appuie sur
ÉTAGE quand l'étage en cours est vide. Toucher aux commandes le désactive.
"""
from math import atan2, hypot, pi, sqrt, acos, cos, sin
from .constantes import ACCELERATIONS, MIROIR_X
from .orbite import angle_pi, TAU
from .trajectoire import approche_minimale
from . import manoeuvre as mod_man
from .textes import t


def poussee_max(v):
    """Poussée totale (N, dans le vide) si l'on mettait plein gaz maintenant."""
    return sum(n * mot.m.poussee for mot, res, n in v.moteurs() if sum(r.carburant for r in res) > 0)


def _vitesse_surface(c, x, y, vx, vy):
    """Vitesse par rapport au sol qui tourne sous le vaisseau."""
    w = c.vitesse_rotation
    return vx + w * y, vy - w * x


# =============================================================================
# Programmes de pilotage
# =============================================================================
class Programme:
    nom = ""

    def piloter(self, u, v):
        """Appelé à chaque image. Renvoie False quand le programme est terminé."""
        return False

    @staticmethod
    def etager_si_vide(u, v):
        if v.gaz > 0 and v.etage_epuise():
            u.separer_etage()


class ExecuterNoeud(Programme):
    """Pointe dans l'axe du nœud, avance le temps jusqu'à l'allumage, pousse, coupe.

    Une poussée réelle dure un moment, pendant lequel le vaisseau tourne autour de la planète :
    en visant une direction figée, on perd 1 à 2 % d'efficacité (assez pour rater la Lune).
    Le pilote adapte donc sa façon de pousser au but de la manœuvre :
      - circularisation (orbite visée ronde) : il pousse à l'horizontale et coupe quand
        l'orbite est la plus ronde possible ;
      - autre manœuvre prograde ou rétrograde (transfert...) : il suit le prograde réel et
        coupe quand l'énergie de l'orbite atteint celle du plan (c'est elle qui fixe l'apoapside) ;
      - sinon : il suit la direction du nœud jusqu'à épuisement de son Δv.
    """
    nom = "manœuvre"

    def __init__(self):
        self.but = None                 # "rond", "energie" ou "noeud"
        self.sens = 1                   # +1 : on accélère, -1 : on freine
        self.energie_visee = None
        self.reste_precedent = None        # Δv restant à l'image précédente (circularisation)

    def _choisir_but(self, v, n):
        self.sens = 1 if n.pro >= 0 else -1
        o = v.plan[0].orbite if v.plan and v.plan[0].corps is v.corps else None
        if o is None or abs(n.rad) > 0.1 * abs(n.pro):
            self.but = "noeud"
        elif o.elliptique and o.e < 0.02 and o.e < v.troncons[0].orbite.e - 0.005:
            self.but = "rond"                           # on rend l'orbite ronde (pas un simple phasage)
        else:
            self.but, self.energie_visee = "energie", o.energie

    def _fin(self, u, v, message=None):
        v.gaz = 0.0
        u.supprimer_noeud()
        u.dire(message if message is not None else t("Manœuvre exécutée"), (120, 230, 140), 4)
        return False

    def piloter(self, u, v):
        n = v.noeud
        if n is None:                                  # nœud consommé : c'est fini
            v.gaz = 0.0
            return False
        if self.but is None:
            if n.commencee:                                # combustion déjà lancée (à la main) :
                self.but = "noeud"                         # on suit le nœud tel quel, sans crash
            else:
                self._choisir_but(v, n)
        allumage = mod_man.instant_allumage(v, n)
        if not n.commencee and u.t < allumage - 30.0:  # on patiente en accélérant le temps
            v.sas, v.gaz = "manoeuvre", 0.0
            u.accel = len(ACCELERATIONS) - 1           # le limiteur ralentira avant l'allumage
            return True
        u.accel = 0
        brule = u.t >= allumage or n.commencee
        x, y, vx, vy = u.etat(v)
        r, vitesse = hypot(x, y), hypot(vx, vy)
        mu = v.corps.mu
        if not brule or self.but == "noeud":
            v.sas = "manoeuvre"
            vise, reste = mod_man.angle_dv(v, n), n.dv()
        else:
            n.pilote_energie = True                    # c'est le pilote qui dira quand c'est fini
            v.sas = "pilote"
            if self.but == "rond":
                ux, uy = x / r, y / r
                hx, hy = -uy, ux                       # horizontale, dans le sens du mouvement
                if hx * vx + hy * vy < 0:
                    hx, hy = -hx, -hy
                v_hor, v_rad = hx * vx + hy * vy, ux * vx + uy * vy
                # Δv qui donnerait ici une orbite ronde : (vitesse circulaire, à l'horizontale) - vitesse
                dvx = (sqrt(mu / r) - v_hor) * hx - v_rad * ux
                dvy = (sqrt(mu / r) - v_hor) * hy - v_rad * uy
                reste = hypot(dvx, dvy)
                if reste < 0.3 or (self.reste_precedent is not None and reste > self.reste_precedent + 0.05
                                   and reste < 20.0):
                    return self._fin(u, v)            # orbite ronde (ou on commence à s'en éloigner)
                self.reste_precedent = reste
                vise = atan2(dvy, dvx)
            else:
                energie = 0.5 * vitesse * vitesse - mu / r
                reste = (self.energie_visee - energie) * self.sens / max(vitesse, 1.0)
                if reste <= 0.02:
                    return self._fin(u, v)
                vise = atan2(vy, vx) + (0.0 if self.sens > 0 else pi)
            v.cap_pilote = vise
        erreur = abs(angle_pi(v.angle - vise)) if vise is not None else 0.0
        if not brule:
            v.gaz = 0.0
            return True
        f = poussee_max(v)
        if f <= 0.0:                                   # étage vide : ÉTAGE, sinon abandon
            self.etager_si_vide(u, v)
            if poussee_max(v) > 0.0:
                v.gaz = 1.0                            # nouvel étage : plein gaz tout de suite
                return True
            # abandon : on coupe les gaz (sinon la manette reste à fond) et on prévient
            v.gaz = 0.0
            u.dire(t("Manœuvre interrompue : plus de carburant"), (255, 160, 90), 4)
            return False
        if erreur < 0.05:
            v.gaz = max(0.02, min(1.0, reste / (f / v.masse())))       # douceur sur la dernière seconde
        elif erreur > 0.15:
            v.gaz = 0.0
        self.etager_si_vide(u, v)
        return True


class MiseEnOrbite(Programme):
    """Virage gravitationnel, croisière hors de l'atmosphère, puis circularisation par un nœud."""
    nom = "orbite"

    def __init__(self):
        self.phase = "montee"
        self.circularisation = None

    def piloter(self, u, v):
        c = v.corps
        ap_vise = c.atm_h * 1.85 if c.atm_h > 0 else 0.15 * c.R
        x, y, vx, vy = u.etat(v)
        alt = hypot(x, y) - c.R
        haut = atan2(y, x)
        if self.phase == "montee":
            debut, fin = (150.0, 0.8 * c.atm_h) if c.atm_h > 0 else (30.0, 0.4 * ap_vise)
            inclinaison = min(pi / 2, (pi / 2) * max(0.0, (alt - debut) / fin) ** 0.55)
            v.sas, v.cap_pilote, v.gaz = "pilote", haut + inclinaison, 1.0
            u.accel = min(u.accel, 3)
            self.etager_si_vide(u, v)
            if v.orbite is not None and v.orbite.elliptique and v.orbite.ra - c.R > ap_vise:
                v.gaz = 0.0
                self.phase = "croisiere"
            elif poussee_max(v) <= 0.0 and v.delta_v() < 1.0:
                u.dire(t("Pilote : plus de carburant pour atteindre l'orbite"), (255, 150, 60), 5)
                return False
        elif self.phase == "croisiere":             # on sort de l'atmosphère, nez en avant
            v.sas, v.gaz = "pro", 0.0
            if alt > c.atm_h + 200.0 and v.mode == "rails":
                if not planifier_circularisation(u, v, silencieux=True):
                    return False
                self.phase, self.circularisation = "circularisation", ExecuterNoeud()
            elif v.mode == "rails":
                u.accel = min(max(u.accel, 3), 4)
        else:
            if not self.circularisation.piloter(u, v):
                o = v.orbite
                ok = o is not None and o.elliptique and o.rp - c.R > c.atm_h + 500.0
                u.dire(t("Pilote : en orbite !") if ok else t("Pilote : orbite incomplète"), (120, 230, 140), 5)
                return False
        return True


# =============================================================================
# Assistant de manœuvres (pose un nœud ; « Exécuter » s'occupe du reste)
# =============================================================================
def planifier_circularisation(u, v, silencieux=False):
    """Nœud à la prochaine apoapside (au périapside si l'orbite est ouverte) pour une orbite ronde."""
    if v.mode == "pose" or not v.troncons:
        return False
    o = v.troncons[0].orbite
    if o.elliptique and o.ra < 1e18:
        instant, r = u.t + o.delai_apoapside(u.t), o.ra
    else:
        d = o.delai_periapside(u.t)
        if d is None or d < 0:
            if not silencieux:
                u.dire(t("Circularisation impossible : le périapside est passé"), (255, 150, 60), 4)
            return False
        instant, r = u.t + d, o.rp
    vitesse = sqrt(max(0.0, o.mu * (2.0 / r - 1.0 / o.a)))
    u.placer_noeud(instant, pro=sqrt(o.mu / r) - vitesse)
    if not silencieux:
        u.dire(t("Nœud de circularisation posé ({dv:+.0f} m/s)", dv=sqrt(o.mu / r) - vitesse), (110, 200, 235), 4)
    return True


def _rencontre(plan, cible):
    return next((tr for tr in plan if tr.entree and tr.corps is cible), None)


def _dv_pour_apoapside(v, t, r_vise):
    """Δv prograde (au temps t) qui porte l'apoapside à r_vise, par dichotomie."""
    n = mod_man.Manoeuvre(t)
    bas, haut = 0.0, 3000.0
    for _ in range(40):
        n.pro = 0.5 * (bas + haut)
        r = mod_man.orbite_apres(v, n)
        ra = r[0].ra if (r is not None and r[0].elliptique) else float("inf")
        if ra < r_vise:
            bas = n.pro
        else:
            haut = n.pro
    return 0.5 * (bas + haut)


def _chercher(u, v, cible, parent, candidats):
    """Parmi des (instant, Δv), le meilleur : une rencontre, sinon l'approche la plus serrée."""
    meilleur = None
    for t, dv in candidats:
        n = mod_man.Manoeuvre(t, dv)
        plan = mod_man.plan(v, n, 0.0, 4)
        tr = _rencontre(plan, cible)
        if tr is not None:
            haut_peri = tr.orbite.rp - cible.R - cible.atm_h
            note = -1e12 + abs(haut_peri - 0.3 * cible.R) if haut_peri > 0 else -1e11
            d = 0.0
        else:
            appr = approche_minimale(plan, cible.position_relative, parent, t)
            if appr is None:
                continue
            d = appr[1]
            note = d
        if meilleur is None or note < meilleur[0]:
            meilleur = (note, t, dv, tr is not None, d)
    return meilleur


def planifier_transfert(u, v, cible):
    """Pose le nœud de départ vers une lune du corps actuel, ou vers une planète voisine."""
    if v.mode == "pose" or not v.troncons or not v.troncons[0].orbite.elliptique:
        u.dire(t("Transfert : il faut d'abord être en orbite"), (255, 150, 60), 4)
        return False
    o, c = v.troncons[0].orbite, v.corps
    periode = o.periode
    if cible.parent is c:                                   # une lune : on vise son orbite
        pas = periode / 72.0
        candidats = [(u.t + (k + 0.5) * pas, _dv_pour_apoapside(v, u.t + (k + 0.5) * pas, cible.a))
                     for k in range(72)]
        meilleur = _chercher(u, v, cible, c, candidats)
        attente = None
    elif c.parent is not None and cible.parent is c.parent and cible is not c:
        meilleur, attente = _transfert_planete(u, v, o, c, cible)
    else:
        u.dire(t("Transfert direct impossible vers {vers} depuis {de}", vers=t(cible.nom), de=t(c.nom)), (255, 150, 60), 5)
        return False
    if meilleur is None:
        u.dire(t("Transfert : aucune trajectoire trouvée"), (255, 150, 60), 4)
        return False
    _, instant, dv, rencontre, d = meilleur
    for _ in range(2):                                      # affinage du Δv au plus près
        mieux = _chercher(u, v, cible, cible.parent, [(instant, dv + k * 0.5) for k in range(-12, 13)])
        if mieux is not None and mieux[0] < meilleur[0]:
            meilleur = mieux
        _, instant, dv, rencontre, d = meilleur
    u.placer_noeud(instant, pro=dv)
    quand = "" if attente is None else t(" (fenêtre de tir dans {j:.1f} j)", j=attente / 86400.0)
    if rencontre:
        u.dire(t("Transfert vers {corps} planifié{quand} : {dv:+.0f} m/s",
                 corps=t(cible.nom), quand=quand, dv=dv), (120, 230, 140), 6)
    else:
        u.dire(t("Transfert vers {corps} : passage à {km:.0f} km, affine le nœud à la main{quand}",
                 corps=t(cible.nom), km=d / 1e3, quand=quand), (255, 200, 90), 6)
    return True


def planifier_retour(u, v):
    """Depuis l'orbite d'une lune : nœud qui ramène vers sa planète, périapside au ras de
    l'atmosphère (on y rentre sans avoir à freiner). On essaie 48 endroits de l'orbite et plusieurs
    poussées, puis on affine la meilleure."""
    c = v.corps
    p = c.parent
    if p is None or p.parent is None or v.mode == "pose" or not v.troncons \
            or not v.troncons[0].orbite.elliptique:
        u.dire(t("Retour : il faut être en orbite autour d'une lune"), (255, 150, 60), 5)
        return False
    o = v.troncons[0].orbite
    vise = p.R + (0.4 * p.atm_h if p.atm_h > 0 else 0.03 * p.R)
    v_ech = sqrt(2.0 * c.mu / o.a) - sqrt(c.mu / o.a)        # poussée minimale pour quitter la lune

    def essai(t, dv):
        plan = mod_man.plan(v, mod_man.Manoeuvre(t, dv), 0.0, 3)
        tr = next((tr for tr in plan if tr.corps is p), None)
        if tr is None:
            return None
        return (abs(tr.orbite.rp - vise) + 20.0 * dv, t, dv, tr.orbite.rp)

    # 96 endroits de l'orbite : la direction de départ compte plus que tout, une grille
    # trop grossière rate la fenêtre et « planifie » un survol à des milliers de km
    notes = [e for e in (essai(u.t + 30.0 + k * o.periode / 96.0, v_ech * (1.02 + 0.08 * j))
                         for k in range(96) for j in range(12)) if e is not None]
    if not notes:
        u.dire(t("Retour : aucune trajectoire trouvée"), (255, 150, 60), 5)
        return False
    meilleur = min(notes)
    for pas_t, pas_dv in ((o.periode / 200.0, 0.02 * v_ech), (o.periode / 1000.0, 0.004 * v_ech)):
        _, t0, dv0, _ = meilleur
        notes = [e for e in (essai(t0 + i * pas_t, dv0 + j * pas_dv)
                             for i in range(-4, 5) for j in range(-4, 5)) if e is not None]
        meilleur = min(notes + [meilleur])
    _, instant, dv, rp = meilleur
    u.placer_noeud(instant, pro=dv)
    u.dire(t("Retour vers {corps} planifié : périapside à {km:.1f} km ({dv:+.0f} m/s)",
             corps=t(p.nom), km=(rp - p.R) / 1e3, dv=dv), (120, 230, 140), 6)
    return True


def _transfert_planete(u, v, o, planete, cible):
    """Fenêtre de tir (transfert de Hohmann entre les deux planètes), puis départ depuis l'orbite."""
    soleil = planete.parent
    a1, a2 = planete.a, cible.a
    at = 0.5 * (a1 + a2)
    duree = pi * sqrt(at ** 3 / soleil.mu)

    def angle(corps, t):
        x, y = corps.position_relative(t)
        return atan2(y, x)

    # 1) quand la cible sera-t-elle au bon endroit ? (angle d'avance pour un Hohmann)
    phase_ideale = pi - cible.n * duree
    dn = cible.n - planete.n
    phase = angle_pi(angle(cible, u.t) - angle(planete, u.t))
    attente = ((phase_ideale - phase) / dn) % (TAU / abs(dn))
    t_fenetre = u.t + attente
    # 2) vitesse d'excès hyperbolique à fournir, et direction de sortie (sens de la planète)
    v_inf = sqrt(soleil.mu * (2.0 / a1 - 1.0 / at)) - sqrt(soleil.mu / a1)
    _, _, vxp, vyp = planete.etat_relatif(t_fenetre)
    direction = atan2(vyp, vxp) + (0.0 if v_inf > 0 else pi)
    r0, mu = o.a, planete.mu
    e = 1.0 + r0 * v_inf * v_inf / mu
    x, y, vx, vy = o.etat(u.t)
    sens = 1.0 if x * vy - y * vx > 0 else -1.0
    angle_peri = direction - sens * acos(-1.0 / e)      # l'allumage se fait au futur périapside
    # 3) instant où le vaisseau passe à cet angle, autour de la fenêtre
    meilleur_t, ecart = t_fenetre, 9.0
    for k in range(240):
        t = t_fenetre - 0.5 * o.periode + k * o.periode / 240.0
        px, py = o.position(t)
        d = abs(angle_pi(atan2(py, px) - angle_peri))
        if d < ecart:
            meilleur_t, ecart = t, d
    dv0 = sqrt(v_inf * v_inf + 2.0 * mu / r0) - sqrt(mu / r0)
    # 4) affinage : grille grossière puis fine autour de l'estimation
    grille = [(meilleur_t + i * 0.025 * o.periode, dv0 + j * 5.0) for i in range(-10, 11) for j in range(-4, 5)]
    m = _chercher(u, v, cible, soleil, grille)
    if m is not None:
        grille = [(m[1] + i * 0.005 * o.periode, m[2] + j * 1.0) for i in range(-5, 6) for j in range(-4, 5)]
        m2 = _chercher(u, v, cible, soleil, grille)
        m = m2 if m2 is not None and m2[0] < m[0] else m
    return m, attente


def simule_rentree(corps, x, y, vx, vy, masse, cd_a, a_moteur=0.0, dv_moteur=0.0,
                   limite=250.0, s_voile=0.0, contact_max=250.0, t0=0.0, info=None):
    """Verdict d'une rentrée : depuis cet état, le vaisseau peut-il se POSER ?
    Intégration grossière : la gravité partout, l'air sous le plafond (freiné par
    rapport au sol), le moteur en rétro tant qu'on dépasse la limite d'ouverture de
    la voile et tant qu'il reste du carburant (dv_moteur).
    Avec s_voile > 0 (surface de voiles toutes ouvertes), la voile se déploie dès que
    la vitesse le permet, avec sa montée en puissance de 3 s ; le verdict alors exige
    un contact sous contact_max (la limite de POSE, pas « juste pas brûlé » : sur une
    rentrée raide, la voile ne s'ouvrait qu'à 30 m du sol — trop tard pour rien).
    C'est un verdict, pas une prédiction : le contact est jugé au niveau 0 de la
    surface. Le relief du lieu de rentrée, lui, compte pour l'ouverture de la
    voile : si l'air n'amène la vitesse à la limite d'ouverture qu'au ras des
    collines (rentrée rasante), la voile ouvre trop tard — verdict refusé, et le
    pilote raidira la rentrée ou renoncera au lieu d'écraser le vaisseau."""
    w = corps.vitesse_rotation
    dt = 2.0
    ouv = 0.0
    t = 0.0
    alt_ouv = None                                  # altitude d'ouverture de la voile
    t_ouv = None                                    # instant (pour le relief du lieu)
    for _ in range(1000000):
        t += dt
        r = hypot(x, y)
        alt = r - corps.R
        vrx, vry = vx + w * y, vy - w * x        # vitesse par rapport au sol
        vrel = hypot(vrx, vry)
        # le terrain SOUS le vaisseau (longitude liée au sol) : on se pose sur le
        # relief, pas au niveau 0 de la mer — juger le contact à R + 0 fait tomber
        # le verdict des centaines de mètres plus bas que la vraie pose (davantage
        # de chute, frein plus long côté verdict) et refusait des poses réussies.
        sol = corps.relief(atan2(y, x) - corps.angle_rotation(t0 + t))
        haut = alt - sol                         # hauteur au-dessus du TERRAIN
        if alt <= sol:
            if info is not None:
                info["alt_ouv"] = alt_ouv           # None si la voile n'a jamais ouvert
                info["v_contact"] = vrel
            if s_voile > 0.0 and alt_ouv is not None:
                # relief du lieu de rentrée (longitude où la voile devait s'ouvrir) :
                # une ouverture au ras des collines arrive trop tard pour rien
                lon_ouv = atan2(y, x) - corps.angle_rotation(t0 + t_ouv)
                if alt_ouv <= corps.relief(lon_ouv) + 60.0:
                    return False
            return vrel <= contact_max           # au sol : posable ou écrasé
            # (et non à +300 m : sur une entrée raide, l'air ne devient assez dense
            # pour la limite de pose que dans les derniers 300 m — s'arrêter plus tôt
            # refusait des vaisseaux que la voile pose pourtant tout en douceur)
        if alt <= corps.atm_h:
            if s_voile > 0.0 and vrel <= limite:
                if ouv == 0.0:                   # la voile commence à s'ouvrir ici :
                    alt_ouv, t_ouv = alt, t      # assez haut au-dessus du relief ?
                ouv = min(1.0, ouv + dt / 3.0)   # la voile se gonfle en 3 s (univers)
            cda = cd_a + s_voile * ouv * ouv
            k = 0.5 * corps.densite(alt) * cda * vrel / masse
            vx -= k * vrx * dt
            vy -= k * vry * dt
        g = corps.mu / (r * r)
        vx -= g * x / r * dt
        vy -= g * y / r * dt
        dans_air = alt <= corps.atm_h
        # le frein « moteur » n'attend la vitesse d'ouverture de la voile que s'il y a
        # une voile : en plein vide (Lune), la chute depuis l'orbite reste sous 250 m/s
        # et le moteur n'aurait jamais freiné — verdict faux, pose refusée à tort.
        seuil = limite if (dans_air and s_voile > 0.0) else 0.0
        # le frein du verdict IMITE le vrai contrôleur, ce n'est pas un suicide-burn
        # idéal : entrée en freinage à 1,25·arret + 40 (arret : distance d'arrêt à
        # 0,85 de la poussée, gravité déduite — la formule même de la phase « chute »
        # du pilote), puis brûlage sans relâche vers l'arrêt AU SOL (rétro surface ;
        # viser le zéro inertiel laissait au contact la vitesse de rotation du corps,
        # 47 m/s sur Terre). Un verdict « optimal » (frein le plus tard possible,
        # profil v² = 2·(a−g)·h) désaccordait verdict et vol : le lander à forte
        # dérive horizontale ne se posait QUE grâce au freinage précoce (tuer la
        # dérive prend du temps) — le frein tardif le faisait s'écraser à 108 m/s de
        # dérive, verdict vrai mais vol faux. Sous voile ouverte et bas, le moteur
        # n'est qu'une aide (comme la phase freinage sous parachute, sous 300 m).
        peut = 0.85 * a_moteur - g > 0.0
        arret = (vrel * vrel - seuil * seuil) \
            / (2.0 * max(0.1, 0.85 * a_moteur - g))
        # l'aide moteur sous voile (moins de 300 m du sol, comme le vrai freinage
        # « parachute ouvert ») ne doit PAS passer par le seuil d'ouverture : une
        # fois la voile ouverte on est sous 250 m/s et la porte vrel > seuil serait
        # toujours fermée — l'aide ne s'allumait jamais (contact à la vitesse
        # terminale de la voile, 14,3 m/s, pour un posé que le flux réussit).
        aide_voile = s_voile > 0.0 and ouv > 0.0 and haut < 300.0
        if a_moteur > 0.0 and dv_moteur > 0.0 and (
                (peut and vrel > seuil and haut < 1.25 * arret + 40.0)
                or aide_voile):
            dv = min(a_moteur * dt, dv_moteur, vrel)  # ni de carburant infini,
            k = dv / vrel                             # ni de frein au-delà de l'arrêt
            dv_moteur -= dv
            vx -= k * vrx
            vy -= k * vry
        x += vx * dt
        y += vy * dt
        # pas large dans le vide, plus fin à l'approche de la planète (le verdict se
        # joue sur la chute près d'elle et la traversée de la couche dense). Sans
        # atmosphère (Lune, Mercure), l'échelle de raffinement est l'atmosphère qui
        # n'existe pas : on prend une fraction du rayon, sinon dt restait à 2 s
        # jusqu'au contact et le freinage final était jugé de travers.
        ref = corps.atm_h if corps.atm_h > 0.0 else max(2000.0, 0.02 * corps.R)
        dt = 2.0 if alt > 200.0 * ref else (0.5 if alt > ref else 0.05)
        if r > 200.0 * corps.R:
            return False                         # reparti dans l'espace : rien à freiner
    return False


def essai_pose(u, v, programme, limite_pas=60 * 1200, depart=None):
    """Joue en OMBRE le reste de la descente : cloner le vaisseau dans un Univers
    bac à sable, y poursuivre le même programme, et renvoyer True si le clone SE POSE
    (sans être détruit ni abandonner, dans le délai). Verdict EXACT : le vol d'essai
    utilise le vrai contrôleur (freinage, largage d'étage, parachute), donc verdict
    et vol ne peuvent plus se contredire — les modèles approchés de simule_rentree
    désaccordaient (étages en série, réservoirs qui se vident : un lander était
    abandonné pour une pose que le vrai vol réussit à 6,1 m/s). Avec `depart`, l'ombre
    part d'une phase donnée (phase None : « desorbite », ou « chute » en entrée
    directe) au lieu de la phase du programme."""
    from .univers import Univers
    from .vaisseau import construire
    from .orbite import Orbite
    essai_u = Univers(bac_a_sable=True)
    essai_u.t = u.t                          # même instant (angle_rotation du corps)
    c = v.corps
    ev = construire(v.nom, [p.m.cle for p in v.pieces], c)
    for piece, modele in zip(ev.pieces, v.pieces):
        piece.carburant = modele.carburant   # même carburant restant
    ev.corps = c
    x, y, vx, vy = u.etat(v)
    ev.x, ev.y, ev.vx, ev.vy = x, y, vx, vy
    ev.angle, ev.omega, ev.gaz = v.angle, v.omega, 0.0
    ev.mode = v.mode
    ev.orbite = Orbite(x, y, vx, vy, c.mu, essai_u.t)
    ev.troncons = []
    ev.cache_etat = (None, None)
    essai_u.vaisseaux.append(ev)
    essai_u.actif = ev
    essai_u._predire(ev)
    prg = Atterrissage()
    for cle in ("phase", "monter", "capture_faite", "etager_dabord", "abandon",
                "voile_a_temps", "air_seul_ok", "brute_voile", "verdict_posable",
                "verdict_moteur"):
        setattr(prg, cle, getattr(programme, cle, None))
    if depart is not None:
        prg.phase = depart
    prg.en_ombre = True
    essai_u.pilote = prg                     # pas lancer_pilote : pas de message public
    for _ in range(limite_pas):
        essai_u.avancer(1.0 / 30.0)
        if ev.detruit:
            return False
        if ev.mode == "pose":
            return True
        if essai_u.pilote is None:
            return False                     # le programme a renoncé : pas une pose
    return False


def rp_cible_desorbite(corps, monter=False):
    """Périapside visé par la désorbitation. En DESCENTE (ou sans air) : 8 % sous la
    surface — l'entrée raide fait tout le travail : l'air dense du bas du ciel tue la
    vitesse horizontale, puis la voile ou le moteur finissent la pose. Viser le rasant
    ne laissait qu'une rentrée quasi horizontale (l'air « papier » ne freine que dans
    les derniers 1 500 m) : arrivée à 1,5 km avec 430 m/s de dérive, voile trop tard,
    posé de travers. En MONTÉE (retour plongeant, périapside déjà sous le rasant) :
    remonter juste au rasant, à 0,3·plafond au-dessus des collines, pour que l'air
    freine en plusieurs passes au lieu de tout casser."""
    if corps.atm_h <= 0.0 or not monter:
        return corps.R - 0.08 * corps.R
    relief = getattr(corps, "relief_max", 0.0)
    return corps.R + max(0.3 * corps.atm_h, relief + 400.0)


def etat_apres_desorbitation(corps, r_orbite, rp=None):
    """État après une désorbitation classique (freinage jusqu'au périapside visé,
    voir rp_cible_desorbite) : le point haut de l'ellipse descendante, à la hauteur
    ACTUELLE du vaisseau. Le verdict intégrera ainsi toute la descente."""
    if rp is None:
        rp = rp_cible_desorbite(corps)
    a = 0.5 * (r_orbite + rp)
    v_apo = sqrt(corps.mu * (2.0 / r_orbite - 1.0 / a))
    return r_orbite, 0.0, 0.0, v_apo


# =============================================================================
# Atterrissage automatique
# =============================================================================
class Atterrissage(Programme):
    """Se poser tout seul : désorbitation si besoin, chute en temps accéléré, freinage au dernier
    moment (réglé en continu pour s'arrêter juste au-dessus du sol), puis descente verticale douce.
    Le SAS RÉTRO (par rapport au sol) se redresse de lui-même quand la vitesse devient faible."""
    nom = "atterrissage"

    def __init__(self):
        self.phase = None
        self.brute_voile = False                 # l'air seul n'amènera pas la voile à 250 m/s
        self.air_seul_ok = False                 # verdict : l'air seul amène la voile à temps
        self.voile_a_temps = False               # la voile s'ouvre à temps au-dessus du relief
        self.abandon = False                     # rentrée condamnée : on remonte et on rend la main
        self.verdict_posable = False             # la rentrée amène la voile à 250 m/s (verdict)
        self.verdict_moteur = False              # idem sans voile : le moteur peut finir la pose
        self.capture_faite = False               # la désorbitation après capture aéro
        self.en_ombre = False                    # vol d'essai (essai_pose) : jamais d'abandon
        self.monter = None                       # sens de la désorbitation (fixé à l'entrée)
        self.etager_dabord = False               # verdict raté, mais la config après étage passe

    def etage_apres_posable(self, v, c, etat_cible, t0):
        """Ce qui restera APRÈS le prochain étage (au-dessus du découpleur du bas)
        peut-il se poser ? (verdict identique à celui de la config courante)."""
        from .vaisseau import Vaisseau, indice_decoupleur_bas
        from .constantes import POSE_V_MAX, POSE_V_MAX_TRAIN
        i = indice_decoupleur_bas(v.pieces)
        if i is None or i <= 0:
            return False
        essai = Vaisseau("essai", v.pieces[:i], c)
        if not essai.moteurs() and not essai.parachutes():
            return False                          # rien d'utilisable au-dessus du découpleur
        v_pose = POSE_V_MAX_TRAIN if essai.a_un_train() else POSE_V_MAX
        ex, ey, evx, evy = etat_cible
        m, cda = essai.masse(), essai.cd_a(-1.0, 0.0)
        if c.atm_h > 0.0 and essai.parachutes():
            s_voile = 700.0 * len(essai.parachutes())
            if simule_rentree(c, ex, ey, evx, evy, m, cda, s_voile=s_voile,
                              contact_max=v_pose, t0=t0):
                return True
            a_essai = poussee_max(essai) / m
            return bool(simule_rentree(c, ex, ey, evx, evy, m, cda,
                                       0.85 * a_essai, 0.9 * essai.delta_v(),
                                       s_voile=s_voile, contact_max=v_pose, t0=t0))
        a_essai = poussee_max(essai) / m if essai.moteurs() else 0.0
        return bool(simule_rentree(c, ex, ey, evx, evy, m, cda,
                                   0.85 * a_essai, 0.9 * essai.delta_v(),
                                   contact_max=v_pose, t0=t0))

    def piloter(self, u, v):
        c = v.corps
        if v.mode == "pose":
            v.gaz = 0.0
            return False
        if self.etager_dabord:               # l'étage du bas ne servait qu'à alourdir
            self.etager_dabord = False
            u.separer_etage()
            return True
        if c.gazeux:                         # géante gazeuse ou étoile : pas de surface
            u.dire(t("Pilote : {corps} n'a pas de surface où se poser", corps=t(c.nom)),
                   (255, 150, 60), 5)
            return False
        # les boosters brûlent à plein gaz dès qu'on met du gaz (impossible de les doser)
        # et leur flamme part en même temps que le parachute : on les largue tout de suite
        from .vaisseau import porteurs_actifs
        if porteurs_actifs(v.pieces):
            u._larguer_boosters(v)
            u.dire(t("Pilote : largage des boosters"), (120, 230, 140), 4)
        v.ref_vitesse, v.sas = "surface", "retro"
        x, y, vx, vy = u.etat(v)
        r = hypot(x, y)
        hauteur = u.altitude(v) - v.geometrie().bas      # du bas du vaisseau jusqu'au terrain
        svx, svy = _vitesse_surface(c, x, y, vx, vy)
        v_vert = (svx * x + svy * y) / r
        vitesse = hypot(svx, svy)
        pesanteur = c.mu / (r * r)
        # avec une atmosphère, le parachute fait le gros du freinage : on le déploie
        # dès que c'est permis, et le moteur garde son carburant pour se poser en douceur
        if (c.atm_h > 0.0 and vitesse <= 250.0 and u.altitude(v) < c.atm_h
                and v.parachutes() and not v.parachute_ouvert()):
            v.gaz = 0.0          # la voile se déploie moteurs coupés : jamais ouvrir
            u.ouvrir_parachute() # le parachute dans la flamme du freinage
            v.sas = "stab"      # la voile redresse le vaisseau (le RÉTRO l'alignait sur
                                # sa dérive — presque horizontale au bigoudi — et on se
                                # posait penché : « posé de travers »)
        f = poussee_max(v)
        if f <= 0.0:
            # plus de poussée : l'étage courant est vide, on essaie de passer au suivant
            # (sauf sous parachute ouvert : séparer casserait la voile)
            if not v.parachute_ouvert():
                v.gaz = 1.0
                # on n'étage que si ce qui reste au-dessus du découpleur garde un moteur :
                # larguer la dernière section (train compris) ne servirait qu'à s'écraser
                from .vaisseau import indice_decoupleur_bas, indice_moteur
                i = indice_decoupleur_bas(v.pieces)
                if i is not None and indice_moteur(v.pieces[:i]) is not None:
                    self.etager_si_vide(u, v)
                f = poussee_max(v)
            if f <= 0.0:
                # aucun moteur utilisable : si un parachute peut encore finir la descente,
                # on continue sans rien dire (le verdict de la phase None jugera la
                # rentrée tout haut dans le ciel — la capsule nue des scénarios Apollo
                # n'a pas de moteur et se pose très bien) ; sinon on s'arrête
                if v.parachute_ouvert() or (c.atm_h > 0.0 and v.parachutes()):
                    v.gaz = 0.0
                    return True
                v.gaz = 0.0
                if not v.moteurs():
                    u.dire(t("Pilote : aucun moteur pour se poser"), (255, 150, 60), 5)
                else:
                    u.dire(t("Pilote : plus de carburant pour se poser"), (255, 150, 60), 5)
                return False
        a_max = f / v.masse()
        g_sol = c.mu / (c.R * c.R)
        if self.phase is None:
            # sans trajectoire prédite, le verdict est impossible : juste après la mise en
            # orbite (coast en physique, gaz coupé), on attend une image — le retour sur
            # rails apportera les tronçons. Sinon on jugeait une orbite quasi circulaire
            # comme une « chute directe » (v.verticale légèrement négative) et on refusait
            # des fusées dont l'étage se pose pourtant très bien.
            if not v.troncons and v.mode == "physique" and u.altitude(v) >= c.atm_h:
                return True
            # le parachute peut-il finir la descente tout seul ? (vitesse d'arrivée au sol
            # sous grande voile, moteur coupé) — sinon il faut un vrai moteur avec de la marge.
            # La limite est celle de la pose : plus généreuse avec un train (14 m/s au lieu
            # de 8) — sinon un retour lunaire avec train, un peu lourd, était refusé à tort.
            from .constantes import POSE_V_MAX, POSE_V_MAX_TRAIN
            v_pose = POSE_V_MAX_TRAIN if v.a_un_train() else POSE_V_MAX
            # et il faut que la rentrée amène SOUS la vitesse d'ouverture de la voile
            # avant le sol (un retour lunaire lourd, moteur trop faible pour freiner,
            # percutait le relief à 450 m/s après avoir accepté de se « poser »)
            tombe = v_vert < 0.0 and hauteur < 0.3 * c.R
            tr = v.troncons[0] if v.troncons else None
            # une trajectoire qui touche est une chute directe ; avec de l'air et un
            # périapside sous le sol, on la corrige plutôt : remonter le périapside au
            # niveau rasant, pour que l'atmosphère freine en plusieurs passes. Sans
            # prédiction (rentrée déjà engagée, mode physique), on se fie au mouvement :
            # v.verticale négative bas dans le ciel = on tombe déjà. (Sur une orbite
            # fermée, v.verticale est négative la moitié du temps : ne JAMAIS s'y fier
            # quand les tronçons existent — on refusait ou on « chutait » sans descendre.)
            plonge = tr is not None and tr.fin in ("impact", "atmo")
            chute_directe = ((plonge and (c.atm_h <= 0.0 or tr.fin == "atmo"))
                             or (tr is None and tombe))
            # état que le verdict doit juger : tel quel si la trajectoire plonge déjà,
            # sinon après la désorbitation à venir (même cible que la désorbitation
            # réelle : raide en descente, rasant si le périapside est sous le rasant)
            if chute_directe:
                ex, ey, evx, evy = x, y, vx, vy
            else:
                rp_vise = rp_cible_desorbite(c, monter=bool(
                    v.orbite is not None and v.orbite.elliptique
                    and v.orbite.rp < rp_cible_desorbite(c, True)))
                ex, ey, evx, evy = etat_apres_desorbitation(c, r, rp_vise)
            if c.atm_h > 0.0 and bool(v.parachutes()):
                cda, masse = v.cd_a(-1.0, 0.0), v.masse()
                s_voile = 700.0 * len(v.parachutes())
                info = {}
                air_seul = simule_rentree(c, ex, ey, evx, evy, masse, cda,
                                          s_voile=s_voile, contact_max=v_pose, t0=u.t,
                                          info=info)
                self.air_seul_ok = bool(air_seul)
                # en chute directe, l'état jugé est l'état RÉEL (déjà engagé) :
                # « la voile ouvre à temps » y est donc fiable dès maintenant (en
                # desorbitation classique, il sera rejugé à la fin de la mise à feu)
                if chute_directe:
                    self.voile_a_temps = bool(air_seul
                                              and info.get("alt_ouv") is not None)
                # la rentrée amène-t-elle à une vraie POSE (voile ouverte à temps et
                # contact doux), avec ou sans l'aide du moteur ? Mémorisé : la
                # transition desorbite→chute s'en servira (l'état réel a pu changer,
                # mais la stratégie, elle, ne change pas).
                self.verdict_posable = bool(air_seul
                                            or simule_rentree(c, ex, ey, evx, evy, masse, cda,
                                                              0.85 * a_max, 0.9 * v.delta_v(),
                                                              s_voile=s_voile,
                                                              contact_max=v_pose, t0=u.t))
                voile_capable = (sqrt(2.0 * masse * g_sol / (c.rho0 * 700.0)) < v_pose
                                 and self.verdict_posable)
            else:
                voile_capable = False
                air_seul = False
                self.verdict_posable = False
                # sans voile possible : « tenir face à la gravité » (0,85*a - g) ne suffit
                # pas — il faut de quoi VRAIMENT s'arrêter avant le sol. Sinon on acceptait
                # des rentrées impossibles (Spoutnik freinait à 645 m/s depuis 13 km :
                # il planait en brûlant tout son carburant, puis tapait le sol à 54 m/s).
                self.verdict_moteur = bool(simule_rentree(
                    c, ex, ey, evx, evy, v.masse(), v.cd_a(-1.0, 0.0),
                    0.85 * a_max, 0.9 * v.delta_v(), contact_max=v_pose, t0=u.t))
            # accepté ? avec une voile : tenir face à la gravité OU verdict de la rentrée ;
            # sans voile : le verdict du moteur seul fait foi — sauf s'il dit non : le
            # verdict imite le contrôleur avec une MASSE FIXE, alors que le vrai vol
            # largue ses étages et brûle à masse décroissante (un moteur-seul était
            # refusé, puis se posait à 6,2 m/s). Dernier mot au vol d'ombre : si le VRAI
            # contrôleur, joué jusqu'au bout depuis ici, se pose, on fonce.
            if not (c.atm_h > 0.0 and bool(v.parachutes())):
                posable = self.verdict_moteur or essai_pose(
                    u, v, self, depart="chute" if chute_directe else "desorbite")
            else:
                posable = voile_capable or 0.85 * a_max - g_sol >= 0.15 * g_sol
            if not posable and self.etage_apres_posable(v, c, (ex, ey, evx, evy), u.t):
                # la config APRÈS étage se pose : décrocher le poids mort du bas — un
                # réservoir plein sous un moteur faible faisait refuser des fusées dont
                # l'étage du haut (voile, train) se pose très bien tout seul.
                self.etager_dabord = True
                posable = True
                u.dire(t("Pilote : séparation de l'étage avant la pose"), (120, 230, 140), 4)
            if (not posable and chute_directe and c.atm_h > 0.0):
                # l'entrée directe est condamnée (orbite rasante déjà dans l'air : le
                # vaisseau arrive trop vite et trop de travers pour que la voile
                # s'ouvre — posé de travers au ras du relief). Une désorbitation raide
                # (périapside à -8 % de R, même cible que la désorbitation classique)
                # tue la dérive horizontale : l'air freine alors comme sur un retour
                # d'orbite basse, que la voile sait poser. On ne refusera que si même
                # cette rentrée raide ne passe pas.
                rp_raid = rp_cible_desorbite(c, monter=bool(
                    v.orbite is not None and v.orbite.elliptique
                    and v.orbite.rp < rp_cible_desorbite(c, True)))
                ex2, ey2, evx2, evy2 = etat_apres_desorbitation(c, r, rp_raid)
                if c.atm_h > 0.0 and bool(v.parachutes()):
                    s_voile = 700.0 * len(v.parachutes())
                    posable = bool(
                        simule_rentree(c, ex2, ey2, evx2, evy2, v.masse(),
                                       v.cd_a(-1.0, 0.0), s_voile=s_voile,
                                       contact_max=v_pose, t0=u.t)
                        or simule_rentree(c, ex2, ey2, evx2, evy2, v.masse(),
                                          v.cd_a(-1.0, 0.0), 0.85 * a_max,
                                          0.9 * v.delta_v(), s_voile=s_voile,
                                          contact_max=v_pose, t0=u.t))
                else:
                    posable = bool(simule_rentree(
                        c, ex2, ey2, evx2, evy2, v.masse(), v.cd_a(-1.0, 0.0),
                        0.85 * a_max, 0.9 * v.delta_v(), contact_max=v_pose, t0=u.t))
                if posable:
                    ex, ey, evx, evy = ex2, ey2, evx2, evy2
                    chute_directe = False          # on passera par « desorbite »
                    u.dire(t("Pilote : freinage pour raidir la rentrée"),
                           (120, 230, 140), 4)
            if not posable:
                u.dire(t("Pilote : moteur trop faible pour se poser ici"), (255, 150, 60), 5)
                return False
            if tr is not None and tr.fin == "sortie":
                # la trajectoire quitte le secteur : pas la peine de freiner, on s'en va
                u.dire(t("Pilote : on quitte {corps}, pas d'atterrissage ici", corps=t(c.nom)),
                       (255, 150, 60), 5)
                return False
            self.phase = "chute" if chute_directe else "desorbite"
            o = v.orbite
            if (self.phase == "desorbite" and c.atm_h <= 0.0 and o is not None
                    and o.elliptique and o.rp < rp_cible_desorbite(c)):
                self.phase = "chute"                     # la trajectoire touche déjà le sol
                chute_directe = True
            # avec de l'air et un périapside sous le niveau rasant (retour lunaire
            # plongeant) : on garde la phase « desorbite », qui remontera le périapside
            # en poussant prograde — foncer dans l'air à ~1 km/s cassait le vaisseau.
            # Le frein miroir ne prend la main que si le moteur NE PEUT PAS finir la
            # pose : sinon le flux normal (voile + freinage final au moteur) suffit et
            # le miroir ne ferait que gaspiller le carburant du freinage final.
            peut_poser = 0.85 * a_max - g_sol >= 0.15 * g_sol
            self.brute_voile = bool(self.phase == "chute" and c.atm_h > 0.0
                                    and v.parachutes() and not air_seul and not peut_poser)

        if self.phase == "desorbite":          # amener le périapside au niveau visé
            o = v.orbite
            # on pousse par rapport à l'ORBITE (vitesse inertielle) : le « rétro
            # surface » dépend de la rotation de la planète, et haut dans le ciel il ne
            # veut plus rien dire — il faisait fuir l'orbite (bug du retour lunaire :
            # tout le carburant partait sans rien freiner). Trop haut : rétrograde pour
            # faire baisser le périapside ; trop bas (retour lunaire plongeant) :
            # prograde pour le remonter au niveau rasant, où l'air freinera en douceur.
            if self.monter is None:                  # le sens se décide à l'entrée : près de
                # l'apoapside, un seul geste de poussée fait sauter le rp de plusieurs
                # centaines de mètres — le recalculer à chaque image faisait basculer
                # monter/descendre sans fin autour de la cible (cycle limite, tout le
                # carburant y passait sans jamais atteindre « atteint »). « Trop bas »
                # se juge sur le rasant (retour plongeant) : on remontera alors au
                # rasant ; sinon on descend raide, sous la surface.
                self.monter = bool(o is not None and o.elliptique
                                   and o.rp < rp_cible_desorbite(c, monter=True))
            monter = self.monter
            if self.abandon:
                # remontée de secours : viser au-dessus de l'air (et du relief), pas le
                # rasant — le but est de rendre un vaisseau en sécurité, pas de re-rentrer
                cible = c.R + c.atm_h + max(2000.0, getattr(c, "relief_max", 0.0))
            else:
                cible = rp_cible_desorbite(c, monter=monter)
            v.sas = "pro" if monter else "retro"
            v.ref_vitesse = "orbite"
            erreur = abs(angle_pi(v.angle - (u.angle_sas(v) or v.angle)))
            v.gaz = 1.0 if erreur < 0.15 else 0.0
            u.accel = 0
            atteint = (o.rp >= cible - 200.0 if monter else o.rp < cible)
            if o is not None and atteint and self.abandon:
                # au-dessus de l'air : le vaisseau est en sécurité, on rend la main
                v.gaz = 0.0
                u.dire(t("Pilote : rentrée annulée, à vous de jouer"),
                       (255, 150, 60), 6)
                return False
            if o is not None and atteint:
                v.gaz, self.phase = 0.0, "chute"
                v.ref_vitesse = "surface"                # la descente, elle, se juge au sol
                v.sas = "retro"                          # la montée laissait « pro » : nez
                # prograde pendant la rentrée, et le freinage poussait vers l'AVANT.
                # comme en phase None : une voile ne sert que s'il y a de l'air (sur un
                # corps sans atmosphère, brûler en rétro orbite au ras du sol est faux).
                # Et le freinage « brute » (moteur miroir du verdict) ne prend la main
                # que si l'AIR SEUL ne peut pas amener à une vraie pose : sinon le flux
                # normal (voile + aide moteur dans l'air) s'en charge — le faire brûler
                # en rétro orbite là-haut retarde l'arrivée sous 250 m/s et la voile
                # s'ouvrait au ras du sol.
                from .constantes import POSE_V_MAX, POSE_V_MAX_TRAIN
                v_pose = POSE_V_MAX_TRAIN if v.a_un_train() else POSE_V_MAX
                args = (c, x, y, vx, vy, v.masse(), v.cd_a(-1.0, 0.0))
                if v.parachutes():
                    # la voile ouvre-t-elle à temps au-dessus du relief ? (contact jugé
                    # sans limite de pose : le moteur finit le dernier mètre en dessous
                    # de 250 m/s — et alt_ouv doit exister : une voile jamais ouverte
                    # n'est pas une voile « à temps »). Jugé ICI, sur l'état réel :
                    # le verdict du départ partait de la désorbitation CALCULÉE, mais le
                    # vrai vol attend son alignement avant la mise à feu — la longitude
                    # de rentrée, donc le relief sous la voile, peut différer.
                    info = {}
                    ouvre = simule_rentree(*args, s_voile=700.0 * len(v.parachutes()),
                                           contact_max=1e9, t0=u.t, info=info)
                    self.voile_a_temps = bool(ouvre and info.get("alt_ouv") is not None)
                air_seul = simule_rentree(*args,
                                          s_voile=700.0 * len(v.parachutes()),
                                          contact_max=v_pose, t0=u.t)
                self.air_seul_ok = bool(air_seul)
                peut_poser = 0.85 * a_max - g_sol >= 0.15 * g_sol
                self.brute_voile = bool(c.atm_h > 0.0 and v.parachutes()
                                        and not air_seul and not peut_poser)
                # rentrée condamnée ? ni la voile (jamais à temps), ni le moteur (verdict
                # complet raté, et pas de plan « brute » ni de freinage d'air au moteur
                # pour l'amener à ouvrir) — foncer serait un crash assuré (trop lourd
                # pour une seule voile, Hercule). On remonte le périapside au-dessus de
                # l'air et on rend la main.
                sans_espoir = c.atm_h > 0.0 and not self.en_ombre \
                    and not self.voile_a_temps \
                    and not air_seul and not self.brute_voile
                if sans_espoir and essai_pose(u, v, self):
                    # vol d'ombre : le VRAI contrôleur, joué jusqu'au bout, se pose —
                    # les verdicts approchés s'étaient trompés, pas le vol : on fonce.
                    sans_espoir = False
                if sans_espoir:
                    self.abandon = True
                    self.monter = True
                    self.phase = "desorbite"
                    v.sas = "pro"
                    v.ref_vitesse = "orbite"
                    u.dire(t("Pilote : pose impossible ici, on remonte"),
                           (255, 150, 60), 6)
                    return True
            return True
        o = v.orbite
        if (c.atm_h > 0.0 and self.phase == "chute" and o is not None and o.elliptique
                and not self.capture_faite
                and o.ra - c.R < 0.25 * c.R and o.rp > c.R - 0.08 * c.R):
            # l'aérofreinage a capté le vaisseau sur une orbite basse : on désorbite
            # maintenant comme depuis une orbite basse classique (périapside à 8 %
            # sous la surface) — la rentrée qui suit est celle d'un retour d'orbite
            # basse, que l'air puis la voile savent faire. Attendre la décroissance
            # orbitale finit au contraire par percuter le relief en vol horizontal.
            # Une seule fois : sinon il repartait en désorbitation pendant la rentrée
            # même (le rp d'un deorbit classique reste au-dessus de R - 8 %) et il
            # brûlait son carburant dans une boucle désorbite/chute.
            self.capture_faite = True
            self.phase = "desorbite"
            self.monter = None                     # re-décider le sens pour cette capture
            v.sas = "retro"
            v.ref_vitesse = "orbite"
            return True
        # distance d'arrêt si l'on freinait maintenant (avec une marge)
        peut_freiner = a_max * 0.85 - pesanteur > 0.0   # le moteur peut-il arrêter la chute ?
        # freinage_utile à 0,85 de la poussée et entrée en freinage à 1,25·arret + 40 :
        # le freinage démarre tôt, et c'est VOLONTIER — tuer la dérive horizontale
        # d'une rentrée prend du temps, il faut s'y prendre en haute altitude (le
        # lander à deux étages se pose grâce à ce départ anticipé ; un déclencheur
        # « optimal » au ras du profil le faisait s'écraser à 108 m/s de dérive).
        # Les vaisseaux que ce freinage long condamne (survol : gravité mange le
        # gain) sont REFUSÉS par le verdict de la rentrée, qui imite cette formule.
        freinage_utile = max(0.1, a_max * 0.85 - pesanteur)
        arret = vitesse * vitesse / (2.0 * freinage_utile)
        if self.phase == "chute":
            v.gaz = 0.0
            if self.brute_voile and vitesse > 250.0:
                # l'air seul n'amènera jamais la voile à sa vitesse d'ouverture : le
                # moteur doit freiner. Mais au bon moment : brûler tôt dans le vide ne
                # sert qu'à ce que la gravité referait — on attend que la distance
                # d'arrêt approche (deux fois par sécurité, la gravité ré-accélère),
                # puis on freine sans relâche jusqu'à l'ouverture de la voile.
                arret_voile = (vitesse * vitesse - 250.0 * 250.0) \
                    / (2.0 * max(1.0, 0.85 * a_max))
                if hauteur - c.atm_h < 2.0 * arret_voile:
                    v.gaz = 1.0
                    # dans le vide, freiner par rapport à l'orbite : le « rétro surface »
                    # (w·r) ne veut plus rien dire là-haut, comme pour la désorbitation
                    v.ref_vitesse = "surface" if hauteur <= c.atm_h else "orbite"
                reste = hauteur / max(1.0, -v_vert)
                u.accel = min(_accel_pour(reste), 3)
                return True
            # avec un parachute à bord : ne rien brûler tant que la vitesse dépasse la
            # limite d'ouverture ET que le verdict (jugé sur l'état réel à la fin de la
            # désorbitation) promet que l'air amène la voile à temps, au-dessus du
            # relief. Les vieilles formules de vitesse terminale se trompaient sur les
            # rentrées rasantes : quasi horizontal, le vaisseau plane à 300 m/s jusqu'au
            # relief et la voile n'ouvre jamais — le verdict, lui, intègre la vraie
            # trajectoire.
            attend_voile = (c.atm_h > 0.0 and v.parachutes() and vitesse > 250.0
                            and self.voile_a_temps)
            if attend_voile:
                # attendre l'air : l'air seul amènera la voile à sa vitesse d'ouverture
                # (vitesse terminale locale ou au sol sous 200-250), on se laisse porter
                reste = hauteur / max(1.0, -v_vert)
                u.accel = min(_accel_pour(reste), 3)
            elif ((v.parachute_ouvert() and hauteur <= 300.0)
                    or (peut_freiner and hauteur <= 1.25 * arret + 40.0)):
                # freinage au moteur — seulement s'il PEUT arrêter la chute : sinon
                # arret est astronomique (freinage_utile clampé à 0,1) et l'on « freinait »
                # dès 8 km d'altitude, tout le carburant y passait sans ralentir, et la
                # voile ne s'ouvrait qu'au ras du sol trop tard (les cas « trop vite pour
                # la voile » avec un moteur faible sont gérés plus bas, dans le else)
                self.phase = "freinage"
                u.accel = 0
            else:
                # moteur trop faible pour arrêter la chute : la voile fera le travail, on
                # fond droit dessus (sinon arret est astronomique et l'on « freinait » en
                # plein ciel : tout le carburant partait sans ralentir, puis on abandonnait)
                reste = hauteur if not peut_freiner else hauteur - 1.25 * arret
                reste = reste / max(1.0, -v_vert)
                u.accel = min(_accel_pour(reste), 3)
                # dans l'air avec une voile à bord mais trop vite pour l'ouvrir (250 m/s) :
                # freiner au moteur, sinon la chute libre arrive trop vite pour être
                # arrêtée — mais seulement si la trajectoire plonge directement : sur une
                # rentrée rasante en plusieurs passes, l'air freine tout seul, brûler à
                # chaque passage gaspillerait le carburant qu'il faut pour la pose
                tr2 = v.troncons[0] if v.troncons else None
                if (c.atm_h > 0.0 and v.parachutes() and vitesse > 250.0
                        and c.densite(u.altitude(v)) > 0.0
                        and tr2 is not None and tr2.fin in ("impact", "atmo")):
                    v.gaz = 1.0
            return True
        u.accel = 0
        if v.parachute_ouvert():
            # sous voile : si l'air seul amène doucement au sol (vitesse d'arrivée sous 6 m/s),
            # on coupe tout — le parachute finit la descente et on garde le carburant.
            # Densité ACTUELLE (conservative) : en descendant, l'air ne peut que se
            # densifier, donc la vitesse d'arrivée réelle ne peut que baisser — et sur
            # un relief, l'air est plus ténu que ne le dit rho0 au niveau de la mer.
            v_arr = sqrt(2.0 * v.masse() * g_sol
                         / (c.densite(u.altitude(v))
                            * (v.cd_a(-1.0, 0.0) + v.surface_parachutes())))
            if c.atm_h > 0.0 and v_arr <= 6.0:
                v.gaz = 0.0
                return True
            if hauteur > 300.0:
                # voile ouverte en haute altitude : c'est elle qui freine, le moteur
                # ne fume pas sous la voile — l'aide ne rallume que sous 300 m
                # (comme la porte d'entrée en freinage « parachute ouvert »)
                v.gaz = 0.0
                return True
        if vitesse <= 6.0:
            v.gaz = 0.0                                  # déjà doux : on économise
            return True
        if hauteur > 12.0 or vitesse > 4.0:              # freinage : s'arrêter juste au-dessus du sol
            # planer tant que la distance d'arrêt est confortable : freiner à demi en plein
            # ciel fait planer le vaisseau des minutes entières et brûle tout le carburant
            # en pertes de gravité. On coupe tout, et le tout-brûler reprendra quand la
            # distance d'arrêt aura rattrapé 50 % de l'altitude restante.
            # (jamais sous voile : là, le moteur sert d'abord à tuer la dérive horizontale)
            if not v.parachute_ouvert() and hauteur > 400.0 and arret < 0.5 * hauteur:
                v.gaz = 0.0
                return True
            besoin = (vitesse * vitesse - 2.25) / (2.0 * max(hauteur - 4.0, 0.5)) + pesanteur
            v.gaz = max(0.0, min(1.0, besoin / a_max))
        else:                                            # derniers mètres : 1,5 m/s, bien droit
            v.gaz = max(0.0, min(1.0, (pesanteur + 2.5 * (-1.5 - v_vert)) / a_max))
        return True


# =============================================================================
# Rendez-vous et amarrage
# =============================================================================
def _accel_pour(reste):
    """Plus forte accélération du temps qui laisse encore ~5 s réelles avant l'échéance."""
    k = 0
    while k + 1 < len(ACCELERATIONS) and ACCELERATIONS[k + 1] <= reste / 5.0:
        k += 1
    return k


def geometrie_amarrage(u, v, cible, ports=None):
    """Position et vitesse du port du vaisseau par rapport au port libre visé de la cible.

    axial : distance devant le port cible, le long de son axe ; lateral : écart sur le côté.
    vise : orientation que doit prendre le vaisseau pour présenter son port face à celui de la cible.
    Un port « ("lat", k) » de la cible est son port latéral : on s'y amarre par le nez.
    """
    pv = [ports[0]] if ports else v.ports_libres()
    pc = [ports[1]] if ports else cible.ports_libres() + [("lat", k) for k in cible.ports_radiaux()]
    if not pv or not pc or not all(p in v.ports_libres() for p in pv) or \
            not all(p in cible.ports_libres() for p in pc if isinstance(p, str)):
        return None
    ea, ec = u.etat(v), u.etat(cible)
    meilleur = None
    for a in pv:
        qx, qy, _, _ = v.point_port(ea, a)
        for b in pc:
            if isinstance(b, tuple):                       # port latéral libre de la cible
                px, py, dx, dy = cible.point_port_radial(ec, b[1])
            else:
                px, py, dx, dy = cible.point_port(ec, b)
            d = hypot(qx - px, qy - py)
            if meilleur is None or d < meilleur[0]:
                meilleur = (d, a, b, qx, qy, px, py, dx, dy)
    d, a, b, qx, qy, px, py, dx, dy = meilleur
    nx, ny = -dy, dx
    rx, ry = qx - px, qy - py
    wx, wy = ea[2] - ec[2], ea[3] - ec[3]
    vise = atan2(-dy, -dx) if a == "haut" else atan2(dy, dx)
    return {"distance": d, "axial": rx * dx + ry * dy, "lateral": rx * nx + ry * ny,
            "w": (wx, wy), "w_axial": wx * dx + wy * dy, "w_lateral": wx * nx + wy * ny,
            "port": (px, py, dx, dy), "normale": (nx, ny), "q": (qx, qy),
            "vise": vise, "erreur": angle_pi(v.angle - vise), "ports": (a, b)}


class Amarrage(Programme):
    """Approche au moteur principal jusqu'à un point d'attente devant le port de la cible,
    puis ligne droite finale au RCS (poussée dosée), de plus en plus doucement."""
    nom = "amarrage"
    ATTENTE = 25.0          # m devant le port de la cible : là où commence la ligne droite finale
    PROCHE = 120.0          # en deçà, on ne manœuvre plus qu'au RCS

    def __init__(self, cible=None):
        self.cible = cible
        self.ports = None
        self.pousse = False

    def _fin(self, u, v, message=None):
        v.gaz = 0.0
        u.commandes.avant = u.commandes.cote = 0
        if message:
            u.dire(message, (255, 150, 60), 5)
        return False

    def piloter(self, u, v):
        if self.cible is None:
            self.cible = u.cible
        c = self.cible
        # amarré ! Soit la cible a rejoint le vaisseau, soit (port latéral) le vaisseau a
        # rejoint la cible : c'est alors elle qui reste et qu'on pilote — il faut s'arrêter,
        # sinon l'aide continue à manœuvrer la station et vide son monergol pour rien.
        if c is None or c.detruit or c not in u.vaisseaux or c is v:
            return self._fin(u, v)
        geo = geometrie_amarrage(u, v, c, self.ports)
        if geo is None:
            return self._fin(u, v, t("Amarrage : il faut un port libre de chaque côté"))
        self.ports = geo["ports"]
        v.sas = "pilote"
        if geo["distance"] > self.PROCHE:
            return self._approche(u, v, geo)
        u.accel = 0
        return self._final(u, v, geo)

    def _approche(self, u, v, geo):
        """Au moteur : viser le point d'attente, à une allure qui diminue en s'approchant."""
        px, py, dx, dy = geo["port"]
        qx, qy = geo["q"]
        tx, ty = px + dx * self.ATTENTE - qx, py + dy * self.ATTENTE - qy
        dist = max(hypot(tx, ty), 1e-6)
        voulue = max(1.0, min(20.0, dist / 50.0))
        wx, wy = geo["w"]
        dvx, dvy = voulue * tx / dist - wx, voulue * ty / dist - wy
        besoin = hypot(dvx, dvy)
        v.rcs = False
        u.commandes.avant = u.commandes.cote = 0
        f = poussee_max(v)
        if f <= 0.0:
            return self._fin(u, v, t("Amarrage : plus de carburant dans l'étage en cours"))
        self.pousse = besoin > (0.3 if self.pousse else 1.5)     # hystérésis : moins d'allers-retours
        if self.pousse:
            cap = atan2(dvy, dvx)
            v.cap_pilote = cap
            v.gaz = max(0.02, min(1.0, besoin / (f / v.masse() * 0.5))) \
                if abs(angle_pi(v.angle - cap)) < 0.08 else 0.0
            u.accel = 0
        else:
            v.gaz = 0.0
            v.cap_pilote = geo["vise"]                           # on se présente déjà dans l'axe
            u.accel = min(_accel_pour(dist / max(1.0, voulue)), 4)
        return True

    def _final(self, u, v, geo):
        """Au RCS : se placer dans l'axe du port, puis avancer jusqu'au contact."""
        v.gaz = 0.0
        v.rcs = True
        v.cap_pilote = geo["vise"]
        axial, lat = geo["axial"], geo["lateral"]
        wa, wl = geo["w_axial"], geo["w_lateral"]
        pret = abs(geo["erreur"]) < 0.05 and abs(lat) < 0.5 and abs(wl) < 0.3
        if pret:                                   # ligne droite finale
            va = -max(0.25, min(1.0, 0.08 * axial))
        else:                                      # rester à distance le temps de s'aligner
            va = max(-1.5, min(1.5, 0.12 * (max(min(axial, self.ATTENTE), 6.0) - axial)))
        vl = max(-1.0, min(1.0, -0.25 * lat))
        aa, al = (va - wa) / 2.0, (vl - wl) / 2.0  # accélérations voulues dans le repère du port
        _, _, dx, dy = geo["port"]
        nx, ny = geo["normale"]
        gx, gy = aa * dx + al * nx, aa * dy + al * ny
        a_rcs = v.poussee_rcs() / v.masse() if v.mono() > 0.0 else 0.0
        if a_rcs <= 0.0:
            return self._fin(u, v, t("Amarrage : plus de monergol pour le RCS"))
        ca, sa = cos(v.angle), sin(v.angle)
        avant = (gx * ca + gy * sa) / a_rcs
        cote = (-gx * sa + gy * ca) / a_rcs * (1.0 if MIROIR_X else -1.0)
        n = hypot(avant, cote)
        if n < 0.05:                               # zone morte : on économise le monergol
            avant = cote = 0.0
        elif n > 1.0:
            avant, cote = avant / n, cote / n
        u.commandes.avant, u.commandes.cote = avant, cote
        return True


def _plus_proche(o1, o2, t0, t1, n=240):
    """Instant et distance de la plus courte approche entre deux orbites du même corps, sur [t0, t1]."""
    def dist(t):
        x1, y1 = o1.position(t)
        x2, y2 = o2.position(t)
        return hypot(x1 - x2, y1 - y2)
    pas = (t1 - t0) / n
    tm = min((t0 + k * pas for k in range(n + 1)), key=dist)
    a, b = max(t0, tm - pas), min(t1, tm + pas)
    for _ in range(30):                            # section dorée autour du meilleur échantillon
        m1, m2 = a + 0.382 * (b - a), a + 0.618 * (b - a)
        if dist(m1) < dist(m2):
            b = m2
        else:
            a = m1
    tm = 0.5 * (a + b)
    return tm, dist(tm)


def planifier_rendez_vous(u, v, cible):
    """Pose un nœud qui amène près de la cible. Renvoie l'instant de la rencontre, ou None.

    Deux familles d'essais : un transfert (altitudes différentes) lancé au bon angle de phase,
    et des orbites de phasage (même altitude) qui ramènent au point de départ en même temps
    que la cible, après 1 à 3 tours. Le meilleur est affiné à la fin.
    """
    c = v.corps
    o = v.troncons[0].orbite if v.troncons else None
    oc = cible.orbite if cible.mode == "rails" else None
    if o is None or oc is None or not o.elliptique or not oc.elliptique or cible.corps is not c:
        u.dire(t("Rendez-vous : il faut être en orbite autour du même corps que la cible"), (255, 150, 60), 5)
        return None
    mu = o.mu
    x, y, vx, vy = o.etat(u.t)
    sens = 1.0 if x * vy - y * vx > 0 else -1.0

    def angle(orb, t):
        px, py = orb.position(t)
        return atan2(py, px)

    def essai(t, dv):
        n = mod_man.Manoeuvre(t, dv)
        r = mod_man.orbite_apres(v, n)
        if r is None or not r[0].elliptique or r[0].rp < c.R + c.atm_h + 500.0:
            return None
        tm, d = _plus_proche(r[0], oc, t, t + 3.3 * r[0].periode, 180)
        return (d + 0.02 * abs(dv), t, dv, tm)          # à distance égale, le moins cher

    depart = u.t + 60.0
    na, nc = TAU / o.periode, TAU / oc.periode
    candidats = []
    r1, r2 = o.a, oc.a
    if abs(r2 - r1) > 0.02 * r1:                          # transfert vers l'altitude de la cible
        duree = pi * sqrt((0.5 * (r1 + r2)) ** 3 / mu)
        phase = angle_pi(sens * (angle(oc, depart) - angle(o, depart)))
        dn = nc - na
        attente = ((pi - nc * duree - phase) / dn) % (TAU / abs(dn))
        dv0 = sqrt(mu * (2.0 / r1 - 2.0 / (r1 + r2))) - sqrt(mu / r1)
        candidats += [(depart + attente + i * o.periode / 60.0, dv0 + j * 2.0)
                      for i in range(-6, 7) for j in range(-4, 5)]
    avance = (sens * (angle(oc, depart) - angle(o, depart))) % TAU    # la cible est devant de tant
    rb = hypot(*o.position(depart))
    vb = hypot(*o.etat(depart)[2:])
    for k in (1, 2, 3):                                   # orbites de phasage
        for m in (k, k + 1):
            periode = (TAU * m - avance) / (nc * k)
            if not 0.7 * o.periode < periode < 1.4 * o.periode:
                continue
            a2 = (mu * (periode / TAU) ** 2) ** (1.0 / 3.0)
            if 2.0 / rb - 1.0 / a2 <= 0.0:
                continue
            dv0 = sqrt(mu * (2.0 / rb - 1.0 / a2)) - vb
            candidats += [(depart + i * 15.0, dv0 + j * 1.0) for i in range(-2, 3) for j in range(-3, 4)]
    notes = [e for e in (essai(t, dv) for t, dv in candidats) if e is not None]
    if not notes:
        u.dire(t("Rendez-vous : aucune trajectoire trouvée"), (255, 150, 60), 5)
        return None
    meilleur = min(notes)
    for pas_t, pas_dv in ((o.periode / 240.0, 0.5), (o.periode / 1200.0, 0.1)):   # affinage
        _, t0, dv0, _ = meilleur
        notes = [e for e in (essai(t0 + i * pas_t, dv0 + j * pas_dv)
                             for i in range(-4, 5) for j in range(-4, 5)) if e is not None]
        meilleur = min(notes + [meilleur])
    note, instant, dv, tm = meilleur
    u.placer_noeud(instant, pro=dv)
    u.dire(t("Rendez-vous planifié : passage à {km:.1f} km de {corps} ({dv:+.0f} m/s)", km=(
        note - 0.02 * abs(dv)) / 1e3, corps=t(cible.nom), dv=dv), (120, 230, 140), 6)
    return tm


class RendezVous(Programme):
    """Tout seul jusqu'au port de la cible : départ, croisière, puis amarrage."""
    nom = "rendez-vous"

    def __init__(self, cible):
        self.cible = cible
        self.etape = "plan"
        self.sous = None
        self.t_rencontre = None

    def piloter(self, u, v):
        c = self.cible
        if c.detruit or c not in u.vaisseaux:
            return False
        if self.etape == "plan":
            self.t_rencontre = planifier_rendez_vous(u, v, c)
            if self.t_rencontre is None:
                return False
            self.etape, self.sous = "depart", ExecuterNoeud()
            return True
        if self.etape == "depart":
            if self.sous.piloter(u, v):
                return True
            self.etape = "croisiere"
            o = v.orbite
            if o is not None and o.elliptique and c.orbite is not None:   # rencontre réelle, après la poussée
                self.t_rencontre = _plus_proche(o, c.orbite, u.t, u.t + 3.3 * o.periode, 240)[0]
        if self.etape == "croisiere":
            v.gaz, v.sas = 0.0, "stab"
            e1, e2 = u.etat(v), u.etat(c)
            d = hypot(e1[0] - e2[0], e1[1] - e2[1])
            if d < 5000.0 or u.t > self.t_rencontre - 20.0:
                if d > 30_000.0:
                    u.dire(t("Rendez-vous manqué ({km:.0f} km) : relance-le pour corriger", km=d / 1e3), (255, 150, 60), 6)
                    return False
                u.accel = 0
                u.cible = c
                self.etape, self.sous = "amarrage", Amarrage(c)
                return True
            u.accel = _accel_pour(self.t_rencontre - 20.0 - u.t)
            return True
        return self.sous.piloter(u, v)


# =============================================================================
# Ce que propose le bouton PILOTE, et les informations d'atterrissage
# =============================================================================
def actions(u, v):
    """[(libellé, fonction)] des aides utilisables maintenant."""
    from .corps import Corps
    out = []
    if u.pilote is not None:
        out.append((t("Arrêter le pilote ({nom})", nom=t(u.pilote.nom)), u.arreter_pilote))
    if v is None:
        return out
    c = v.corps
    o = v.orbite if v.mode != "pose" else None
    bas = v.mode == "pose" or (o is not None and o.rp < c.R + c.atm_h + 500.0)
    if bas and poussee_max(v) + sum(n * m.m.poussee for m, r, n in v.moteurs()) > 0:
        out.append((t("Mise en orbite"), lambda: u.lancer_pilote(MiseEnOrbite())))
    if v.noeud is not None:
        out.append((t("Exécuter la manœuvre"), lambda: u.lancer_pilote(ExecuterNoeud())))
    if v.mode != "pose" and not getattr(c, "gazeux", False) and \
            sum(n * m.m.poussee for m, r, n in v.moteurs()) > 0:
        out.append((t("Atterrissage automatique"), lambda: u.lancer_pilote(Atterrissage())))
    if o is not None and not o.degeneree and v.noeud is None:
        out.append((t("Circulariser"), lambda: planifier_circularisation(u, v)))
    if o is not None and o.elliptique and v.noeud is None and c.parent is not None \
            and c.parent.parent is not None:                  # autour d'une lune : rentrer à la maison
        corps_retour = "la Terre" if c.parent.nom == "Terre" else c.parent.nom
        out.append((t("Retour vers {corps}", corps=t(corps_retour)),
                    lambda: planifier_retour(u, v)))
    cible = u.cible
    if cible is not None and not isinstance(cible, Corps) and cible.corps is c and v.mode != "pose" \
            and cible.mode != "pose" and v.ports_libres() and cible.ports_libres():
        e1, e2 = u.etat(v), u.etat(cible)
        if hypot(e1[0] - e2[0], e1[1] - e2[1]) < 5000.0:
            out.append((t("Amarrage automatique"), lambda: u.lancer_pilote(Amarrage(cible))))
        elif o is not None and o.elliptique and v.noeud is None and cible.mode == "rails":
            out.append((t("Rendez-vous et amarrage"), lambda: u.lancer_pilote(RendezVous(cible))))
    if isinstance(cible, Corps) and o is not None and o.elliptique and v.noeud is None and \
            (cible.parent is c or (c.parent is not None and cible.parent is c.parent and cible is not c)):
        out.append((t("Transfert vers {corps}", corps=t(cible.nom)),
                    lambda: planifier_transfert(u, v, cible)))
    return out


def infos_atterrissage(u, v):
    """Lignes (nom, valeur, alerte) pendant une descente vers le sol, ou None."""
    if v is None or v.mode == "pose" or not v.troncons:
        return None
    c = v.corps
    x, y, vx, vy = u.etat(v)
    r = hypot(x, y)
    bas = v.geometrie().bas
    alt = u.altitude(v) - bas                        # hauteur du bas au-dessus du terrain
    svx, svy = _vitesse_surface(c, x, y, vx, vy)
    v_vert = (svx * x + svy * y) / r
    if v_vert >= 0.0:                            # on monte (décollage, avant l'apoapside) : rien à dire
        return None
    tr = v.troncons[0]
    impact = tr.t1 - u.t if tr.fin == "impact" else None
    entree = tr.t1 - u.t if tr.fin == "atmo" and tr.t1 - u.t < 3600.0 else None   # retour dans l'air
    if impact is None and entree is None and not (v.mode == "physique" and alt < 15_000 and v_vert < -1.0):
        return None
    if impact is not None and impact > 3600.0:
        return None
    from .constantes import (POSE_V_MAX, POSE_V_MAX_TRAIN, POSE_H_MAX, POSE_H_MAX_TRAIN,
                             POSE_INCLINAISON, POSE_INCLINAISON_TRAIN)
    train = v.a_un_train()
    v_max, h_max = (POSE_V_MAX_TRAIN, POSE_H_MAX_TRAIN) if train else (POSE_V_MAX, POSE_H_MAX)
    v_horiz = abs(-svx * y + svy * x) / r
    proche = alt < 300.0                         # près du sol : les limites pour se poser comptent
    lignes = [("Altitude", alt, False),
              ("Vit. verticale", v_vert, proche and -v_vert > v_max),
              ("Vit. horizontale", v_horiz, proche and v_horiz > h_max)]
    if proche:
        incl = abs(angle_pi(v.angle - atan2(y, x)))
        lignes.append(("Inclinaison", incl * 180.0 / pi,
                       incl > (POSE_INCLINAISON_TRAIN if train else POSE_INCLINAISON)))
    if entree is not None:                       # atmosphère : la traînée décidera de la suite
        lignes.append(("Entrée atmo. dans", entree, False))
        return lignes
    if impact is not None:
        lignes.append(("Impact dans", impact, impact < 20.0))
    a = poussee_max(v) / v.masse() - c.g               # décélération possible, pesanteur déduite
    if a <= 0.0:
        lignes.append(("Freinage", "poussée trop faible", True))
        return lignes
    freinage = None
    if impact is not None:                               # on suit la trajectoire jusqu'au sol
        for k in range(61):
            t = u.t + impact * k / 60.0
            px, py, pvx, pvy = tr.orbite.etat(t)
            sx, sy = _vitesse_surface(c, px, py, pvx, pvy)
            if hypot(px, py) - c.R - bas <= 1.15 * (sx * sx + sy * sy) / (2.0 * a):
                freinage = t - u.t
                break
    else:
        vitesse = hypot(svx, svy)
        freinage = (alt - 1.15 * vitesse * vitesse / (2.0 * a)) / max(1.0, -v_vert)
    if freinage is not None:
        lignes.append(("Freinage dans", max(0.0, freinage), freinage <= 1.0))
    return lignes


def infos_amarrage(u, v):
    """Aide au docking : [(nom, valeur, alerte)] quand la cible est un vaisseau à moins de 5 km."""
    from .corps import Corps
    c = u.cible
    if v is None or c is None or isinstance(c, Corps) or c.corps is not v.corps or v.mode == "pose":
        return None
    geo = geometrie_amarrage(u, v, c)
    if geo is None or geo["distance"] > 5000.0:
        return None
    d = geo["distance"]
    rapprochement = -geo["w_axial"]
    return [("Distance au port", d, False),
            ("Vit. relative", hypot(*geo["w"]), False),
            ("Rapprochement", rapprochement, d < 30.0 and rapprochement > 2.0),
            ("Écart latéral", geo["lateral"], d < 20.0 and abs(geo["lateral"]) > 1.0),
            ("Alignement", abs(geo["erreur"]) * 180.0 / pi, d < 20.0 and abs(geo["erreur"]) > 0.35),
            ("Ports (nous → cible)", "%s → %s" % geo["ports"], False)]
