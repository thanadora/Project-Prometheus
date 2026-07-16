# Suite de tests

272 tests, ~1 minute d'exécution, couverture 96–100% sur tous les modules de
logique pure (`config`, `actions`, `map`, `food`, `weather`, `agent`,
`policy`, `policy_registry`, `reproduction`, `migration`, `world`, `save`,
`logger`).

**Volontairement exclus** : `gui.py`, `renderer.py`, `config_gui.py`,
`recorder.py`, `main.py`. Ce sont des modules d'interface (Tkinter/OpenCV)
sans display disponible en CI/tests automatisés, et qui contiennent très peu
de logique propre (ils orchestrent surtout les modules déjà couverts). Les
tester nécessiterait soit un serveur X virtuel (Xvfb) soit un gros travail de
mock — pas fait ici faute d'un vrai bénéfice proportionné à l'effort.

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
- `test_config_propagation.py` — documente un bug réel découvert en écrivant
  cette suite (voir plus bas).
- `test_integration.py` — fait tourner la vraie boucle de simulation (bruit
  de Perlin compris) sur des centaines de ticks pour détecter les
  régressions structurelles qu'un test unitaire isolé ne verrait pas.

## Bugs réels découverts en écrivant cette suite

Ces tests ne se contentent pas de documenter le comportement actuel : trois
comportements surprenants ont été repérés en les écrivant, et sont
maintenant figés par un test dédié pour qu'une correction future soit un
choix conscient plutôt qu'une régression de plus :

1. **`TOROIDAL_WORLD` (et toute constante importée directement dans
   `agent.py`) ne réagit pas aux changements faits par `config_gui.py`.**
   `agent.py` fait `from config import TOROIDAL_WORLD` — un import par
   valeur, figé à l'import du module, qui a lieu avant que l'écran de
   configuration ne s'exécute. La case à cocher "Monde toroïdal" de l'écran
   de démarrage n'a donc **aucun effet réel** en jeu.
   → `tests/test_config_propagation.py`

2. **Un agent isolé sur un îlot trop petit lors d'une migration n'est ni tué
   ni relocalisé.** `migration.py` remplace la carte entière pour tout le
   monde, mais seuls les agents dont l'îlot dépasse `min_land` (10% de la
   terre totale) sont repositionnés. Les autres gardent leurs anciennes
   coordonnées, qui peuvent très bien être de l'eau sur la nouvelle carte.
   → `tests/test_migration.py::test_known_quirk_stranded_agent_not_relocated_nor_killed`

3. **La décision de reproduction ignore la policy propre de l'agent.**
   `world_phase()` appelle toujours `reproduce(agent, world, policy)` avec
   la policy *globale* passée à `world_phase`, jamais `agent.policy` —
   contrairement à `think()`, qui privilégie bien `agent.policy` s'il
   existe. Un agent avec une policy spécifique qui refuse de se reproduire
   peut donc se reproduire quand même si la policy globale l'accepte.
   → `tests/test_reproduction.py::test_reproduction_decision_uses_the_passed_in_policy_not_agents_own`

D'autres comportements plus mineurs (mais tout aussi réels) sont documentés
au fil des fichiers sous forme de tests `test_known_quirk_*` ou
`test_known_fragility_*`, avec une explication en commentaire à chaque fois :
nourriture "orpheline" dans `food.py` après un changement de biome, absence
de gestion d'erreur pour un fichier de sauvegarde tronqué, dimensions du
monde non persistées à la sauvegarde.
