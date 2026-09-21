# Aile Noire

Prototype de jeu vidéo en style 16 bits, fait à partir d'une planche de sprites générée par IA : un dragon noir et son cavalier, à piloter au-dessus d'un fjord à l'aube.

Le but est de tester si une planche « IA » peut devenir un vrai jeu.

## Jouer

Ouvrir `Aile-Noire.html` dans un navigateur (double-clic). Le fichier est autonome : il fonctionne hors ligne et n'a rien à installer.

| Action | Clavier | Manette à l'écran |
|---|---|---|
| Voler, marcher | ← → | croix |
| Monter / piquer | ↑ / ↓ | croix |
| Cracher le feu (maintenu : rafale) | Espace | A (rouge) |
| Ruée | C | B (jaune) |
| Looping | ↑ + Ruée, ou 2 × ↑ | |
| Au sol : accroupi, super saut | ↓ puis ↑ | |
| Animations d'origine / marionnette | B | |
| Repères (ancre, collisions) | I | |
| Couper le son | M | icône haut-parleur |

Mode entraînement sans ennemis : ajouter `#calme` à la fin de l'adresse.

## Comment c'est fait

La planche d'origine (`ChatGPT Image 21 sept. 2026, 11_55_30.png`) n'est pas utilisable telle quelle : fond gris, étiquettes, images non alignées, pas de vrai battement d'ailes. La chaîne de fabrication :

1. `outils/extraire_sprites.py` : découpe les 49 images, retire le fond (transparence recalculée sur les bords), les recale sur une ancre commune et cale les animations au sol sur la ligne de sol. Produit `assets/dragon_sheet.png` (grille régulière, utilisable dans Godot, Unity ou Phaser) et `assets/dragon_sheet.json`.
2. `outils/animer_ailes.py` : découpe l'aile, la queue et la tête pour une animation en marionnette (battement d'ailes, tête d'attaque greffée). Ajoute une animation `flap` pré-calculée et la description de la marionnette dans le JSON.
3. `outils/construire_jeu.py` : assemble `outils/jeu.src.html` et la planche en un seul fichier, `Aile-Noire.html`.

Pour tout reconstruire (Python 3 avec Pillow, numpy et scipy) :

```sh
python3 outils/extraire_sprites.py "ChatGPT Image 21 sept. 2026, 11_55_30.png" assets
python3 outils/animer_ailes.py
python3 outils/construire_jeu.py
```

## Limites connues

- Au sol (marche, atterrissage, saut, mort), le dragon utilise encore les images de la planche.
- La planche IA est dessinée « faux pixel art » (floue) et varie un peu d'une image à l'autre ; le rendu 16 bits (demi-résolution, palette de 15 teintes) le masque en grande partie.
