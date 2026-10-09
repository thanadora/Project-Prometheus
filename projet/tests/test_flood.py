import random

import config
import flood as flood_module
from flood import _find_shore_cell, update_floods

from tests.conftest import make_world, make_agent


def shore_world(**kwargs):
    # (1,0) est de l'eau, le reste est de la prairie praticable.
    return make_world(width=5, height=5,
                      overrides={(1, 0): config.BIOME_WATER}, **kwargs)


class TestFindShoreCell:
    def test_finds_land_adjacent_to_water(self, monkeypatch):
        world = shore_world()
        monkeypatch.setattr(random, "randint", lambda a, b: a)  # essaie (0,0)
        monkeypatch.setattr(random, "choice", lambda seq: seq[0])
        pos = _find_shore_cell(world, radius=5)
        assert pos is not None
        assert world.map.get_biome(*pos) != config.BIOME_WATER
        x, y = pos
        assert any(world.map.get_biome(x + dx, y + dy) == config.BIOME_WATER
                   for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)])

    def test_returns_none_without_water(self, monkeypatch):
        world = make_world(width=4, height=4)  # tout prairie
        monkeypatch.setattr(random, "randint", lambda a, b: a)
        assert _find_shore_cell(world, radius=5) is None

    def test_infinite_mode_samples_around_agents(self, monkeypatch):
        world = shore_world(infinite=True)
        world.agents = [make_agent(x=10, y=10)]
        seen = {}

        def fake_randint(a, b):
            seen["range"] = (a, b)
            return a
        monkeypatch.setattr(random, "randint", fake_randint)
        monkeypatch.setattr(random, "choice", lambda seq: seq[0])
        _find_shore_cell(world, radius=3)
        assert seen["range"][0] >= 10 - 3  # échantillonnage autour de l'agent


class TestUpdateFloods:
    def test_rain_can_flood_a_shore_cell(self, monkeypatch):
        world = shore_world(weather=config.WEATHER_RAIN)
        monkeypatch.setattr(random, "random", lambda: 0.0)  # < chance de crue
        monkeypatch.setattr(flood_module, "_find_shore_cell", lambda w, r: (0, 0))
        update_floods(world)
        assert (0, 0) in world.flooded
        assert world.flooded[(0, 0)] == config.FLOOD_DURATION
        assert world.map.get_biome(0, 0) == config.BIOME_WATER

    def test_flooded_cell_becomes_unwalkable(self, monkeypatch):
        world = shore_world(weather=config.WEATHER_RAIN)
        monkeypatch.setattr(random, "random", lambda: 0.0)
        monkeypatch.setattr(flood_module, "_find_shore_cell", lambda w, r: (2, 2))
        assert world.map.is_walkable(2, 2) is True
        update_floods(world)
        assert world.map.is_walkable(2, 2) is False

    def test_no_flood_when_weather_clear(self, monkeypatch):
        world = shore_world(weather=config.WEATHER_CLEAR)
        monkeypatch.setattr(random, "random", lambda: 0.0)
        monkeypatch.setattr(flood_module, "_find_shore_cell", lambda w, r: (0, 0))
        update_floods(world)
        assert world.flooded == {}

    def test_flooded_cells_recede_and_restore_biome(self):
        world = shore_world(weather=config.WEATHER_CLEAR)
        world.map.flood([(2, 2)], world)
        world.flooded[(2, 2)] = 1  # plus qu'un tick
        update_floods(world)
        assert world.flooded == {}
        assert world.map.get_biome(2, 2) == config.BIOME_PRAIRIE
        assert world.map.is_walkable(2, 2) is True

    def test_max_cells_cap_blocks_new_floods(self, monkeypatch):
        world = shore_world(weather=config.WEATHER_RAIN)
        config.FLOOD_MAX_CELLS = 1
        world.flooded[(4, 4)] = 50
        monkeypatch.setattr(random, "random", lambda: 0.0)
        monkeypatch.setattr(flood_module, "_find_shore_cell", lambda w, r: (0, 0))
        update_floods(world)
        assert (0, 0) not in world.flooded  # plafond atteint

    def test_flood_clears_food_on_covered_cell(self, monkeypatch):
        world = shore_world(weather=config.WEATHER_RAIN, food_amounts={(0, 0): 3})
        monkeypatch.setattr(random, "random", lambda: 0.0)
        monkeypatch.setattr(flood_module, "_find_shore_cell", lambda w, r: (0, 0))
        update_floods(world)
        assert world.food.food_map[(0, 0)] == 0

    def test_world_phase_skips_floods_when_disabled(self, monkeypatch):
        config.ENABLE_FLOODS = False
        from world import world_phase
        from policy import HardcodedPolicy

        world = shore_world(weather=config.WEATHER_RAIN)
        world.agents = [make_agent(x=2, y=2, policy=HardcodedPolicy())]
        monkeypatch.setattr(random, "random", lambda: 0.0)
        world_phase(world, HardcodedPolicy())
        assert world.flooded == {}
