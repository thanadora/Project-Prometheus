WORLD_WIDTH = 30
WORLD_HEIGHT = 20
VISION_RADIUS = 5
TOROIDAL_WORLD = False
MAX_SIMULATION_STEPS = 10000

# Énergie
MOVE_COST = 1
IDLE_COST = 0.6
MAX_ENERGY = 100
MAX_AGE = 300

# Population
INITIAL_AGENT_COUNT = 5

# UI
CELL_SIZE = 15
MARGIN = 3
SIMULATION_DELAY_MS = 100
BACKGROUND_COLOR = "black"
GRID_COLOR = "#222222"

# -----------------------------
# BIOMES
# -----------------------------
BIOME_WATER   = 0
BIOME_DESERT  = 1
BIOME_PRAIRIE = 2
BIOME_FOREST  = 3

WATER_THRESHOLD   = 0.38
FOREST_THRESHOLD  = 0.45
PRAIRIE_THRESHOLD = 0.60

BIOME_COLORS = {
    BIOME_WATER:   "#1a3a5c",
    BIOME_DESERT:  "#c2a35a",
    BIOME_PRAIRIE: "#4a7c3f",
    BIOME_FOREST:  "#1e4d2b",
}

# -----------------------------
# NOURRITURE PAR BIOME
# -----------------------------
# (gain_energie, taux_repousse, capacite_max, couleur)
FOOD_TYPES = {
    BIOME_DESERT:  dict(gain=8,  respawn=0.001, capacity=2, color="#e8c84a"),
    BIOME_PRAIRIE: dict(gain=20, respawn=0.003, capacity=4, color="#90ee90"),
    BIOME_FOREST:  dict(gain=35, respawn=0.006, capacity=7, color="#00aa00"),
}

# valeur par défaut (utilisée dans world.py)
INITIAL_FOOD_COUNT = 50
FOOD_RESPAWN_RATE  = 0.003  # gardé pour compatibilité
FOOD_GAIN          = 20     # gardé pour compatibilité

# -----------------------------
# CYCLE JOUR / NUIT
# -----------------------------
DAY_DURATION       = 100   # ticks par cycle complet
NIGHT_RATIO        = 0.4   # 40% du cycle est la nuit
NIGHT_VISION_RATIO = 0.4   # vision réduite à 40% la nuit
NIGHT_IDLE_COST    = 1.0   # idle cost plus élevé la nuit