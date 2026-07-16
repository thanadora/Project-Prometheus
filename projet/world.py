"""
world.py — Définition du monde et boucle principale (world_phase).

Les logiques métier sont déléguées à des modules dédiés :
  weather.py      → météo et humidité du sol
  migration.py    → vote et migration collective
  reproduction.py → naissance de nouveaux agents
"""

import random
from dataclasses import dataclass, field
from typing import List
from logger import get_logger

import config
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
    WEATHER_CLEAR,
    BIOME_WATER,
    BIOME_PRAIRIE,
    MAX_THIRST,
    SOIL_MOISTURE_INIT,
    FOOD_GROWTH_RADIUS,
    CHUNK_UNLOAD_DISTANCE,
    CHUNK_UNLOAD_INTERVAL,
)
from agent import Agent, think, apply_free_action, apply_timed_action, update_agent_life
from map import GameMap
from food import FoodSystem
from weather import update_weather
from migration import check_migration
from reproduction import reproduce
from policy_registry import distribute_policies


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
    _land_cache: dict = field(default_factory=dict, repr=False)
    _land_cache_valid: bool = True
    infinite: bool = False

    def next_id(self):
        self._next_id += 1
        return self._next_id

    def time_of_day(self):
        return (self.tick % DAY_DURATION) / DAY_DURATION

    def is_night(self):
        if not config.ENABLE_DAY_NIGHT:
            return False
        return self.time_of_day() >= (1 - NIGHT_RATIO)

    def current_season(self):
        if not config.ENABLE_SEASONS:
            return SEASON_SPRING
        idx = (self.tick % YEAR_DURATION) // SEASON_DURATION
        return [SEASON_SPRING, SEASON_SUMMER, SEASON_AUTUMN, SEASON_WINTER][idx]

    def season_progress(self):
        return (self.tick % SEASON_DURATION) / SEASON_DURATION


# -----------------------------
# REWARD
# -----------------------------
def compute_reward(agent, prev_energy, prev_thirst):
    if not agent.alive:
        return -10.0
    reward  = (agent.energy - prev_energy) * 0.1
    reward += (agent.thirst - prev_thirst) * 0.05
    if agent.energy < 20:
        reward -= 0.5
    if agent.thirst < 20:
        reward -= 0.3
    return reward


# -----------------------------
# INIT
# -----------------------------
def _new_map_and_food(width, height, infinite=False):
    game_map = GameMap(width=width, height=height, infinite=infinite)
    game_map.initialize()
    food = FoodSystem(width=width, height=height)
    if infinite:
        food.initialize(game_map.biome_map, infinite=True, game_map=game_map,
                         center=(0, 0), radius=FOOD_GROWTH_RADIUS * 2)
    else:
        food.initialize(game_map.biome_map)
    return game_map, food


def _find_walkable_near(game_map, center, min_count):
    """Cherche des cases praticables en élargissant un anneau autour de `center`,
    utilisé au lancement du mode infini pour trouver où poser les premiers agents
    sans avoir à générer toute une carte."""
    cx, cy = center
    found  = []
    radius = 0
    max_radius = 300
    while len(found) < min_count and radius < max_radius:
        radius += 5
        found = [
            (x, y)
            for x in range(cx - radius, cx + radius + 1)
            for y in range(cy - radius, cy + radius + 1)
            if game_map.is_walkable(x, y)
        ]
    random.shuffle(found)
    return found


def initialize_world():
    log      = get_logger()
    infinite = config.INFINITE_WORLD
    world    = World(width=WORLD_WIDTH, height=WORLD_HEIGHT, infinite=infinite)
    world.map, world.food = _new_map_and_food(world.width, world.height, infinite)

    if not config.ENABLE_BIOMES:
        if infinite:
            log.warning(0, "Biomes désactivés en mode monde infini — biomes réactivés (nécessaires à la génération à la demande)")
        else:
            world.map.biome_map = {
                (x, y): BIOME_PRAIRIE
                for x in range(world.width)
                for y in range(world.height)
            }
            world.food.initialize(world.map.biome_map)

    if infinite:
        # Un seul groupe d'agents au centre — libre de s'étendre ensuite,
        # comme au démarrage d'un serveur Minecraft.
        walkable = _find_walkable_near(world.map, (0, 0), INITIAL_AGENT_COUNT * 4)
    else:
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

    log.info(0, f"Monde initialisé — {len(world.agents)} agents — biomes={'ON' if config.ENABLE_BIOMES else 'OFF'} — infini={'ON' if infinite else 'OFF'}")
    distribute_policies(world.agents, config.POLICY_DISTRIBUTION)
    return world


# -----------------------------
# COLLISIONS & NETTOYAGE
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


def _active_cells(world):
    """Cases autour de chaque agent vivant où la nourriture doit pousser —
    équivalent des "chunks chargés" autour des joueurs sur un serveur Minecraft."""
    r     = FOOD_GROWTH_RADIUS
    r_sq  = r * r
    cells = set()
    for agent in world.agents:
        if not agent.alive:
            continue
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                if dx * dx + dy * dy > r_sq:
                    continue
                pos = (agent.x + dx, agent.y + dy)
                world.map.get_biome(*pos)  # génère/charge la case au besoin
                cells.add(pos)
    return cells


def _unload_far_chunks(world):
    """Libère de la mémoire les cases de biome/nourriture trop loin de tout
    agent vivant. Elles seront régénérées à l'identique (même seed) si un
    agent y repasse un jour."""
    if world.tick % CHUNK_UNLOAD_INTERVAL != 0:
        return

    agents_pos = [(a.x, a.y) for a in world.agents if a.alive]
    if not agents_pos:
        return
    d = CHUNK_UNLOAD_DISTANCE

    def near_any_agent(pos):
        px, py = pos
        for ax, ay in agents_pos:
            if abs(px - ax) <= d and abs(py - ay) <= d:
                return True
        return False

    world.map.biome_map = {p: b for p, b in world.map.biome_map.items() if near_any_agent(p)}
    world.food.food_map = {p: v for p, v in world.food.food_map.items() if near_any_agent(p)}
    world.food.food_positions &= set(world.food.food_map.keys())
    world._land_cache = {}
    world._land_cache_valid = True


def _remove_dead_agents(world):
    log  = get_logger()
    dead = [a for a in world.agents if not a.alive]
    for a in dead:
        log.info(world.tick, f"Agent #{a.id} mort | énergie={a.energy:.1f} soif={a.thirst:.1f} âge={a.age} gén={a.generation}")
    world.death_count += len(dead)
    world.agents = [a for a in world.agents if a.alive]


# -----------------------------
# BOUCLE PRINCIPALE
# -----------------------------
def world_phase(world, policy):
    # 1. Météo
    if config.ENABLE_WEATHER and config.ENABLE_BIOMES:
        update_weather(world)

    # 2. Boucle 1 : perception + décision + actions gratuites
    # Tout le monde perçoit le même monde avant que quiconque agisse.
    # free_actions (vote_migrate) n'affecte que l'agent lui-même,
    # donc les fusionner avec think() ne change pas le comportement des autres.
    for agent in world.agents:
        if not agent.alive:
            continue
        think(agent, world, policy)
        for action in agent.free_actions:
            apply_free_action(agent, action)

    # 3. Migration — après les votes, avant les actions physiques
    # Inutile en monde infini : sans bords, un groupe en détresse peut simplement
    # continuer à se déplacer plutôt que d'être téléporté ailleurs.
    if config.ENABLE_MIGRATION and not world.infinite:
        check_migration(world)

    # 4. Boucle 2 : action principale + vieillissement + reproduction + récompense
    newborns = []
    for agent in world.agents:
        if not agent.alive:
            continue
        apply_timed_action(agent, world, agent.pending_action)
        if not agent.alive:
            continue
        update_agent_life(agent, world)
        if agent.alive and config.ENABLE_REPRODUCTION:
            baby = reproduce(agent, world, policy)
            if baby:
                newborns.append(baby)
        if agent.alive:
            agent.last_reward = compute_reward(agent, agent._prev_energy, agent._prev_thirst)
    # 5. Nettoyage + naissances
    _resolve_collisions(world)
    _remove_dead_agents(world)

    log = get_logger()
    if len(world.agents) <= 5:
        log.warning(world.tick, f"Population critique : {len(world.agents)} agents restants")

    for baby in newborns:
        baby.id = world.next_id()
    world.agents.extend(newborns)

    # 6. Croissance nourriture
    if world.infinite:
        cells = _active_cells(world)
        world.food.grow_food(world.map.biome_map, world.soil_moisture, cells=cells)
        _unload_far_chunks(world)
    else:
        world.food.grow_food(world.map.biome_map, world.soil_moisture)
    world.tick += 1