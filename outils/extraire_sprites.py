"""Transforme une planche de sprites « IA » (fond gris, étiquettes, cadrage libre)
en planche propre pour un moteur de jeu : fond transparent, grille régulière,
images recalées sur un point d'ancrage commun, + fichier JSON de description.

Usage : python3 extraire_sprites.py <planche.png> [dossier_sortie]
Dépendances : Pillow, numpy, scipy.
"""
import json, sys
from pathlib import Path
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

# Noms des animations, dans l'ordre de lecture des étiquettes (gauche→droite, haut→bas)
NOMS = ['idle', 'attack', 'hurt', 'dead', 'flight', 'jump', 'walk', 'land']
# Animations en boucle : recalées sur leur 1re image. Les autres : de proche en proche.
BOUCLES = {'idle', 'flight', 'walk', 'attack'}
# Animations au sol : calées verticalement sur la ligne de sol dessinée dans la planche
# (valeur = image de référence pour ce sol : index, ou 'median' de toutes les images).
AU_SOL = {'walk': 'median', 'jump': 0, 'land': -1, 'dead': -1}
SEUIL = 12          # écart au fond (niveaux de gris) au-delà duquel un pixel est du sprite
MARGE = 6           # marge transparente autour de chaque case


def modele_fond(g):
    """Fond = dégradé lisse : ajustement quadratique sur les pixels « gris moyen »."""
    h, w = g.shape
    cand = ndi.binary_erosion(np.abs(g - np.median(g)) < 10, iterations=6)
    yy, xx = np.mgrid[0:h, 0:w]
    x, y = xx / w, yy / h
    m = np.stack([np.ones_like(x), x, y, x * x, y * y, x * y], -1)
    coef, *_ = np.linalg.lstsq(m[cand][::7], g[cand][::7], rcond=None)
    return m @ coef


def masque_sprite(d):
    """Tout ce qui n'est pas relié au bord par des pixels « fond » est du sprite ;
    puis les poches de fond enfermées (entre aile et cavalier, entre les pattes…)
    redeviennent du fond. Une poche = zone ≥ 8 px proche du gris d'origine, dont
    le cœur (hors bords flous) reste très proche du fond."""
    bas = np.abs(d) <= SEUIL
    lab, _ = ndi.label(bas)
    bord = np.unique(np.r_[lab[0], lab[-1], lab[:, 0], lab[:, -1]])
    fond = np.isin(lab, bord[bord > 0])
    lab2, n2 = ndi.label((np.abs(d) < 9) & ~fond)
    for i, sl in enumerate(ndi.find_objects(lab2)):
        zone = lab2[sl] == i + 1
        if zone.sum() < 8:
            continue
        coeur = ndi.binary_erosion(zone)
        if coeur.any() and np.abs(d[sl][coeur]).mean() < 7.5:
            fond[sl] |= zone
    return ~fond


def detourer(rgb, g, bg, d, fg):
    """Alpha « démélangé » sur toute la planche.
    Cœur du sprite : opaque. Bande de 2 px autour du contour : chaque pixel est vu
    comme un mélange entre la couleur locale du sprite (F : le plus sombre ou le plus
    clair du voisinage, c.-à-d. le trait de contour, la flamme, la poussière) et le
    gris du fond (B) → alpha = (I − B) / (F − B), puis couleur « défondue ».
    Résultat : ni liseré gris, ni escalier dur, quel que soit le décor derrière."""
    coeur = ndi.binary_erosion(fg, iterations=2)
    zone = ndi.binary_dilation(fg, iterations=2) & ~coeur
    # référence F = vrai dessin franc du voisinage (trait sombre, ou flamme/poussière claire)
    gmin = ndi.minimum_filter(np.where(fg & (d < -40), g, 1e3), size=7)
    gmax = ndi.maximum_filter(np.where(fg & (d > 40), g, -1e3), size=7)
    with np.errstate(divide='ignore', invalid='ignore'):
        a_sombre = np.where(gmin < 1e3, d / (np.minimum(gmin, g) - bg), -d / 60)
        # côté clair sans dessin clair à côté = halo de sur-accentuation de l'image → transparent
        a_clair = np.where(gmax > -1e3, d / (np.maximum(gmax, g) - bg), 0)
    a = np.where(d < 0, a_sombre, a_clair)
    a = np.clip((np.clip(np.nan_to_num(a), 0, 1) - 0.06) / 0.94, 0, 1)
    alpha = np.where(coeur, 1.0, np.where(zone, a, 0.0))
    # éclats isolés quasi transparents = bruit de compression
    lab, n = ndi.label(alpha > 0)
    if n:
        taille = ndi.sum(np.ones_like(g), lab, range(1, n + 1))
        pic = ndi.maximum(alpha, lab, range(1, n + 1))
        bruit = [i + 1 for i in range(n) if taille[i] < 4 and pic[i] < 0.6]
        alpha[np.isin(lab, bruit)] = 0
    out = rgb.copy()
    part = (alpha > 0) & (alpha < 1)
    for k in range(3):
        c = out[..., k]
        c[part] = (c[part] - (1 - alpha[part]) * bg[part]) / alpha[part]
    rgba = np.dstack([np.clip(out, 0, 255), alpha * 255]).round().astype(np.uint8)
    rgba[alpha == 0] = 0
    return rgba


def composantes(fg, g):
    lab, n = ndi.label(fg, structure=np.ones((3, 3)))
    idx = range(1, n + 1)
    aire = ndi.sum(np.ones_like(g), lab, idx)
    moy = ndi.mean(g, lab, idx)
    comps = []
    for i, sl in enumerate(ndi.find_objects(lab)):
        comps.append(dict(id=i + 1, y0=sl[0].start, y1=sl[0].stop, x0=sl[1].start,
                          x1=sl[1].stop, aire=aire[i], clair=moy[i] > 200))
    return lab, comps


def dist_boites(a, b):
    dx = max(b['x0'] - a['x1'], a['x0'] - b['x1'], 0)
    dy = max(b['y0'] - a['y1'], a['y0'] - b['y1'], 0)
    return (dx * dx + dy * dy) ** 0.5


def regrouper(comps):
    """Sépare étiquettes (glyphes clairs), images (grosses composantes) et détails."""
    glyphes = [c for c in comps if c['clair'] and c['aire'] < 900 and 12 <= c['y1'] - c['y0'] <= 30]
    images = [c for c in comps if c['aire'] > 3000]
    reste = [c for c in comps if c not in glyphes and c not in images]
    # glyphes voisins -> une étiquette
    etiquettes = []
    for c in sorted(glyphes, key=lambda c: (c['y0'], c['x0'])):
        for e in etiquettes:
            if dist_boites(e, c) < 30:
                e.update(x0=min(e['x0'], c['x0']), x1=max(e['x1'], c['x1']),
                         y0=min(e['y0'], c['y0']), y1=max(e['y1'], c['y1']))
                break
        else:
            etiquettes.append(dict(c))
    etiquettes = [e for e in etiquettes if e['x1'] - e['x0'] > 30]  # un mot, pas un éclat isolé
    # chaque détail (flamme, étincelle, poussière) rejoint l'image la plus proche
    for im in images:
        im['ids'] = [im['id']]
    for c in reste:
        if c['aire'] < 3 or any(dist_boites(e, c) < 15 for e in etiquettes):
            continue  # poussière d'antialiasing autour du texte
        proche = min(images, key=lambda im: dist_boites(im, c))
        if dist_boites(proche, c) < 40:
            proche['ids'].append(c['id'])
            proche.update(x0=min(proche['x0'], c['x0']), x1=max(proche['x1'], c['x1']),
                          y0=min(proche['y0'], c['y0']), y1=max(proche['y1'], c['y1']))
    # chaque image appartient à l'étiquette la plus proche sur sa gauche, même bande
    def bande(o):
        return (o['y0'] + o['y1']) / 2
    anims = {}
    for im in images:
        cands = [e for e in etiquettes if e['x1'] <= im['x0'] + 5 and abs(bande(e) - bande(im)) < 60]
        if not cands:
            sys.exit(f"Image en x={im['x0']}, y={im['y0']} sans étiquette à sa gauche.")
        e = max(cands, key=lambda e: e['x1'])
        anims.setdefault(id(e), (e, []))[1].append(im)
    ordre = sorted(anims.values(), key=lambda t: (round(bande(t[0]) / 60), t[0]['x0']))
    return [sorted(ims, key=lambda im: im['x0']) for _, ims in ordre]


def recaler(ref, img):
    """Décalage (dy, dx) qui superpose au mieux la silhouette sombre de img sur ref."""
    h = max(ref.shape[0], img.shape[0]) * 2
    w = max(ref.shape[1], img.shape[1]) * 2
    fa = np.fft.rfft2(ref, (h, w))
    fb = np.fft.rfft2(img, (h, w))
    cc = np.fft.irfft2(fa * np.conj(fb), (h, w))
    dy, dx = np.unravel_index(np.argmax(cc), cc.shape)
    if dy > h // 2: dy -= h
    if dx > w // 2: dx -= w
    return int(dy), int(dx)


def silhouette(rgba):
    lum = rgba[..., :3].mean(2)
    return ((rgba[..., 3] > 128) & (lum < 100)).astype(float)


def main():
    src = Path(sys.argv[1])
    sortie = Path(sys.argv[2]) if len(sys.argv) > 2 else src.parent / 'assets'
    sortie.mkdir(parents=True, exist_ok=True)
    rgb = np.array(Image.open(src).convert('RGB')).astype(float)
    g = rgb.mean(2)
    bg = modele_fond(g)
    d = g - bg
    fg = masque_sprite(d)
    lab, comps = composantes(fg, g)
    groupes = regrouper(comps)
    if len(groupes) != len(NOMS):
        sys.exit(f"Trouvé {len(groupes)} animations, attendu {len(NOMS)} : vérifier NOMS.")

    # 1) détourage de toute la planche, puis chaque image garde les pixels dont
    #    le morceau de sprite le plus proche lui appartient (les bords flous inclus)
    rgba_tout = detourer(rgb, g, bg, d, fg)
    dist, (iy, ix) = ndi.distance_transform_edt(lab == 0, return_indices=True)
    proche = np.where(dist <= 3, lab[iy, ix], 0)
    anims = {}
    for nom, ims in zip(NOMS, groupes):
        frames = []
        for im in ims:
            y0, y1, x0, x1 = im['y0'] - 4, im['y1'] + 4, im['x0'] - 4, im['x1'] + 4
            a_moi = np.isin(proche[y0:y1, x0:x1], im['ids'])
            rgba = rgba_tout[y0:y1, x0:x1] * a_moi[..., None]
            frames.append(dict(rgba=rgba.astype(np.uint8), pos=[y0, x0], bas=im['y1']))
        anims[nom] = frames

    # 2) recalage : chaque image reçoit une origine (oy, ox) = position de l'ancre dans l'image
    def origine_relative(ref, img):
        dy, dx = recaler(silhouette(ref['rgba']), silhouette(img['rgba']))
        return ref['o'][0] - dy, ref['o'][1] - dx

    base = anims['idle'][0]
    sil = silhouette(base['rgba'])
    cy, cx = ndi.center_of_mass(sil)
    base['o'] = (cy, cx)
    for nom in NOMS:
        fr = anims[nom]
        if nom != 'idle':
            # 1re image recalée sur idle[0] (sauf jump : sa dernière image = pose de vol)
            if nom == 'jump':
                fr[-1]['o'] = origine_relative(base, fr[-1])
                for i in range(len(fr) - 2, -1, -1):
                    fr[i]['o'] = origine_relative(fr[i + 1], fr[i])
                continue
            fr[0]['o'] = origine_relative(base, fr[0])
        for i in range(1, len(fr)):
            ref = fr[0] if nom in BOUCLES else fr[i - 1]
            fr[i]['o'] = origine_relative(ref, fr[i])

    # 2b) animations au sol : on garde le recalage horizontal, mais la verticale suit le sol
    #     de la planche ; 'body' mémorise où se trouve le corps par rapport à l'ancre.
    def sol_de(nom):
        fr = anims[nom]
        ref = AU_SOL[nom]
        return float(np.median([f['bas'] for f in fr])) if ref == 'median' else fr[ref]['bas']
    marche = anims['walk']
    sol_marche = sol_de('walk')
    G = float(np.median([(sol_marche - f['pos'][0]) - f['o'][0] for f in marche]))
    for fr in anims.values():
        for f in fr:
            f['body'] = 0.0
    for nom in AU_SOL:
        sol = sol_de(nom)
        for f in anims[nom]:
            o_sol = (sol - f['pos'][0]) - G
            f['body'] = f['o'][0] - o_sol
            f['o'] = (o_sol, f['o'][1])

    # 3) grille régulière : case commune, ancre au même endroit dans chaque case
    haut = max(f['o'][0] for fr in anims.values() for f in fr)
    gauche = max(f['o'][1] for fr in anims.values() for f in fr)
    bas = max(f['rgba'].shape[0] - f['o'][0] for fr in anims.values() for f in fr)
    droite = max(f['rgba'].shape[1] - f['o'][1] for fr in anims.values() for f in fr)
    ay, ax = int(np.ceil(haut)) + MARGE, int(np.ceil(gauche)) + MARGE
    ch, cw = ay + int(np.ceil(bas)) + MARGE, ax + int(np.ceil(droite)) + MARGE
    ncol = max(len(fr) for fr in anims.values())
    planche = np.zeros((ch * len(NOMS), cw * ncol, 4), np.uint8)
    meta = dict(image='dragon_sheet.png', frameWidth=cw, frameHeight=ch,
                anchor=dict(x=ax, y=ay), animations={})
    for r, nom in enumerate(NOMS):
        for c, f in enumerate(anims[nom]):
            oy, ox = int(round(ay - f['o'][0])), int(round(ax - f['o'][1]))
            h, w = f['rgba'].shape[:2]
            case = planche[r * ch:(r + 1) * ch, c * cw:(c + 1) * cw]
            zone = case[oy:oy + h, ox:ox + w]
            src_ = f['rgba'][:zone.shape[0], :zone.shape[1]]
            np.copyto(zone, src_, where=src_[..., 3:4] > 0)
        meta['animations'][nom] = dict(row=r, frames=len(anims[nom]), grounded=nom in AU_SOL,
                                       bodyY=[int(round(f['body'])) for f in anims[nom]])
    meta['groundOffset'] = int(round(G))

    # bouche : premier jet de flamme de l'attaque (pixels très clairs), relatif à l'ancre
    r = NOMS.index('attack')
    # bout du museau sur la 1re image (pas encore de flamme, dont le contour est sombre)
    museau = np.nonzero(silhouette(planche[r * ch:(r + 1) * ch, :cw]).sum(0) > 2)[0].max()
    for c in range(len(anims['attack'])):
        case = planche[r * ch:(r + 1) * ch, c * cw:(c + 1) * cw]
        feu = (case[..., 3] > 200) & (case[..., :3].mean(2) > 200)
        feu[:, :museau - 3] = False  # (l'œil et le visage du cavalier sont clairs aussi)
        if feu.sum() > 20:
            ys, xs = np.nonzero(feu)
            meta['animations']['attack']['fireFrame'] = c
            meta['mouth'] = dict(x=int(museau) - ax, y=int(np.median(ys)) - ay)
            break

    Image.fromarray(planche).save(sortie / 'dragon_sheet.png', optimize=True)
    (sortie / 'dragon_sheet.json').write_text(json.dumps(meta, indent=2))
    print(f"{sum(len(f) for f in anims.values())} images -> {sortie/'dragon_sheet.png'} "
          f"({planche.shape[1]}x{planche.shape[0]}, case {cw}x{ch}, ancre {ax},{ay}, sol +{meta['groundOffset']}, bouche {meta.get('mouth')})")
    for nom in NOMS:
        print(f"  {nom:7s} {len(anims[nom])} images  corps {meta['animations'][nom]['bodyY']}")


if __name__ == '__main__':
    main()
