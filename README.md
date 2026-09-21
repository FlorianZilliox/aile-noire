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
| Animations d'origine / marionnette | P | |
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

## Comment c'est fait

La planche d'origine (`ChatGPT Image 21 sept. 2026, 11_55_30.png`) n'est pas utilisable telle quelle : fond gris, étiquettes, images non alignées, pas de vrai battement d'ailes. La chaîne de fabrication :

1. `outils/extraire_sprites.py` : découpe les 49 images, retire le fond (transparence recalculée sur les bords), les recale sur une ancre commune et cale les animations au sol sur la ligne de sol. Produit `assets/dragon_sheet.png` (grille régulière, utilisable dans Godot, Unity ou Phaser) et `assets/dragon_sheet.json`.
2. `outils/animer_ailes.py` : découpe l'aile, la queue et la tête pour animer le dragon en marionnette (battement d'ailes continu, tête d'attaque greffée). Ajoute une animation `flap` pré-calculée et la description de la marionnette dans le JSON.
3. `outils/construire_jeu.py` : assemble `outils/jeu.src.html` et la planche en un seul fichier, `Dragon-Rider.html`.

Pour tout reconstruire (Python 3 avec Pillow, numpy et scipy) :

```sh
python3 outils/extraire_sprites.py "ChatGPT Image 21 sept. 2026, 11_55_30.png" assets
python3 outils/animer_ailes.py
python3 outils/construire_jeu.py
```

## Limites connues

- Au sol (marche, atterrissage, saut, mort), le dragon utilise encore les images de la planche.
- La planche IA est dessinée « faux pixel art » (floue) et varie un peu d'une image à l'autre ; le rendu 16 bits (demi-résolution, palette réduite) le masque en grande partie.
