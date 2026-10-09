# Project Prometheus — Simulation de Vie Artificielle

Une simulation d'écosystème artificiel en Python avec des agents autonomes évoluant dans un monde procédural.

## Aperçu

Les agents naissent, se déplacent, mangent, boivent, dorment, stockent de la nourriture, communiquent, se reproduisent et meurent dans un monde généré par Perlin noise. Le monde est divisé en biomes avec un cycle jour/nuit, des saisons, une météo dynamique, un relief (altitude), des catastrophes naturelles (incendies, inondations) et un système de migration collective. Un mode « monde infini » façon Minecraft est aussi disponible, avec génération de terrain à la demande autour des agents.

## Structure du projet

Tout le code vit dans le sous-dossier `projet/` — les commandes ci-dessous s'exécutent depuis ce dossier.

```
projet/
├── main.py               # Point d'entrée
├── config.py              # Toutes les constantes de la simulation
├── config_gui.py          # Interface de configuration au lancement
├── world.py                # Structure World, initialisation, boucle principale (world_phase)
├── agent.py                # Perception, décision, actions, vie des agents
├── actions.py               # Constantes d'actions et tables de correspondance
├── policy.py                # Politiques de décision (HardcodedPolicy, RandomPolicy)
├── policy_registry.py       # Registre des policies disponibles + distribution par agent
├── food.py                  # Système de nourriture par biome (pousse + pourriture)
├── map.py                   # Génération de la carte (Perlin noise, altitude)
├── weather.py               # Météo et humidité du sol
├── fire.py                  # Incendies de forêt (propagation, cendre fertile)
├── flood.py                 # Inondations temporaires (pluie / tempête)
├── migration.py               # Vote et migration collective des agents
├── reproduction.py             # Mécanique de reproduction
├── gui.py                      # Interface graphique tkinter + graphe population
├── renderer.py                  # Fonctions de rendu du monde sur le canvas (séparé de gui.py)
├── logger.py                     # Système de logs de la simulation
├── save.py                        # Sauvegarde / chargement JSON (robuste)
├── recorder.py                     # Enregistrement vidéo MP4 (mode écran ou tick par tick)
├── tools/
│   ├── context_pack.py             # Empaquette uniquement les fichiers nécessaires à une tâche (dev)
│   └── benchmark.py                 # Benchmark headless de la boucle de simulation
├── tests/                           # Suite de tests pytest (voir tests/README.md)
├── pytest.ini
└── requirements-dev.txt
```

## Fonctionnalités

**Monde**
- Génération procédurale par Perlin noise (seed aléatoire à chaque lancement)
- Biomes : eau (infranchissable), forêt, prairie, désert, montagne rocheuse, montagne enneigée, et **terre brûlée** (cendre fertile laissée par les incendies)
- Chaque biome a ses propres stats de nourriture (gain, repousse, capacité)
- Relief : altitude avec ombrage, et rendu optionnel en 2.5D
- Monde optionnellement toroïdal (bords connectés)
- **Monde infini** (façon Minecraft) : plus de bords fixes, la carte et la nourriture sont générées à la demande autour des agents, avec déchargement mémoire des zones non visitées

**Cycle temporel**
- Cycle jour/nuit avec éclairage progressif (aube, jour, crépuscule, nuit)
- 4 saisons (printemps, été, automne, hiver) influençant la météo
- 5 types de météo : dégagé, pluie, tempête, sécheresse, gel
- La météo affecte la vision, le coût de déplacement, l'humidité du sol, le risque d'incendie et les crues

**Catastrophes naturelles**
- **Feux de forêt** : départ aléatoire favorisé par la sécheresse et l'été, propagation de forêt en forêt, extinction par la pluie/le gel, destruction de la nourriture, dégâts aux agents pris dans les flammes. Les cases en feu sont marquées d'un 🔥 à l'écran (visible même la nuit) et le départ de feu est annoncé dans les logs. Après combustion, la case devient de la **cendre fertile** (nourriture qui repousse vite) puis redevient prairie.
- **Inondations** : pendant la pluie/la tempête, des berges sont recouvertes temporairement (cases infranchissables, bleu plus clair à l'écran), puis l'eau se retire et le biome d'origine est restauré. À ne pas confondre avec l'expansion d'eau des tempêtes successives (météo), qui, elle, monte le niveau des lacs de façon durable.

**Agents**
- Perception de la nourriture et de l'eau dans un rayon de vision
- Vision réduite la nuit et par mauvais temps
- Soif : les agents doivent boire sur les cases adjacentes à l'eau
- **Fatigue / sommeil** : la fatigue monte en agissant (surtout en marchant) ; dormir la régénère et régénère de l'énergie (bonus la nuit). Au-delà du seuil d'épuisement, tous les coûts d'énergie sont multipliés.
- **Maladie** : manger une nourriture pourrie (marquée 💀) a un double malus — le repas rapporte moins (valeur × fraîcheur) et peut rendre l'agent malade (🤢). La maladie est purement physiologique : elle vide l'énergie à grande vitesse (par défaut **3 énergie/tick pendant 60 ticks**, soit ~180), bien au-delà du coût de vie normal, et peut tuer. Aucun comportement d'IA n'est nécessaire pour la gérer. Réglable (seuil, chance, durée, drain) et désactivable via le module 🤒 Maladie.
- Inventaire (poches) : ramasser et stocker X nourritures pour les manger plus tard — **la nourriture transportée vieillit et perd de sa valeur** (plus lentement qu'au sol)
- Communication : chaque agent peut « dire » une lettre par tick (action libre, gratuite), perçue par les autres agents dans un rayon d'écoute — mécanisme brut, aucun sens câblé en dur
- Vieillissement et mort naturelle
- Reproduction asexuée si énergie suffisante (la policy propre de l'agent décide, pas seulement la policy globale) et plafonnable via « Population max » — recommandé en monde infini, où la croissance est exponentielle si on la laisse libre
- Vote et migration collective vers un nouveau monde si la population est en détresse
- Signal de récompense par tick (base pour un futur apprentissage par renforcement)

**Écologie de la nourriture**
- Repousse organique selon la fertilité du biome, l'humidité du sol et la proximité de l'eau
- **Pourriture** : une nourriture au sol reste fraîche environ un jour de jeu, puis sa valeur nutritive décroît (manger du vieux nourrit moins) et elle finit par disparaître. Une fois bien pourrie, elle est marquée d'une **tête de mort 💀** à l'écran, et la manger peut **rendre l'agent malade 🤢** (perte d'énergie massive pendant la maladie). Pour rester visible même dans les mondes sur-pâturés, une petite fraction des repousses naît déjà pourrie (réglable : « Repousse déjà pourrie »). Dans l'inventaire, la fraîcheur baisse doucement jusqu'à un minimum.
- La pousse est évaluée par lots (tous les N ticks, probabilités ajustées) pour ne pas coûter cher en monde infini

**Simulation**
- Coût énergétique du mouvement et du repos (plus élevé la nuit, par gel, et en état d'épuisement)
- Nourriture consommée à l'arrivée sur une case ou ramassée dans l'inventaire
- Résolution des conflits de nourriture par ordre aléatoire

**IA**
- Plusieurs policies disponibles via un registre (`policy_registry.py`) : `HardcodedPolicy` (règles de survie codées en dur) et `RandomPolicy` (baseline basse)
- Distribution configurable de la population entre policies (ex. 70% Hardcoded / 30% Random)
- Chaque agent peut avoir sa propre policy, indépendante de la policy globale de la simulation

## Installation

```bash
cd projet
python -m venv venv
source venv/bin/activate   # Linux/macOS
venv\Scripts\activate      # Windows
pip install -r requirements-dev.txt   # noise, opencv-python, numpy, pytest, pytest-cov, pillow
```

`opencv-python` et `numpy` sont nécessaires même sans enregistrement vidéo (import direct dans `gui.py`). `pytest` et `pytest-cov` ne sont utiles que pour lancer la suite de tests (voir `tests/README.md`).

## Lancement

```bash
python main.py
```

Une fenêtre de configuration s'ouvre avant la simulation. Elle permet de régler tous les paramètres, d'activer ou désactiver des modules entiers, de répartir les policies d'IA et de personnaliser les raccourcis clavier.

Depuis la dernière correction, **tous les réglages de cet écran ont un effet réel** : les modules lisent la configuration dynamiquement (`config.X`) au lieu de copier les valeurs à l'import (bug historique documenté par `tests/test_config_propagation.py`).

## Configuration au lancement

La fenêtre de configuration est organisée en onglets :

| Onglet | Contenu |
|---|---|
| 🌍 Monde | Dimensions, agents initiaux, population max (0 = ∞), monde toroïdal ou infini, seuils de biomes |
| ⚡ Énergie | Énergie max, âge max, rayon de vision, coûts de déplacement, **fatigue/sommeil** |
| 💧 Soif | Soif max, taux par biome/nuit, dégâts, seuil critique, quantité bue |
| 🍎 Nourriture | Nourriture initiale, taille inventaire, gain/repousse/capacité par biome, **pourriture** et **maladie** |
| 🌙 Jour/Nuit | Durée du jour, ratio nuit, vision nocturne, durée des saisons |
| ⛅ Météo | Probabilité de changement, humidité du sol |
| 🔥 Catastrophes | Feux (départ, propagation, durée, dégâts) et inondations (chances, durée, plafonds) |
| 🚶 Migration | Seuils de vote, cooldown, seuils de détresse, population max migrable |
| 💬 Communication | Taille de l'alphabet, rayon d'écoute |
| 🎮 Modules | Activer/désactiver des systèmes entiers (voir ci-dessous), niveau de log |
| 🤖 IA | Répartition des agents entre les policies disponibles (curseurs, total = 100%) |
| 🎮 Contrôles | Réassignation des raccourcis clavier (cliquer sur une touche pour la réassigner) |

### Modules activables/désactivables

| Module | Effet si désactivé |
|---|---|
| 🗺 Biomes | Tout le monde devient prairie (désactive aussi Soif, Météo, Saisons, Feux, Inondations) |
| 💧 Soif | Les agents n'ont pas soif, l'eau est ignorée |
| ⛅ Météo | Toujours temps dégagé (désactive aussi les Inondations) |
| 🍂 Saisons | Printemps permanent (désactive aussi Météo) |
| 🌙 Cycle jour/nuit | Toujours jour |
| 🚶 Migration | Pas de migration collective (désactivée aussi en monde infini) |
| 🎒 Inventaire | Les agents ne peuvent pas stocker de nourriture |
| 👶 Reproduction | Pas de nouveaux agents |
| 💀 Mort de vieillesse | Les agents ne meurent que par manque d'énergie |
| 💬 Communication | Les agents ne parlent plus |
| ⛰ Altitude | Plus d'ombrage de relief (désactive aussi le rendu 2.5D) |
| 😴 Sommeil / fatigue | Pas de fatigue, l'action Dormir ne fait rien |
| 🥫 Nourriture qui pourrit | La nourriture reste fraîche indéfiniment (désactive aussi la Maladie) |
| 🤒 Maladie | Manger pourri ne rend jamais malade |
| 🔥 Feux de forêt | Aucun incendie |
| 🌊 Inondations | Aucune crue |

Les dépendances sont gérées automatiquement : désactiver les Biomes désactive aussi Soif, Météo, Saisons, Feux et Inondations ; désactiver la Météo désactive les Inondations ; désactiver la Pourriture désactive la Maladie ; activer le monde infini désactive la Migration.

## Interface

- **Canvas** — monde simulé avec agents, nourriture, biomes et relief, assombri la nuit et par mauvais temps ; les cases en feu sont orange vif, les zones inondées bleu clair, la terre brûlée brun sombre ; déplaçable à la souris (glisser) et navigable au clavier en monde infini
- **Panneau agent** — cliquer sur un agent affiche ses stats détaillées (énergie, soif, fatigue, inventaire + fraîcheur, action en cours, reward, policy)
- **Panneau debug** — graphes détachables (population, communication) affichables/masquables
- **Barre d'info** — tick, saison, météo, humidité du sol, heure, agents, nourriture, morts, migrations, et compteurs 🔥 feux / 🌊 crues en cours
- **Graphe population** — courbes agents / nourriture / morts en temps réel
- **Menu Vue** — bascule l'ombrage d'altitude et le rendu en relief 2.5D
- **Menu Enregistrement** — capture vidéo MP4 en mode écran (vitesse réelle) ou tick par tick

**Couleur des agents**

| Couleur | Signification |
|---|---|
| Vert | Nouveau-né (< 5 ticks) |
| Jaune | Soif critique |
| Cyan | Énergie > 60 |
| Orange | Énergie > 30 |
| Rouge | Énergie critique |

Le chiffre affiché sur chaque agent est sa génération, « 💤 » indique un agent endormi. Le point jaune à droite est la lettre parlée. L'agent sélectionné affiche son rayon de vision en pointillés.

**Raccourcis clavier** (par défaut — personnalisables dans l'onglet 🎮 Contrôles)

| Touche | Action |
|---|---|
| `Espace` | Pause / Reprise |
| `+` | Accélérer |
| `-` | Ralentir |
| `f` | Fast forward (aller à un tick donné) |
| `d` | Afficher/masquer le panneau debug |
| `Ctrl+S` | Sauvegarder |
| `Ctrl+O` | Charger |
| `↑ ↓ ← →` | Déplacer la caméra |
| `Tab` / `Maj+Tab` | Agent suivant / précédent |

## Architecture IA

`policy.py` contient les policies, et `policy_registry.py` le registre pour en ajouter de nouvelles sans toucher au reste du code : il suffit d'implémenter une sous-classe de `BasePolicy` et de l'ajouter au `REGISTRY`. La répartition entre policies se configure par pourcentage dans l'onglet 🤖 IA, et chaque agent peut avoir sa propre policy. Chaque agent expose :
- `agent.observation` — vecteur normalisé (nourriture, eau, énergie, soif, **fatigue**)
- `agent.perception` — dictionnaire brut avec distances et cases adjacentes
- `agent.last_reward` — signal de récompense du tick précédent
- `agent.policy` — la policy assignée à cet agent (peut différer de la policy globale)

**Ajouter / retirer une IA** (vérifié par `tests/test_policy_registry.py` et `tests/test_save.py`) :

- *Ajouter* → implémenter une sous-classe de `BasePolicy` et l'ajouter au `REGISTRY` avec `class`, `description` et `color`. L'écran de config, les graphes, les couleurs d'agents et la sauvegarde s'adaptent automatiquement — aucun autre fichier à toucher (ni `main.py`, qui passe par le registre).
- *Retirer* → supprimer l'entrée du `REGISTRY`. Les sauvegardes qui la référencent restent chargeables : les agents concernés retombent sur la policy par défaut (`Hardcoded`, ou la première du registre) avec un avertissement dans les logs.

**Modèles lourds (réseaux de neurones, LLM…) :** `make_policy` crée une instance par agent — penser à partager les poids entre instances (singleton de module ou cache de classe) plutôt que de les charger dans `__init__`, sinon une copie du modèle est créée pour chaque agent.

## Performances

La boucle de simulation a été optimisée pour préparer l'entraînement massif de policies (headless). Mesures avec `tools/benchmark.py` (300 ticks, agents qui meurent d'âge au tick 300, monde 60×40) :

| Scénario | Avant | Après | Gain |
|---|---|---|---|
| Classique, 60 agents | 428 ticks/s | 617 ticks/s | ×1,4 |
| Infini, 60 agents | 81 ticks/s | 343 ticks/s | **×4,2** |
| Classique, 150 agents | — | 302 ticks/s | — |
| Infini, 150 agents | — | 121 ticks/s | — |

Ce qui a été fait :

1. **Index spatial des agents (`agent._agent_buckets`)** — la communication scannait tous les agents pour chacun d'eux (O(N²)). Les agents sont maintenant rangés dans une grille (taille = rayon d'écoute), reconstruite une fois par tick ; chaque agent ne consulte que les 9 cases autour de lui.
2. **Cache des cases actives en monde infini (`world._active_cells`)** — le disque de cases fertiles autour d'un agent ne dépend que de sa position : il est calculé une fois par position, puis l'union est réutilisée tant que la signature des positions ne change pas. Les offsets du disque sont précalculés et les cases stériles (eau, montagne) sont exclues.
3. **Pousse de la nourriture par lots (`FOOD_GROWTH_INTERVAL`)** — tester ~10 000 cases par tick pour une probabilité de ~0,5 % dominait tout le reste. La pousse est évaluée tous les 4 ticks avec des probabilités ×4 : même espérance, coût ÷4. Le balayage des voisins pour l'humidité est aussi sauté quand le sol est déjà saturé.
4. **Nettoyage mémoire (`world._unload_far_chunks`)** — les cases lointaines étaient comparées à chaque agent (O(cases × agents)). Les agents sont indexés en grille pour ne tester que le voisinage.
5. **Config lue dynamiquement** — au passage, suppression des imports figés qui rendaient l'écran de configuration inopérant.

Pour mesurer vous-même :

```bash
python tools/benchmark.py                                   # les deux modes
python tools/benchmark.py --mode infinite --agents 150 --ticks 1000
```

## Corrections récentes

- **Propagation de la configuration** : les modules utilisaient `from config import X` (valeur figée à l'import, avant même que l'écran de config ne s'affiche) — la plupart des réglages étaient sans effet. Tout passe désormais par `config.X` lu à l'usage (et des variables locales dans les boucles chaudes).
- **Migration** : un agent dont l'îlot était trop petit n'était ni relocalisé ni tué, et pouvait rester sous l'eau de la nouvelle carte. Tous les agents sont maintenant relocalisés (ou tués s'il n'y a plus de place).
- **Reproduction** : `world_phase()` consultait la policy globale au lieu de `agent.policy`.
- **Sauvegarde** : erreurs explicites (`SaveFileError`) pour fichier introuvable/JSON invalide/champs manquants, dimensions du monde persistées, états des catastrophes et âge de la nourriture sauvegardés, compatibilité avec les anciennes sauvegardes.
- **Nourriture orpheline** : quand le biome d'une case change (crue, incendie), la nourriture fantôme est retirée au lieu de rester invisible puis de réapparaître.
- **Feux hors bornes** : en monde classique, la propagation d'un incendie pouvait générer des cases au-delà des bords et faire grossir la carte sans limite. `get_biome()` refuse désormais de générer hors bornes (et les feux/crues vérifient les bords).
- **Reproduction en O(N²)** : l'ensemble des positions occupées était reconstruit à chaque tentative — coûteux quand la population grandit. Il est partagé sur tout un tick, et un plafond de population optionnel (`MAX_POPULATION`) évite l'explosion exponentielle.

## Tests

La suite de tests (425 tests, pytest, ~3,5 secondes) couvre tous les modules de logique pure, plus le rendu (via un canvas factice). Voir `tests/README.md` pour le détail et les commandes.

```bash
pytest
```

## Outils de développement

`tools/context_pack.py` empaquette uniquement les fichiers nécessaires à une tâche donnée, en résolvant récursivement les imports locaux à partir d'un ou plusieurs fichiers point d'entrée :

```bash
python3 tools/context_pack.py agent.py --dry-run
python3 tools/context_pack.py agent.py world.py --out context/
```

`tools/benchmark.py` fait tourner la simulation sans GUI et affiche ticks/s, population finale et cases générées — utile pour vérifier une optimisation ou, plus tard, évaluer des policies en masse.
