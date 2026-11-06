# Validation

- Analyse syntaxique de tous les fichiers Python : réussie avec Python 3.12.
- Tests binaires indépendants : 4 tests réussis (normales, coordonnées/limites, offsets de surface, noms). Commande : `python -B -m unittest discover -s tests -p test_binary.py`.
- Test Blender fourni : démarré sur Blender 4.4 local, puis interrompu faute de retour dans le délai de vérification. Aucun succès d'intégration Blender n'est revendiqué.
- Blender 5.0 : API ciblée, mais non installé ici ; test d'intégration à exécuter avant publication d'une release validée.
- Quake III Arena : pas de validation visuelle effectuée en jeu.
