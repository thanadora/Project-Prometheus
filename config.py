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
FOOD_TYPES = {
    BIOME_DESERT:  dict(gain=10, respawn=0.004, capacity=3, color="#e8c84a"),
    BIOME_PRAIRIE: dict(gain=22, respawn=0.010, capacity=5, color="#90ee90"),
    BIOME_FOREST:  dict(gain=38, respawn=0.018, capacity=8, color="#00aa00"),
}

INITIAL_FOOD_COUNT = 50
FOOD_RESPAWN_RATE  = 0.0005
FOOD_GAIN          = 20

# -----------------------------
# CYCLE JOUR / NUIT
# -----------------------------
DAY_DURATION       = 50
NIGHT_RATIO        = 0.4
NIGHT_VISION_RATIO = 0.4
NIGHT_IDLE_COST    = 1.0

# -----------------------------
# SOIF
# -----------------------------
MAX_THIRST         = 100
THIRST_RATE        = 0.3
THIRST_RATE_DESERT = 0.6
THIRST_RATE_NIGHT  = 0.1
THIRST_DAMAGE      = 1.0
DRINK_AMOUNT       = 40.0
THIRST_CRITICAL    = 25.0

# -----------------------------
# SAISONS
# -----------------------------
SEASON_SPRING = 0
SEASON_SUMMER = 1
SEASON_AUTUMN = 2
SEASON_WINTER = 3

SEASON_DURATION = 150
YEAR_DURATION   = SEASON_DURATION * 4

SEASON_NAMES = {
    SEASON_SPRING: "Printemps",
    SEASON_SUMMER: "Été",
    SEASON_AUTUMN: "Automne",
    SEASON_WINTER: "Hiver",
}

# -----------------------------
# MÉTÉO
# -----------------------------
WEATHER_CLEAR   = 0
WEATHER_RAIN    = 1
WEATHER_STORM   = 2
WEATHER_DROUGHT = 3
WEATHER_FROST   = 4

WEATHER_NAMES = {
    WEATHER_CLEAR:   "☀ Dégagé",
    WEATHER_RAIN:    "🌧 Pluie",
    WEATHER_STORM:   "⛈ Tempête",
    WEATHER_DROUGHT: "🌵 Sécheresse",
    WEATHER_FROST:   "❄ Gel",
}

WEATHER_CHANGE_PROB = 0.85

WEATHER_VISION = {
    WEATHER_CLEAR:   1.0,
    WEATHER_RAIN:    0.7,
    WEATHER_STORM:   0.3,
    WEATHER_DROUGHT: 1.0,
    WEATHER_FROST:   0.8,   # légère réduction — brouillard givrant
}

WEATHER_MOISTURE_DELTA = {
    WEATHER_CLEAR:   -0.002,
    WEATHER_RAIN:    +0.025,
    WEATHER_STORM:   +0.012,
    WEATHER_DROUGHT: -0.010,
    WEATHER_FROST:   -0.004,  # sol gelé, repousse quasi nulle
}

# coût de déplacement supplémentaire par météo
WEATHER_MOVE_COST = {
    WEATHER_CLEAR:   0.0,
    WEATHER_RAIN:    0.0,
    WEATHER_STORM:   0.2,
    WEATHER_DROUGHT: 0.0,
    WEATHER_FROST:   0.5,   # sol gelé, déplacement coûteux
}

# probabilités par saison (clear, rain, storm, drought, frost)
SEASON_WEATHER_PROBS = {
    SEASON_SPRING: [0.40, 0.40, 0.10, 0.05, 0.05],
    SEASON_SUMMER: [0.35, 0.10, 0.15, 0.40, 0.00],
    SEASON_AUTUMN: [0.35, 0.30, 0.20, 0.05, 0.10],
    SEASON_WINTER: [0.25, 0.15, 0.35, 0.00, 0.25],
}


SOIL_MOISTURE_MIN  = 0.15
SOIL_MOISTURE_MAX  = 1
SOIL_MOISTURE_INIT = 1