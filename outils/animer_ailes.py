"""Battement d'ailes par découpe (animation « cutout »).

La planche IA dessine l'aile levée sur presque toutes les images : pas de vrai
battement. On découpe donc l'aile d'une image de référence, puis on la fait
tourner autour de la charnière de l'épaule (vue de profil : l'aile s'écrase,
passe à plat, se retourne sous le corps, remonte à demi repliée). L'aile opposée
(copie assombrie, légèrement décalée) bat derrière le corps, et le corps remonte
un peu à chaque coup d'aile.

Résultat : une animation « flap » pré-calculée ajoutée à assets/dragon_sheet.png (pour
tout moteur), et la description de la marionnette (« rig » : aile, queue, tête, pivots)
dans dragon_sheet.json, que le jeu anime en continu.
Usage : python3 outils/animer_ailes.py   (après extraire_sprites.py)
"""
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

RACINE = Path(__file__).resolve().parent.parent
PLANCHE = RACINE / 'assets' / 'dragon_sheet.png'
META = RACINE / 'assets' / 'dragon_sheet.json'

REFERENCE = ('idle', 0)     # image dont on découpe l'aile
N = 12                      # images par battement
SUR = 4                     # suréchantillonnage des transformations

# Contour de l'aile proche et charnière de l'épaule, en px relatifs à l'ancre du sprite
# (tracés sur idle 1 : pointe, bord d'attaque, bras, puis le dos et les festons).
AILE = [(-83, -68), (47, -68), (47, -30), (40, -26), (38, -16), (35, -3), (34, 6),
        (17, 9), (-3, 11), (-11, 11), (-17, 9), (-25, 5), (-43, -8), (-58, -23), (-83, -43)]
CHARNIERE = ((-11, 11), (34, 6))   # du dos (arrière) à l'épaule (avant)
# Queue : pièce tournant autour de sa base ; le corps garde un recouvrement (COUPE s'arrête avant).
QUEUE = [(-175, -45), (-95, -45), (-90, -5), (-60, 0), (-40, 6), (-34, 12), (-34, 45), (-175, 45)]
QUEUE_COUPE = [(-175, -45), (-95, -45), (-90, -5), (-60, 0), (-50, 3), (-50, 45), (-175, 45)]
PIVOT_QUEUE = (-40, 19)
# Tête : zone remplacée par la tête (et la flamme) des images d'attaque, sous le cavalier.
TETE = [(81, -16), (230, -16), (230, 50), (62, 50), (62, 12), (74, 6), (81, 0)]
# Ce qu'on efface de la tête au repos avant la greffe : le cœur seulement (le cou reste,
# sinon la tête greffée, décalée de quelques px, laisse des trous à la jonction).
TETE_EFFACEE = [(84, -14), (230, -14), (230, 50), (70, 50), (70, 20), (84, 8)]

S_BAS = -0.8       # écrasement vertical au bas du coup d'aile (négatif = sous la charnière)
S_MIN = 0.18       # jamais complètement de profil (sinon l'aile disparaît)
DESCENTE = 0.45    # part du cycle consacrée au coup vers le bas (plus rapide)
DESSOUS = 1.3      # le dessous de la membrane, plus clair : se détache du ventre noir


def profil(phi):
    """Écrasement vertical s, repli sx, rotation (degrés) et rebond du corps pour une phase 0..1."""
    if phi < DESCENTE:
        u = phi / DESCENTE
        s = S_BAS + (1 - S_BAS) * (1 + math.cos(math.pi * u)) / 2
        sx = 1 + 0.04 * math.sin(math.pi * u)            # aile bien tendue en descendant
        rot = -5 * math.sin(math.pi * u)                  # la pointe part vers l'avant
    else:
        u = (phi - DESCENTE) / (1 - DESCENTE)
        s = S_BAS + (1 - S_BAS) * (1 - math.cos(math.pi * u)) / 2
        sx = 1 - 0.14 * math.sin(math.pi * u)            # à demi repliée en remontant
        rot = 7 * math.sin(math.pi * u)                   # la pointe traîne vers l'arrière
    if abs(s) < S_MIN:
        s = math.copysign(S_MIN, s if s != 0 else (1 if phi >= DESCENTE else -1))
    rebond = -2.5 * math.sin(2 * math.pi * (phi - 0.2))   # le corps monte pendant la poussée
    return s, sx, rot, rebond


def matrice(pivot, s, sx, rot, angle_charniere, dx, dy):
    """Affine : ramène la charnière à l'horizontale, écrase/replie, tourne, remet en place."""
    def T(x, y): return np.array([[1, 0, x], [0, 1, y], [0, 0, 1]], float)
    def R(a):
        c, si = math.cos(a), math.sin(a)
        return np.array([[c, -si, 0], [si, c, 0], [0, 0, 1]], float)
    def E(a, b): return np.array([[a, 0, 0], [0, b, 0], [0, 0, 1]], float)
    px, py = pivot
    b = angle_charniere
    return T(px + dx, py + dy) @ R(b + math.radians(rot)) @ E(sx, s) @ R(-b) @ T(-px, -py)


def transformer(calque, M):
    """Applique M (px de la case) avec suréchantillonnage, en alpha prémultiplié."""
    w, h = calque.size
    grand = np.diag([SUR, SUR, 1.0]) @ M
    inv = np.linalg.inv(grand)
    out = calque.convert('RGBa').transform((w * SUR, h * SUR), Image.AFFINE,
                                           data=tuple(inv[:2].ravel()), resample=Image.BICUBIC)
    return out.resize((w, h), Image.BOX).convert('RGBA')


def teinter(calque, f):
    a = np.array(calque).astype(float)
    a[..., :3] *= f
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def decalages_tetes(planche, meta, ref):
    """Décalage de chaque tête d'attaque pour qu'elle tombe pile sur la tête de référence
    (recalage sur la silhouette sombre, flamme exclue, dans la zone de la tête)."""
    from extraire_sprites import recaler
    cw, ch = meta['frameWidth'], meta['frameHeight']
    ax, ay = meta['anchor']['x'], meta['anchor']['y']
    zone = Image.new('L', (cw, ch), 0)
    ImageDraw.Draw(zone).polygon([(x + ax, y + ay) for x, y in TETE], fill=255)
    zone = np.array(zone) > 0

    def sil(img):
        a = np.array(img).astype(float)
        return ((a[..., 3] > 128) & (a[..., :3].mean(2) < 100) & zone).astype(float)
    base = sil(ref)
    r = meta['animations']['attack']['row']
    out = []
    for k in range(meta['animations']['attack']['frames']):
        img = planche.crop((k * cw, r * ch, (k + 1) * cw, (r + 1) * ch))
        dy, dx = recaler(base, sil(img))
        out.append(dict(anim='attack', frame=k, dx=int(dx), dy=int(dy)))
    return out


def main():
    meta = json.loads(META.read_text())
    planche = Image.open(PLANCHE).convert('RGBA')
    cw, ch = meta['frameWidth'], meta['frameHeight']
    ax, ay = meta['anchor']['x'], meta['anchor']['y']
    nom, col = REFERENCE
    ref = planche.crop((col * cw, meta['animations'][nom]['row'] * ch,
                        (col + 1) * cw, (meta['animations'][nom]['row'] + 1) * ch))

    # masque de l'aile (polygone lissé par suréchantillonnage)
    masque = Image.new('L', (cw * SUR, ch * SUR), 0)
    ImageDraw.Draw(masque).polygon([((x + ax) * SUR, (y + ay) * SUR) for x, y in AILE], fill=255)
    m = np.array(masque.resize((cw, ch), Image.BOX)).astype(float) / 255
    r = np.array(ref).astype(float)
    aile = r.copy(); aile[..., 3] *= m
    corps = r.copy(); corps[..., 3] *= 1 - m
    aile, corps = (Image.fromarray(x.round().astype(np.uint8)) for x in (aile, corps))

    (x0, y0), (x1, y1) = CHARNIERE
    pivot = (x1 + ax, y1 + ay)
    angle = math.atan2(y1 - y0, x1 - x0)

    images = []
    for i in range(N):
        s, sx, rot, rebond = profil(i / N)
        dessous = DESSOUS if s < 0 else 1.0                 # on voit le dessous de l'aile
        M = matrice(pivot, s, sx, rot, angle, 0, rebond)
        loin = matrice(pivot, s * 0.92, sx * 0.95, rot, angle, 5, rebond - 3)
        case = Image.new('RGBA', (cw, ch), (0, 0, 0, 0))
        case.alpha_composite(teinter(transformer(aile, loin), 0.5 * dessous))   # aile opposée
        case.alpha_composite(transformer(corps, matrice(pivot, 1, 1, 0, 0, 0, rebond)))
        case.alpha_composite(teinter(transformer(aile, M), dessous))           # aile proche
        images.append(case)

    # ajout (ou remplacement) de la rangée « flap » dans la planche
    anims = meta['animations']
    rang = anims['flap']['row'] if 'flap' in anims else max(a['row'] for a in anims.values()) + 1
    ncol = max(N, max(a['frames'] for k, a in anims.items() if k != 'flap'))
    neuve = Image.new('RGBA', (max(planche.width, ncol * cw), max(planche.height, (rang + 1) * ch)))
    neuve.paste(planche, (0, 0))
    neuve.paste(Image.new('RGBA', (neuve.width, ch)), (0, rang * ch))
    for i, img in enumerate(images):
        neuve.paste(img, (i * cw, rang * ch))
    anims['flap'] = dict(row=rang, frames=N, grounded=False, bodyY=[0] * N,
                         source=f'{nom} {col + 1} découpé (aile animée)')
    # description de la marionnette pour le jeu (qui découpe les pièces lui-même)
    meta['rig'] = dict(
        ref=dict(anim=nom, frame=col),
        wing=dict(poly=AILE, hinge=CHARNIERE, down=S_BAS, downShare=DESCENTE, under=DESSOUS,
                  far=dict(dx=5, dy=-3, scale=0.92, sx=0.95, shade=0.5)),
        tail=dict(poly=QUEUE, cut=QUEUE_COUPE, pivot=PIVOT_QUEUE),
        head=dict(poly=TETE, erase=TETE_EFFACEE, frames=decalages_tetes(planche, meta, ref)),
    )
    neuve.save(PLANCHE, optimize=True)
    META.write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    print(f"flap : {N} images, rangée {rang} -> {PLANCHE.name} ({neuve.width}x{neuve.height})")


if __name__ == '__main__':
    main()
