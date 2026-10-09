# Suite de tests

425 tests, ~3,5 secondes, couverture 96–100% sur tous les modules de logique
pure (`config`, `actions`, `map`, `food`, `weather`, `fire`, `flood`, `agent`,
`policy`, `policy_registry`, `reproduction`, `migration`, `world`, `save`,
`logger`), plus `renderer` via un canvas factice (voir plus bas).

**Volontairement exclus de la couverture classique** : `gui.py`,
`config_gui.py`, `recorder.py`, `main.py`. Ce sont des modules d'interface
(Tkinter/OpenCV) sans display disponible en CI/tests automatisés. `renderer.py`
est désormais testé avec un faux canvas (`test_renderer.py`) car, malgré son
rôle d'affichage, il ne fait que manipuler des données et appeler
`create_rectangle`/`create_line`/etc. — un stub suffit à vérifier les
couleurs (feux, crues, nourriture pourrie) et les overlays.

## Installer

```bash
pip install -r requirements-dev.txt --break-system-packages   # si nécessaire selon l'environnement
```

## Lancer

```bash
pytest                              # tout
pytest tests/test_agent.py -v       # un seul fichier, en détail
pytest -k migration                 # tout ce qui touche à la migration
pytest --cov=. --cov-report=term-missing   # avec couverture (nécessite pytest-cov)
```

## Structure

Un fichier de test par module source (`test_agent.py` ↔ `agent.py`, etc.),
plus :
- `conftest.py` — fixtures partagées : isolation de `config.py` et du hasard
  entre chaque test, constructeurs de `World`/`GameMap`/`FoodSystem`/`Agent`
  déterministes (sans bruit de Perlin) pour des tests unitaires rapides et
  reproductibles.
- `test_config_propagation.py` — vérifie que la config est bien lue
  dynamiquement par tous les modules (le bug historique est corrigé, voir
  plus bas).
- `test_integration.py` — fait tourner la vraie boucle de simulation (bruit
  de Perlin compris) sur des centaines de ticks pour détecter les
  régressions structurelles qu'un test unitaire isolé ne verrait pas.
- `test_fire.py` / `test_flood.py` — catastrophes : ignition, propagation,
  extinction, cendre fertile, crues, décrue.
- `test_renderer.py` — rendu (biomes, aliments, agents) via un canvas factice,
  sans Tkinter ni display.

## Bugs réels corrigés (historiquement documentés par des tests)

Ces comportements surprenants avaient été figés par des tests dédiés. Ils sont
maintenant corrigés, et les tests ont été retournés pour vérifier le bon
comportement :

1. **`from config import X` figeait la configuration à l'import** — comme
   `main.py` importe `world`/`agent` avant d'afficher l'écran de configuration,
   la quasi-totalité des curseurs (taille du monde, coûts, soif, nourriture,
   météo...) était sans effet en jeu, et `TOROIDAL_WORLD` ne fonctionnait pas.
   Les modules lisent désormais `config.X` à l'usage.
   → `tests/test_config_propagation.py`

2. **Un agent isolé sur un îlot trop petit lors d'une migration n'était ni
   tué ni relocalisé** : il gardait ses anciennes coordonnées, qui pouvaient
   être de l'eau sur la nouvelle carte. Tous les agents sont désormais
   relocalisés sur une case praticable, ou tués s'il n'y a plus de place.
   → `tests/test_migration.py`

3. **La décision de reproduction ignorait la policy propre de l'agent** :
   `world_phase()` consultait toujours la policy globale. Un agent dont la
   policy refuse de se reproduire ne se reproduit plus.
   → `tests/test_reproduction.py`

4. **Nourriture orpheline** après un changement de biome (crue, incendie)
   dans `food.py` : elle restait fantôme dans `food_map` et pouvait
   réapparaître. Elle est maintenant retirée.
   → `tests/test_food.py`

5. **Sauvegarde fragile** : un fichier tronqué produisait un `KeyError` brut,
   et les dimensions du monde n'étaient pas persistées (un chargement avec une
   autre taille de config pouvait corrompre la partie). `load_world()` lève
   désormais une `SaveFileError` explicite, et dimensions + états
   (catastrophes, âge de la nourriture, fatigue) sont sauvegardés.
   → `tests/test_save.py`

6. **Feux hors bornes** : la propagation d'un incendie en monde classique
   pouvait générer des cases au-delà des bords (via `get_biome`) et faire
   exploser la carte. `GameMap.get_biome()` ne génère plus jamais hors bornes
   et les feux/crues vérifient les limites.
   → `tests/test_map.py`, `tests/test_fire.py`

7. **Reproduction en O(N²)** : l'ensemble des positions occupées était
   reconstruit à chaque tentative ; avec la croissance exponentielle de la
   population, chaque tick devenait quadratique. Il est maintenant partagé sur
   tout un tick, et un plafond `MAX_POPULATION` (0 = illimité) permet de borner
   la population.
   → `tests/test_reproduction.py`

Les tests continuent de documenter les comportements *volontairement* figés
sous forme de tests `test_known_quirk_*` quand un choix de conception mérite
d'être explicite plutôt que silencieux.
