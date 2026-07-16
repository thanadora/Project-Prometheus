"""
migration.py — Logique de migration collective des agents.
"""

import random
from logger import get_logger
from config import (
    BIOME_WATER,
    MIGRATION_VOTE_THRESHOLD,
    MIGRATION_COOLDOWN,
    MIGRATION_MAX_AGENTS,
    SOIL_MOISTURE_INIT,
    WEATHER_CLEAR,
)


def _reachable_land(world, sx, sy):
    """BFS depuis (sx, sy) avec cache invalidé par update_biomes()."""
    if not world._land_cache_valid:
        world._land_cache = {}
        world._land_cache_valid = True

    key = (sx, sy)
    if key in world._land_cache:
        return world._land_cache[key]

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

    world._land_cache[key] = visited
    return visited


def check_migration(world):
    """
    Déclenche une migration si le vote collectif l'exige.
    Retourne True si une migration a eu lieu.
    """
    from map import GameMap
    from food import FoodSystem

    if getattr(world, "infinite", False):
        # Pas de migration en monde infini : sans bords, ça n'a pas de sens
        # de téléporter la colonie — elle peut juste continuer à se déplacer.
        return False

    log    = get_logger()
    agents = [a for a in world.agents if a.alive]

    if not agents or len(agents) > MIGRATION_MAX_AGENTS:
        return False
    if world.tick - world.last_migration_tick < MIGRATION_COOLDOWN:
        return False

    votes = sum(1 for a in agents if a.vote_migrate)
    if votes / len(agents) < MIGRATION_VOTE_THRESHOLD:
        return False

    total_land = sum(1 for b in world.map.biome_map.values() if b != BIOME_WATER)
    min_land   = max(1, int(total_land * 0.10))
    mobile = [a for a in agents if len(_reachable_land(world, a.x, a.y)) >= min_land]
    if not mobile:
        return False

    # Nouveau monde
    new_map  = GameMap(width=world.width, height=world.height)
    new_map.initialize()
    new_food = FoodSystem(width=world.width, height=world.height)
    new_food.initialize(new_map.biome_map)

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

    world.map               = new_map
    world._land_cache = {}
    world._land_cache_valid = True
    world.food              = new_food
    world.soil_moisture     = SOIL_MOISTURE_INIT
    world.weather           = WEATHER_CLEAR
    world.migration_count  += 1
    world.last_migration_tick = world.tick

    log.info(world.tick, f"MIGRATION #{world.migration_count} — {len(mobile)} agents ont migré")
    return True