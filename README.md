# Project Prometheus — Simulation de Vie Artificielle

Une simulation d'écosystème artificiel en Python avec des agents autonomes évoluant dans un monde procédural.

## Aperçu

Les agents naissent, se déplacent, mangent, boivent, stockent de la nourriture, communiquent, se reproduisent et meurent dans un monde généré par Perlin noise. Le monde est divisé en biomes avec un cycle jour/nuit, des saisons, une météo dynamique, un relief (altitude) et un système de migration collective. Un mode « monde infini » façon Minecraft est aussi disponible, avec génération de terrain à la demande autour des agents.

## Structure du projet

```
.
├── main.py               # Point d'entrée
├── config.py              # Toutes les constantes de la simulation
├── config_gui.py          # Interface de configuration au lancement
├── world.py                # Structure World, initialisation, boucle principale (world_phase)
├── agent.py                # Perception, décision, actions, vie des agents
├── actions.py               # Constantes d'actions et tables de correspondance
├── policy.py                # Politiques de décision (HardcodedPolicy, RandomPolicy)
├── policy_registry.py       # Registre des policies disponibles + distribution par agent
├── food.py                  # Système de nourriture par biome
├── map.py                   # Génération de la carte (Perlin noise, altitude)
├── weather.py                # Météo et humidité du sol
├── migration.py               # Vote et migration collective des agents
├── reproduction.py             # Mécanique de reproduction
├── gui.py                      # Interface graphique tkinter + graphe population
├── renderer.py                  # Fonctions de rendu du monde sur le canvas (séparé de gui.py)
├── logger.py                     # Système de logs de la simulation
├── save.py                        # Sauvegarde / chargement JSON
├── recorder.py                     # Enregistrement vidéo MP4 (mode écran ou tick par tick)
├── tools/
│   └── context_pack.py             # Empaquette uniquement les fichiers nécessaires à une tâche (dev)
├── tests/                           # Suite de tests pytest (voir tests/README.md)
├── pytest.ini
└── requirements-dev.txt
```

## Fonctionnalités

**Monde**
- Génération procédurale par Perlin noise (seed aléatoire à chaque lancement)
- 4 biomes : eau (infranchissable), forêt, prairie, désert
- Chaque biome a ses propres stats de nourriture (gain, repousse, capacité)
- Relief : altitude avec ombrage, et rendu optionnel en 2.5D
- Monde optionnellement toroïdal (bords connectés)
- **Monde infini** (façon Minecraft) : plus de bords fixes, la carte et la nourriture sont générées à la demande autour des agents, avec déchargement mémoire des zones non visitées

**Cycle temporel**
- Cycle jour/nuit avec éclairage progressif (aube, jour, crépuscule, nuit)
- 4 saisons (printemps, été, automne, hiver) influençant la météo
- 5 types de météo : dégagé, pluie, tempête, sécheresse, gel
- La météo affecte la vision, le coût de déplacement et l'humidité du sol

**Agents**
- Perception de la nourriture et de l'eau dans un rayon de vision
- Vision réduite la nuit et par mauvais temps
- Soif : les agents doivent boire sur les cases adjacentes à l'eau
- Inventaire (poches) : les agents peuvent ramasser et stocker X nourritures pour les manger plus tard — le gain énergétique conserve la valeur du biome d'origine
- Communication : chaque agent peut « dire » une lettre par tick (action libre, gratuite), perçue par les autres agents dans un rayon d'écoute — mécanisme brut, aucun sens câblé en dur
- Vieillissement et mort naturelle
- Reproduction asexuée si énergie suffisante
- Vote et migration collective vers un nouveau monde si la population est en détresse
- Signal de récompense par tick (base pour un futur apprentissage par renforcement)

**Simulation**
- Coût énergétique du mouvement et du repos (plus élevé la nuit et par gel)
- Nourriture consommée à l'arrivée sur une case ou ramassée dans l'inventaire
- Repousse organique de la nourriture selon la fertilité du biome et l'humidité du sol
- Résolution des conflits de nourriture par ordre aléatoire

**IA**
- Plusieurs policies disponibles via un registre (`policy_registry.py`) : `HardcodedPolicy` (règles de survie codées en dur) et `RandomPolicy` (baseline basse)
- Distribution configurable de la population entre policies (ex. 70% Hardcoded / 30% Random)
- Chaque agent peut avoir sa propre policy, indépendante de la policy globale de la simulation

## Installation

```bash
python -m venv venv
source venv/bin/activate   # Linux/macOS
venv\Scripts\activate      # Windows
pip install -r requirements-dev.txt   # noise, opencv-python, numpy, pytest, pytest-cov
```

`opencv-python` et `numpy` sont nécessaires même sans enregistrement vidéo (import direct dans `gui.py`). `pytest` et `pytest-cov` ne sont utiles que pour lancer la suite de tests (voir `tests/README.md`).

## Lancement

```bash
python main.py
```

Une fenêtre de configuration s'ouvre avant la simulation. Elle permet de régler tous les paramètres, d'activer ou désactiver des modules entiers, de répartir les policies d'IA et de personnaliser les raccourcis clavier.

## Configuration au lancement

La fenêtre de configuration est organisée en onglets :

| Onglet | Contenu |
|---|---|
| 🌍 Monde | Dimensions, agents initiaux, monde toroïdal ou infini, seuils de biomes |
| ⚡ Énergie | Énergie max, âge max, rayon de vision, coûts de déplacement |
| 💧 Soif | Soif max, taux par biome/nuit, dégâts, seuil critique, quantité bue |
| 🍎 Nourriture | Nourriture initiale, taille inventaire, gain/repousse/capacité par biome |
| 🌙 Jour/Nuit | Durée du jour, ratio nuit, vision nocturne, durée des saisons |
| ⛅ Météo | Probabilité de changement, humidité du sol |
| 🚶 Migration | Seuils de vote, cooldown, seuils de détresse, population max migrable |
| 💬 Communication | Taille de l'alphabet, rayon d'écoute |
| 🎮 Modules | Activer/désactiver des systèmes entiers (voir ci-dessous), niveau de log |
| 🤖 IA | Répartition des agents entre les policies disponibles (curseurs, total = 100%) |
| 🎮 Contrôles | Réassignation des raccourcis clavier (cliquer sur une touche pour la réassigner) |

### Modules activables/désactivables

| Module | Effet si désactivé |
|---|---|
| 🗺 Biomes | Tout le monde devient prairie (désactive aussi Soif, Météo, Saisons) |
| 💧 Soif | Les agents n'ont pas soif, l'eau est ignorée |
| ⛅ Météo | Toujours temps dégagé |
| 🍂 Saisons | Printemps permanent (désactive aussi Météo) |
| 🌙 Cycle jour/nuit | Toujours jour |
| 🚶 Migration | Pas de migration collective (désactivée aussi en monde infini) |
| 🎒 Inventaire | Les agents ne peuvent pas stocker de nourriture |
| 👶 Reproduction | Pas de nouveaux agents |
| 💀 Mort de vieillesse | Les agents ne meurent que par manque d'énergie |
| 💬 Communication | Les agents ne parlent plus |
| ⛰ Altitude | Plus d'ombrage de relief (désactive aussi le rendu 2.5D) |

Les dépendances sont gérées automatiquement : désactiver les Biomes désactive aussi Soif, Météo et Saisons ; activer le monde infini désactive la Migration.

## Interface

- **Canvas** — monde simulé avec agents, nourriture, biomes et relief, assombri la nuit et par mauvais temps ; déplaçable à la souris (glisser) et navigable au clavier en monde infini
- **Panneau agent** — cliquer sur un agent affiche ses stats détaillées (énergie, soif, inventaire, action en cours, reward, policy)
- **Panneau debug** — graphes détachables (population, communication) affichables/masquables
- **Barre d'info** — tick, saison, météo, heure, agents, nourriture, morts, migrations
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

Le chiffre affiché sur chaque agent est sa génération. L'agent sélectionné affiche son rayon de vision en pointillés.

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
- `agent.observation` — vecteur normalisé (nourriture, eau, énergie, soif)
- `agent.perception` — dictionnaire brut avec distances et cases adjacentes
- `agent.last_reward` — signal de récompense du tick précédent
- `agent.policy` — la policy assignée à cet agent (peut différer de la policy globale)

## Tests

La suite de tests (272 tests, pytest) couvre tous les modules de logique pure. Voir `tests/README.md` pour le détail, les commandes et les bugs réels découverts en écrivant la suite.

```bash
pytest
```

## Outils de développement

`tools/context_pack.py` empaquette uniquement les fichiers nécessaires à une tâche donnée, en résolvant récursivement les imports locaux à partir d'un ou plusieurs fichiers point d'entrée :

```bash
python3 tools/context_pack.py agent.py --dry-run
python3 tools/context_pack.py agent.py world.py --out context/
```