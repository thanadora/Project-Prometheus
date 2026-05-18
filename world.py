import random
from dataclasses import dataclass, field
from typing import List

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
    BIOME_DESERT,
    BIOME_PRAIRIE,
    BIOME_FOREST,
    MIGRATION_VOTE_THRESHOLD,
    MIGRATION_DISTRESS_ENERGY,
    MIGRATION_DISTRESS_THIRST,
    MIGRATION_COOLDOWN,
    MAX_AGE



)

from entities import Agent
from food import FoodSystem
from agent import apply_action, think, update_agent_life, reproduce

# -----------------------------
# WORLD STRUCTURE
# -----------------------------
@dataclass
class World:
    width: int
    height: int
    agents: List[Agent] = field(default_factory=list)
    tick: int = 0
    death_count: int = 0
    food: FoodSystem = None
    _next_id: int = field(default=0, repr=False)
    weather: int = WEATHER_CLEAR
    soil_moisture: float = SOIL_MOISTURE_INIT
    migration_count: int = 0          # nombre de migrations effectuées
    last_migration_tick: int = -9999  # tick de la dernière migration

    def next_id(self):
        self._next_id += 1
        return self._next_id

    def time_of_day(self):
        return (self.tick % DAY_DURATION) / DAY_DURATION

    def is_night(self):
        return self.time_of_day() >= (1 - NIGHT_RATIO)

    def current_season(self):
        season_index = (self.tick % YEAR_DURATION) // SEASON_DURATION
        return [SEASON_SPRING, SEASON_SUMMER, SEASON_AUTUMN, SEASON_WINTER][season_index]

    def season_progress(self):
        return (self.tick % SEASON_DURATION) / SEASON_DURATION

# -----------------------------
# MÉTÉO
# -----------------------------
def pick_weather(season):
    weathers = [WEATHER_CLEAR, WEATHER_RAIN, WEATHER_STORM, WEATHER_DROUGHT]
    probs = SEASON_WEATHER_PROBS[season]
    return random.choices(weathers, weights=probs, k=1)[0]

def update_weather(world):
    old_weather = world.weather
    if world.tick % DAY_DURATION == 0:
        if random.random() < WEATHER_CHANGE_PROB:
            season = world.current_season()
            weathers = [
                WEATHER_CLEAR,
                WEATHER_RAIN,
                WEATHER_STORM,
                WEATHER_DROUGHT,
                WEATHER_FROST,
            ]
            probs = SEASON_WEATHER_PROBS[season]

            world.weather = random.choices(
                weathers,
                weights=probs,
                k=1
            )[0]

        if old_weather == WEATHER_STORM  and world.weather == WEATHER_STORM:
            expand_water(world)
        if old_weather == WEATHER_DROUGHT and world.weather == WEATHER_DROUGHT:
            shrink_water(world)

    delta = WEATHER_MOISTURE_DELTA[world.weather]

    world.soil_moisture = max(
        SOIL_MOISTURE_MIN,
        min(SOIL_MOISTURE_MAX, world.soil_moisture + delta)
    )

        
def shrink_water(world):
    to_land = set()

    for (x, y), biome in world.food.biome_map.items():

        if biome != BIOME_WATER:
            continue

        # si la case est en bordure de terre → elle sèche
        for dx, dy in [(-1,0), (1,0), (0,-1), (0,1)]:
            nx, ny = x + dx, y + dy

            if 0 <= nx < world.width and 0 <= ny < world.height:

                if world.food.biome_map.get((nx, ny)) != BIOME_WATER:
                    to_land.add((x, y))
                    break

    world.food.update_biomes(to_land, BIOME_PRAIRIE)

    for pos in to_land:
        world.food.food_map[pos] = 0


def expand_water(world):
    new_water = set()
    for (x, y), biome in world.food.biome_map.items():

        if biome != BIOME_WATER:
            continue

        for dx, dy in [(-1,0), (1,0), (0,-1), (0,1)]:
            nx, ny = x + dx, y + dy

            if 0 <= nx < world.width and 0 <= ny < world.height:

                npos = (nx, ny)

                if world.food.biome_map.get(npos) != BIOME_WATER:
                    new_water.add(npos)

    world.food.update_biomes(new_water, BIOME_WATER)

    # mort des agents
    for agent in world.agents:
        if not world.food.is_walkable(agent.x, agent.y):
            agent.alive = False


# -----------------------------
# UTILS
# -----------------------------
def random_position(world, occupied=None):
    if not occupied:
        return (
            random.randint(0, world.width - 1),
            random.randint(0, world.height - 1),
        )

    all_positions = [
        (x, y)
        for x in range(world.width)
        for y in range(world.height)
        if (x, y) not in occupied
    ]

    if not all_positions:
        return None

    return random.choice(all_positions)

# -----------------------------
# INIT WORLD
# -----------------------------
def initialize_world():
    world = World(width=WORLD_WIDTH, height=WORLD_HEIGHT)

    world.food = FoodSystem(world.width, world.height)
    world.food.initialize()

    occupied = set()
    walkable = [
        (x, y)
        for x in range(world.width)
        for y in range(world.height)
        if world.food.is_walkable(x, y)
    ]

    for _ in range(INITIAL_AGENT_COUNT):
        available = [pos for pos in walkable if pos not in occupied]
        if not available:
            break
        x, y = random.choice(available)
        occupied.add((x, y))
        world.agents.append(
            Agent(
                id=world.next_id(),
                x=x,
                y=y,
                energy=MAX_ENERGY / 2,
                generation=0,
                born_tick=0,
            )
        )

    return world

# -----------------------------
# COLLISIONS (AGENT <-> FOOD)
# -----------------------------
def resolve_collisions(world):
    agents = list(world.agents)
    random.shuffle(agents)

    already_eaten = set()

    for agent in agents:
        if not agent.alive:
            continue
        pos = (agent.x, agent.y)
        if pos in already_eaten:
            continue
        gain = world.food.consume_food(pos)
        if gain > 0:
            agent.energy = min(MAX_ENERGY, agent.energy + gain)
            already_eaten.add(pos)

# -----------------------------
# CLEAN DEAD AGENTS
# -----------------------------
def remove_dead_agents(world):
    alive_agents = [a for a in world.agents if a.alive]
    world.death_count += len(world.agents) - len(alive_agents)
    world.agents = alive_agents

# -----------------------------
# MIGRATION
# -----------------------------
def _reachable_land(world, start_x, start_y):
    """Flood-fill : retourne l'ensemble des cases terrestres accessibles depuis (start_x, start_y)."""
    visited = set()
    stack = [(start_x, start_y)]
    while stack:
        x, y = stack.pop()
        if (x, y) in visited:
            continue
        if not (0 <= x < world.width and 0 <= y < world.height):
            continue
        if not world.food.is_walkable(x, y):
            continue
        visited.add((x, y))
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            stack.append((x + dx, y + dy))
    return visited


def check_migration(world):
    """
    Vérifie si les conditions de migration sont remplies.
    Retourne True et déclenche la migration si c'est le cas.
    """
    
    agents = [a for a in world.agents if a.alive]
    if not agents:
        return False
    if len(agents) > 5:
        return False

    # Cooldown : pas deux migrations trop rapprochées
    if world.tick - world.last_migration_tick < MIGRATION_COOLDOWN:
        return False

    # --- Vote individuel ---
    # Un agent vote "en détresse" s'il manque d'énergie OU de thirst
    votes = sum(
        1 for a in agents
        if a.energy < MIGRATION_DISTRESS_ENERGY or a.thirst < MIGRATION_DISTRESS_THIRST or a.age < MAX_AGE - 30
    )
    

    ratio = votes / len(agents)

    if ratio < MIGRATION_VOTE_THRESHOLD:
        return False

    # --- Détection des agents bloqués par l'eau ---
    # On calcule la zone accessible pour chaque agent ; ceux sur une île restent.
    land_cache = {}  # (x,y) -> frozenset des cases accessibles

    def get_land(x, y):
        if (x, y) not in land_cache:
            land_cache[(x, y)] = _reachable_land(world, x, y)
        return land_cache[(x, y)]

    # Un agent est "mobile" si sa zone terrestre est assez grande (> 10 % de la surface totale)
    total_land = sum(
        1 for pos, b in world.food.biome_map.items() if b != BIOME_WATER
    )
    min_land = max(1, int(total_land * 0.10))

    mobile_agents = [a for a in agents if len(get_land(a.x, a.y)) >= min_land]
    stranded_agents = [a for a in agents if len(get_land(a.x, a.y)) < min_land]

    if not mobile_agents:
        return False  # tout le monde est bloqué, impossible de migrer

    # --- Déclenchement : génération d'une nouvelle map ---
    new_food = FoodSystem(world.width, world.height)
    new_food.initialize()

    # Nouvelle liste de cases marchables
    walkable = [
        (x, y)
        for x in range(world.width)
        for y in range(world.height)
        if new_food.is_walkable(x, y)
    ]
    random.shuffle(walkable)

    # On place les agents mobiles sur la nouvelle map
    occupied = set()
    for agent in mobile_agents:
        available = [pos for pos in walkable if pos not in occupied]
        if not available:
            agent.alive = False
            continue
        pos = available[0]
        agent.x, agent.y = pos
        occupied.add(pos)

    # Les agents bloqués restent (et mourront probablement)
    # On ne touche pas à leur position

    # Mise à jour du monde
    world.food = new_food
    world.soil_moisture = SOIL_MOISTURE_INIT
    world.weather = WEATHER_CLEAR
    world.migration_count += 1
    world.last_migration_tick = world.tick

    return True


# -----------------------------
# MAIN SIMULATION STEP
# -----------------------------
def world_phase(world):
    # 0. migration ?
    check_migration(world)

    # 1. météo
    update_weather(world)

    # 2. les agents pensent et préparent leur action
    for agent in world.agents:
        if not agent.alive:
            continue
        think(agent, world)

    # 3. les agents bougent
    for agent in world.agents:
        if not agent.alive:
            continue
        apply_action(agent, world, agent.pending_action)

    # 4. vieillissement et reproduction après le mouvement
    newborns = []
    for agent in world.agents:
        if not agent.alive:
            continue
        update_agent_life(agent, world)
        if not agent.alive:
            continue
        baby = reproduce(agent, world)
        if baby is not None:
            newborns.append(baby)

    # 5. interactions
    resolve_collisions(world)
    remove_dead_agents(world)

    # 6. ajout des bébés
    for baby in newborns:
        baby.id = world.next_id()
    world.agents.extend(newborns)

    # 7. nourriture
    world.food.grow_food(world.soil_moisture)
    world.tick += 1