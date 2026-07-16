import random

import config
from food import FoodSystem


def flat_biome_map(width, height, biome):
    return {(x, y): biome for x in range(width) for y in range(height)}


class TestInitializeClassic:
    def test_food_map_covers_every_cell_at_zero(self):
        biome_map = flat_biome_map(4, 4, config.BIOME_PRAIRIE)
        food = FoodSystem(width=4, height=4)
        food.initialize(biome_map)
        assert len(food.food_map) == 16
        # Sauf les cases où la nourriture initiale a été semée, tout est à 0.
        assert all(v >= 0 for v in food.food_map.values())

    def test_spawns_exactly_initial_food_count_units_when_capacity_allows(self):
        biome_map = flat_biome_map(20, 20, config.BIOME_PRAIRIE)
        food = FoodSystem(width=20, height=20)
        food.initialize(biome_map)
        total = sum(food.food_map.values())
        assert total == config.INITIAL_FOOD_COUNT

    def test_no_food_spawned_on_water_only_map(self):
        biome_map = flat_biome_map(5, 5, config.BIOME_WATER)
        food = FoodSystem(width=5, height=5)
        food.initialize(biome_map)
        assert sum(food.food_map.values()) == 0
        assert food.food_positions == set()

    def test_food_positions_matches_nonzero_cells(self):
        biome_map = flat_biome_map(10, 10, config.BIOME_FOREST)
        food = FoodSystem(width=10, height=10)
        food.initialize(biome_map)
        nonzero = {pos for pos, amount in food.food_map.items() if amount > 0}
        assert food.food_positions == nonzero


class TestGetCapacity:
    def test_water_has_zero_capacity(self):
        biome_map = {(0, 0): config.BIOME_WATER}
        food = FoodSystem(width=1, height=1)
        assert food._get_capacity(biome_map, (0, 0)) == 0

    def test_land_biome_capacity_matches_config(self):
        biome_map = {(0, 0): config.BIOME_PRAIRIE}
        food = FoodSystem(width=1, height=1)
        expected = config.FOOD_TYPES[config.BIOME_PRAIRIE]["capacity"]
        assert food._get_capacity(biome_map, (0, 0)) == expected

    def test_unknown_position_has_zero_capacity(self):
        food = FoodSystem(width=1, height=1)
        assert food._get_capacity({}, (5, 5)) == 0


class TestConsumeFood:
    def test_consuming_removes_one_unit_and_returns_gain(self):
        biome_map = {(0, 0): config.BIOME_PRAIRIE}
        food = FoodSystem(width=1, height=1)
        food.food_map[(0, 0)] = 3
        food.food_positions.add((0, 0))
        gain = food.consume_food(biome_map, (0, 0))
        assert gain == config.FOOD_TYPES[config.BIOME_PRAIRIE]["gain"]
        assert food.food_map[(0, 0)] == 2

    def test_consuming_last_unit_clears_position_from_positions_set(self):
        biome_map = {(0, 0): config.BIOME_FOREST}
        food = FoodSystem(width=1, height=1)
        food.food_map[(0, 0)] = 1
        food.food_positions.add((0, 0))
        food.consume_food(biome_map, (0, 0))
        assert food.food_map[(0, 0)] == 0
        assert (0, 0) not in food.food_positions

    def test_consuming_empty_position_returns_zero(self):
        biome_map = {(0, 0): config.BIOME_PRAIRIE}
        food = FoodSystem(width=1, height=1)
        assert food.consume_food(biome_map, (0, 0)) == 0

    def test_consuming_on_non_food_biome_returns_zero_without_crash(self):
        biome_map = {(0, 0): config.BIOME_WATER}
        food = FoodSystem(width=1, height=1)
        assert food.consume_food(biome_map, (0, 0)) == 0

    def test_known_quirk_orphan_food_after_biome_change_is_not_removed(self):
        """Documente un comportement existant, potentiellement surprenant :
        si une case avait de la nourriture puis devient de l'eau (tempête),
        consume_food() ne trouve plus le biome dans FOOD_TYPES et rend 0
        SANS retirer la nourriture fantôme du food_map. Ce test fige ce
        comportement pour qu'un changement futur soit conscient et volontaire,
        pas une régression silencieuse."""
        biome_map = {(0, 0): config.BIOME_WATER}
        food = FoodSystem(width=1, height=1)
        food.food_map[(0, 0)] = 5
        food.food_positions.add((0, 0))
        gain = food.consume_food(biome_map, (0, 0))
        assert gain == 0
        assert food.food_map[(0, 0)] == 5  # <- toujours là, "orpheline"


class TestGrowFood:
    def test_forces_growth_when_random_below_growth_probability(self, monkeypatch):
        biome_map = {(0, 0): config.BIOME_PRAIRIE}
        food = FoodSystem(width=1, height=1)
        food.food_map[(0, 0)] = 0
        monkeypatch.setattr(random, "random", lambda: 0.0)  # toujours < growth
        food.grow_food(biome_map, soil_moisture=1.0)
        assert food.food_map[(0, 0)] == 1

    def test_no_growth_when_random_above_growth_probability(self, monkeypatch):
        biome_map = {(0, 0): config.BIOME_PRAIRIE}
        food = FoodSystem(width=1, height=1)
        food.food_map[(0, 0)] = 0
        monkeypatch.setattr(random, "random", lambda: 0.999999)
        food.grow_food(biome_map, soil_moisture=1.0)
        assert food.food_map[(0, 0)] == 0

    def test_does_not_grow_past_capacity(self, monkeypatch):
        biome_map = {(0, 0): config.BIOME_PRAIRIE}
        cap = config.FOOD_TYPES[config.BIOME_PRAIRIE]["capacity"]
        food = FoodSystem(width=1, height=1)
        food.food_map[(0, 0)] = cap
        monkeypatch.setattr(random, "random", lambda: 0.0)
        food.grow_food(biome_map, soil_moisture=1.0)
        assert food.food_map[(0, 0)] == cap  # inchangé : déjà à pleine capacité

    def test_water_biome_never_grows_food(self, monkeypatch):
        biome_map = {(0, 0): config.BIOME_WATER}
        food = FoodSystem(width=1, height=1)
        monkeypatch.setattr(random, "random", lambda: 0.0)
        food.grow_food(biome_map, soil_moisture=1.0)
        assert food.food_map.get((0, 0), 0) == 0

    def test_cells_param_restricts_growth_to_given_set(self, monkeypatch):
        biome_map = flat_biome_map(3, 1, config.BIOME_PRAIRIE)
        food = FoodSystem(width=3, height=1)
        for pos in biome_map:
            food.food_map[pos] = 0
        monkeypatch.setattr(random, "random", lambda: 0.0)
        food.grow_food(biome_map, soil_moisture=1.0, cells=[(0, 0)])
        assert food.food_map[(0, 0)] == 1
        assert food.food_map[(1, 0)] == 0
        assert food.food_map[(2, 0)] == 0

    def test_adjacent_water_boosts_local_moisture_and_growth_chance(self, monkeypatch):
        # Sans eau adjacente : moisture=0.1 -> growth faible.
        # Avec eau adjacente : +0.3 -> growth plus élevée.
        # On fixe random.random() juste entre les deux pour observer la
        # différence de comportement.
        respawn = config.FOOD_TYPES[config.BIOME_PRAIRIE]["respawn"]
        growth_without_water = respawn * 0.1
        growth_with_water = respawn * min(1.0, 0.1 + 0.3)
        threshold = (growth_without_water + growth_with_water) / 2
        monkeypatch.setattr(random, "random", lambda: threshold)

        no_water_map = {(0, 0): config.BIOME_PRAIRIE}
        food_no_water = FoodSystem(width=1, height=1)
        food_no_water.food_map[(0, 0)] = 0
        food_no_water.grow_food(no_water_map, soil_moisture=0.1)
        assert food_no_water.food_map[(0, 0)] == 0

        with_water_map = {(0, 0): config.BIOME_PRAIRIE, (1, 0): config.BIOME_WATER}
        food_with_water = FoodSystem(width=2, height=1)
        food_with_water.food_map[(0, 0)] = 0
        food_with_water.grow_food(with_water_map, soil_moisture=0.1)
        assert food_with_water.food_map[(0, 0)] == 1


class TestClearPosition:
    def test_clears_existing_food(self):
        food = FoodSystem(width=1, height=1)
        food.food_map[(0, 0)] = 4
        food.food_positions.add((0, 0))
        food.clear_position((0, 0))
        assert food.food_map[(0, 0)] == 0
        assert (0, 0) not in food.food_positions

    def test_noop_on_empty_position(self):
        food = FoodSystem(width=1, height=1)
        food.clear_position((0, 0))  # ne doit pas lever
        assert food.food_map.get((0, 0), 0) == 0


class TestIterFood:
    def test_yields_position_and_amount_tuples(self):
        food = FoodSystem(width=2, height=2)
        food.food_map[(0, 0)] = 3
        food.food_map[(1, 1)] = 5
        food.food_positions = {(0, 0), (1, 1)}
        results = sorted(food.iter_food())
        assert results == [(0, 0, 3), (1, 1, 5)]
