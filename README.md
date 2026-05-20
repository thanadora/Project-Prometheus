# Project Prometheus — Simulation de Vie Artificielle

Une simulation d'écosystème artificiel en Python avec des agents autonomes évoluant dans un monde procédural.

## Aperçu

Les agents naissent, se déplacent, mangent, boivent, stockent de la nourriture, se reproduisent et meurent dans un monde généré par Perlin noise. Le monde est divisé en biomes avec un cycle jour/nuit, des saisons, une météo dynamique et un système de migration collective.

## Structure du projet

```
.
├── main.py          # Point d'entrée
├── config.py        # Toutes les constantes de la simulation
├── config_gui.py    # Interface de configuration au lancement
├── world.py         # Structure World, initialisation, boucle principale
├── agent.py         # Perception, décision, actions, vie des agents
├── policy.py        # Politique de décision (remplacer pour une IA)
├── food.py          # Système de nourriture par biome
├── map.py           # Génération de la carte (Perlin noise)
├── gui.py           # Interface graphique tkinter + graphe population
├── save.py          # Sauvegarde / chargement JSON
└── recorder.py      # Enregistrement vidéo MP4
```

## Fonctionnalités

**Monde**
- Génération procédurale par Perlin noise (seed aléatoire à chaque lancement)
- 4 biomes : eau (infranchissable), forêt, prairie, désert
- Chaque biome a ses propres stats de nourriture (gain, repousse, capacité)
- Monde optionnellement toroïdal (bords connectés)

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
- Vieillissement et mort naturelle
- Reproduction asexuée si énergie suffisante
- Vote et migration collective vers un nouveau monde si la population est en détresse
- Signal de récompense par tick (base pour un futur apprentissage par renforcement)

**Simulation**
- Coût énergétique du mouvement et du repos (plus élevé la nuit et par gel)
- Nourriture consommée à l'arrivée sur une case ou ramassée dans l'inventaire
- Repousse organique de la nourriture selon la fertilité du biome et l'humidité du sol
- Résolution des conflits de nourriture par ordre aléatoire

## Installation

```bash
python -m venv venv
source venv/bin/activate   # Linux/macOS
venv\Scripts\activate      # Windows
pip install noise
```

## Lancement

```bash
python main.py
```

Une fenêtre de configuration s'ouvre avant la simulation. Elle permet de régler tous les paramètres et d'activer ou désactiver des modules entiers.

## Configuration au lancement

La fenêtre de configuration est organisée en onglets :

| Onglet | Contenu |
|---|---|
| 🌍 Monde | Dimensions, agents initiaux, monde toroïdal, seuils de biomes |
| ⚡ Énergie | Énergie max, âge max, rayon de vision, coûts de déplacement |
| 💧 Soif | Soif max, taux par biome/nuit, dégâts, seuil critique, quantité bue |
| 🍎 Nourriture | Nourriture initiale, taille inventaire, gain/repousse/capacité par biome |
| 🌙 Jour/Nuit | Durée du jour, ratio nuit, vision nocturne, durée des saisons |
| ⛅ Météo | Probabilité de changement, humidité du sol |
| 🚶 Migration | Seuils de vote, cooldown, seuils de détresse |
| 🎮 Modules | Activer/désactiver des systèmes entiers (voir ci-dessous) |

### Modules activables/désactivables

| Module | Effet si désactivé |
|---|---|
| 🗺 Biomes | Tout le monde devient prairie (désactive aussi Soif, Météo, Saisons) |
| 💧 Soif | Les agents n'ont pas soif, l'eau est ignorée |
| ⛅ Météo | Toujours temps dégagé |
| 🍂 Saisons | Printemps permanent (désactive aussi Météo) |
| 🌙 Cycle jour/nuit | Toujours jour |
| 🚶 Migration | Pas de migration collective |
| 🎒 Inventaire | Les agents ne peuvent pas stocker de nourriture |
| 👶 Reproduction | Pas de nouveaux agents |
| 💀 Mort de vieillesse | Les agents ne meurent que par manque d'énergie |

Les dépendances sont gérées automatiquement : désactiver les Biomes désactive aussi Soif, Météo et Saisons.

## Interface

- **Canvas** — monde simulé avec agents, nourriture et biomes, assombri la nuit et par mauvais temps
- **Panneau agent** — cliquer sur un agent affiche ses stats détaillées (énergie, soif, inventaire, action en cours, reward)
- **Barre d'info** — tick, saison, météo, heure, agents, nourriture, morts, migrations
- **Graphe population** — fenêtre séparée avec courbes agents / nourriture / morts en temps réel

**Couleur des agents**

| Couleur | Signification |
|---|---|
| Vert | Nouveau-né (< 5 ticks) |
| Jaune | Soif critique |
| Cyan | Énergie > 60 |
| Orange | Énergie > 30 |
| Rouge | Énergie critique |

Le chiffre affiché sur chaque agent est sa génération. L'agent sélectionné affiche son rayon de vision en pointillés.

**Raccourcis clavier**

| Touche | Action |
|---|---|
| `Espace` | Pause / Reprise |
| `+` | Accélérer |
| `-` | Ralentir |
| `f` | Fast forward (aller à un tick donné) |

## Architecture IA

`policy.py` est le seul fichier à remplacer pour brancher une vraie IA. La `HardcodedPolicy` fournie sert de baseline comportementale. Chaque agent expose :
- `agent.observation` — vecteur normalisé (nourriture, eau, énergie, soif)
- `agent.perception` — dictionnaire brut avec distances et cases adjacentes
- `agent.last_reward` — signal de récompense du tick précédent