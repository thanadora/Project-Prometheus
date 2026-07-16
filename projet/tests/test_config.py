"""
test_config.py — Vérifie les invariants que config.py doit respecter pour que
le reste du moteur (map.py, weather.py, food.py...) se comporte correctement.
Ce ne sont pas des "vrais" tests de comportement, mais un garde-fou : si
quelqu'un modifie config.py sans faire attention (ex: réordonner un seuil),
ces tests doivent le signaler avant que ça casse silencieusement ailleurs.
"""
import config


class TestBiomeThresholds:
    def test_thresholds_are_strictly_increasing(self):
        # map._fertility_to_biome() suppose cet ordre pour classer les biomes
        # par plage de fertilité croissante. S'il est rompu, des biomes
        # deviennent inatteignables ou se chevauchent.
        assert config.WATER_THRESHOLD < config.FOREST_THRESHOLD
        assert config.FOREST_THRESHOLD < config.PRAIRIE_THRESHOLD

    def test_thresholds_within_unit_range(self):
        for t in (config.WATER_THRESHOLD, config.FOREST_THRESHOLD, config.PRAIRIE_THRESHOLD):
            assert 0.0 <= t <= 1.0

    def test_every_biome_has_a_color(self):
        for biome in (config.BIOME_WATER, config.BIOME_DESERT,
                      config.BIOME_PRAIRIE, config.BIOME_FOREST):
            assert biome in config.BIOME_COLORS


class TestFoodTypes:
    def test_water_has_no_food_type(self):
        assert config.BIOME_WATER not in config.FOOD_TYPES

    def test_land_biomes_have_food_types(self):
        for biome in (config.BIOME_DESERT, config.BIOME_PRAIRIE, config.BIOME_FOREST):
            assert biome in config.FOOD_TYPES

    def test_food_type_fields_are_positive(self):
        for entry in config.FOOD_TYPES.values():
            assert entry["gain"] > 0
            assert entry["respawn"] > 0
            assert entry["capacity"] > 0


class TestAlphabet:
    def test_alphabet_length_matches_size(self):
        assert len(config.ALPHABET) == config.ALPHABET_SIZE

    def test_alphabet_letters_are_unique(self):
        assert len(set(config.ALPHABET)) == len(config.ALPHABET)


class TestWeatherTables:
    _weathers = None

    def setup_method(self):
        self._weathers = [
            config.WEATHER_CLEAR, config.WEATHER_RAIN, config.WEATHER_STORM,
            config.WEATHER_DROUGHT, config.WEATHER_FROST,
        ]

    def test_every_weather_has_a_name(self):
        for w in self._weathers:
            assert w in config.WEATHER_NAMES

    def test_every_weather_has_vision_and_move_cost_and_moisture(self):
        for w in self._weathers:
            assert w in config.WEATHER_VISION
            assert w in config.WEATHER_MOVE_COST
            assert w in config.WEATHER_MOISTURE_DELTA

    def test_season_weather_probs_cover_all_weathers_and_are_positive_sum(self):
        for season, probs in config.SEASON_WEATHER_PROBS.items():
            assert len(probs) == len(self._weathers)
            assert sum(probs) > 0
            assert all(p >= 0 for p in probs)

    def test_every_season_has_a_probability_table(self):
        for season in (config.SEASON_SPRING, config.SEASON_SUMMER,
                       config.SEASON_AUTUMN, config.SEASON_WINTER):
            assert season in config.SEASON_WEATHER_PROBS


class TestKeyBindings:
    def test_every_binding_has_a_readable_label(self):
        assert set(config.KEY_BINDINGS.keys()) == set(config.KEY_BINDING_LABELS.keys())


class TestSoilMoisture:
    def test_min_below_max(self):
        assert config.SOIL_MOISTURE_MIN < config.SOIL_MOISTURE_MAX

    def test_init_within_bounds(self):
        assert config.SOIL_MOISTURE_MIN <= config.SOIL_MOISTURE_INIT <= config.SOIL_MOISTURE_MAX


class TestMigrationThresholds:
    def test_vote_threshold_is_a_fraction(self):
        assert 0.0 < config.MIGRATION_VOTE_THRESHOLD <= 1.0

    def test_age_threshold_below_max_age(self):
        assert config.MIGRATION_AGE_THRESHOLD < config.MAX_AGE
