import random
from dataclasses import dataclass, field
from logger import get_logger
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
    INVENTORY_SIZE,
)


# -----------------------------
# AGENT (données)
# -----------------------------
@dataclass
class Agent:
    id: int
    x: int
    y: int
    energy: float = 50.0
    thirst: float = 50.0
    age: int = 0
    alive: bool = True
    generation: int = 0
    born_tick: int = 0
    perception: dict = field(default_factory=dict)
    observation: list = field(default_factory=list)
    free_actions: list = field(default_factory=list)
    pending_action: int = 0
    vote_migrate: bool = False
    last_reward: float = 0.0
    _prev_energy: float = 0.0
    _prev_thirst: float = 0.0
    inventory: list = field(default_factory=list)


# -----------------------------
# CONSTANTES D'ACTIONS
# -----------------------------
ACTION_UP    = 0
ACTION_DOWN  = 1
ACTION_LEFT  = 2
ACTION_RIGHT = 3
ACTION_IDLE  = 4
ACTION_DRINK = 5
ACTION_VOTE_MIGRATE = 6
ACTION_PICKUP = 7
ACTION_EAT    = 8

TIMED_ACTIONS = {ACTION_UP, ACTION_DOWN, ACTION_LEFT, ACTION_RIGHT, ACTION_IDLE, ACTION_DRINK, ACTION_PICKUP, ACTION_EAT}
FREE_ACTIONS  = {ACTION_VOTE_MIGRATE}

ACTION_TO_DELTA = {
    ACTION_UP:    (0, -1),
    ACTION_DOWN:  (0,  1),
    ACTION_LEFT:  (-1, 0),
    ACTION_RIGHT: (1,  0),
    ACTION_IDLE:  (0,  0),
    ACTION_DRINK: (0,  0),
}

OBS_FOOD_DX   = 0
OBS_FOOD_DY   = 1
OBS_FOOD_DIST = 2
OBS_ENERGY    = 3
OBS_THIRST    = 4
OBS_WATER_DX  = 5
OBS_WATER_DY  = 6
OBS_SIZE      = 7


# -----------------------------
# PERCEPTION
# -----------------------------
def perceive(agent, world):
    import config

    min_food_dist  = float("inf")
    closest_food   = None
    min_water_dist = float("inf")
    closest_water  = None

    night_ratio    = NIGHT_VISION_RATIO if world.is_night() else 1.0
    weather_ratio  = WEATHER_VISION.get(world.weather, 1.0)
    current_radius = VISION_RADIUS * night_ratio * weather_ratio
    vision_sq      = current_radius * current_radius

    for x, y, amount in world.food.iter_food():
        if not world.map.is_walkable(x, y):
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
    if config.ENABLE_BIOMES and config.ENABLE_THIRST:
        for x in range(max(0, agent.x - int(current_radius)),
                       min(world.width, agent.x + int(current_radius) + 1)):
            for y in range(max(0, agent.y - int(current_radius)),
                           min(world.height, agent.y + int(current_radius) + 1)):
                if world.map.biome_map.get((x, y)) != BIOME_WATER:
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
    p        = agent.perception
    max_dist = max(world.width, world.height)
    return [
        p["food_dx"]   / world.width,
        p["food_dy"]   / world.height,
        p["food_dist"] / max_dist if p["food_dist"] != -1 else -1,
        agent.energy   / MAX_ENERGY,
        agent.thirst   / MAX_THIRST,
        p["water_dx"]  / world.width,
        p["water_dy"]  / world.height,
    ]


# -----------------------------
# APPLICATION DES ACTIONS
# -----------------------------
def apply_free_action(agent, action):
    if action == ACTION_VOTE_MIGRATE:
        agent.vote_migrate = True
        return True
    return False


def apply_timed_action(agent, world, action):
    import config

    if not agent.alive:
        return

    if action == ACTION_DRINK:
        if not config.ENABLE_THIRST:
            return
        agent.thirst = min(MAX_THIRST, agent.thirst + DRINK_AMOUNT)
        get_logger().debug(world.tick, f"Agent #{agent.id} boit | soif={agent.thirst:.1f}")
        return

    if action == ACTION_PICKUP:
        if not config.ENABLE_INVENTORY:
            return
        if len(agent.inventory) < INVENTORY_SIZE:
            gain = world.food.consume_food(world.map.biome_map, (agent.x, agent.y))
            if gain > 0:
                agent.inventory.append(gain)
                get_logger().debug(world.tick, f"Agent #{agent.id} ramasse nourriture (+{gain}) | inventaire={agent.inventory}")
        return

    if action == ACTION_EAT:
        if not config.ENABLE_INVENTORY:
            return
        if agent.inventory:
            gain = agent.inventory.pop(0)
            agent.energy = min(MAX_ENERGY, agent.energy + gain)
            get_logger().debug(world.tick, f"Agent #{agent.id} mange depuis poche (+{gain}) | énergie={agent.energy:.1f}")
        return

    if action not in ACTION_TO_DELTA:
        return

    dx, dy = ACTION_TO_DELTA[action]
    new_x  = agent.x + dx
    new_y  = agent.y + dy

    if TOROIDAL_WORLD:
        new_x %= world.width
        new_y %= world.height
    else:
        if not (0 <= new_x < world.width and 0 <= new_y < world.height):
            return

    if not world.map.is_walkable(new_x, new_y):
        return

    agent.x = new_x
    agent.y = new_y

    if dx != 0 or dy != 0:
        weather_extra = WEATHER_MOVE_COST.get(world.weather, 0.0)
        agent.energy -= (MOVE_COST - IDLE_COST) + weather_extra
    if agent.energy <= 0:
        agent.alive = False


# -----------------------------
# VIE
# -----------------------------
def _update_thirst(agent, world):
    import config
    if not config.ENABLE_THIRST:
        return

    biome = world.map.biome_map.get((agent.x, agent.y))
    if not config.ENABLE_BIOMES:
        rate = THIRST_RATE
    elif world.is_night():
        rate = THIRST_RATE_NIGHT
    elif biome == BIOME_DESERT:
        rate = THIRST_RATE_DESERT
    else:
        rate = THIRST_RATE

    agent.thirst = max(0, agent.thirst - rate)
    if agent.thirst <= 0:
        get_logger().warning(world.tick, f"Agent #{agent.id} soif critique — dégâts énergie ({agent.energy:.1f} → {agent.energy - THIRST_DAMAGE:.1f})")
        agent.energy -= THIRST_DAMAGE
        if agent.energy <= 0:
            agent.alive = False

def update_agent_life(agent, world):
    import config
    log = get_logger()
    agent.age += 1
    idle_cost  = NIGHT_IDLE_COST if world.is_night() else IDLE_COST
    agent.energy -= idle_cost + (agent.age / MAX_AGE) * 0.1
    if config.ENABLE_AGE_DEATH and agent.age >= MAX_AGE:
        log.info(world.tick, f"Agent #{agent.id} mort de vieillesse | âge={agent.age} gén={agent.generation}")
        agent.alive = False
        return
    if agent.energy <= 0:
        log.info(world.tick, f"Agent #{agent.id} mort d'épuisement | âge={agent.age} gén={agent.generation}")
        agent.alive = False
        return
    _update_thirst(agent, world)


# -----------------------------
# THINK (appelé par world_phase)
# -----------------------------
def think(agent, world, policy):
    agent.perception  = perceive(agent, world)
    agent.observation = build_observation(agent, world)

    agent._prev_energy = agent.energy
    agent._prev_thirst = agent.thirst

    agent.vote_migrate = False
    agent.free_actions, agent.pending_action = policy.decide(agent, world)
