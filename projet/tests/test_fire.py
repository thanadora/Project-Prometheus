import random

import config
import pytest
from fire import _ignite, _pick_forest_cell, _try_ignition, update_fires

from tests.conftest import make_world, make_agent


def forest_world(**kwargs):
    return make_world(width=6, height=6, default_biome=config.BIOME_FOREST, **kwargs)


class TestIgnite:
    def test_forest_cell_ignites_and_burns_food(self):
        world = forest_world(food_amounts={(2, 2): 3})
        assert _ignite(world, (2, 2)) is True
        assert world.burning[(2, 2)] == config.FIRE_BURN_DURATION
        assert world.food.food_map[(2, 2)] == 0

    def test_non_forest_cell_does_not_ignite(self):
        world = make_world(width=4, height=4, default_biome=config.BIOME_PRAIRIE)
        assert _ignite(world, (1, 1)) is False
        assert world.burning == {}

    def test_water_never_ignites(self):
        world = make_world(width=4, height=4, overrides={(1, 1): config.BIOME_WATER})
        assert _ignite(world, (1, 1)) is False

    def test_respects_max_active_fires(self):
        config.FIRE_MAX_ACTIVE = 1
        world = forest_world()
        assert _ignite(world, (0, 0)) is True
        assert _ignite(world, (1, 1)) is False
        assert len(world.burning) == 1


class TestPickForestCell:
    def test_retries_until_forest_found(self, monkeypatch):
        world = make_world(width=4, height=4, default_biome=config.BIOME_WATER,
                           overrides={(2, 2): config.BIOME_FOREST})
        seq = iter([0, 0, 2, 2])  # (0,0) eau, puis (2,2) forêt
        monkeypatch.setattr(random, "randrange", lambda n: next(seq))
        assert _pick_forest_cell(world) == (2, 2)

    def test_returns_none_without_any_forest(self, monkeypatch):
        world = make_world(width=4, height=4, default_biome=config.BIOME_PRAIRIE)
        monkeypatch.setattr(random, "randrange", lambda n: 0)
        assert _pick_forest_cell(world) is None

    def test_infinite_mode_samples_around_agents(self, monkeypatch):
        world = make_world(width=16, height=16, default_biome=config.BIOME_WATER,
                           overrides={(10, 10): config.BIOME_FOREST}, infinite=True)
        world.agents = [make_agent(x=10, y=10)]
        monkeypatch.setattr(random, "choice", lambda seq: seq[0])
        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        assert _pick_forest_cell(world) == (10, 10)


class TestIgnition:
    def test_ignition_hits_forest_even_on_mostly_water_map(self, monkeypatch):
        """Régression : le départ tirait une case uniformément sur la carte et
        échouait presque toujours quand la forêt était minoritaire (cartes
        réelles : ~10% de forêt). Il cible désormais une case de forêt."""
        world = make_world(width=6, height=6, default_biome=config.BIOME_WATER,
                           overrides={(5, 5): config.BIOME_FOREST},
                           weather=config.WEATHER_DROUGHT)
        world.tick = config.SEASON_DURATION * config.SEASON_SUMMER  # été
        seq = iter([5, 5])
        monkeypatch.setattr(random, "randrange", lambda n: next(seq))
        monkeypatch.setattr(random, "random", lambda: 0.0)
        _try_ignition(world)
        assert (5, 5) in world.burning

    def test_drought_and_summer_ignite_random_forest(self, monkeypatch):
        world = forest_world(weather=config.WEATHER_DROUGHT)
        world.tick = config.SEASON_DURATION * config.SEASON_SUMMER  # été
        monkeypatch.setattr(random, "randrange", lambda n: 2)
        monkeypatch.setattr(random, "random", lambda: 0.0)  # toujours < chance
        _try_ignition(world)
        assert (2, 2) in world.burning

    def test_rain_prevents_ignition(self, monkeypatch):
        world = forest_world(weather=config.WEATHER_RAIN)
        monkeypatch.setattr(random, "randrange", lambda n: 2)
        monkeypatch.setattr(random, "random", lambda: 0.0)
        _try_ignition(world)
        assert world.burning == {}

    def test_no_ignition_when_roll_above_chance(self, monkeypatch):
        world = forest_world(weather=config.WEATHER_DROUGHT)
        world.tick = config.SEASON_DURATION * config.SEASON_SUMMER
        monkeypatch.setattr(random, "randrange", lambda n: 2)
        monkeypatch.setattr(random, "random", lambda: 0.999)
        _try_ignition(world)
        assert world.burning == {}

    def test_ignition_targets_around_agents_in_infinite_mode(self, monkeypatch):
        world = make_world(width=12, height=12, default_biome=config.BIOME_FOREST,
                           infinite=True)
        world.agents = [make_agent(x=10, y=10)]
        world.tick = config.SEASON_DURATION * config.SEASON_SUMMER
        world.weather = config.WEATHER_DROUGHT
        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        monkeypatch.setattr(random, "random", lambda: 0.0)
        _try_ignition(world)
        assert (10, 10) in world.burning


class TestUpdateFires:
    def test_spreads_to_adjacent_forest(self, monkeypatch):
        world = forest_world()
        world.burning[(2, 2)] = 10
        monkeypatch.setattr(random, "random", lambda: 0.001)  # ni départ ni extinction
        update_fires(world)
        assert (3, 2) in world.burning
        assert (2, 3) in world.burning

    def test_does_not_spread_through_prairie(self, monkeypatch):
        world = make_world(width=5, height=1, default_biome=config.BIOME_PRAIRIE)
        world.map.biome_map[(0, 0)] = config.BIOME_FOREST
        world.burning[(0, 0)] = 10
        monkeypatch.setattr(random, "random", lambda: 0.001)
        update_fires(world)
        assert (1, 0) not in world.burning
        assert (0, 0) in world.burning  # la case d'origine brûle toujours

    def test_rain_extinguishes_burning_cells(self, monkeypatch):
        world = forest_world(weather=config.WEATHER_RAIN)
        world.burning[(2, 2)] = 10
        monkeypatch.setattr(random, "random", lambda: 0.0)  # < chance d'extinction
        update_fires(world)
        assert (2, 2) not in world.burning

    def test_burned_out_cell_becomes_fertile_ash(self):
        world = forest_world()
        world.burning[(2, 2)] = 1
        update_fires(world)
        assert (2, 2) not in world.burning
        assert world.map.biome_map[(2, 2)] == config.BIOME_BURNT
        assert world.burnt[(2, 2)] == config.FIRE_ASH_DURATION

    def test_ash_reverts_to_prairie_after_delay(self):
        world = forest_world()
        world.map.biome_map[(2, 2)] = config.BIOME_BURNT
        world.burnt[(2, 2)] = 1
        update_fires(world)
        assert (2, 2) not in world.burnt
        assert world.map.biome_map[(2, 2)] == config.BIOME_PRAIRIE

    def test_fire_damages_agents_standing_in_flames(self):
        world = forest_world()
        agent = make_agent(x=2, y=2, energy=50)
        world.agents = [agent]
        world.burning[(2, 2)] = 10
        update_fires(world)
        assert agent.energy == 50 - config.FIRE_DAMAGE

    def test_fire_kills_agent_with_no_energy_left(self):
        world = forest_world()
        agent = make_agent(x=2, y=2, energy=config.FIRE_DAMAGE - 1)
        world.agents = [agent]
        world.burning[(2, 2)] = 10
        update_fires(world)
        assert agent.alive is False

    def test_world_phase_skips_fires_when_disabled(self):
        config.ENABLE_FIRES = False
        from world import world_phase
        from policy import HardcodedPolicy

        world = forest_world()
        world.burning[(2, 2)] = 5
        world.agents = [make_agent(x=0, y=0, policy=HardcodedPolicy())]
        world_phase(world, HardcodedPolicy())
        assert world.burning[(2, 2)] == 5  # pas décrémenté : module éteint

    def test_fire_never_spreads_out_of_map_bounds(self, monkeypatch):
        """Régression : la propagation hors bornes générait des cellules à
        l'infini via get_biome(), faisant exploser la taille de la carte."""
        world = make_world(width=3, height=3, default_biome=config.BIOME_FOREST)
        world.burning[(0, 0)] = 100
        world.map.biome_map[(2, 2)] = config.BIOME_FOREST
        monkeypatch.setattr(random, "random", lambda: 0.001)  # propage sans s'éteindre
        cells_before = len(world.map.biome_map)
        for _ in range(50):
            update_fires(world)
        assert cells_before == 9
        assert all(0 <= x < 3 and 0 <= y < 3 for x, y in world.burning)
