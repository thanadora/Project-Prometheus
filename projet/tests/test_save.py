import json

import pytest

import config
from save import save_world, load_world
from policy import HardcodedPolicy, RandomPolicy
from policy_registry import policy_name

from tests.conftest import make_world, make_agent


class TestSaveLoadRoundTrip:
    def test_world_level_fields_round_trip(self, tmp_path):
        world = make_world(width=config.WORLD_WIDTH, height=config.WORLD_HEIGHT,
                            tick=123, weather=config.WEATHER_RAIN, soil_moisture=0.42)
        world.death_count = 3
        world.migration_count = 2
        world.last_migration_tick = 100
        path = tmp_path / "save.json"

        save_world(world, str(path))
        loaded = load_world(str(path))

        assert loaded.tick == 123
        assert loaded.weather == config.WEATHER_RAIN
        assert loaded.soil_moisture == 0.42
        assert loaded.death_count == 3
        assert loaded.migration_count == 2
        assert loaded.last_migration_tick == 100

    def test_agents_round_trip(self, tmp_path):
        world = make_world(width=config.WORLD_WIDTH, height=config.WORLD_HEIGHT)
        agent = make_agent(id=7, x=3, y=4, energy=55.5, thirst=44.4, age=12,
                            generation=2, born_tick=5)
        agent.policy = HardcodedPolicy()
        agent.inventory = [{"type": config.OBJECT_TYPE_FOOD, "value": 3}]
        world.agents = [agent]
        path = tmp_path / "save.json"

        save_world(world, str(path))
        loaded = load_world(str(path))

        assert len(loaded.agents) == 1
        a = loaded.agents[0]
        assert (a.id, a.x, a.y) == (7, 3, 4)
        assert a.energy == 55.5
        assert a.thirst == 44.4
        assert a.age == 12
        assert a.generation == 2
        assert a.born_tick == 5
        assert a.inventory == [{"type": config.OBJECT_TYPE_FOOD, "value": 3}]
        assert policy_name(a.policy) == "Hardcoded"

    def test_random_policy_name_round_trips_too(self, tmp_path):
        world = make_world(width=config.WORLD_WIDTH, height=config.WORLD_HEIGHT)
        agent = make_agent(id=1, x=0, y=0)
        agent.policy = RandomPolicy()
        world.agents = [agent]
        path = tmp_path / "save.json"
        save_world(world, str(path))
        loaded = load_world(str(path))
        assert policy_name(loaded.agents[0].policy) == "Random"

    def test_biome_and_food_maps_round_trip(self, tmp_path):
        world = make_world(width=5, height=5, overrides={(1, 1): config.BIOME_WATER},
                            food_amounts={(2, 2): 4})
        path = tmp_path / "save.json"
        save_world(world, str(path))
        loaded = load_world(str(path))
        assert loaded.map.biome_map[(1, 1)] == config.BIOME_WATER
        assert loaded.food.food_map[(2, 2)] == 4
        assert (2, 2) in loaded.food.food_positions

    def test_dead_agents_round_trip_as_dead(self, tmp_path):
        world = make_world(width=5, height=5)
        world.agents = [make_agent(id=1, alive=False)]
        path = tmp_path / "save.json"
        save_world(world, str(path))
        loaded = load_world(str(path))
        assert loaded.agents[0].alive is False


class TestSaveLoadEdgeCases:
    def test_legacy_inventory_format_ints_are_normalized_to_dicts(self, tmp_path):
        # Compat ascendante : un ancien fichier de sauvegarde pourrait avoir
        # un inventaire sous forme de simples entiers plutôt que de dicts.
        world = make_world(width=5, height=5)
        world.agents = [make_agent(id=1)]
        path = tmp_path / "save.json"
        save_world(world, str(path))

        with open(path) as f:
            data = json.load(f)
        data["agents"][0]["inventory"] = [7]  # format legacy
        with open(path, "w") as f:
            json.dump(data, f)

        loaded = load_world(str(path))
        assert loaded.agents[0].inventory == [{"type": config.OBJECT_TYPE_FOOD, "value": 7}]

    def test_missing_policy_name_defaults_to_hardcoded(self, tmp_path):
        world = make_world(width=5, height=5)
        world.agents = [make_agent(id=1)]  # policy=None par défaut
        path = tmp_path / "save.json"
        save_world(world, str(path))
        loaded = load_world(str(path))
        assert policy_name(loaded.agents[0].policy) == "Hardcoded"

    def test_corrupted_json_raises(self, tmp_path):
        path = tmp_path / "broken.json"
        path.write_text("{not valid json")
        with pytest.raises(json.JSONDecodeError):
            load_world(str(path))

    def test_known_fragility_missing_required_key_raises_keyerror(self, tmp_path):
        """Documente un manque de robustesse existant : load_world() accède
        directement à data["tick"], data["weather"], etc. sans valeur par
        défaut ni message d'erreur clair. Un fichier de sauvegarde tronqué
        ou partiellement corrompu (mais toujours du JSON valide) fait planter
        le chargement avec un KeyError peu explicite plutôt qu'un message
        du type "fichier de sauvegarde invalide"."""
        world = make_world(width=5, height=5)
        path = tmp_path / "save.json"
        save_world(world, str(path))
        with open(path) as f:
            data = json.load(f)
        del data["tick"]
        with open(path, "w") as f:
            json.dump(data, f)
        with pytest.raises(KeyError):
            load_world(str(path))

    def test_known_quirk_world_dimensions_are_not_persisted(self, tmp_path):
        """Documente un autre manque : World.width/height ne sont jamais
        écrits dans le fichier de sauvegarde. Au chargement, load_world()
        utilise TOUJOURS config.WORLD_WIDTH / config.WORLD_HEIGHT courants
        plutôt que la taille du monde effectivement sauvegardé. Si la config
        a changé entre-temps (ou si on charge une sauvegarde faite avec une
        autre taille de monde), la carte et les agents chargés peuvent se
        retrouver hors des nouvelles dimensions du monde sans avertissement."""
        original_w, original_h = config.WORLD_WIDTH, config.WORLD_HEIGHT
        try:
            world = make_world(width=50, height=50)
            path = tmp_path / "save.json"
            save_world(world, str(path))

            config.WORLD_WIDTH, config.WORLD_HEIGHT = 5, 5
            loaded = load_world(str(path))

            # Le monde chargé a la taille de la config ACTUELLE (5x5), pas
            # celle (50x50) du monde effectivement sauvegardé.
            assert (loaded.width, loaded.height) == (5, 5)
        finally:
            config.WORLD_WIDTH, config.WORLD_HEIGHT = original_w, original_h
