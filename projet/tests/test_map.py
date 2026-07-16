import config
from map import GameMap, _fertility_to_biome


class TestFertilityToBiome:
    def test_below_water_threshold_is_water(self):
        assert _fertility_to_biome(config.WATER_THRESHOLD - 0.01) == config.BIOME_WATER

    def test_between_water_and_forest_is_forest(self):
        mid = (config.WATER_THRESHOLD + config.FOREST_THRESHOLD) / 2
        assert _fertility_to_biome(mid) == config.BIOME_FOREST

    def test_between_forest_and_prairie_is_prairie(self):
        mid = (config.FOREST_THRESHOLD + config.PRAIRIE_THRESHOLD) / 2
        assert _fertility_to_biome(mid) == config.BIOME_PRAIRIE

    def test_above_prairie_threshold_is_desert(self):
        assert _fertility_to_biome(config.PRAIRIE_THRESHOLD + 0.01) == config.BIOME_DESERT

    def test_boundaries_are_exclusive_on_the_upper_side(self):
        # "< seuil" partout : exactement au seuil, on bascule dans la
        # catégorie suivante.
        assert _fertility_to_biome(config.WATER_THRESHOLD) != config.BIOME_WATER


class TestClassicMode:
    def test_initialize_fills_every_cell(self):
        m = GameMap(width=5, height=4)
        m.initialize(offset_x=0, offset_y=0)
        assert len(m.biome_map) == 5 * 4
        assert len(m.altitude_map) == 5 * 4

    def test_biomes_are_valid_values(self):
        m = GameMap(width=8, height=8)
        m.initialize(offset_x=12, offset_y=34)
        valid = {config.BIOME_WATER, config.BIOME_DESERT, config.BIOME_PRAIRIE, config.BIOME_FOREST}
        assert set(m.biome_map.values()) <= valid

    def test_get_biome_matches_precomputed_map(self):
        m = GameMap(width=6, height=6)
        m.initialize(offset_x=5, offset_y=5)
        for pos, biome in m.biome_map.items():
            assert m.get_biome(*pos) == biome

    def test_is_walkable_false_only_on_water(self):
        m = GameMap(width=10, height=10)
        m.initialize(offset_x=1, offset_y=1)
        for pos, biome in m.biome_map.items():
            assert m.is_walkable(*pos) == (biome != config.BIOME_WATER)

    def test_same_offsets_give_same_map(self):
        m1 = GameMap(width=6, height=6)
        m1.initialize(offset_x=42, offset_y=17)
        m2 = GameMap(width=6, height=6)
        m2.initialize(offset_x=42, offset_y=17)
        assert m1.biome_map == m2.biome_map


class TestInfiniteMode:
    def test_initialize_does_not_prefill(self):
        m = GameMap(width=10, height=10, infinite=True)
        m.initialize(offset_x=0, offset_y=0)
        assert m.biome_map == {}

    def test_get_biome_generates_and_caches(self):
        m = GameMap(width=10, height=10, infinite=True)
        m.initialize(offset_x=0, offset_y=0)
        b1 = m.get_biome(100, -50)
        assert (100, -50) in m.biome_map
        b2 = m.get_biome(100, -50)
        assert b1 == b2
        assert len(m.biome_map) == 1  # un seul accès = une seule case en cache

    def test_far_apart_coordinates_do_not_collide_in_cache(self):
        m = GameMap(width=10, height=10, infinite=True)
        m.initialize(offset_x=0, offset_y=0)
        m.get_biome(0, 0)
        m.get_biome(1000, -1000)
        assert len(m.biome_map) == 2


class TestAltitude:
    def test_get_altitude_within_unit_range(self):
        m = GameMap(width=6, height=6)
        m.initialize(offset_x=3, offset_y=3)
        for pos in m.biome_map:
            assert 0.0 <= m.get_altitude(*pos) <= 1.0

    def test_get_altitude_falls_back_to_neutral_after_transformation(self):
        m = GameMap(width=6, height=6)
        m.initialize(offset_x=3, offset_y=3)
        m.update_biomes({(2, 2)}, config.BIOME_WATER)
        assert m.get_altitude(2, 2) == 0.5


class TestUpdateBiomes:
    def test_changes_biome_at_given_positions_only(self):
        m = GameMap(width=5, height=5)
        m.initialize(offset_x=0, offset_y=0)
        before = dict(m.biome_map)
        m.update_biomes({(1, 1)}, config.BIOME_WATER)
        assert m.biome_map[(1, 1)] == config.BIOME_WATER
        for pos, biome in before.items():
            if pos != (1, 1):
                assert m.biome_map[pos] == biome

    def test_resets_altitude_to_neutral(self):
        m = GameMap(width=5, height=5)
        m.initialize(offset_x=0, offset_y=0)
        m.update_biomes({(0, 0)}, config.BIOME_PRAIRIE)
        assert m.altitude_map[(0, 0)] == 0.5

    def test_invalidates_world_land_cache_when_world_given(self):
        class DummyWorld:
            _land_cache_valid = True
        w = DummyWorld()
        m = GameMap(width=3, height=3)
        m.initialize(offset_x=0, offset_y=0)
        m.update_biomes({(0, 0)}, config.BIOME_FOREST, world=w)
        assert w._land_cache_valid is False

    def test_no_world_given_does_not_raise(self):
        m = GameMap(width=3, height=3)
        m.initialize(offset_x=0, offset_y=0)
        m.update_biomes({(0, 0)}, config.BIOME_FOREST)  # ne doit pas lever
