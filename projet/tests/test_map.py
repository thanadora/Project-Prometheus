import math
from collections import Counter

import config
from map import GameMap, _fertility_to_biome, _humidity_biome, stretch_altitude, altitude_band


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


class TestHumidityBiome:
    """_humidity_biome() décide forêt/prairie/désert en mélangeant fertilité
    et humidité (voir HUMIDITY_INFLUENCE) -- l'eau, elle, reste décidée par
    la seule fertilité, inchangée."""

    def test_below_water_threshold_is_still_water_regardless_of_humidity(self):
        low_fertility = config.WATER_THRESHOLD - 0.01
        assert _humidity_biome(low_fertility, 0.0) == config.BIOME_WATER
        assert _humidity_biome(low_fertility, 1.0) == config.BIOME_WATER

    def test_zero_influence_matches_pure_fertility_behaviour(self):
        # HUMIDITY_INFLUENCE=0 -> comportement d'origine, identique à
        # _fertility_to_biome() quelle que soit l'humidité.
        original = config.HUMIDITY_INFLUENCE
        config.HUMIDITY_INFLUENCE = 0.0
        try:
            for fertility in [0.3, 0.42, 0.5, 0.7, 0.95]:
                for humidity in [0.0, 0.5, 1.0]:
                    assert _humidity_biome(fertility, humidity) == _fertility_to_biome(fertility)
        finally:
            config.HUMIDITY_INFLUENCE = original

    def test_high_humidity_can_turn_borderline_desert_into_forest(self):
        # Une fertilité tout juste au-dessus du seuil désert doit pouvoir
        # basculer en forêt avec une humidité maximale -- la preuve que la
        # forêt ne dépend plus uniquement de la proximité de l'eau.
        borderline_desert = config.PRAIRIE_THRESHOLD + 0.02
        assert _fertility_to_biome(borderline_desert) == config.BIOME_DESERT
        assert _humidity_biome(borderline_desert, 1.0) == config.BIOME_FOREST

    def test_low_humidity_can_turn_borderline_forest_into_desert(self):
        # Symétriquement : une fertilité tout juste au-dessus du seuil de
        # l'eau (jusque-là toujours forêt, collée au lac) doit pouvoir
        # devenir désert avec une humidité minimale -- un désert peut
        # border un lac.
        borderline_forest = config.WATER_THRESHOLD + 0.05
        assert _fertility_to_biome(borderline_forest) == config.BIOME_FOREST
        assert _humidity_biome(borderline_forest, 0.0) == config.BIOME_DESERT

    def test_dryness_shift_never_escapes_the_valid_range(self):
        # Le décalage additif est borné explicitement à [0,1] -- une
        # fertilité déjà maximale combinée à une humidité minimale (donc un
        # décalage vers le sec) ne doit jamais produire une valeur hors
        # limites ni planter.
        assert _humidity_biome(1.0, 0.0) == config.BIOME_DESERT


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

    def test_get_altitude_always_neutral_when_module_disabled(self):
        # Avec ENABLE_ALTITUDE=False, get_altitude() ne doit jamais regarder
        # le bruit généré, même si altitude_map contient une autre valeur.
        config.ENABLE_ALTITUDE = False
        m = GameMap(width=6, height=6)
        m.initialize(offset_x=3, offset_y=3)
        assert m.get_altitude(2, 2) == 0.5
        assert m.altitude_map == {}  # jamais rempli quand le module est OFF

    def test_get_altitude_generates_on_demand_in_infinite_mode(self):
        # En mode infini, get_altitude() peut être appelé sur une case jamais
        # visitée via get_biome() d'abord : elle doit se générer elle-même.
        m = GameMap(width=10, height=10, infinite=True)
        m.initialize(offset_x=0, offset_y=0)
        assert (5, 5) not in m.altitude_map
        altitude = m.get_altitude(5, 5)
        assert 0.0 <= altitude <= 1.0
        assert (5, 5) in m.biome_map  # la case a bien été générée au passage

    def test_get_altitude_on_demand_matches_get_biome_altitude(self):
        # La même case doit avoir la même altitude, qu'on l'aborde d'abord
        # par get_biome() ou par get_altitude() (cohérence documentée dans
        # le docstring de get_altitude).
        m1 = GameMap(width=10, height=10, infinite=True)
        m1.initialize(offset_x=9, offset_y=9)
        alt_first = m1.get_altitude(3, -4)

        m2 = GameMap(width=10, height=10, infinite=True)
        m2.initialize(offset_x=9, offset_y=9)
        m2.get_biome(3, -4)
        alt_second = m2.altitude_map[(3, -4)]

        assert alt_first == alt_second


class TestStretchAltitude:
    def test_neutral_altitude_stays_neutral(self):
        assert stretch_altitude(0.5) == 0.5

    def test_extremes_map_to_zero_and_one(self):
        assert math.isclose(stretch_altitude(1.0), 1.0, abs_tol=1e-9)
        assert math.isclose(stretch_altitude(0.0), 0.0, abs_tol=1e-9)

    def test_symmetric_around_neutral(self):
        for d in (0.05, 0.2, 0.4):
            above = stretch_altitude(0.5 + d) - 0.5
            below = 0.5 - stretch_altitude(0.5 - d)
            assert math.isclose(above, below, abs_tol=1e-9)

    def test_monotonically_increasing(self):
        values = [stretch_altitude(a / 20) for a in range(21)]
        assert values == sorted(values)

    def test_stretches_values_away_from_center(self):
        # C'est tout le but de la fonction : un écart donné à 0.5 doit être
        # amplifié (sauf exactement au centre ou aux extrêmes).
        raw = 0.5 + 0.1
        assert stretch_altitude(raw) - 0.5 > raw - 0.5


class TestAltitudeBand:
    def test_neutral_altitude_gives_middle_band(self):
        # ALTITUDE_BANDS=5 par défaut -> bande 2 = la bande du milieu.
        mid_band = config.ALTITUDE_BANDS // 2
        assert altitude_band(0.5) == mid_band

    def test_max_altitude_gives_last_band(self):
        assert altitude_band(1.0) == config.ALTITUDE_BANDS - 1

    def test_min_altitude_gives_first_band(self):
        assert altitude_band(0.0) == 0

    def test_band_always_within_valid_range(self):
        for a in [i / 50 for i in range(51)]:
            band = altitude_band(a)
            assert 0 <= band <= config.ALTITUDE_BANDS - 1

    def test_monotonically_non_decreasing(self):
        bands = [altitude_band(a / 50) for a in range(51)]
        assert bands == sorted(bands)


class TestApplyMountain:
    def test_water_stays_water_even_at_extreme_altitude(self):
        assert GameMap._apply_mountain(config.BIOME_WATER, 0.99) == config.BIOME_WATER

    def test_altitude_at_or_above_snow_threshold_becomes_snow(self):
        assert (
            GameMap._apply_mountain(config.BIOME_PRAIRIE, config.MOUNTAIN_SNOW_THRESHOLD)
            == config.BIOME_MOUNTAIN_SNOW
        )

    def test_altitude_between_rock_and_snow_becomes_rock(self):
        mid = (config.MOUNTAIN_ROCK_THRESHOLD + config.MOUNTAIN_SNOW_THRESHOLD) / 2
        assert GameMap._apply_mountain(config.BIOME_FOREST, mid) == config.BIOME_MOUNTAIN_ROCK

    def test_altitude_at_rock_threshold_becomes_rock(self):
        assert (
            GameMap._apply_mountain(config.BIOME_DESERT, config.MOUNTAIN_ROCK_THRESHOLD)
            == config.BIOME_MOUNTAIN_ROCK
        )

    def test_altitude_below_rock_threshold_keeps_base_biome(self):
        below = config.MOUNTAIN_ROCK_THRESHOLD - 0.01
        assert GameMap._apply_mountain(config.BIOME_DESERT, below) == config.BIOME_DESERT


class TestMountainOverlayIntegration:
    def test_generated_mountains_are_consistent_with_their_own_altitude(self):
        # Fait tourner la vraie génération (bruit compris) et vérifie que
        # partout où une case est montagne, son altitude mémorisée respecte
        # bien les seuils utilisés pour la classer -- ce que ne peut pas
        # garantir un test unitaire de _apply_mountain() seul, puisque
        # _generate_cell() est le seul appelant réel dans le pipeline.
        m = GameMap(width=40, height=40)
        m.initialize(offset_x=7, offset_y=7)
        seen_rock = seen_snow = False
        for pos, biome in m.biome_map.items():
            altitude = m.altitude_map[pos]
            if biome == config.BIOME_MOUNTAIN_SNOW:
                seen_snow = True
                assert altitude >= config.MOUNTAIN_SNOW_THRESHOLD
            elif biome == config.BIOME_MOUNTAIN_ROCK:
                seen_rock = True
                assert config.MOUNTAIN_ROCK_THRESHOLD <= altitude < config.MOUNTAIN_SNOW_THRESHOLD
            elif biome != config.BIOME_WATER:
                assert altitude < config.MOUNTAIN_ROCK_THRESHOLD
        # Sur une grille 40x40, les deux paliers de montagne doivent
        # apparaître -- sinon le test ne vérifierait rien du tout.
        assert seen_rock
        assert seen_snow


class TestHumidityGeneration:
    """Garde-fous d'intégration : si quelqu'un débranchait _compute_humidity()
    de _generate_cell() par erreur, ces tests le détecteraient (contrairement
    aux tests unitaires de _humidity_biome(), qui ne touchent jamais la vraie
    génération)."""

    def test_humidity_actually_changes_the_generated_map(self):
        config.HUMIDITY_INFLUENCE = 0.0
        m_no_humidity = GameMap(width=30, height=30)
        m_no_humidity.initialize(offset_x=11, offset_y=11)

        config.HUMIDITY_INFLUENCE = 0.9
        m_with_humidity = GameMap(width=30, height=30)
        m_with_humidity.initialize(offset_x=11, offset_y=11)

        assert m_no_humidity.biome_map != m_with_humidity.biome_map

    def test_water_placement_never_depends_on_humidity(self):
        # L'eau reste décidée uniquement par la fertilité (voir
        # _humidity_biome) : son emplacement doit être strictement identique
        # quelle que soit HUMIDITY_INFLUENCE.
        config.HUMIDITY_INFLUENCE = 0.0
        m1 = GameMap(width=30, height=30)
        m1.initialize(offset_x=11, offset_y=11)
        water1 = {pos for pos, b in m1.biome_map.items() if b == config.BIOME_WATER}

        config.HUMIDITY_INFLUENCE = 0.9
        m2 = GameMap(width=30, height=30)
        m2.initialize(offset_x=11, offset_y=11)
        water2 = {pos for pos, b in m2.biome_map.items() if b == config.BIOME_WATER}

        assert water1 == water2


class TestFertilityStretch:
    """Régression du diagnostic "eau et désert pas naturels" : le bruit brut
    ne dépasse quasiment jamais [0.24, 0.75] (voir FERTILITY_CONTRAST dans
    config.py), ce qui rendait eau et désert presque invisibles malgré des
    seuils qui semblaient raisonnables. Ces tests vérifient que l'étirement
    et l'échelle plus large corrigent bien ça au niveau de la vraie
    génération -- pas seulement en théorie sur la fonction de blend."""

    def test_fertility_reaches_near_the_extremes(self):
        m = GameMap(width=1, height=1)
        m.initialize(offset_x=17, offset_y=17)
        values = [m._compute_fertility(x, y) for x in range(250) for y in range(120)]
        assert min(values) < 0.22
        assert max(values) > 0.78

    def test_water_and_desert_are_meaningfully_represented(self):
        m = GameMap(width=100, height=60)
        m.initialize(offset_x=17, offset_y=17)
        counts = Counter(m.biome_map.values())
        total = sum(counts.values())
        assert counts.get(config.BIOME_WATER, 0) / total > 0.08
        assert counts.get(config.BIOME_DESERT, 0) / total > 0.08

    def test_water_forms_coherent_lakes_not_scattered_ponds(self):
        # À l'ancienne échelle (10, plus fine que l'altitude/l'humidité),
        # l'eau se répartissait en dizaines de mares minuscules et
        # déconnectées. Avec FERTILITY_NOISE_SCALE plus large, on doit
        # trouver au moins un lac (composante connexe de cases d'eau)
        # nettement plus grand qu'une poignée de cases.
        m = GameMap(width=100, height=60)
        m.initialize(offset_x=17, offset_y=17)
        water = {pos for pos, b in m.biome_map.items() if b == config.BIOME_WATER}

        def component(start, remaining):
            stack, seen = [start], {start}
            while stack:
                x, y = stack.pop()
                for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    n = (x + dx, y + dy)
                    if n in remaining and n not in seen:
                        seen.add(n)
                        stack.append(n)
            return seen

        remaining = set(water)
        largest = 0
        while remaining:
            comp = component(next(iter(remaining)), remaining)
            largest = max(largest, len(comp))
            remaining -= comp
        assert largest > 30


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
