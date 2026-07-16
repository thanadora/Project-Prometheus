import random

import config
from weather import update_weather, _shrink_water, _expand_water
from map import GameMap
from food import FoodSystem
from world import World
from agent import Agent


def build_world(width, height, biome_overrides, weather=None, soil_moisture=None, tick=0):
    m = GameMap(width=width, height=height)
    m.biome_map = {(x, y): config.BIOME_PRAIRIE for x in range(width) for y in range(height)}
    m.altitude_map = {(x, y): 0.5 for x in range(width) for y in range(height)}
    for pos, biome in biome_overrides.items():
        m.biome_map[pos] = biome
    f = FoodSystem(width=width, height=height)
    f.initialize(m.biome_map)
    w = World(width=width, height=height, map=m, food=f, tick=tick)
    if weather is not None:
        w.weather = weather
    if soil_moisture is not None:
        w.soil_moisture = soil_moisture
    return w


class TestUpdateWeatherTiming:
    def test_weather_unchanged_between_day_boundaries(self, monkeypatch):
        w = build_world(3, 3, {}, weather=config.WEATHER_CLEAR, tick=1)
        # tick=1 n'est pas un multiple de DAY_DURATION (sauf si DAY_DURATION==1)
        assert config.DAY_DURATION > 1
        monkeypatch.setattr(random, "random", lambda: 0.0)  # forcerait un changement si testé
        update_weather(w)
        assert w.weather == config.WEATHER_CLEAR

    def test_moisture_still_updates_on_non_boundary_ticks(self):
        w = build_world(3, 3, {}, weather=config.WEATHER_RAIN, soil_moisture=0.5, tick=1)
        update_weather(w)
        expected = min(config.SOIL_MOISTURE_MAX,
                        0.5 + config.WEATHER_MOISTURE_DELTA[config.WEATHER_RAIN])
        assert w.soil_moisture == expected

    def test_soil_moisture_is_clamped_to_bounds(self):
        w = build_world(3, 3, {}, weather=config.WEATHER_DROUGHT,
                         soil_moisture=config.SOIL_MOISTURE_MIN, tick=1)
        update_weather(w)
        assert w.soil_moisture >= config.SOIL_MOISTURE_MIN

    def test_weather_can_change_on_day_boundary(self, monkeypatch):
        w = build_world(3, 3, {}, weather=config.WEATHER_CLEAR, tick=config.DAY_DURATION)
        monkeypatch.setattr(random, "random", lambda: 0.0)  # < WEATHER_CHANGE_PROB -> change
        monkeypatch.setattr(random, "choices", lambda pop, weights, k: [config.WEATHER_STORM])
        update_weather(w)
        assert w.weather == config.WEATHER_STORM

    def test_weather_stable_when_change_roll_fails(self, monkeypatch):
        w = build_world(3, 3, {}, weather=config.WEATHER_CLEAR, tick=config.DAY_DURATION)
        monkeypatch.setattr(random, "random", lambda: 0.999999)  # > WEATHER_CHANGE_PROB
        update_weather(w)
        assert w.weather == config.WEATHER_CLEAR


class TestExpandWater:
    def test_grows_water_into_adjacent_land(self):
        overrides = {(1, 1): config.BIOME_WATER}
        w = build_world(3, 3, overrides)
        _expand_water(w)
        assert w.map.biome_map[(1, 1)] == config.BIOME_WATER
        # les 4 voisins directs doivent être devenus de l'eau
        for pos in [(0, 1), (2, 1), (1, 0), (1, 2)]:
            assert w.map.biome_map[pos] == config.BIOME_WATER
        # le coin, non adjacent (diagonale), doit rester inchangé
        assert w.map.biome_map[(0, 0)] == config.BIOME_PRAIRIE

    def test_clears_food_on_newly_flooded_cells(self):
        overrides = {(1, 1): config.BIOME_WATER}
        w = build_world(3, 3, overrides)
        w.food.food_map[(0, 1)] = 5
        w.food.food_positions.add((0, 1))
        _expand_water(w)
        assert w.food.food_map[(0, 1)] == 0
        assert (0, 1) not in w.food.food_positions

    def test_drowns_agents_caught_by_expanding_water(self):
        overrides = {(1, 1): config.BIOME_WATER}
        w = build_world(3, 3, overrides)
        drowned = Agent(id=1, x=0, y=1, energy=50, thirst=50)
        safe = Agent(id=2, x=0, y=0, energy=50, thirst=50)
        w.agents = [drowned, safe]
        _expand_water(w)
        assert drowned.alive is False
        assert safe.alive is True


class TestShrinkWater:
    def test_shrinks_border_water_to_prairie(self):
        overrides = {(1, 1): config.BIOME_WATER}
        w = build_world(3, 3, overrides)
        _shrink_water(w)
        assert w.map.biome_map[(1, 1)] == config.BIOME_PRAIRIE

    def test_only_shrinks_water_adjacent_to_land(self):
        # Un lac 2x2 entouré de terre : toutes les cases sont bordières ici
        # (dans une grille 4x4, le lac occupe (1,1)-(2,2)), donc tout doit
        # redevenir prairie en un seul appel.
        overrides = {(1, 1): config.BIOME_WATER, (2, 1): config.BIOME_WATER,
                     (1, 2): config.BIOME_WATER, (2, 2): config.BIOME_WATER}
        w = build_world(4, 4, overrides)
        _shrink_water(w)
        for pos in overrides:
            assert w.map.biome_map[pos] == config.BIOME_PRAIRIE

    def test_clears_food_on_newly_dried_cells(self):
        overrides = {(1, 1): config.BIOME_WATER}
        w = build_world(3, 3, overrides)
        # de la nourriture "orpheline" existante sur la case d'eau (cf. quirk food.py)
        w.food.food_map[(1, 1)] = 3
        w.food.food_positions.add((1, 1))
        _shrink_water(w)
        assert w.food.food_map[(1, 1)] == 0
        assert (1, 1) not in w.food.food_positions

    def test_isolated_lake_far_from_land_is_untouched(self):
        # Lac qui occupe TOUTE la carte : aucune case n'est adjacente à de la
        # terre, donc _shrink_water ne doit rien changer.
        m = GameMap(width=2, height=2)
        m.biome_map = {(x, y): config.BIOME_WATER for x in range(2) for y in range(2)}
        m.altitude_map = {(x, y): 0.5 for x in range(2) for y in range(2)}
        f = FoodSystem(width=2, height=2)
        f.initialize(m.biome_map)
        w = World(width=2, height=2, map=m, food=f)
        _shrink_water(w)
        assert all(b == config.BIOME_WATER for b in w.map.biome_map.values())
