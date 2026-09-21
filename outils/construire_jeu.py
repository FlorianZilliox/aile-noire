"""Assemble le jeu en UN fichier autonome (planche + description intégrées) :
double-clic pour jouer, hors ligne, sur n'importe quel ordinateur ou téléphone.

Usage : python3 outils/construire_jeu.py
"""
import base64
from pathlib import Path

ICI = Path(__file__).resolve().parent
RACINE = ICI.parent
source = (ICI / 'jeu.src.html').read_text(encoding='utf-8')
png = (RACINE / 'assets' / 'dragon_sheet.png').read_bytes()
meta = (RACINE / 'assets' / 'dragon_sheet.json').read_text(encoding='utf-8')
html = (source.replace('/*SPRITE_META*/null', meta.strip())
              .replace('/*SPRITE_DATA*/', base64.b64encode(png).decode('ascii')))
sortie = RACINE / 'Aile-Noire.html'
sortie.write_text(html, encoding='utf-8')
print(f"{sortie.name} : {len(html) / 1e6:.1f} Mo")
