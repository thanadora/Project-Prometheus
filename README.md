## Simulation de Vie Artificielle

Une simulation d'écosystème artificiel en Python avec des agents autonomes évoluant dans un monde procédural.

## Aperçu

Les agents naissent, se déplacent, mangent, se reproduisent et meurent dans un monde généré par Perlin noise. Le monde est divisé en biomes (eau, forêt, prairie, désert) avec un cycle jour/nuit qui affecte la vision et le métabolisme des agents.

## Structure du projet

```
.
├── main.py        # Point d'entrée
├── config.py      # Toutes les constantes de la simulation
├── entities.py    # Dataclass Agent
├── world.py       # Structure World, initialisation, boucle principale
├── agent.py       # Perception, décision, actions, reproduction
├── food.py        # Système de nourriture et biomes (Perlin noise)
└── gui.py         # Interface graphique tkinter
```

## Fonctionnalités

**Monde**
- Génération procédurale par Perlin noise (seed aléatoire à chaque lancement)
- 4 biomes : eau (infranchissable), forêt, prairie, désert
- Chaque biome a ses propres stats de nourriture (gain, repousse, capacité)
- Cycle jour/nuit avec éclairage progressif (aube, jour, crépuscule, nuit)

**Agents**
- Perception de la nourriture dans un rayon de vision (réduit la nuit)
- Déplacement vers la nourriture la plus proche
- Vieillissement et mort naturelle
- Reproduction asexuée si énergie suffisante
- Les agents ne peuvent pas traverser l'eau

**Simulation**
- Coût énergétique du mouvement et du repos (plus élevé la nuit)
- Nourriture consommée à l'arrivée sur une case
- Repousse organique de la nourriture selon la fertilité du biome
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

## Configuration

Tous les paramètres sont dans `config.py` :

| Paramètre | Défaut | Description |
|---|---|---|
| `WORLD_WIDTH` / `WORLD_HEIGHT` | 30 / 20 | Dimensions du monde |
| `INITIAL_AGENT_COUNT` | 5 | Agents au démarrage |
| `VISION_RADIUS` | 5 | Rayon de perception |
| `MAX_ENERGY` | 100 | Énergie maximale |
| `MAX_AGE` | 300 | Âge maximum en ticks |
| `DAY_DURATION` | 100 | Durée d'un cycle jour/nuit |
| `NIGHT_RATIO` | 0.4 | Fraction du cycle en nuit |
| `WATER_THRESHOLD` | 0.38 | Seuil Perlin pour l'eau |
| `FOREST_THRESHOLD` | 0.45 | Seuil Perlin pour la forêt |
| `PRAIRIE_THRESHOLD` | 0.60 | Seuil Perlin pour la prairie |

## Interface

- **Canvas du haut** — monde simulé avec agents et nourriture, assombri la nuit
- **Barre d'info** — tick, heure estimée, nombre d'agents, quantité de nourriture, morts

**Couleur des agents**
- Vert — nouveau-né (< 5 ticks)
- Cyan — énergie > 60
- Orange — énergie > 30
- Rouge — énergie critique

Le chiffre affiché sur chaque agent est sa génération. Project-Prometheus
