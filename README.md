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
| Briser un mur fissuré | feu ou ruée | |
| Repères (ancre, collisions) | I | |
| Couper le son | M | icône haut-parleur |

Les lettres affichées sur les boutons à l'écran sont les touches du clavier.

## L'histoire

1. **Acte I · Les Terres Décharnées** : arbres morts, églises en ruine, charognards et âmes errantes.
2. **Acte II · Le Cimetière des Rois** : mausolées, orages, chauves-souris et spectres (on ne les touche que lorsqu'ils sont visibles).
3. **Acte III · Les Cryptes** : ossuaires, bougies, crânes ardents.
4. **Le Veilleur**, au fond des cryptes. Puis un nouveau cycle, plus difficile.

Chaque acte est un niveau dessiné à la main, à explorer en vol et à pied :

- **Le souffle** (barre sous les cœurs) : voler l'use, monter l'use plus vite ; épuisé, le dragon ne peut que planer vers le bas. Se poser le rend, tout comme les **colonnes de cendre** (courants ascendants) qui portent vers le haut. Face au Veilleur, il ne s'use pas.
- **Dangers** : pics (un cœur, on rebondit), gouffres (un cœur, retour au dernier sol sûr).
- **Secrets** : murs fissurés à briser, reliques (3 par acte en général), cœurs cachés.
- **Autels** : on les allume en s'y posant ; ils soignent, et après une défaite on reprend au dernier autel allumé.
- La porte au bout de l'acte mène au suivant ; au fond des cryptes, l'arène du Veilleur se referme.

5 cœurs ; les ennemis en lâchent parfois un, et chaque nouvel acte en rend 2.

Raccourcis d'entraînement, à ajouter à la fin de l'adresse : `#calme` (sans ennemis), `#acte=2`, `#acte=3`, `#veilleur`. `#essai` expose des aides de test (`window.__essai`) pour les outils de vérification.

## Level design

Les niveaux sont des fichiers texte, `niveaux/acte1.txt`, `acte2.txt`, `acte3.txt` : une lettre = une case de 16 × 16 pixels, 22 lignes de haut. Les lignes qui commencent par `;` sont des commentaires. On les modifie dans n'importe quel éditeur, puis on relance `python3 outils/construire_jeu.py`.

| Lettre | Case | Lettre | Objet |
|---|---|---|---|
| `.` | vide | `P` | départ du dragon |
| `#` | roc | `E` | porte de sortie de l'acte |
| `=` | corniche (on la traverse par-dessous, on s'y pose) | `f` | autel (point de reprise) |
| `^` | pics | `h` / `r` | cœur / relique |
| `x` | mur fissuré (feu ou ruée ; tout le mur cède d'un coup) | `V` | le Veilleur (son arène) |
| `~` | colonne de cendre (porte vers le haut, rend le souffle) | `T` `t` `+` | arbre mort, tombe, croix (décor) |

Ennemis : `c` charognard, `a` âme errante, `b` chauve-souris, `s` spectre, `k` crâne ardent. Ils se réveillent quand ils entrent dans le champ ; un ennemi vaincu le reste.

Mesures utiles pour dessiner une carte (le dragon est grand) :

- Au sol, il lui faut **3 cases de haut** ; en vol, 3 cases suffisent aussi, mais avec peu de marge.
- Il enjambe seul une marche d'**une case** ; au-delà, il faut sauter ou voler.
- Son feu part à hauteur de gueule : un mur fissuré doit être atteignable de face, au sol ou en vol (pas seulement par-dessus).
- Le souffle plein permet environ 7 s de vol à plat (≈ 1 200 px, 75 cases) ou 3,5 s de montée : au-delà, prévoir un sol ou une colonne de cendre.
- Hors de la carte : roc sur les côtés et en haut, gouffre en bas.

## Pixel Artist

`pixel_artist/` est le pipeline qui redessine le dragon en pixel art et le prépare pour le jeu. Le jeu n'embarque plus la planche IA d'origine.

- **Recette** (`pixel_artist/dragon.json`) : la pose de base en vol et ses pièces (polygone + pivot), la palette de 15 teintes, les zones protégées et les variantes.
- **Pixel art** : réduction de moitié, palette en rampe du noir bleuté au blanc chaud (le détail des ailes et du corps est conservé), puis nettoyage des éclats clairs parasites (griffes, poussière) hors des zones protégées (yeux, dents, visage du cavalier, souffle).
- **En vol** : le dragon est une marionnette (ailes, aile opposée, queue, tête, cavalier) animée en continu ; au tir, la vraie tête gueule ouverte du modèle est greffée (6 variantes recalées automatiquement).
- **Au sol** : course, décollage, atterrissage et chute utilisent les images du modèle, redessinées avec la même palette (`dragon_propre.png`).
- **Sorties** (`assets/pixel-artist/`) : `dragon.png` + `dragon.json` (pièces et variantes), `dragon_propre.png` + `.json` (toutes les images, utilisables dans un autre moteur), `apercu.png`.

```sh
python3 pixel_artist/pixel_artist.py      # régénère pièces, planche propre et aperçu
python3 outils/construire_jeu.py          # intègre le tout dans Dragon-Rider.html
```

## Comment c'est fait

La planche d'origine (`ChatGPT Image 21 sept. 2026, 11_55_30.png`) n'est pas utilisable telle quelle : fond gris, étiquettes, images non alignées, pas de vrai battement d'ailes. La chaîne de fabrication :

1. `outils/extraire_sprites.py` : découpe les 49 images, retire le fond (transparence recalculée sur les bords), les recale sur une ancre commune et cale les animations au sol sur la ligne de sol. Produit `assets/dragon_sheet.png` (grille régulière, utilisable dans Godot, Unity ou Phaser) et `assets/dragon_sheet.json`.
2. `outils/animer_ailes.py` : découpe l'aile, la queue et la tête pour animer le dragon en marionnette (battement d'ailes continu, tête d'attaque greffée). Ajoute une animation `flap` pré-calculée et la description de la marionnette dans le JSON.
3. `pixel_artist/pixel_artist.py` : redessine le dragon en pixel art et le découpe en pièces (voir plus haut).
4. `outils/construire_jeu.py` : assemble `outils/jeu.src.html`, les sorties Pixel Artist et les niveaux (`niveaux/`) en un seul fichier, `Dragon-Rider.html` (≈ 300 Ko).

Pour tout reconstruire (Python 3 avec Pillow, numpy et scipy) :

```sh
python3 outils/extraire_sprites.py "ChatGPT Image 21 sept. 2026, 11_55_30.png" assets
python3 outils/animer_ailes.py
python3 pixel_artist/pixel_artist.py
python3 outils/construire_jeu.py
```

## Limites connues

- Les images au sol viennent de la planche IA (redessinées) : elles gardent ses petites incohérences d'une image à l'autre.
- De nouvelles poses ou animations demandent une nouvelle source (dessin ou planche générée).
