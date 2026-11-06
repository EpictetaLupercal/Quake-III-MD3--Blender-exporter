# Blender MD3 Exporter

Add-on Python ciblant **Blender 5.0**, export MD3 version 15 pour Quake III Arena. Sans dépendance Python externe. Licence MIT.

## Installation

1. Télécharger `io_export_md3.py`.
2. Blender : **Edit > Preferences > Add-ons > menu > Install from Disk** ; sélectionner ce fichier et activer l'add-on.
3. En mode Objet : **File > Export > Quake III Arena (.md3)**.

## Préparer et exporter

- Sélectionner les meshes et les empties `tag_*` à exporter. Une UV map active est obligatoire sur chaque mesh.
- Orienter le modèle : **+X avant, +Y gauche, +Z haut**. Les coordonnées monde sont exportées ; placer l'origine du modèle à l'origine de la scène. Aucune rotation automatique des axes.
- `Scale` multiplie les coordonnées, avec 1 unité Blender = 1 unité Quake par défaut. Les unités physiques de scène ne sont pas converties automatiquement.
- Chaque matériau produit une ou plusieurs surfaces. Son nom sert de chemin de shader Quake, par exemple `models/mapobjects/crate/wood`. La propriété personnalisée texte `md3_shader` du matériau peut remplacer ce nom. Les chemins utilisent `/` et sont relatifs à `baseq3`, sans préfixe `baseq3/`.
- Les textures et matériaux Blender ne sont pas convertis : fournir séparément les images et, si nécessaire, les scripts `.shader` du jeu. Un matériau absent donne un chemin vide.
- Cocher **Export scene frame range** pour exporter chaque frame entière de la plage de scène, bornes incluses. Sinon seule la frame courante est exportée, à sous-frame zéro.
- Armatures, shape keys et modificateurs sont évalués en déformations de sommets. Le fichier ne contient pas de squelette. La topologie, les UV, les indices de matériaux et la triangulation doivent rester identiques. Ajouter un modificateur Triangulate avant les déformations si nécessaire ; les changements détectés annulent l'export.
- Les empties `tag_weapon`, `tag_torso`, etc. deviennent des tags animés. Leurs axes locaux sont exportés ; les échelles sont retirées. Les réflexions et cisaillements des tags sont refusés.

Les UV sont retournés verticalement, les normales par coin sont compressées, les transformations miroir des meshes sont prises en compte. Les surfaces sont découpées automatiquement en blocs de 333 triangles maximum pour rester sous les limites du renderer Quake III original. Les coins partagés au sein d'une face restent partagés ; les coins de faces distinctes restent séparés pour préserver les normales et UV.

Limites : 1024 frames, 16 tags, 32 surfaces ; coordonnées quantifiées au 1/64, comprises dans [-512, 511.984375] après arrondi. Noms ASCII uniquement, 63 octets maximum (suffixes de surfaces inclus). Réduire Scale ou simplifier le modèle si une limite est atteinte. Les instances de collection et objets non mesh ne sont pas réalisés automatiquement.

Pour un joueur Q3, exporter séparément `lower.md3`, `upper.md3`, `head.md3` avec leurs tags appropriés. Les fichiers `.skin`, `animation.cfg`, LOD et archives `.pk3` ne sont pas générés. Si une surface est découpée, utiliser ses noms suffixés dans les fichiers `.skin`.

## Développement et vérification

```sh
blender --background --factory-startup --python-exit-code 1 --python tests/blender_smoke.py
```

Le test vérifie l'en-tête, les offsets, les surfaces, les UV/normales via leur taille binaire, deux frames animées, un tag, la restauration de la timeline et la conservation du fichier lors d'un export invalide. Il ne remplace pas une validation visuelle en jeu.

Voir `VALIDATION.md` pour les tests réellement exécutés. Le dépôt est prêt à être publié sur GitHub ; aucune publication distante n'est effectuée.

## Références

- [API Mesh Blender 5.0](https://docs.blender.org/api/5.0/bpy.types.Mesh.html)
- [Définition MD3 officielle, id Software](https://github.com/id-Software/Quake-III-Arena/blob/master/code/qcommon/qfiles.h)
- [Limites du renderer Quake III](https://github.com/id-Software/Quake-III-Arena/blob/master/code/renderer/tr_surface.c)

Implémentation indépendante en Python ; aucun code du moteur n'est incorporé.
