"""Pixel Artist : redessine un personnage en pixel art propre et le découpe en pièces articulées.

Une recette (pixel_artist/<nom>.json) décrit les poses de base et leurs pièces. Le pipeline :
  1. prend chaque pose dans la planche nettoyée (outils/extraire_sprites.py) ;
  2. calcule une palette commune à toutes les poses (mêmes teintes partout) ;
  3. redessine en pixel art : réduction, lissage sélectif (les détails contrastés
     comme l'œil ou le visage sont protégés), quantification, nettoyage, contour ;
  4. découpe chaque pose en calques (une pièce = un polygone + un pivot ; le corps
     garde l'articulation pour qu'aucun trou n'apparaisse quand la pièce bouge) ;
  5. écrit l'atlas des pièces + sa description, une planche propre de toutes les
     images du modèle, et un aperçu où chaque pièce est mise en mouvement.

Usage : python3 pixel_artist/pixel_artist.py [pixel_artist/dragon.json]
Dépendances : Pillow, numpy, scipy.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi

ICI = Path(__file__).resolve().parent
SORTIE = ICI.parent / 'assets' / 'pixel-artist'
CROIX = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], bool)


def hex_rgb(h):
    return [int(h[i:i + 2], 16) for i in (1, 3, 5)]


# ---------------------------------------------------------------- 1. poses
class Planche:
    def __init__(self, recette):
        self.img = Image.open(ICI / recette['planche']).convert('RGBA')
        self.desc = json.loads((ICI / recette['description']).read_text())
        self.cw, self.ch = self.desc['frameWidth'], self.desc['frameHeight']
        self.ax, self.ay = self.desc['anchor']['x'], self.desc['anchor']['y']

    def cellule(self, anim, i):
        r = self.desc['animations'][anim]['row']
        return self.img.crop((i * self.cw, r * self.ch, (i + 1) * self.cw, (r + 1) * self.ch))

    def toutes(self):
        for nom, a in self.desc['animations'].items():
            if nom == 'flap':            # animation calculée, pas une image du modèle
                continue
            for i in range(a['frames']):
                yield nom, i, self.cellule(nom, i)


# ---------------------------------------------------------------- 2-3. pixel art
def reduire(cellule, f):
    """Luminance moyenne par surface (pondérée par la présence) et masque du sujet."""
    a = np.array(cellule).astype(float)
    presence = a[..., 3] / 255
    lum = a[..., :3].mean(2)
    h, w = presence.shape
    W, H = round(w * f), round(h * f)
    pile = np.dstack([lum * presence, presence * 255]).clip(0, 255).astype(np.uint8)
    petit = np.array(Image.fromarray(pile[..., [0, 0, 0, 1]]).resize((W, H), Image.BOX)).astype(float)
    couverture = petit[..., 3] / 255
    L = np.where(couverture > 0, petit[..., 0] / np.maximum(couverture, 1e-6), 0)
    return L, couverture >= 0.5


def lisser(L, m, seuil):
    """Médiane 3×3 limitée au sujet ; un pixel très différent de ses voisins (détail) est gardé tel quel."""
    h, w = L.shape
    pad = np.pad(np.where(m, L, -1), 1, constant_values=-1)
    fen = np.stack([pad[dy:dy + h, dx:dx + w] for dy in range(3) for dx in range(3)], -1)
    fen = np.where(fen < 0, L[..., None], fen)
    med = np.median(fen, -1)
    return np.where(np.abs(L - med) > seuil, L, med)


def centres_communs(valeurs, k):
    """k-moyennes 1D sur la luminance : k teintes communes à toutes les poses."""
    v = np.concatenate(valeurs)
    c = np.quantile(v, np.linspace(0.03, 0.97, k))
    for _ in range(50):
        lab = np.argmin(np.abs(v[:, None] - c[None, :]), 1)
        c = np.array([v[lab == j].mean() if (lab == j).any() else c[j] for j in range(k)])
    return np.sort(c)


def nettoyer(idx, passes):
    """Un pixel sans voisin de sa couleur, à faible contraste avec la majorité autour, rejoint la majorité."""
    h, w = idx.shape
    k = idx.max() + 1
    for _ in range(passes):
        pad = np.pad(idx, 1, constant_values=-1)
        v8 = np.stack([pad[1 + dy:1 + dy + h, 1 + dx:1 + dx + w] for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx], -1)
        v4 = np.stack([pad[1 + dy:1 + dy + h, 1 + dx:1 + dx + w] for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1))], -1)
        memes = (v4 == idx[..., None]).sum(-1)
        comptes = np.stack([(v8 == c).sum(-1) for c in range(k)], -1)
        maj, opaques = comptes.argmax(-1), (v8 >= 0).sum(-1)
        idx = np.where((idx >= 0) & (memes == 0) & (opaques >= 5) & (np.abs(maj - idx) <= 1), maj, idx)
    return idx


def eclats(idx, protege, n):
    """Pixel clair isolé (griffe, poussière, reflet parasite) : il rejoint ses voisins, sauf en zone protégée
    (yeux, dents, visage du cavalier, étincelles du souffle)."""
    h, w = idx.shape
    pad = np.pad(idx, 1, constant_values=-1)
    v8 = np.stack([pad[1 + dy:1 + dy + h, 1 + dx:1 + dx + w] for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx], -1)
    voisins_clairs = ((v8 >= idx[..., None] - 2) & (v8 >= 0)).sum(-1)
    isole = (idx >= round(n * 0.6)) & (voisins_clairs == 0) & ~protege
    opaques = (v8 >= 0).sum(-1)
    med = np.sort(np.where(v8 >= 0, v8, 99), -1)
    mediane = np.take_along_axis(med, np.maximum(opaques // 2, 0)[..., None], -1)[..., 0]
    out = np.where(isole, np.where(opaques >= 3, mediane, -1), idx)
    # petits groupes clairs (1 ou 2 pixels) hors zone protégée : même traitement
    clair = (out >= round(n * 0.6)) & ~protege
    lab, nb = ndi.label(clair, np.ones((3, 3), bool))
    if nb:
        tailles = ndi.sum(np.ones_like(lab), lab, range(1, nb + 1))
        petits = np.isin(lab, [k + 1 for k in range(nb) if tailles[k] <= 2])
        pad = np.pad(np.where(clair, -1, out), 1, constant_values=-1)
        v8 = np.stack([pad[1 + dy:1 + dy + h, 1 + dx:1 + dx + w] for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx], -1)
        sombres = (v8 >= 0).sum(-1)
        tri = np.sort(np.where(v8 >= 0, v8, 99), -1)
        med2 = np.take_along_axis(tri, np.maximum(sombres // 2, 0)[..., None], -1)[..., 0]
        out = np.where(petits, np.where(sombres >= 2, med2, -1), out)
    return out


def pixeliser(cellule, rec, centres, protege=None):
    """→ tableau d'indices de palette (−1 : transparent), avec un pixel de marge (et le contour si demandé)."""
    L, m = reduire(cellule, rec['echelle'])
    n = len(rec['palette'])
    if rec.get('mode') == 'rampe':               # luminance → teinte d'une palette ordonnée du sombre au clair
        idx = np.full(L.shape, -1)
        idx[m] = np.minimum(n - 1, np.round(np.power(np.clip(L[m] / 255, 0, 1), rec.get('gamma', 1)) * (n - 1))).astype(int)
    else:                                        # k-moyennes sur la luminance lissée, puis rangs de palette
        Ls = lisser(L, m, rec['detail'])
        idx = np.full(L.shape, -1)
        idx[m] = np.argmin(np.abs(Ls[m][:, None] - centres[None, :]), 1)
        idx = nettoyer(idx, rec['passes'])
        rangs = np.array(rec['rangs'])
        idx = np.where(idx >= 0, rangs[np.maximum(idx, 0)], -1)
    out = np.full((L.shape[0] + 2, L.shape[1] + 2), -1)
    out[1:-1, 1:-1] = idx
    if rec.get('eclats'):
        out = eclats(out, protege if protege is not None else np.zeros(out.shape, bool), n)
    if rec.get('contour', True):
        plein = out >= 0
        out[ndi.binary_dilation(plein, CROIX) & ~plein] = 0
    return out


def retracer_contour(idx):
    """Refait le contour après un effacement : pas de contour orphelin, pas de bord ouvert."""
    plein = idx > 0                                  # l'indice 0 est réservé au contour
    out = np.where(plein, idx, -1)
    out[ndi.binary_dilation(plein, CROIX) & ~plein] = 0
    return out


def en_image(idx, palette, teinte=None, force=0.0):
    img = np.zeros(idx.shape + (4,), np.uint8)
    for j, c in enumerate(palette):
        couleur = np.array(c, float)
        if teinte is not None:
            couleur = couleur * (1 - force) + np.array(teinte, float) * force
        img[idx == j, :3] = couleur.round().astype(np.uint8)
        img[idx == j, 3] = 255
    return Image.fromarray(img)


# ---------------------------------------------------------------- 4. découpe
def dans_polygone(xs, ys, poly):
    dedans = np.zeros(xs.shape, bool)
    n = len(poly)
    for i in range(n):
        (x1, y1), (x2, y2) = poly[i], poly[(i - 1) % n]
        croise = (y1 > ys) != (y2 > ys)
        with np.errstate(divide='ignore', invalid='ignore'):
            xint = (x2 - x1) * (ys - y1) / (y2 - y1) + x1
        dedans ^= croise & (xs < xint)
    return dedans


def dist_segment(xs, ys, a, b):
    (ax, ay), (bx, by) = a, b
    dx, dy = bx - ax, by - ay
    t = np.clip(((xs - ax) * dx + (ys - ay) * dy) / (dx * dx + dy * dy or 1), 0, 1)
    return np.hypot(xs - ax - t * dx, ys - ay - t * dy)


def decouper(idx, pose, rec, planche):
    f = rec['echelle']
    vers = lambda p: ((planche.ax + p[0]) * f + 1, (planche.ay + p[1]) * f + 1)
    H, W = idx.shape
    ys, xs = np.mgrid[0:H, 0:W] + 0.5
    for zone in pose.get('effacer', []):               # poussière, ombre dessinée… : hors du personnage
        idx = np.where(dans_polygone(xs, ys, [vers(p) for p in zone]), -1, idx)
    if pose.get('effacer') and rec.get('contour', True):
        idx = retracer_contour(idx)
    appart = np.full(idx.shape, -1)
    for k, piece in enumerate(pose['pieces']):
        appart[dans_polygone(xs, ys, [vers(p) for p in piece['poly']]) & (idx >= 0) & (appart < 0)] = k
    corps = np.where(appart < 0, idx, -1)
    calques = []
    for k, piece in enumerate(pose['pieces']):
        pivot = vers(piece['pivot'])
        axe = vers(piece['axe']) if 'axe' in piece else None
        dist = dist_segment(xs, ys, axe, pivot) if axe else np.hypot(xs - pivot[0], ys - pivot[1])
        garde = (appart == k) & (dist <= rec['jointure'])
        corps[garde] = idx[garde]                     # le corps garde l'articulation
        c = dict(nom=piece['nom'], role=piece['role'], z=piece['z'], parent=piece.get('parent'),
                 double=piece.get('double', False), phase=piece.get('phase'), pivot=pivot, axe=axe,
                 pixels=np.where(appart == k, idx, -1))
        calques.append(c)
        if piece['role'] == 'machoire':               # l'intérieur de la gueule, visible quand elle s'ouvre
            calques.append(dict(nom='gueule', role='gueule', z=piece['z'] - 0.5, parent=piece.get('parent'),
                                double=False, phase=None, pivot=pivot, axe=None,
                                pixels=np.where(appart == k, 1, -1)))
    calques.insert(0, dict(nom='corps', role='corps', z=0, parent=None, double=False, phase=None,
                           pivot=None, axe=None, pixels=corps))
    return calques, appart, idx


def recaler(ref, img):
    """Décalage entier (dy, dx) qui superpose au mieux la silhouette sombre de img sur ref."""
    h, w = ref.shape[0] * 2, ref.shape[1] * 2
    cc = np.fft.irfft2(np.fft.rfft2(ref, (h, w)) * np.conj(np.fft.rfft2(img, (h, w))), (h, w))
    dy, dx = np.unravel_index(np.argmax(cc), cc.shape)
    return (dy - h if dy > h // 2 else dy), (dx - w if dx > w // 2 else dx)


def variantes(piece, calque, pose, rec, planche, centres, protege):
    """Même pièce prise dans d'autres images du modèle (ex. têtes d'attaque gueule ouverte)."""
    v = piece['variantes']
    f = rec['echelle']
    vers = lambda p: ((planche.ax + p[0]) * f + 1, (planche.ay + p[1]) * f + 1)
    sombre = lambda px: ((px >= 0) & (px <= len(rec['palette']) * 0.4)).astype(float)
    base = sombre(calque['pixels'])
    sortie = []
    for i in range(planche.desc['animations'][v['anim']]['frames']):
        idx = pixeliser(planche.cellule(v['anim'], i), rec, centres, protege)
        H, W = idx.shape
        ys, xs = np.mgrid[0:H, 0:W] + 0.5
        pix = np.where(dans_polygone(xs, ys, [vers(p) for p in v['poly']]), idx, -1)
        dy, dx = recaler(base, sombre(np.where(dans_polygone(xs, ys, [vers(p) for p in piece['poly']]), pix, -1)))
        sortie.append({'pixels': pix, 'decalage': (int(dx), int(dy))})
    return sortie


# ---------------------------------------------------------------- 5. atlas
def boite(pixels):
    ys, xs = np.nonzero(pixels >= 0)
    if not len(xs):
        return None
    return xs.min(), ys.min(), xs.max() + 1, ys.max() + 1


def emballer(morceaux, largeur=512):
    """Rangement en étagères : du plus haut au plus bas, de gauche à droite."""
    ordre = sorted(range(len(morceaux)), key=lambda i: -morceaux[i].shape[0])
    places, x, y, haut = [None] * len(morceaux), 0, 0, 0
    for i in ordre:
        h, w = morceaux[i].shape
        if x + w > largeur:
            x, y, haut = 0, y + haut + 1, 0
        places[i] = (x, y)
        x, haut = x + w + 1, max(haut, h)
    return places, (largeur, y + haut)


# ---------------------------------------------------------------- aperçu : mettre les pièces en mouvement
def matrice_locale(c, params, u):
    """Même convention que le jeu : transformation d'une pièce autour de son pivot."""
    def T(x, y): return np.array([[1, 0, x], [0, 1, y], [0, 0, 1]], float)
    def R(a): return np.array([[math.cos(a), -math.sin(a), 0], [math.sin(a), math.cos(a), 0], [0, 0, 1]])
    def E(a, b): return np.array([[a, 0, 0], [0, b, 0], [0, 0, 1]], float)
    if c['pivot'] is None:
        return np.eye(3)
    px, py = c['pivot']
    role = c['role']
    if role == 'aile':
        a = params.get('aile', {})
        qx, qy = c['axe'] or (px - 10, py)
        b = math.atan2(py - qy, px - qx)
        return T(px, py) @ R(b + a.get('rot', 0)) @ E(a.get('sx', 1), a.get('s', 1)) @ R(-b) @ T(-px, -py)
    if role == 'tete':
        t = params.get('tete', {})
        return T(px + t.get('dx', 0) * u, py + t.get('dy', 0) * u) @ R(t.get('rot', 0)) @ T(-px, -py)
    rot = {'machoire': params.get('machoire', 0), 'queue': params.get('queue', 0), 'cavalier': params.get('cavalier', 0),
           'jambe': params.get('jambes', {}).get(c['nom'], 0)}.get(role, 0)
    return T(px, py) @ R(rot) @ T(-px, -py)


def composer(calques, taille, palette, params, marge=20):
    W, H = taille[0] + 2 * marge, taille[1] + 2 * marge
    toile = Image.new('RGBA', (W, H))
    parents = {c['nom']: c for c in calques}
    u = taille[1] / 40
    decal = np.array([[1, 0, marge], [0, 1, marge], [0, 0, 1]], float)
    for c in sorted(calques, key=lambda c: c['z']):
        m = matrice_locale(c, params, u)
        p = parents.get(c['parent']) if c['parent'] else None
        if p is not None:
            m = matrice_locale(p, params, u) @ m
        inv = np.linalg.inv(decal @ m)
        img = en_image(c['pixels'], palette)
        img = img.transform((W, H), Image.AFFINE, data=tuple(inv[:2].ravel()), resample=Image.NEAREST)
        toile.alpha_composite(img)
    return toile


# ---------------------------------------------------------------- principal
def masque_protege(rec, planche, forme):
    f = rec['echelle']
    H, W = forme
    ys, xs = np.mgrid[0:H, 0:W] + 0.5
    m = np.zeros(forme, bool)
    for zone in rec.get('proteger', []):
        m |= dans_polygone(xs, ys, [((planche.ax + p[0]) * f + 1, (planche.ay + p[1]) * f + 1) for p in zone])
    return m


def main():
    chemin = Path(sys.argv[1]) if len(sys.argv) > 1 else ICI / 'dragon.json'
    rec = json.loads(chemin.read_text())
    planche = Planche(rec)
    palette = [hex_rgb(h) for h in rec['palette']]
    f = rec['echelle']

    sources = {nom: planche.cellule(*pose['source']) for nom, pose in rec['poses'].items()}
    centres = None
    if rec.get('mode') != 'rampe':               # palette commune : teintes calculées sur toutes les poses
        valeurs = []
        for cell in sources.values():
            L, m = reduire(cell, f)
            valeurs.append(lisser(L, m, rec['detail'])[m])
        centres = centres_communs(valeurs, rec['teintes'])
    forme = (round(planche.ch * f) + 2, round(planche.cw * f) + 2)
    protege = masque_protege(rec, planche, forme)

    SORTIE.mkdir(parents=True, exist_ok=True)
    description = {'nom': rec['nom'], 'echelle': f, 'palette': rec['palette'], 'poses': {}}
    morceaux, refs, apercus = [], [], []

    def ranger(pixels, entree, decalage=(0, 0)):
        b = boite(pixels)
        if b is None:
            return False
        x0, y0, x1, y1 = b
        morceaux.append(pixels[y0:y1, x0:x1])
        entree['origine'] = [int(x0 + decalage[0]), int(y0 + decalage[1])]
        refs.append(entree)
        return True

    for nom, pose in rec['poses'].items():
        idx = pixeliser(sources[nom], rec, centres, protege)
        calques, appart, idx = decouper(idx, pose, rec, planche)
        anim = planche.desc['animations'][pose['source'][0]]
        ancre = [planche.ax * f + 1, planche.ay * f + 1]
        info = {'taille': [idx.shape[1], idx.shape[0]], 'ancre': ancre,
                'sol': ancre[1] + planche.desc['groundOffset'] * f if anim.get('grounded') else None, 'calques': []}
        pieces = {p['nom']: p for p in pose['pieces']}
        vars_apercu = []
        for c in calques:
            entree = {k: c[k] for k in ('nom', 'role', 'z', 'parent', 'double', 'phase') if c[k] not in (None, False)}
            if c['pivot'] is not None:
                entree['pivot'] = [round(c['pivot'][0], 2), round(c['pivot'][1], 2)]
            if c['axe'] is not None:
                entree['axe'] = [round(c['axe'][0], 2), round(c['axe'][1], 2)]
            if not ranger(c['pixels'], entree):
                continue
            piece = pieces.get(c['nom'])
            if piece and 'variantes' in piece:
                entree['variantes'] = []
                for v in variantes(piece, c, pose, rec, planche, centres, protege):
                    ev = {}
                    if ranger(v['pixels'], ev, v['decalage']):
                        entree['variantes'].append(ev)
                        vars_apercu.append((c, v))
            info['calques'].append(entree)
        description['poses'][nom] = info
        apercus.append((nom, idx, calques, appart, info, vars_apercu))

    places, (aw, ah) = emballer(morceaux)
    atlas = Image.new('RGBA', (aw, ah))
    for m, (x, y), entree in zip(morceaux, places, refs):
        atlas.paste(en_image(m, palette), (x, y))
        entree['atlas'] = [x, y, m.shape[1], m.shape[0]]
    atlas.save(SORTIE / f"{rec['nom']}.png", optimize=True)
    (SORTIE / f"{rec['nom']}.json").write_text(json.dumps(description, indent=1, ensure_ascii=False))

    # planche propre : toutes les images du modèle, redessinées avec la même palette et les mêmes réglages
    cw, ch = forme[1], forme[0]
    anims = {k: v for k, v in planche.desc['animations'].items() if k != 'flap'}
    colonnes = max(a['frames'] for a in anims.values())
    propre = Image.new('RGBA', (colonnes * cw, len(anims) * ch))
    for r, (nom, a) in enumerate(anims.items()):
        for i in range(a['frames']):
            propre.paste(en_image(pixeliser(planche.cellule(nom, i), rec, centres, protege), palette), (i * cw, r * ch))
    propre.save(SORTIE / f"{rec['nom']}_propre.png", optimize=True)
    bouche = planche.desc.get('mouth')
    (SORTIE / f"{rec['nom']}_propre.json").write_text(json.dumps({
        'image': f"{rec['nom']}_propre.png", 'frameWidth': cw, 'frameHeight': ch,
        'anchor': {'x': planche.ax * f + 1, 'y': planche.ay * f + 1},
        'groundOffset': planche.desc['groundOffset'] * f, 'palette': rec['palette'],
        'mouth': {'x': bouche['x'] * f, 'y': bouche['y'] * f} if bouche else None,
        'animations': {k: {'row': r, 'frames': a['frames'], 'grounded': a.get('grounded', False),
                           'bodyY': [round(b * f, 2) for b in a.get('bodyY', [0] * a['frames'])],
                           **({'fireFrame': a['fireFrame']} if 'fireFrame' in a else {})}
                       for r, (k, a) in enumerate(anims.items())},
    }, indent=1, ensure_ascii=False))

    # aperçu : pièces colorées, pièces en mouvement, têtes d'attaque greffées, puis la course
    TEINTES = [(224, 112, 46), (111, 179, 210), (181, 138, 214), (127, 181, 138), (214, 193, 90), (214, 115, 138)]
    lignes = []
    for nom, idx, calques, appart, info, vars_apercu in apercus:
        arr = np.array(en_image(idx, palette)).astype(float)
        for k in range(appart.max() + 1):
            sel = appart == k
            arr[sel, :3] = arr[sel, :3] * 0.5 + np.array(TEINTES[k % len(TEINTES)]) * 0.5
        vues = [Image.fromarray(arr.astype(np.uint8)),
                composer(calques, info['taille'], palette, {'aile': {'s': -0.8}, 'queue': 0.3, 'cavalier': -0.15})]
        for c, v in vars_apercu[2:5]:           # la tête d'attaque remplace la tête au repos
            greffe = [x for x in calques if x is not c] + [dict(c, pixels=np.roll(np.roll(v['pixels'], v['decalage'][1], 0), v['decalage'][0], 1))]
            vues.append(composer(greffe, info['taille'], palette, {}))
        lignes.append((nom, vues))
    course = []
    r = list(anims).index('walk')
    for i in range(anims['walk']['frames']):
        course.append(propre.crop((i * cw, r * ch, (i + 1) * cw, (r + 1) * ch)))
    lignes.append(('course (planche propre)', course))
    z = 3
    largeur = max(sum(v.width * z + 12 for v in vues) for _, vues in lignes)
    hauteur = sum(max(v.height for v in vues) * z + 22 for _, vues in lignes)
    apercu = Image.new('RGB', (largeur, hauteur), (27, 24, 33))
    d = ImageDraw.Draw(apercu)
    y = 0
    for nom, vues in lignes:
        d.text((6, y + 4), nom, fill=(230, 224, 220))
        x = 0
        for v in vues:
            fond = Image.new('RGBA', v.size, (70, 44, 64, 255))
            fond.alpha_composite(v)
            apercu.paste(fond.convert('RGB').resize((v.width * z, v.height * z), Image.NEAREST), (x, y + 18))
            x += v.width * z + 12
        y += max(v.height for v in vues) * z + 22
    apercu.save(SORTIE / 'apercu.png')

    nb = sum(len(p['calques']) for p in description['poses'].values())
    print(f"{rec['nom']} : {len(description['poses'])} pose(s), {nb} calques -> {SORTIE.name}/{rec['nom']}.png ({aw}x{ah}), "
          f"planche propre {propre.width}x{propre.height}, aperçu")


if __name__ == '__main__':
    main()
