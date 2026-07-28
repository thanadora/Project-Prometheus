"""
weather.py — Gestion de la météo et de l'humidité du sol.
"""

import random
from logger import get_logger
from config import (
    DAY_DURATION,
    BIOME_WATER,
    BIOME_MOUNTAIN_ROCK,
    BIOME_MOUNTAIN_SNOW,
    WEATHER_CLEAR,
    WEATHER_RAIN,
    WEATHER_STORM,
    WEATHER_DROUGHT,
    WEATHER_FROST,
    WEATHER_MOISTURE_DELTA,
    WEATHER_CHANGE_PROB,
    SEASON_WEATHER_PROBS,
    SOIL_MOISTURE_MIN,
    SOIL_MOISTURE_MAX,
    SOIL_MOISTURE_INIT,
)

_WEATHERS = [WEATHER_CLEAR, WEATHER_RAIN, WEATHER_STORM, WEATHER_DROUGHT, WEATHER_FROST]


def update_weather(world):
    old_weather = world.weather

    if world.tick % DAY_DURATION == 0:
        if random.random() < WEATHER_CHANGE_PROB:
            season        = world.current_season()
            world.weather = random.choices(_WEATHERS, weights=SEASON_WEATHER_PROBS[season], k=1)[0]

        if old_weather == WEATHER_STORM   and world.weather == WEATHER_STORM:
            _expand_water(world)
        if old_weather == WEATHER_DROUGHT and world.weather == WEATHER_DROUGHT:
            _shrink_water(world)

    delta = WEATHER_MOISTURE_DELTA[world.weather]
    world.soil_moisture = max(SOIL_MOISTURE_MIN, min(SOIL_MOISTURE_MAX, world.soil_moisture + delta))


def _in_bounds(world, x, y):
    if getattr(world, "infinite", False):
        return True
    return 0 <= x < world.width and 0 <= y < world.height


def _shrink_water(world):
    to_land = {
        (x, y)
        for (x, y), biome in world.map.biome_map.items()
        if biome == BIOME_WATER
        and any(
            world.map.biome_map.get((x + dx, y + dy)) != BIOME_WATER
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]
            if _in_bounds(world, x + dx, y + dy)
        )
    }
    world.map.unflood(to_land, world)
    for pos in to_land:
        world.food.clear_position(pos)


def _expand_water(world):
    log = get_logger()
    new_water = {
        (x + dx, y + dy)
        for (x, y), biome in world.map.biome_map.items()
        if biome == BIOME_WATER
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]
        if _in_bounds(world, x + dx, y + dy)
        and world.map.biome_map.get((x + dx, y + dy)) not in
        (BIOME_WATER, BIOME_MOUNTAIN_ROCK, BIOME_MOUNTAIN_SNOW)
    }
    world.map.flood(new_water, world)
    for pos in new_water:
        world.food.clear_position(pos)
    for agent in world.agents:
        if not world.map.is_walkable(agent.x, agent.y):
            agent.alive = False
            log.warning(world.tick, f"Agent #{agent.id} noyé par expansion de l'eau en ({agent.x},{agent.y})")