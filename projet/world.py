"""
world.py — Définition du monde et boucle principale (world_phase).

Les logiques métier sont déléguées à des modules dédiés :
  weather.py      → météo et humidité du sol
  fire.py         → feux de forêt
  flood.py        → inondations temporaires
  migration.py    → vote et migration collective
  reproduction.py → naissance de nouveaux agents
"""

import random
from dataclasses import dataclass, field
from typing import List
from logger import get_logger

import config
from agent import (
    Agent, think, apply_free_action, apply_timed_action, update_agent_life,
    apply_food_effects,
)
from map import GameMap
from food import FoodSystem
from weather import update_weather
from migration import check_migration
from reproduction import reproduce
from policy_registry import distribute_policies
from fire import update_fires
from flood import update_floods


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
    weather: int = field(default_factory=lambda: config.WEATHER_CLEAR)
    soil_moisture: float = field(default_factory=lambda: config.SOIL_MOISTURE_INIT)
    migration_count: int = 0
    last_migration_tick: int = -9999
    _land_cache: dict = field(default_factory=dict, repr=False)
    _land_cache_valid: bool = True
    infinite: bool = False
    # Catastrophes en cours (voir fire.py / flood.py) :
    #   burning : {(x, y): ticks de combustion restants}
    #   burnt   : {(x, y): ticks de cendre fertile restants}
    #   flooded : {(x, y): ticks avant décrue}
    burning: dict = field(default_factory=dict)
    burnt: dict = field(default_factory=dict)
    flooded: dict = field(default_factory=dict)
    # Index spatial des agents pour la communication, reconstruit une fois
    # par tick (voir agent._agent_buckets).
    _agent_grid: dict = field(default_factory=dict, repr=False)
    _agent_grid_tick: int = field(default=-1, repr=False)
    # Cache des cases actives en monde infini (voir _active_cells).
    _cells_for_pos: dict = field(default_factory=dict, repr=False)
    _active_cells_cache: set = field(default_factory=set, repr=False)
    _active_cells_sig: frozenset = field(default=None, repr=False)

    def next_id(self):
        self._next_id += 1
        return self._next_id

    def time_of_day(self):
        return (self.tick % config.DAY_DURATION) / config.DAY_DURATION

    def is_night(self):
        if not config.ENABLE_DAY_NIGHT:
            return False
        return self.time_of_day() >= (1 - config.NIGHT_RATIO)

    def current_season(self):
        if not config.ENABLE_SEASONS:
            return config.SEASON_SPRING
        idx = (self.tick % config.YEAR_DURATION) // config.SEASON_DURATION
        return [config.SEASON_SPRING, config.SEASON_SUMMER,
                config.SEASON_AUTUMN, config.SEASON_WINTER][idx]

    def season_progress(self):
        return (self.tick % config.SEASON_DURATION) / config.SEASON_DURATION


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
    # Pas de pénalité dédiée pour la maladie : le drain d'énergie massif
    # qu'elle inflige est déjà capté par la variation d'énergie ci-dessus.
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
                         center=(0, 0), radius=config.FOOD_GROWTH_RADIUS * 2)
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
    world    = World(width=config.WORLD_WIDTH, height=config.WORLD_HEIGHT, infinite=infinite)
    world.map, world.food = _new_map_and_food(world.width, world.height, infinite)

    if not config.ENABLE_BIOMES:
        if infinite:
            log.warning(0, "Biomes désactivés en mode monde infini — biomes réactivés (nécessaires à la génération à la demande)")
        else:
            world.map.biome_map = {
                (x, y): config.BIOME_PRAIRIE
                for x in range(world.width)
                for y in range(world.height)
            }
            world.food.initialize(world.map.biome_map)

    if infinite:
        # Un seul groupe d'agents au centre — libre de s'étendre ensuite,
        # comme au démarrage d'un serveur Minecraft.
        walkable = _find_walkable_near(world.map, (0, 0), config.INITIAL_AGENT_COUNT * 4)
    else:
        walkable = [
            (x, y)
            for x in range(world.width)
            for y in range(world.height)
            if world.map.is_walkable(x, y)
        ]
        random.shuffle(walkable)

    for x, y in walkable[:config.INITIAL_AGENT_COUNT]:
        world.agents.append(Agent(
            id=world.next_id(),
            x=x, y=y,
            energy=config.MAX_ENERGY / 2,
            thirst=config.MAX_THIRST / 2,
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
        freshness = world.food.freshness_at(pos)
        gain = world.food.consume_food(world.map.biome_map, pos)
        if gain > 0:
            # Manger au sol applique les mêmes effets que depuis l'inventaire
            # (valeur × fraîcheur + risque de maladie si pourri).
            apply_food_effects(agent, world, gain, freshness)
            eaten.add(pos)


def _cells_around_position(world, x, y):
    """Disque de cases fertiles (biomes de FOOD_TYPES) autour d'une position.
    Sert au mode infini pour ne faire pousser la nourriture que là où des
    agents peuvent la voir, sans parcourir un monde sans bords. Les cases
    sont générées au besoin (get_biome), donc ce calcul est le seul endroit
    qui "charge" du terrain par tick — d'où le cache par position et les
    offsets de disque précalculés."""
    r          = config.FOOD_GROWTH_RADIUS
    food_types = config.FOOD_TYPES
    game_map   = world.map
    cells      = set()
    for dx, dy in _disk_offsets(r):
        pos = (x + dx, y + dy)
        if game_map.get_biome(*pos) in food_types:
            cells.add(pos)
    return frozenset(cells)


_disk_offsets_cache = {}


def _disk_offsets(radius):
    """Liste précalculée des décalages (dx, dy) d'un disque de rayon `radius`
    (mise en cache par rayon). Évite de refaire un double range + comparaison
    de distance pour chaque agent à chaque tick."""
    offsets = _disk_offsets_cache.get(radius)
    if offsets is None:
        offsets = tuple(
            (dx, dy)
            for dx in range(-radius, radius + 1)
            for dy in range(-radius, radius + 1)
            if dx * dx + dy * dy <= radius * radius
        )
        _disk_offsets_cache[radius] = offsets
    return offsets


def _active_cells(world):
    """Cases fertiles autour des agents vivants où la nourriture pousse
    (utilisé en mode infini).

    Optimisation : le disque de cases d'un agent ne dépend que de sa position.
    On le calcule une fois par position (cache `_cells_for_pos`) et on réutilise
    l'union tant que la signature (positions des agents vivants) ne change pas.
    Recalculer l'union à chaque tick ne coûte alors que des opérations
    ensemblistes en C, au lieu de re-parcourir ~600 cases par agent en Python
    et d'appeler get_biome() pour chacune.

    Le cache des positions est invalidé par les modules qui changent les
    biomes (flood/unflood, feux) — voir map.flood(), map.unflood() et fire.py."""
    alive     = [(a.x, a.y) for a in world.agents if a.alive]
    signature = frozenset(alive)

    cache = world._cells_for_pos
    if (signature == world._active_cells_sig
            and all(pos in cache for pos in alive)):
        return world._active_cells_cache

    # Ménage : en monde infini les agents errent loin, le cache par position
    # grossirait sans fin — on ne garde que les positions encore utiles.
    if len(cache) > 2 * len(alive) + 64:
        cache = {pos: cache[pos] for pos in alive if pos in cache}
        world._cells_for_pos = cache

    for pos in alive:
        if pos not in cache:
            cache[pos] = _cells_around_position(world, pos[0], pos[1])

    cells = set().union(*(cache[pos] for pos in alive)) if alive else set()
    world._active_cells_cache = cells
    world._active_cells_sig   = signature
    return cells


def _unload_far_chunks(world):
    """Libère de la mémoire les cases de biome/nourriture trop loin de tout
    agent vivant. Elles seront régénérées à l'identique (même seed) si un
    agent y repasse un jour.

    Optimisation : les positions d'agents sont d'abord indexées par case de
    grille de taille `d`, et une case du monde n'est testée qu'en regardant sa
    propre case de grille dans un rayon de 1. Sans ça, chaque case connue était
    comparée à chaque agent (O(cases × agents)) à chaque nettoyage."""
    if world.tick % config.CHUNK_UNLOAD_INTERVAL != 0:
        return

    agents_pos = [(a.x, a.y) for a in world.agents if a.alive]
    if not agents_pos:
        return
    d = config.CHUNK_UNLOAD_DISTANCE

    near_buckets = set()
    for ax, ay in agents_pos:
        bx, by = ax // d, ay // d
        for ddx in (-1, 0, 1):
            for ddy in (-1, 0, 1):
                near_buckets.add((bx + ddx, by + ddy))

    def near_any_agent(pos):
        return (pos[0] // d, pos[1] // d) in near_buckets

    world.map.biome_map = {p: b for p, b in world.map.biome_map.items() if near_any_agent(p)}
    world.food.food_map = {p: v for p, v in world.food.food_map.items() if near_any_agent(p)}
    world.food.food_positions &= set(world.food.food_map.keys())
    world.food.food_age = {p: age for p, age in world.food.food_age.items()
                           if p in world.food.food_map}
    # Les catastrophes en cours suivent le même sort : une case en feu/burnt/
    # inondée très loin de tout agent est oubliée (elle se régénérera telle
    # quelle, sans feu ni crue, si un agent y revient).
    world.burning = {p: t for p, t in world.burning.items() if near_any_agent(p)}
    world.burnt   = {p: t for p, t in world.burnt.items()   if near_any_agent(p)}
    world.flooded = {p: t for p, t in world.flooded.items() if near_any_agent(p)}
    world._land_cache = {}
    world._land_cache_valid = True
    world._cells_for_pos = {}
    world._active_cells_sig = None


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
    # 1. Météo, puis catastrophes naturelles (elles modifient les biomes
    #    avant que quiconque perçoive le monde de ce tick).
    if config.ENABLE_WEATHER and config.ENABLE_BIOMES:
        update_weather(world)
    if config.ENABLE_BIOMES and config.ENABLE_FIRES:
        update_fires(world)
    if config.ENABLE_BIOMES and config.ENABLE_WEATHER and config.ENABLE_FLOODS:
        update_floods(world)

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
    occupied = None  # partagé entre les tentatives de reproduction de ce tick
    for agent in world.agents:
        if not agent.alive:
            continue
        apply_timed_action(agent, world, agent.pending_action)
        if not agent.alive:
            continue
        update_agent_life(agent, world)
        if agent.alive and config.ENABLE_REPRODUCTION:
            under_cap = (config.MAX_POPULATION <= 0
                         or len(world.agents) + len(newborns) < config.MAX_POPULATION)
            # La policy propre de l'agent prime sur la policy globale, comme
            # pour think() — un agent dont la policy refuse de se reproduire
            # ne doit pas se reproduire parce que la policy globale accepte.
            effective_policy = agent.policy if agent.policy is not None else policy
            if under_cap:
                if occupied is None:
                    occupied = {(a.x, a.y) for a in world.agents}
                baby = reproduce(agent, world, effective_policy, occupied=occupied)
                if baby:
                    newborns.append(baby)
                    occupied.add((baby.x, baby.y))
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

    # 6. Croissance + pourriture de la nourriture.
    #    La pousse est évaluée tous les FOOD_GROWTH_INTERVAL ticks (avec des
    #    probabilités multipliées d'autant) ; la pourriture, elle, avance
    #    chaque tick car elle ne coûte qu'un parcours des cases avec de la
    #    nourriture (bien moins que tout le disque actif).
    if world.infinite:
        if world.tick % config.FOOD_GROWTH_INTERVAL == 0:
            cells = _active_cells(world)
            world.food.grow_food(world.map.biome_map, world.soil_moisture, cells=cells)
        world.food.update_rot()
        _unload_far_chunks(world)
    else:
        if world.tick % config.FOOD_GROWTH_INTERVAL == 0:
            world.food.grow_food(world.map.biome_map, world.soil_moisture)
        world.food.update_rot()

    world.tick += 1
