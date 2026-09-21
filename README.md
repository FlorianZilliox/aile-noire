# Dragon Rider

Un dragonnier traverse un monde éteint sur son dragon noir : des terres décharnées jusqu'aux cryptes, où quelque chose veille encore. Prototype de jeu en style 16 bits, fait à partir d'une planche de sprites générée par IA.

Le but du projet : tester si une planche « IA » peut devenir un vrai jeu.

## Jouer

En ligne : https://florianzilliox.github.io/dragon-rider/ (une fois GitHub Pages activé)

Ou ouvrir `Dragon-Rider.html` dans un navigateur (double-clic). Le fichier est autonome : il fonctionne hors ligne et n'a rien à installer.

| Action | Clavier | Manette à l'écran |
|---|---|---|
| Voler, marcher | ← → (ou Q/A et D) | croix |
| Monter / piquer | ↑ / ↓ (ou Z/W et S) | croix |
| Cracher le feu (maintenu : rafale) | X ou Espace | bouton X |
| Ruée à travers les ennemis | C, ou 2 × ← / → | bouton C |
| Piqué éclair | ↓ + C | |
| Au sol : accroupi, super saut | ↓ puis ↑ | |
| Repères (ancre, collisions) | I | |
| Couper le son | M | icône haut-parleur |

Les lettres affichées sur les boutons à l'écran sont les touches du clavier.

## L'histoire

1. **Acte I · Les Terres Décharnées** : arbres morts, églises en ruine, charognards et âmes errantes.
2. **Acte II · Le Cimetière des Rois** : mausolées, orages, chauves-souris et spectres (on ne les touche que lorsqu'ils sont visibles).
3. **Acte III · Les Cryptes** : ossuaires, bougies, crânes ardents.
4. **Le Veilleur**, au fond des cryptes. Puis un nouveau cycle, plus difficile.

5 cœurs ; les ennemis en lâchent parfois un, et chaque nouvel acte en rend 2. Après une chute, on reprend au début de l'acte (ou devant le Veilleur).

Raccourcis d'entraînement, à ajouter à la fin de l'adresse : `#calme` (sans ennemis), `#acte=2`, `#acte=3`, `#veilleur`.

## Pixel Artist

`pixel_artist/` est le pipeline qui redessine le dragon en pixel art propre et le découpe en pièces articulées. Le jeu n'utilise plus aucune image de la planche IA : il anime lui-même les pièces (ailes, aile opposée, queue, tête, mâchoire, cavalier, quatre pattes).

- **Recette** (`pixel_artist/dragon.json`) : les poses de base (en vol, au sol, à terre), les pièces de chaque pose (polygone + pivot), la palette et les réglages.
- **Pixel art** : réduction, lissage sélectif (les détails contrastés comme l'œil ou le visage du cavalier sont protégés), palette commune de 9 teintes, nettoyage des pixels isolés, contour net.
- **Sorties** (`assets/pixel-artist/`) : l'atlas des pièces (`dragon.png`, 7 Ko) et sa description (`dragon.json`), une planche propre de toutes les images du modèle (`dragon_propre.png`, pour un autre moteur), et `apercu.png` où chaque pièce est mise en mouvement.

```sh
python3 pixel_artist/pixel_artist.py      # régénère l'atlas, la planche propre et l'aperçu
python3 outils/construire_jeu.py          # intègre l'atlas dans Dragon-Rider.html
```

## Comment c'est fait

La planche d'origine (`ChatGPT Image 21 sept. 2026, 11_55_30.png`) n'est pas utilisable telle quelle : fond gris, étiquettes, images non alignées, pas de vrai battement d'ailes. La chaîne de fabrication :

1. `outils/extraire_sprites.py` : découpe les 49 images, retire le fond (transparence recalculée sur les bords), les recale sur une ancre commune et cale les animations au sol sur la ligne de sol. Produit `assets/dragon_sheet.png` (grille régulière, utilisable dans Godot, Unity ou Phaser) et `assets/dragon_sheet.json`.
2. `outils/animer_ailes.py` : découpe l'aile, la queue et la tête pour animer le dragon en marionnette (battement d'ailes continu, tête d'attaque greffée). Ajoute une animation `flap` pré-calculée et la description de la marionnette dans le JSON.
3. `pixel_artist/pixel_artist.py` : redessine le dragon en pixel art et le découpe en pièces (voir plus haut).
4. `outils/construire_jeu.py` : assemble `outils/jeu.src.html` et l'atlas Pixel Artist en un seul fichier, `Dragon-Rider.html` (≈ 100 Ko).

Pour tout reconstruire (Python 3 avec Pillow, numpy et scipy) :

```sh
python3 outils/extraire_sprites.py "ChatGPT Image 21 sept. 2026, 11_55_30.png" assets
python3 outils/animer_ailes.py
python3 pixel_artist/pixel_artist.py
python3 outils/construire_jeu.py
```

## Limites connues

- Les pattes, découpées dans une pose de la planche IA où elles se chevauchent, bougent de façon discrète : une marche plus ample demandera de redessiner les pattes à part.
- Les poses de base viennent encore de la planche IA (redessinées par Pixel Artist) : de nouvelles poses demandent une nouvelle source.
