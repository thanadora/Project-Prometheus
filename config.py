WORLD_WIDTH = 30
WORLD_HEIGHT = 20
VISION_RADIUS = 5
TOROIDAL_WORLD = False
MAX_SIMULATION_STEPS = 10000

# -----------------------------
# MONDE INFINI (façon Minecraft)
# -----------------------------
# Option de lancement, indépendante du monde "classique" à bords fixes.
# Quand elle est activée : plus de bords, plus de migration (inutile sans bords),
# la carte/nourriture sont générées à la demande autour des agents.
INFINITE_WORLD          = False
INFINITE_VIEW_WIDTH     = 40   # largeur de la fenêtre de caméra (en cases)
INFINITE_VIEW_HEIGHT    = 30   # hauteur de la fenêtre de caméra (en cases)
FOOD_GROWTH_RADIUS      = 12   # rayon (cases) autour de chaque agent où la nourriture pousse
CHUNK_UNLOAD_DISTANCE   = 60   # cases au-delà desquelles une zone visitée est libérée de la mémoire
CHUNK_UNLOAD_INTERVAL   = 300  # ticks entre deux passages de nettoyage mémoire

# -----------------------------
# CONTRÔLES (personnalisables depuis les paramètres de lancement)
# -----------------------------
# Valeurs = séquences de bind Tkinter valides (ex: "<space>", "+", "<Control-s>").
KEY_BINDINGS = {
    "pause":        "<space>",
    "speed_up":     "+",
    "speed_down":   "-",
    "fast_forward": "f",
    "toggle_debug": "d",
    "save":         "<Control-s>",
    "load":         "<Control-o>",
    "pan_up":       "<Up>",
    "pan_down":     "<Down>",
    "pan_left":     "<Left>",
    "pan_right":    "<Right>",
    "next_agent":   "<Tab>",
    "prev_agent":   "<Shift-Tab>",
}
# Labels lisibles pour l'écran de paramètres / l'affichage in-game
KEY_BINDING_LABELS = {
    "pause":        "Pause / Reprendre",
    "speed_up":     "Accélérer",
    "speed_down":   "Ralentir",
    "fast_forward": "Avance rapide",
    "toggle_debug": "Panneau debug",
    "save":         "Sauvegarder",
    "load":         "Charger",
    "pan_up":       "Caméra ↑",
    "pan_down":     "Caméra ↓",
    "pan_left":     "Caméra ←",
    "pan_right":    "Caméra →",
    "next_agent":   "Agent suivant",
    "prev_agent":   "Agent précédent",
}
# Boutons souris : 1 = clic gauche, 2 = clic molette, 3 = clic droit
MOUSE_SELECT_BUTTON = 1   # sélectionner un agent
MOUSE_DRAG_BUTTON   = 3   # glisser pour déplacer la caméra (monde infini)

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
BIOME_MOUNTAIN_ROCK = 4
BIOME_MOUNTAIN_SNOW = 5

WATER_THRESHOLD   = 0.38
FOREST_THRESHOLD  = 0.45
PRAIRIE_THRESHOLD = 0.60

# -----------------------------
# ALTITUDE
# -----------------------------
# ENABLE_ALTITUDE : conserve la valeur de bruit (0..1) par case et l'utilise
# pour ombrer les couleurs de biome (relief cosmétique). Actif par défaut
# dès que les biomes sont actifs.
# ENABLE_ALTITUDE_2_5D : option d'affichage supplémentaire (désactivée par
# défaut) qui, en plus de l'ombrage, décale visuellement chaque case selon
# son altitude pour donner un effet de relief façon blocs/2.5D. Purement
# visuel pour l'instant — n'affecte ni le déplacement ni la visibilité.
ENABLE_ALTITUDE      = True
ENABLE_ALTITUDE_2_5D = True

# Bruit d'altitude totalement séparé de celui des biomes (voir map.py). Une
# échelle plus grande donne des massifs montagneux larges et cohérents
# plutôt que des variations calées sur chaque frontière de biome.
ALTITUDE_NOISE_SCALE = 16.0

# Seuils (sur l'altitude BRUTE 0..1, indépendants des paliers d'ombrage
# ci-dessous) à partir desquels le relief devient assez élevé pour que la
# case devienne de la montagne — rocheuse, puis enneigée au-delà d'un
# second seuil — à la place du biome climatique (désert/prairie/forêt).
# L'eau reste toujours prioritaire : un lac reste un lac même en altitude.
MOUNTAIN_ROCK_THRESHOLD = 0.58   # ≈ 15 % du terrain le plus élevé
MOUNTAIN_SNOW_THRESHOLD = 0.63   # ≈ 4 % du terrain le plus élevé

# Le bruit de Perlin (3 octaves) reste naturellement proche de 0.5 — sans
# étirement, les écarts d'altitude sont trop subtils pour se voir. On étire
# donc l'écart à la moyenne avant de l'utiliser pour l'ombrage/le relief.
ALTITUDE_CONTRAST      = 4.0    # facteur d'étirement de l'écart à 0.5
ALTITUDE_SHADE_STRENGTH = 0.40  # 0 = pas d'ombrage, 1 = contraste maximal
ALTITUDE_MAX_OFFSET     = 14    # décalage vertical max (px, à zoom normal) en mode 2.5D
ALTITUDE_BANDS          = 5     # nombre de paliers d'altitude (façon carte topographique)
ALTITUDE_CONTOUR_COLOR  = "#333333"  # couleur des lignes de niveau entre paliers

# Teinte supplémentaire pour le palier le plus haut / le plus bas : au-delà
# du simple éclaircissement, on tire la couleur vers un gris rocheux (sommet)
# ou un bleu-gris sombre (creux). S'applique en plus de la couleur du biome
# montagne lui-même, pour une variation douce à l'intérieur des massifs.
ALTITUDE_PEAK_COLOR    = "#d9d3c1"
ALTITUDE_PEAK_BLEND    = 0.25
ALTITUDE_VALLEY_COLOR  = "#1a2230"
ALTITUDE_VALLEY_BLEND  = 0.20

BIOME_COLORS = {
    BIOME_WATER:   "#1a3a5c",
    BIOME_DESERT:  "#c2a35a",
    BIOME_PRAIRIE: "#4a7c3f",
    BIOME_FOREST:  "#1e4d2b",
    BIOME_MOUNTAIN_ROCK: "#8a8072",
    BIOME_MOUNTAIN_SNOW: "#eef1f5",
}

# -----------------------------
# NOURRITURE PAR BIOME
# -----------------------------
# Pas d'entrée pour BIOME_MOUNTAIN_ROCK / BIOME_MOUNTAIN_SNOW : zone hostile,
# aucune nourriture n'y pousse (food.py ignore tout biome absent d'ici).
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

# -----------------------------
# MIGRATION
# -----------------------------
# Part des agents devant voter "en détresse" pour déclencher la migration
MIGRATION_VOTE_THRESHOLD  = 0.90   # 80 %

# Seuils individuels : un agent vote "en détresse" si l'une de ces conditions est vraie
MIGRATION_DISTRESS_ENERGY = 5.0   # énergie faible
MIGRATION_DISTRESS_THIRST = 5.0   # soif critique

# Intervalle minimum entre deux migrations (en ticks) pour éviter les migrations en boucle
MIGRATION_COOLDOWN        = 200

# Taille de population max en dessous de laquelle une migration collective peut encore
# se déclencher (au-delà, on considère que téléporter toute la colonie n'a plus de sens).
# Avant, ce seuil était écrit en dur (5) dans migration.py — maintenant c'est réglable.
MIGRATION_MAX_AGENTS      = 30

# Seuil d'âge à partir duquel un agent vote en détresse (proche de la mort naturelle)
MIGRATION_AGE_THRESHOLD   = MAX_AGE - 30

SAVE_CRITICAL_AGENTS     = 3    # seuil bas  → déclenche la sauvegarde
SAVE_CRITICAL_RECOVERY   = 10   # seuil haut → réarme la 

VIDEO_FPS_SCREEN = 30   # FPS mode "ce qu'on voit à l'écran"
VIDEO_FPS_TICK   = 10   # FPS mode "tick par tick"

OUTPUT_DIR = "outputs"

# Inventaire
INVENTORY_SIZE = 3
ACTION_PICKUP  = 7
ACTION_EAT     = 8

# -----------------------------
# OBJETS (inventaire)
# -----------------------------
# Chaque objet de l'inventaire est un dict {"type": ..., "value": ...}.
# Un seul type existe pour l'instant (nourriture) ; la structure est prête pour en
# ajouter d'autres plus tard (eau transportable, matériaux...) sans tout refactorer.
OBJECT_TYPE_FOOD = "food"
OBJECT_TYPES = {
    OBJECT_TYPE_FOOD: {"label": "Nourriture", "icon": "🍖"},
}

ENABLE_THIRST      = True
ENABLE_BIOMES      = True
ENABLE_DAY_NIGHT   = True
ENABLE_SEASONS     = True
ENABLE_WEATHER     = True
ENABLE_MIGRATION   = True
ENABLE_INVENTORY   = True
ENABLE_REPRODUCTION = True
ENABLE_AGE_DEATH   = True

# -----------------------------
# COMMUNICATION (lettres)
# -----------------------------
# Mécanisme brut : un agent peut "dire" une lettre par tick (action libre, ne coûte pas de temps).
# Les agents voisins la perçoivent. Aucune signification n'est câblée en dur : si un langage
# doit émerger, ce sera via une policy (évolutive/apprenante) qui reste à construire séparément.
ENABLE_COMMUNICATION = True
ALPHABET_SIZE        = 5                                   # nombre de lettres distinctes (2 à 10)
ALPHABET             = list("ABCDEFGHIJ")[:ALPHABET_SIZE]  # recalculé depuis ALPHABET_SIZE
COMM_RADIUS          = 5                                   # rayon (cases) dans lequel une lettre est entendue

LOG_LEVEL = "INFO"   # DEBUG / INFO / WARNING / ERROR

POLICY_DISTRIBUTION = {"Hardcoded": 1.0}