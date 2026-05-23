import random
from dataclasses import dataclass, field
from typing import List
from logger import get_logger
from policy_registry import distribute_policies

from config import (
    WORLD_WIDTH,
    WORLD_HEIGHT,
    INITIAL_AGENT_COUNT,
    MAX_ENERGY,
    DAY_DURATION,
    NIGHT_RATIO,
    SEASON_DURATION,
    YEAR_DURATION,
    SEASON_SPRING,
    SEASON_SUMMER,
    SEASON_AUTUMN,
    SEASON_WINTER,
    WEATHER_FROST,
    WEATHER_CLEAR,
    WEATHER_RAIN,
    WEATHER_STORM,
    WEATHER_DROUGHT,
    WEATHER_MOISTURE_DELTA,
    WEATHER_CHANGE_PROB,
    SEASON_WEATHER_PROBS,
    SOIL_MOISTURE_MIN,
    SOIL_MOISTURE_MAX,
    SOIL_MOISTURE_INIT,
    BIOME_WATER,
    BIOME_PRAIRIE,
    MIGRATION_VOTE_THRESHOLD,
    MIGRATION_COOLDOWN,
    MAX_THIRST,
)
from agent import Agent, apply_free_action, apply_timed_action, think, update_agent_life
from map import GameMap
from food import FoodSystem


# -----------------------------
# WORLD
# -----------------------------
@dataclass
class World:
    width: int
    height: int
    agents: List[Agent] = field(default_factory=list)
    tick: int = 0
    death_count: int = 0
    map: GameMap = None
    food: FoodSystem = None
    _next_id: int = field(default=0, repr=False)
    weather: int = WEATHER_CLEAR
    soil_moisture: float = SOIL_MOISTURE_INIT
    migration_count: int = 0
    last_migration_tick: int = -9999

    def next_id(self):
        self._next_id += 1
        return self._next_id

    def time_of_day(self):
        return (self.tick % DAY_DURATION) / DAY_DURATION

    def is_night(self):
        import config
        if not config.ENABLE_DAY_NIGHT:
            return False
        return self.time_of_day() >= (1 - NIGHT_RATIO)

    def current_season(self):
        import config
        if not config.ENABLE_SEASONS:
            return SEASON_SPRING   # saison fixe
        idx = (self.tick % YEAR_DURATION) // SEASON_DURATION
        return [SEASON_SPRING, SEASON_SUMMER, SEASON_AUTUMN, SEASON_WINTER][idx]

    def season_progress(self):
        return (self.tick % SEASON_DURATION) / SEASON_DURATION


# -----------------------------
# REWARD (signal d'apprentissage)
# -----------------------------
def compute_reward(agent, prev_energy, prev_thirst):
    """
    Calcule la récompense après exécution des actions du tick.
    Défini ici (dans l'environnement) car c'est l'environnement
    qui décide ce qui est bon ou mauvais, pas l'agent.
    """
    if not agent.alive:
        return -10.0

    reward = 0.0
    reward += (agent.energy - prev_energy) * 0.1
    reward += (agent.thirst - prev_thirst) * 0.05

    if agent.energy < 20:
        reward -= 0.5
    if agent.thirst < 20:
        reward -= 0.3

    return reward


# -----------------------------
# MÉTÉO
# -----------------------------
def update_weather(world):
    old_weather = world.weather
    if world.tick % DAY_DURATION == 0:
        if random.random() < WEATHER_CHANGE_PROB:
            season   = world.current_season()
            weathers = [WEATHER_CLEAR, WEATHER_RAIN, WEATHER_STORM, WEATHER_DROUGHT, WEATHER_FROST]
            world.weather = random.choices(weathers, weights=SEASON_WEATHER_PROBS[season], k=1)[0]

        if old_weather == WEATHER_STORM   and world.weather == WEATHER_STORM:
            _expand_water(world)
        if old_weather == WEATHER_DROUGHT and world.weather == WEATHER_DROUGHT:
            _shrink_water(world)

    delta = WEATHER_MOISTURE_DELTA[world.weather]
    world.soil_moisture = max(SOIL_MOISTURE_MIN, min(SOIL_MOISTURE_MAX, world.soil_moisture + delta))


def _shrink_water(world):
    to_land = {
        (x, y)
        for (x, y), biome in world.map.biome_map.items()
        if biome == BIOME_WATER
        and any(
            world.map.biome_map.get((x + dx, y + dy)) != BIOME_WATER
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]
            if 0 <= x + dx < world.width and 0 <= y + dy < world.height
        )
    }
    world.map.update_biomes(to_land, BIOME_PRAIRIE)
    for pos in to_land:
        world.food.clear_position(pos)


def _expand_water(world):
    log = get_logger()
    new_water = {
        (x + dx, y + dy)
        for (x, y), biome in world.map.biome_map.items()
        if biome == BIOME_WATER
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]
        if 0 <= x + dx < world.width and 0 <= y + dy < world.height
        and world.map.biome_map.get((x + dx, y + dy)) != BIOME_WATER
    }
    world.map.update_biomes(new_water, BIOME_WATER)
    for pos in new_water:
        world.food.clear_position(pos)
    for agent in world.agents:
        if not world.map.is_walkable(agent.x, agent.y):
            agent.alive = False
            log.warning(world.tick, f"Agent #{agent.id} noyé par expansion de l'eau en ({agent.x},{agent.y})")


# -----------------------------
# INIT
# -----------------------------
def _new_map_and_food(width, height):
    game_map = GameMap(width=width, height=height)
    game_map.initialize()
    food = FoodSystem(width=width, height=height)
    food.initialize(game_map.biome_map)
    return game_map, food


def initialize_world():
    import config
    log = get_logger()
    world = World(width=WORLD_WIDTH, height=WORLD_HEIGHT)
    world.map, world.food = _new_map_and_food(world.width, world.height)

    if not config.ENABLE_BIOMES:
        # Remplace tout par prairie, retire l'eau
        from config import BIOME_PRAIRIE
        world.map.biome_map = {
            (x, y): BIOME_PRAIRIE
            for x in range(world.width)
            for y in range(world.height)
        }
        world.food.initialize(world.map.biome_map)

    walkable = [
        (x, y)
        for x in range(world.width)
        for y in range(world.height)
        if world.map.is_walkable(x, y)
    ]
    random.shuffle(walkable)

    for x, y in walkable[:INITIAL_AGENT_COUNT]:
        world.agents.append(Agent(
            id=world.next_id(),
            x=x, y=y,
            energy=MAX_ENERGY / 2,
            thirst=MAX_THIRST / 2,
            generation=0,
            born_tick=0,
        ))


    log.info(0, f"Monde initialisé — {len(world.agents)} agents — biomes={'ON' if config.ENABLE_BIOMES else 'OFF'}")
    
    from policy_registry import distribute_policies
    distribute_policies(world.agents, config.POLICY_DISTRIBUTION)
    return world


# -----------------------------
# COLLISIONS
# -----------------------------
def _resolve_collisions(world):
    agents = list(world.agents)
    random.shuffle(agents)
    eaten = set()
    for agent in agents:
        if not agent.alive:
            continue
        pos = (agent.x, agent.y)
        if pos in eaten:
            continue
        gain = world.food.consume_food(world.map.biome_map, pos)
        if gain > 0:
            agent.energy = min(MAX_ENERGY, agent.energy + gain)
            eaten.add(pos)


def _remove_dead_agents(world):
    log = get_logger()
    dead = [a for a in world.agents if not a.alive]
    for a in dead:
        log.info(world.tick, f"Agent #{a.id} mort | énergie={a.energy:.1f} soif={a.thirst:.1f} âge={a.age} gén={a.generation}")
    world.death_count += len(dead)
    world.agents = [a for a in world.agents if a.alive]


# -----------------------------
# REPRODUCTION
# -----------------------------
def _reproduce(agent, world, policy):
    """
    La décision de se reproduire est déléguée à policy.
    La mécanique (trouver une case libre, créer le bébé) reste ici.
    """
    if not policy.decide_reproduce(agent, world):
        return None

    occupied  = {(a.x, a.y) for a in world.agents}
    neighbors = [
        (agent.x + dx, agent.y + dy)
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]
        if 0 <= agent.x + dx < world.width
        and 0 <= agent.y + dy < world.height
        and (agent.x + dx, agent.y + dy) not in occupied
        and world.map.is_walkable(agent.x + dx, agent.y + dy)
    ]
    if not neighbors:
        return None

    x, y          = random.choice(neighbors)
    agent.energy -= 40
    log = get_logger()
    log.info(world.tick, f"Agent #{agent.id} se reproduit → bébé gén.{agent.generation+1} en ({x},{y})")
    return Agent(
        id=-1,
        x=x, y=y,
        generation=agent.generation + 1,
        born_tick=world.tick,
        energy=40,
        thirst=50,
        policy=agent.policy
    )


# -----------------------------
# MIGRATION
# -----------------------------
def _reachable_land(world, sx, sy):
    visited, stack = set(), [(sx, sy)]
    while stack:
        x, y = stack.pop()
        if (x, y) in visited:
            continue
        if not (0 <= x < world.width and 0 <= y < world.height):
            continue
        if not world.map.is_walkable(x, y):
            continue
        visited.add((x, y))
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            stack.append((x + dx, y + dy))
    return visited


def _check_migration(world):
    agents = [a for a in world.agents if a.alive]
    if not agents or len(agents) > 5:
        return False
    if world.tick - world.last_migration_tick < MIGRATION_COOLDOWN:
        return False

    votes = sum(1 for a in agents if a.vote_migrate)
    if votes / len(agents) < MIGRATION_VOTE_THRESHOLD:
        return False

    total_land = sum(1 for b in world.map.biome_map.values() if b != BIOME_WATER)
    min_land   = max(1, int(total_land * 0.10))
    land_cache = {}

    def get_land(a):
        key = (a.x, a.y)
        if key not in land_cache:
            land_cache[key] = _reachable_land(world, a.x, a.y)
        return land_cache[key]

    mobile = [a for a in agents if len(get_land(a)) >= min_land]
    if not mobile:
        return False

    new_map, new_food = _new_map_and_food(world.width, world.height)
    walkable = [
        (x, y)
        for x in range(world.width)
        for y in range(world.height)
        if new_map.is_walkable(x, y)
    ]
    random.shuffle(walkable)

    occupied = set()
    for agent in mobile:
        available = [p for p in walkable if p not in occupied]
        if not available:
            agent.alive = False
            continue
        agent.x, agent.y = available[0]
        occupied.add(available[0])

    world.map             = new_map
    world.food            = new_food
    world.soil_moisture   = SOIL_MOISTURE_INIT
    world.weather         = WEATHER_CLEAR
    world.migration_count += 1
    world.last_migration_tick = world.tick
    log = get_logger()
    log.info(world.tick, f"MIGRATION #{world.migration_count} — {len(mobile)} agents ont migré")
    return True


# -----------------------------
# BOUCLE PRINCIPALE
# -----------------------------
def world_phase(world, policy):
    import config  # lecture dynamique des flags (modifiés par config_gui)

    # 1. météo
    if config.ENABLE_WEATHER and config.ENABLE_BIOMES:
        update_weather(world)

    # 2. perception + décision
    for agent in world.agents:
        if agent.alive:
            think(agent, world, policy)

    # 3. actions gratuites
    for agent in world.agents:
        if agent.alive:
            for action in agent.free_actions:
                apply_free_action(agent, action)

    # 4. migration
    if config.ENABLE_MIGRATION:
        _check_migration(world)

    # 5. action principale
    for agent in world.agents:
        if agent.alive:
            apply_timed_action(agent, world, agent.pending_action)

    # 6. vieillissement + reproduction
    newborns = []
    for agent in world.agents:
        if not agent.alive:
            continue
        update_agent_life(agent, world)
        if agent.alive and config.ENABLE_REPRODUCTION:
            baby = _reproduce(agent, world, policy)
            if baby:
                newborns.append(baby)

    # 7. récompenses
    for agent in world.agents:
        if agent.alive:
            agent.last_reward = compute_reward(agent, agent._prev_energy, agent._prev_thirst)

    # 8. nettoyage + naissances
    _resolve_collisions(world)
    _remove_dead_agents(world)

    log = get_logger()
    n = len(world.agents)
    if n <= 5:
        log.warning(world.tick, f"Population critique : {n} agents restants")

    for baby in newborns:
        baby.id = world.next_id()
    world.agents.extend(newborns)

    # 9. croissance nourriture
    world.food.grow_food(world.map.biome_map, world.soil_moisture)
    world.tick += 1
