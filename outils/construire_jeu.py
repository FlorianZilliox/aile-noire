"""Assemble le jeu en UN fichier autonome : double-clic pour jouer, hors ligne, sur n'importe quel appareil.

Le dragon vient du pipeline Pixel Artist (pixel_artist/pixel_artist.py) : un petit atlas de pièces
articulées et sa description sont intégrés au fichier ; le jeu les anime lui-même.

Usage : python3 outils/construire_jeu.py
"""
import base64
from pathlib import Path

ICI = Path(__file__).resolve().parent
RACINE = ICI.parent
PIXEL = RACINE / 'assets' / 'pixel-artist'
source = (ICI / 'jeu.src.html').read_text(encoding='utf-8')
if not (PIXEL / 'dragon.png').exists():
    raise SystemExit("Atlas du dragon absent : lancer d'abord  python3 pixel_artist/pixel_artist.py")
atlas = (PIXEL / 'dragon.png').read_bytes()
meta = (PIXEL / 'dragon.json').read_text(encoding='utf-8')
html = (source.replace('/*PIXEL_META*/null', meta.strip())
              .replace('/*PIXEL_DATA*/', base64.b64encode(atlas).decode('ascii')))
sortie = RACINE / 'Dragon-Rider.html'
sortie.write_text(html, encoding='utf-8')
print(f"{sortie.name} : {len(html) / 1e3:.0f} Ko")
