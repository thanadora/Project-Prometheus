import config
from dataclasses import dataclass, field
from logger import get_logger
from actions import (
    ACTION_DRINK, ACTION_PICKUP, ACTION_EAT, ACTION_VOTE_MIGRATE,
    ACTION_TO_DELTA, TIMED_ACTIONS, FREE_ACTIONS,
    is_speak_action, speak_letter_index,
)
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
    COMM_RADIUS,
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
    spoken_letter: str = None
    heard_letters: list = field(default_factory=list)
    policy: object = field(default=None, repr=False)


# -----------------------------
# PERCEPTION
# -----------------------------
def perceive(agent, world):
    min_food_dist  = float("inf")
    closest_food   = None
    min_water_dist = float("inf")
    closest_water  = None

    night_ratio    = NIGHT_VISION_RATIO if world.is_night() else 1.0
    weather_ratio  = WEATHER_VISION.get(world.weather, 1.0)
    current_radius = VISION_RADIUS * night_ratio * weather_ratio
    vision_sq      = current_radius * current_radius

    infinite = getattr(world, "infinite", False)

    for dx in range(-int(current_radius), int(current_radius) + 1):
        for dy in range(-int(current_radius), int(current_radius) + 1):
            if infinite:
                real_x = agent.x + dx
                real_y = agent.y + dy
            elif TOROIDAL_WORLD:
                real_x = (agent.x + dx) % world.width
                real_y = (agent.y + dy) % world.height
            else:
                real_x = agent.x + dx
                real_y = agent.y + dy
                if not (0 <= real_x < world.width and 0 <= real_y < world.height):
                    continue
            pos = (real_x, real_y)
            if pos not in world.food.food_positions:
                continue
            dist = dx * dx + dy * dy
            if dist > vision_sq:
                continue
            if dist < min_food_dist:
                min_food_dist = dist
                closest_food  = (dx, dy)

    adjacent_water = False
    if config.ENABLE_BIOMES and config.ENABLE_THIRST:
        if infinite:
            x_range = range(agent.x - int(current_radius), agent.x + int(current_radius) + 1)
            y_range = range(agent.y - int(current_radius), agent.y + int(current_radius) + 1)
        else:
            x_range = range(max(0, agent.x - int(current_radius)),
                             min(world.width, agent.x + int(current_radius) + 1))
            y_range = range(max(0, agent.y - int(current_radius)),
                             min(world.height, agent.y + int(current_radius) + 1))
        for x in x_range:
            for y in y_range:
                # get_biome() : en mode infini, regarder autour de soi génère/charge
                # le terrain à la demande (comme l'exploration de chunks).
                biome = world.map.get_biome(x, y) if infinite else world.map.biome_map.get((x, y))
                if biome != BIOME_WATER:
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

    heard_letters = []
    if config.ENABLE_COMMUNICATION:
        comm_sq = COMM_RADIUS * COMM_RADIUS
        for other in world.agents:
            if other is agent or not other.alive or not other.spoken_letter:
                continue
            dx = other.x - agent.x
            dy = other.y - agent.y
            if TOROIDAL_WORLD and not infinite:
                dx = (dx + world.width  // 2) % world.width  - world.width  // 2
                dy = (dy + world.height // 2) % world.height - world.height // 2
            if dx * dx + dy * dy <= comm_sq:
                heard_letters.append({"dx": dx, "dy": dy, "letter": other.spoken_letter, "from_id": other.id})

    result = {
        "food_dx": 0, "food_dy": 0, "food_dist": -1,
        "water_dx": 0, "water_dy": 0, "water_dist": -1,
        "adjacent_water": adjacent_water,
        "heard_letters": heard_letters,
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
    if is_speak_action(action):
        if not config.ENABLE_COMMUNICATION:
            return False
        idx = speak_letter_index(action)
        if 0 <= idx < len(config.ALPHABET):
            agent.spoken_letter = config.ALPHABET[idx]
            return True
        return False
    return False


def apply_timed_action(agent, world, action):
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
                agent.inventory.append({"type": config.OBJECT_TYPE_FOOD, "value": gain})
                get_logger().debug(world.tick, f"Agent #{agent.id} ramasse nourriture (+{gain}) | inventaire={agent.inventory}")
        return

    if action == ACTION_EAT:
        if not config.ENABLE_INVENTORY:
            return
        if agent.inventory:
            item = agent.inventory.pop(0)
            if item["type"] == config.OBJECT_TYPE_FOOD:
                agent.energy = min(MAX_ENERGY, agent.energy + item["value"])
            get_logger().debug(world.tick, f"Agent #{agent.id} mange depuis poche ({item['type']} +{item['value']}) | énergie={agent.energy:.1f}")
        return

    if action not in ACTION_TO_DELTA:
        return

    dx, dy = ACTION_TO_DELTA[action]
    new_x  = agent.x + dx
    new_y  = agent.y + dy

    if getattr(world, "infinite", False):
        pass  # pas de bords à vérifier
    elif TOROIDAL_WORLD:
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
    agent.perception   = perceive(agent, world)
    agent.observation  = build_observation(agent, world)
    agent.heard_letters = agent.perception.get("heard_letters", [])

    agent._prev_energy = agent.energy
    agent._prev_thirst = agent.thirst

    agent.vote_migrate  = False
    agent.spoken_letter = None
    effective_policy = agent.policy if agent.policy is not None else policy
    agent.free_actions, agent.pending_action = effective_policy.decide(agent, world)