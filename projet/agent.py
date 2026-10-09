import random
import config
from dataclasses import dataclass, field
from logger import get_logger
from actions import (
    ACTION_DRINK, ACTION_PICKUP, ACTION_EAT, ACTION_VOTE_MIGRATE, ACTION_SLEEP,
    ACTION_IDLE, ACTION_TO_DELTA, TIMED_ACTIONS, FREE_ACTIONS,
    is_speak_action, speak_letter_index,
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
    fatigue: float = 0.0
    # Maladie (nourriture pourrie) : nombre de ticks restants, 0 = sain.
    sick_ticks: int = 0


# -----------------------------
# INDEX SPATIAL DES AGENTS
# -----------------------------
def _agent_buckets(world):
    """Index des agents vivants par case de grille (taille = rayon d'écoute),
    reconstruit une fois par tick puis réutilisé par tous les `perceive()`.

    Sans lui, chaque agent parcourait la liste complète des agents pour
    chercher qui il entend : O(N²) par tick. Avec l'index, chaque agent ne
    regarde que les 9 cases de grille autour de lui (rayon d'écoute ≤ taille
    d'une case, donc tout locuteur audible est forcément dans ce voisinage).

    Exposé dans `world._agent_grid` pour être partagé entre agents ; le tick
    sert de clé de fraîcheur (les positions ne changent pas pendant la phase
    de perception/décision, donc un cache par tick est exact).
    """
    cached = getattr(world, "_agent_grid", None)
    if cached is not None and getattr(world, "_agent_grid_tick", -1) == world.tick:
        return cached

    r = max(1, config.COMM_RADIUS)
    grid = {}
    for other in world.agents:
        if not other.alive:
            continue
        key = (other.x // r, other.y // r)
        grid.setdefault(key, []).append(other)

    if hasattr(world, "_agent_grid"):
        world._agent_grid = grid
        world._agent_grid_tick = world.tick
    return grid


# -----------------------------
# PERCEPTION
# -----------------------------
def perceive(agent, world):
    min_food_dist  = float("inf")
    closest_food   = None
    min_water_dist = float("inf")
    closest_water  = None

    night_ratio    = config.NIGHT_VISION_RATIO if world.is_night() else 1.0
    weather_ratio  = config.WEATHER_VISION.get(world.weather, 1.0)
    current_radius = config.VISION_RADIUS * night_ratio * weather_ratio
    vision_sq      = current_radius * current_radius
    radius_int     = int(current_radius)

    infinite = getattr(world, "infinite", False)

    for dx in range(-radius_int, radius_int + 1):
        for dy in range(-radius_int, radius_int + 1):
            if infinite:
                real_x = agent.x + dx
                real_y = agent.y + dy
            elif config.TOROIDAL_WORLD:
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
            x_range = range(agent.x - radius_int, agent.x + radius_int + 1)
            y_range = range(agent.y - radius_int, agent.y + radius_int + 1)
        else:
            x_range = range(max(0, agent.x - radius_int),
                             min(world.width, agent.x + radius_int + 1))
            y_range = range(max(0, agent.y - radius_int),
                             min(world.height, agent.y + radius_int + 1))
        for x in x_range:
            for y in y_range:
                # get_biome() : en mode infini, regarder autour de soi génère/charge
                # le terrain à la demande (comme l'exploration de chunks).
                biome = world.map.get_biome(x, y) if infinite else world.map.biome_map.get((x, y))
                if biome != config.BIOME_WATER:
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
        comm_radius = max(1, config.COMM_RADIUS)
        comm_sq     = comm_radius * comm_radius
        grid        = _agent_buckets(world)
        bx, by      = agent.x // comm_radius, agent.y // comm_radius

        if config.TOROIDAL_WORLD and not infinite:
            nbx = max(1, (world.width  + comm_radius - 1) // comm_radius)
            nby = max(1, (world.height + comm_radius - 1) // comm_radius)
            keys = {((bx + ddx) % nbx, (by + ddy) % nby)
                    for ddx in (-1, 0, 1) for ddy in (-1, 0, 1)}
        else:
            keys = [(bx + ddx, by + ddy)
                    for ddx in (-1, 0, 1) for ddy in (-1, 0, 1)]

        for key in keys:
            for other in grid.get(key, ()):
                if other is agent or not other.spoken_letter:
                    continue
                dx = other.x - agent.x
                dy = other.y - agent.y
                if config.TOROIDAL_WORLD and not infinite:
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
    observation = [
        p["food_dx"]   / world.width,
        p["food_dy"]   / world.height,
        p["food_dist"] / max_dist if p["food_dist"] != -1 else -1,
        agent.energy   / config.MAX_ENERGY,
        agent.thirst   / config.MAX_THIRST,
        p["water_dx"]  / world.width,
        p["water_dy"]  / world.height,
    ]
    # La fatigue fait partie de l'état de l'agent (utile pour une policy
    # apprenante) : normalisée sur MAX_FATIGUE, 0 si le module est désactivé,
    # pour garder un vecteur de taille constante.
    if config.ENABLE_FATIGUE and config.MAX_FATIGUE > 0:
        observation.append(agent.fatigue / config.MAX_FATIGUE)
    else:
        observation.append(0.0)
    # Idem pour la maladie : 1.0 tant que l'agent est malade, 0.0 sinon.
    observation.append(
        1.0 if (config.ENABLE_SICKNESS and agent.sick_ticks > 0) else 0.0
    )
    return observation


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
        agent.thirst = min(config.MAX_THIRST, agent.thirst + config.DRINK_AMOUNT)
        get_logger().debug(world.tick, f"Agent #{agent.id} boit | soif={agent.thirst:.1f}")
        return

    if action == ACTION_SLEEP:
        if not config.ENABLE_FATIGUE:
            return
        # La récupération (fatigue + énergie) est appliquée dans
        # update_agent_life(), au même endroit que les autres coûts de vie.
        get_logger().debug(world.tick, f"Agent #{agent.id} dort | fatigue={agent.fatigue:.1f}")
        return

    if action == ACTION_PICKUP:
        if not config.ENABLE_INVENTORY:
            return
        if len(agent.inventory) < config.INVENTORY_SIZE:
            pos       = (agent.x, agent.y)
            freshness = world.food.freshness_at(pos)
            gain      = world.food.consume_food(world.map.biome_map, pos)
            if gain > 0:
                item = {"type": config.OBJECT_TYPE_FOOD, "value": gain}
                if config.ENABLE_FOOD_ROT:
                    item["freshness"] = freshness
                agent.inventory.append(item)
                get_logger().debug(world.tick, f"Agent #{agent.id} ramasse nourriture (+{gain}) | inventaire={agent.inventory}")
        return

    if action == ACTION_EAT:
        if not config.ENABLE_INVENTORY:
            return
        if agent.inventory:
            item = agent.inventory.pop(0)
            if item["type"] == config.OBJECT_TYPE_FOOD:
                value = apply_food_effects(
                    agent, world,
                    item.get("value", 0),
                    item.get("freshness", 1.0),
                )
                get_logger().debug(world.tick, f"Agent #{agent.id} mange depuis poche ({item['type']} +{value:.1f}) | énergie={agent.energy:.1f}")
        return

    if action not in ACTION_TO_DELTA:
        return

    dx, dy = ACTION_TO_DELTA[action]
    new_x  = agent.x + dx
    new_y  = agent.y + dy

    if getattr(world, "infinite", False):
        pass  # pas de bords à vérifier
    elif config.TOROIDAL_WORLD:
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
        weather_extra = config.WEATHER_MOVE_COST.get(world.weather, 0.0)
        cost = (config.MOVE_COST - config.IDLE_COST) + weather_extra
        if config.ENABLE_FATIGUE and agent.fatigue >= config.EXHAUSTION_THRESHOLD:
            cost *= config.EXHAUSTION_COST_MULT
        agent.energy -= cost
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
        rate = config.THIRST_RATE
    elif world.is_night():
        rate = config.THIRST_RATE_NIGHT
    elif biome == config.BIOME_DESERT:
        rate = config.THIRST_RATE_DESERT
    else:
        rate = config.THIRST_RATE

    agent.thirst = max(0, agent.thirst - rate)
    if agent.thirst <= 0:
        get_logger().warning(world.tick, f"Agent #{agent.id} soif critique — dégâts énergie ({agent.energy:.1f} → {agent.energy - config.THIRST_DAMAGE:.1f})")
        agent.energy -= config.THIRST_DAMAGE
        if agent.energy <= 0:
            agent.alive = False


def _update_fatigue(agent, world):
    """Fait évoluer la fatigue : elle monte en agissant (surtout en marchant),
    stagne en idle et baisse en dormant. Appelée une fois par tick depuis
    update_agent_life(), après que la policy a choisi l'action du tick."""
    if agent.pending_action == ACTION_SLEEP:
        agent.fatigue = max(0.0, agent.fatigue - config.FATIGUE_REST_RECOVERY)
        return

    dx, dy = ACTION_TO_DELTA.get(agent.pending_action, (0, 0))
    gain = config.FATIGUE_PER_TICK
    if dx != 0 or dy != 0:
        gain += config.FATIGUE_MOVE_EXTRA
    elif agent.pending_action == ACTION_IDLE:
        gain -= config.FATIGUE_IDLE_RECOVERY
    agent.fatigue = max(0.0, min(config.MAX_FATIGUE, agent.fatigue + gain))


def _age_inventory(agent):
    """La nourriture transportée vieillit : sa fraîcheur baisse à chaque tick
    (plus lentement qu'au sol) jusqu'à FOOD_MIN_FRESHNESS."""
    for item in agent.inventory:
        if item.get("type") != config.OBJECT_TYPE_FOOD:
            continue
        freshness = item.get("freshness", 1.0)
        item["freshness"] = max(
            config.FOOD_MIN_FRESHNESS,
            freshness - config.FOOD_INVENTORY_ROT_RATE,
        )


def apply_food_effects(agent, world, base_value, freshness):
    """Applique les effets d'un repas : énergie gagnée (valeur × fraîcheur)
    puis risque de tomber malade si la nourriture était pourrie.

    Centralisé ici pour que manger au sol (collision) et manger depuis
    l'inventaire appliquent exactement le même malus. Retourne l'énergie
    effectivement gagnée."""
    value = base_value
    if config.ENABLE_FOOD_ROT:
        value *= freshness
    agent.energy = min(config.MAX_ENERGY, agent.energy + value)

    if (config.ENABLE_SICKNESS and config.ENABLE_FOOD_ROT
            and freshness <= config.FOOD_SICKNESS_THRESHOLD
            and random.random() < config.SICKNESS_CHANCE):
        agent.sick_ticks = max(agent.sick_ticks, config.SICKNESS_DURATION)
        get_logger().warning(
            world.tick,
            f"🤢 Agent #{agent.id} tombe malade après avoir mangé de la "
            f"nourriture pourrie (fraîcheur {freshness:.2f})",
        )
    return value


def update_agent_life(agent, world):
    log = get_logger()
    agent.age += 1

    if config.ENABLE_FATIGUE:
        _update_fatigue(agent, world)

    sleeping = config.ENABLE_FATIGUE and agent.pending_action == ACTION_SLEEP
    if sleeping:
        # Dormir : pas de coût de repos, l'agent récupère de l'énergie
        # (davantage la nuit — c'est le moment naturel pour dormir).
        mult = config.SLEEP_NIGHT_MULT if world.is_night() else 1.0
        agent.energy = min(config.MAX_ENERGY, agent.energy + config.SLEEP_ENERGY_REGEN * mult)
    else:
        idle_cost = config.NIGHT_IDLE_COST if world.is_night() else config.IDLE_COST
        if config.ENABLE_FATIGUE and agent.fatigue >= config.EXHAUSTION_THRESHOLD:
            idle_cost *= config.EXHAUSTION_COST_MULT
        agent.energy -= idle_cost + (agent.age / config.MAX_AGE) * 0.1

    # Maladie : drain d'énergie tant qu'elle dure.
    if config.ENABLE_SICKNESS and agent.sick_ticks > 0:
        agent.sick_ticks -= 1
        agent.energy -= config.SICKNESS_ENERGY_DRAIN
        if agent.sick_ticks == 0:
            log.info(world.tick, f"Agent #{agent.id} guérit de sa maladie")

    if config.ENABLE_AGE_DEATH and agent.age >= config.MAX_AGE:
        log.info(world.tick, f"Agent #{agent.id} mort de vieillesse | âge={agent.age} gén={agent.generation}")
        agent.alive = False
        return
    if agent.energy <= 0:
        if config.ENABLE_SICKNESS and agent.sick_ticks > 0:
            log.info(world.tick, f"Agent #{agent.id} mort de maladie | âge={agent.age} gén={agent.generation}")
        else:
            log.info(world.tick, f"Agent #{agent.id} mort d'épuisement | âge={agent.age} gén={agent.generation}")
        agent.alive = False
        return
    _update_thirst(agent, world)
    if config.ENABLE_FOOD_ROT:
        _age_inventory(agent)


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
