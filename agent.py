import random
from config import (
    VISION_RADIUS,
    TOROIDAL_WORLD,
    MOVE_COST,
    IDLE_COST,
    MAX_ENERGY,
    MAX_AGE,
    NIGHT_VISION_RATIO,
    NIGHT_IDLE_COST,
    MAX_THIRST,
    THIRST_RATE,
    THIRST_RATE_DESERT,
    THIRST_RATE_NIGHT,
    THIRST_DAMAGE,
    DRINK_AMOUNT,
    BIOME_DESERT,
    BIOME_WATER,
    WEATHER_VISION,
    WEATHER_MOVE_COST,
)
from entities import Agent

# -----------------------------
# CONSTANTES D'ACTIONS
# -----------------------------
# Actions qui consomment une unité de temps (une seule par tick)
ACTION_UP    = 0
ACTION_DOWN  = 1
ACTION_LEFT  = 2
ACTION_RIGHT = 3
ACTION_IDLE  = 4
ACTION_DRINK = 5

# Actions gratuites (plusieurs possibles par tick, avant l'action principale)
ACTION_VOTE_MIGRATE = 6

TIMED_ACTIONS = {ACTION_UP, ACTION_DOWN, ACTION_LEFT, ACTION_RIGHT, ACTION_IDLE, ACTION_DRINK}
FREE_ACTIONS  = {ACTION_VOTE_MIGRATE}

ACTION_TO_DELTA = {
    ACTION_UP:    (0, -1),
    ACTION_DOWN:  (0,  1),
    ACTION_LEFT:  (-1, 0),
    ACTION_RIGHT: (1,  0),
    ACTION_IDLE:  (0,  0),
    ACTION_DRINK: (0,  0),
}

# Indices dans le vecteur d'observation (stable pour l'IA)
OBS_FOOD_DX   = 0
OBS_FOOD_DY   = 1
OBS_FOOD_DIST = 2
OBS_ENERGY    = 3
OBS_THIRST    = 4
OBS_WATER_DX  = 5
OBS_WATER_DY  = 6
OBS_SIZE = 7  # dimension totale du vecteur d'observation

# -----------------------------
# PERCEPTION
# -----------------------------
def perceive(agent, world):
    """
    Collecte les informations brutes de l'environnement autour de l'agent.
    Retourne un dict lisible ; build_observation() le normalise pour l'IA.
    """
    min_food_dist  = float("inf")
    closest_food   = None
    min_water_dist = float("inf")
    closest_water  = None

    night_ratio    = NIGHT_VISION_RATIO if world.is_night() else 1.0
    weather_ratio  = WEATHER_VISION.get(world.weather, 1.0)
    current_radius = VISION_RADIUS * night_ratio * weather_ratio
    vision_sq      = current_radius * current_radius

    if world.food is None:
        return {
            "food_dx": 0, "food_dy": 0, "food_dist": -1,
            "water_dx": 0, "water_dy": 0, "water_dist": -1,
            "adjacent_water": False,
        }

    for x, y, amount in world.food.iter_food():
        if not world.food.is_walkable(x, y):
            continue
        dx = x - agent.x
        dy = y - agent.y
        if TOROIDAL_WORLD:
            if dx >  world.width  // 2: dx -= world.width
            elif dx < -world.width  // 2: dx += world.width
            if dy >  world.height // 2: dy -= world.height
            elif dy < -world.height // 2: dy += world.height
        dist = dx * dx + dy * dy
        if dist > vision_sq:
            continue
        if dist < min_food_dist:
            min_food_dist = dist
            closest_food  = (dx, dy)

    adjacent_water = False
    for x in range(max(0, agent.x - int(current_radius)),
                   min(world.width, agent.x + int(current_radius) + 1)):
        for y in range(max(0, agent.y - int(current_radius)),
                       min(world.height, agent.y + int(current_radius) + 1)):
            if world.food.biome_map.get((x, y)) != BIOME_WATER:
                continue
            dx   = x - agent.x
            dy   = y - agent.y
            dist = dx * dx + dy * dy
            if dist > vision_sq:
                continue
            if dist < min_water_dist:
                min_water_dist = dist
                closest_water  = (dx, dy)
            if dist == 1:
                adjacent_water = True

    result = {
        "food_dx": 0, "food_dy": 0, "food_dist": -1,
        "water_dx": 0, "water_dy": 0, "water_dist": -1,
        "adjacent_water": adjacent_water,
    }
    if closest_food is not None:
        result["food_dx"]   = closest_food[0]
        result["food_dy"]   = closest_food[1]
        result["food_dist"] = min_food_dist ** 0.5
    if closest_water is not None:
        result["water_dx"]   = closest_water[0]
        result["water_dy"]   = closest_water[1]
        result["water_dist"] = min_water_dist ** 0.5

    return result


# -----------------------------
# OBSERVATION (entrée de l'IA)
# -----------------------------
def build_observation(agent, world):
    """
    Retourne un vecteur numpy-compatible de taille OBS_SIZE,
    toutes valeurs normalisées dans [-1, 1] ou [0, 1].

    C'est l'unique interface entre l'environnement et l'IA.
    Les indices sont constants (OBS_FOOD_DX, etc.).
    """
    p        = agent.perception
    max_dist = max(world.width, world.height)
    return [
        p["food_dx"]  / world.width,                              # OBS_FOOD_DX
        p["food_dy"]  / world.height,                             # OBS_FOOD_DY
        p["food_dist"] / max_dist if p["food_dist"] != -1 else -1,# OBS_FOOD_DIST
        agent.energy  / MAX_ENERGY,                               # OBS_ENERGY
        agent.thirst  / MAX_THIRST,                               # OBS_THIRST
        p["water_dx"] / world.width,                              # OBS_WATER_DX
        p["water_dy"] / world.height,                             # OBS_WATER_DY
    ]


# -----------------------------
# REWARD (signal d'apprentissage)
# -----------------------------
def compute_reward(agent, prev_energy, prev_thirst):
    """
    Calcule la récompense obtenue après l'exécution des actions de ce tick.

    Convention :
      - positif = bon pour la survie
      - négatif = mauvais
      - mort = pénalité forte

    À affiner selon la politique d'entraînement choisie.
    """
    if not agent.alive:
        return -10.0

    reward = 0.0

    # Gain / perte d'énergie
    delta_energy = agent.energy - prev_energy
    reward += delta_energy * 0.1

    # Gain / perte de soif (thirst monte quand on boit)
    delta_thirst = agent.thirst - prev_thirst
    reward += delta_thirst * 0.05

    # Pénalité si en zone critique
    if agent.energy < 20:
        reward -= 0.5
    if agent.thirst < 20:
        reward -= 0.3

    return reward


# -----------------------------
# APPLICATION DES ACTIONS
# -----------------------------
def apply_free_action(agent, action):
    """
    Applique une action gratuite (sans coût de temps).
    Retourne True si l'action a été reconnue.
    """
    if action == ACTION_VOTE_MIGRATE:
        agent.vote_migrate = True
        return True
    return False


def apply_timed_action(agent, world, action):
    """
    Applique l'action principale de l'agent (coûte une unité de temps).
    """
    if not agent.alive:
        return

    if action == ACTION_DRINK:
        agent.thirst = min(MAX_THIRST, agent.thirst + DRINK_AMOUNT)
        return

    if action not in ACTION_TO_DELTA:
        return

    dx, dy  = ACTION_TO_DELTA[action]
    new_x   = agent.x + dx
    new_y   = agent.y + dy

    if TOROIDAL_WORLD:
        new_x %= world.width
        new_y %= world.height
    else:
        if not (0 <= new_x < world.width and 0 <= new_y < world.height):
            return

    if world.food is not None and not world.food.is_walkable(new_x, new_y):
        return

    agent.x = new_x
    agent.y = new_y

    if dx != 0 or dy != 0:
        weather_extra  = WEATHER_MOVE_COST.get(world.weather, 0.0)
        agent.energy  -= (MOVE_COST - IDLE_COST) + weather_extra
    if agent.energy <= 0:
        agent.alive = False


# -----------------------------
# SOIF
# -----------------------------
def _update_thirst(agent, world):
    biome = world.food.biome_map.get((agent.x, agent.y))

    if world.is_night():
        rate = THIRST_RATE_NIGHT
    elif biome == BIOME_DESERT:
        rate = THIRST_RATE_DESERT
    else:
        rate = THIRST_RATE

    agent.thirst = max(0, agent.thirst - rate)

    if agent.thirst <= 0:
        agent.energy -= THIRST_DAMAGE
        if agent.energy <= 0:
            agent.alive = False


# -----------------------------
# VIE / REPRODUCTION
# -----------------------------
def update_agent_life(agent, world):
    agent.age += 1
    idle_cost     = NIGHT_IDLE_COST if world.is_night() else IDLE_COST
    agent.energy -= idle_cost + (agent.age / MAX_AGE) * 0.1
    if agent.age >= MAX_AGE or agent.energy <= 0:
        agent.alive = False
        return
    _update_thirst(agent, world)


def reproduce(agent, world):
    if agent.energy <= 80 or agent.thirst <= 40:
        return None

    occupied  = {(a.x, a.y) for a in world.agents}
    neighbors = [
        (agent.x + dx, agent.y + dy)
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]
        if 0 <= agent.x + dx < world.width
        and 0 <= agent.y + dy < world.height
        and (agent.x + dx, agent.y + dy) not in occupied
        and world.food.is_walkable(agent.x + dx, agent.y + dy)
    ]
    if not neighbors:
        return None

    x, y          = random.choice(neighbors)
    agent.energy -= 40
    return Agent(
        id=-1,
        x=x,
        y=y,
        generation=agent.generation + 1,
        born_tick=world.tick,
        energy=40,
        thirst=50,
        age=0,
        alive=True,
    )


# -----------------------------
# THINK  (appelé par world_phase)
# -----------------------------
def think(agent, world, policy):
    """
    Met à jour la perception et l'observation, puis délègue la décision
    à `policy` — objet avec une méthode decide(agent, world).

    Le seul couplage avec l'IA est ici : remplacer policy suffit.
    """
    agent.perception  = perceive(agent, world)
    agent.observation = build_observation(agent, world)

    # snapshot pour le calcul de récompense après exécution
    agent._prev_energy = agent.energy
    agent._prev_thirst = agent.thirst

    agent.vote_migrate = False
    agent.free_actions, agent.pending_action = policy.decide(agent, world)
