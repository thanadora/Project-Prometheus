import json

import pytest

import config
from save import save_world, load_world, SaveFileError
from policy import HardcodedPolicy, RandomPolicy
from policy_registry import default_policy_name, policy_name

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

    def test_unknown_policy_name_falls_back_to_default(self, tmp_path):
        # Retirer une IA du registre ne doit pas rendre les anciennes
        # sauvegardes impossibles à charger : repli documenté sur la policy
        # par défaut (avec avertissement dans les logs).
        world = make_world(width=5, height=5)
        world.agents = [make_agent(id=1)]
        path = tmp_path / "save.json"
        save_world(world, str(path))

        with open(path) as f:
            data = json.load(f)
        data["agents"][0]["policy"] = "PolicyRetirée"
        with open(path, "w") as f:
            json.dump(data, f)

        loaded = load_world(str(path))
        assert policy_name(loaded.agents[0].policy) == default_policy_name()

    def test_corrupted_json_raises_explicit_save_error(self, tmp_path):
        path = tmp_path / "broken.json"
        path.write_text("{not valid json")
        with pytest.raises(SaveFileError):
            load_world(str(path))

    def test_missing_required_key_raises_explicit_save_error(self, tmp_path):
        """Un fichier de sauvegarde tronqué ou partiellement corrompu (mais
        toujours du JSON valide) doit produire une SaveFileError claire,
        pas un KeyError brut remonté du fin fond du chargement."""
        world = make_world(width=5, height=5)
        path = tmp_path / "save.json"
        save_world(world, str(path))
        with open(path) as f:
            data = json.load(f)
        del data["tick"]
        with open(path, "w") as f:
            json.dump(data, f)
        with pytest.raises(SaveFileError, match="tick"):
            load_world(str(path))

    def test_world_dimensions_are_persisted_and_used_on_load(self, tmp_path):
        """Les dimensions du monde sont désormais écrites dans la sauvegarde
        et relues au chargement, même si la configuration courante a changé
        entre-temps."""
        original_w, original_h = config.WORLD_WIDTH, config.WORLD_HEIGHT
        try:
            world = make_world(width=50, height=50)
            path = tmp_path / "save.json"
            save_world(world, str(path))

            config.WORLD_WIDTH, config.WORLD_HEIGHT = 5, 5
            loaded = load_world(str(path))

            assert (loaded.width, loaded.height) == (50, 50)
        finally:
            config.WORLD_WIDTH, config.WORLD_HEIGHT = original_w, original_h

    def test_nonexistent_file_raises_save_file_error(self, tmp_path):
        with pytest.raises(SaveFileError, match="introuvable"):
            load_world(str(tmp_path / "nope.json"))

    def test_agent_missing_field_raises_save_file_error(self, tmp_path):
        world = make_world(width=5, height=5)
        world.agents = [make_agent(id=1)]
        path = tmp_path / "save.json"
        save_world(world, str(path))
        with open(path) as f:
            data = json.load(f)
        del data["agents"][0]["energy"]
        with open(path, "w") as f:
            json.dump(data, f)
        with pytest.raises(SaveFileError, match="Agent"):
            load_world(str(path))


class TestSaveLoadNewState:
    def test_fatigue_round_trips(self, tmp_path):
        world = make_world(width=5, height=5)
        world.agents = [make_agent(id=1, fatigue=42.5)]
        path = tmp_path / "save.json"
        save_world(world, str(path))
        loaded = load_world(str(path))
        assert loaded.agents[0].fatigue == 42.5

    def test_sickness_round_trips(self, tmp_path):
        world = make_world(width=5, height=5)
        world.agents = [make_agent(id=1, sick_ticks=42)]
        path = tmp_path / "save.json"
        save_world(world, str(path))
        loaded = load_world(str(path))
        assert loaded.agents[0].sick_ticks == 42

    def test_food_age_round_trips(self, tmp_path):
        world = make_world(width=5, height=5, food_amounts={(2, 2): 2})
        world.food.food_age[(2, 2)] = 77
        path = tmp_path / "save.json"
        save_world(world, str(path))
        loaded = load_world(str(path))
        assert loaded.food.food_age[(2, 2)] == 77

    def test_catastrophe_state_round_trips(self, tmp_path):
        world = make_world(width=5, height=5)
        world.burning[(1, 1)] = 10
        world.burnt[(2, 2)] = 300
        world.flooded[(3, 3)] = 40
        path = tmp_path / "save.json"
        save_world(world, str(path))
        loaded = load_world(str(path))
        assert loaded.burning == {(1, 1): 10}
        assert loaded.burnt == {(2, 2): 300}
        assert loaded.flooded == {(3, 3): 40}

    def test_old_save_without_new_fields_still_loads(self, tmp_path):
        """Compatibilité ascendante : une sauvegarde d'avant les catastrophes
        (sans burning/burnt/flooded/fatigue/food_age) se charge sans erreur."""
        world = make_world(width=5, height=5)
        world.agents = [make_agent(id=1)]
        path = tmp_path / "save.json"
        save_world(world, str(path))
        with open(path) as f:
            data = json.load(f)
        for key in ("food_age", "burning", "burnt", "flooded"):
            del data[key]
        for agent in data["agents"]:
            del agent["fatigue"]
            del agent["sick_ticks"]
        with open(path, "w") as f:
            json.dump(data, f)

        loaded = load_world(str(path))
        assert loaded.agents[0].fatigue == 0.0
        assert loaded.agents[0].sick_ticks == 0
        assert loaded.burning == {} and loaded.burnt == {} and loaded.flooded == {}
