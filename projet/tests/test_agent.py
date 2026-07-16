import random

import config
from agent import (
    Agent, perceive, build_observation, apply_free_action, apply_timed_action,
    _update_thirst, update_agent_life, think,
)
from actions import (
    ACTION_UP, ACTION_DOWN, ACTION_LEFT, ACTION_RIGHT, ACTION_IDLE,
    ACTION_DRINK, ACTION_PICKUP, ACTION_EAT, ACTION_VOTE_MIGRATE, action_speak,
)

from tests.conftest import make_world, make_agent


# ---------------------------------------------------------------------------
# perceive()
# ---------------------------------------------------------------------------
class TestPerceiveFood:
    def test_finds_food_within_vision(self):
        world = make_world(width=10, height=10, food_amounts={(5, 3): 1})
        agent = make_agent(x=5, y=5)
        result = perceive(agent, world)
        assert result["food_dx"] == 0
        assert result["food_dy"] == -2
        assert result["food_dist"] == 2

    def test_ignores_food_outside_vision_radius(self):
        far = config.VISION_RADIUS + 50
        world = make_world(width=200, height=200, food_amounts={(100 + far, 100): 1})
        agent = make_agent(x=100, y=100)
        result = perceive(agent, world)
        assert result["food_dist"] == -1

    def test_no_food_gives_dist_minus_one(self):
        world = make_world(width=10, height=10)
        agent = make_agent(x=5, y=5)
        result = perceive(agent, world)
        assert result["food_dist"] == -1
        assert result["food_dx"] == 0
        assert result["food_dy"] == 0

    def test_picks_closest_food_among_several(self):
        world = make_world(width=10, height=10, food_amounts={(5, 6): 1, (5, 8): 1})
        agent = make_agent(x=5, y=5)
        result = perceive(agent, world)
        assert result["food_dy"] == 1  # (5,6) est plus proche que (5,8)


class TestPerceiveWater:
    def test_finds_adjacent_water(self):
        world = make_world(width=10, height=10, overrides={(6, 5): config.BIOME_WATER})
        agent = make_agent(x=5, y=5)
        result = perceive(agent, world)
        assert result["adjacent_water"] is True
        assert result["water_dx"] == 1
        assert result["water_dy"] == 0
        assert result["water_dist"] == 1.0

    def test_no_water_in_range_gives_dist_minus_one(self):
        world = make_world(width=10, height=10)  # tout praire, pas d'eau
        agent = make_agent(x=5, y=5)
        result = perceive(agent, world)
        assert result["water_dist"] == -1
        assert result["adjacent_water"] is False

    def test_distant_water_not_adjacent(self):
        world = make_world(width=10, height=10, overrides={(9, 5): config.BIOME_WATER})
        agent = make_agent(x=5, y=5)
        result = perceive(agent, world)
        assert result["adjacent_water"] is False
        assert result["water_dist"] == 4.0

    def test_water_ignored_when_thirst_disabled(self):
        config.ENABLE_THIRST = False
        world = make_world(width=10, height=10, overrides={(6, 5): config.BIOME_WATER})
        agent = make_agent(x=5, y=5)
        result = perceive(agent, world)
        assert result["water_dist"] == -1
        assert result["adjacent_water"] is False


class TestPerceiveCommunication:
    def test_hears_nearby_speaking_agent(self):
        world = make_world(width=10, height=10)
        listener = make_agent(id=1, x=5, y=5)
        speaker = make_agent(id=2, x=6, y=5)
        speaker.spoken_letter = "A"
        world.agents = [listener, speaker]
        result = perceive(listener, world)
        assert len(result["heard_letters"]) == 1
        heard = result["heard_letters"][0]
        assert heard["letter"] == "A"
        assert heard["from_id"] == 2
        assert heard["dx"] == 1 and heard["dy"] == 0

    def test_does_not_hear_self(self):
        world = make_world(width=10, height=10)
        agent = make_agent(id=1, x=5, y=5)
        agent.spoken_letter = "A"
        world.agents = [agent]
        result = perceive(agent, world)
        assert result["heard_letters"] == []

    def test_does_not_hear_silent_agents(self):
        world = make_world(width=10, height=10)
        listener = make_agent(id=1, x=5, y=5)
        silent = make_agent(id=2, x=6, y=5)  # spoken_letter=None par défaut
        world.agents = [listener, silent]
        result = perceive(listener, world)
        assert result["heard_letters"] == []

    def test_does_not_hear_dead_agents(self):
        world = make_world(width=10, height=10)
        listener = make_agent(id=1, x=5, y=5)
        dead = make_agent(id=2, x=6, y=5, alive=False)
        dead.spoken_letter = "Z"
        world.agents = [listener, dead]
        result = perceive(listener, world)
        assert result["heard_letters"] == []

    def test_out_of_comm_radius_not_heard(self):
        far = config.COMM_RADIUS + 20
        world = make_world(width=200, height=200)
        listener = make_agent(id=1, x=100, y=100)
        speaker = make_agent(id=2, x=100 + far, y=100)
        speaker.spoken_letter = "B"
        world.agents = [listener, speaker]
        result = perceive(listener, world)
        assert result["heard_letters"] == []

    def test_communication_disabled_returns_no_letters(self):
        config.ENABLE_COMMUNICATION = False
        world = make_world(width=10, height=10)
        listener = make_agent(id=1, x=5, y=5)
        speaker = make_agent(id=2, x=6, y=5)
        speaker.spoken_letter = "A"
        world.agents = [listener, speaker]
        result = perceive(listener, world)
        assert result["heard_letters"] == []


# ---------------------------------------------------------------------------
# build_observation()
# ---------------------------------------------------------------------------
class TestBuildObservation:
    def test_normalizes_energy_and_thirst(self):
        world = make_world(width=10, height=10)
        agent = make_agent(x=5, y=5, energy=config.MAX_ENERGY, thirst=config.MAX_THIRST)
        agent.perception = perceive(agent, world)
        obs = build_observation(agent, world)
        assert obs[3] == 1.0  # energy / MAX_ENERGY
        assert obs[4] == 1.0  # thirst / MAX_THIRST

    def test_food_dist_minus_one_when_no_food_seen(self):
        world = make_world(width=10, height=10)
        agent = make_agent(x=5, y=5)
        agent.perception = perceive(agent, world)
        obs = build_observation(agent, world)
        assert obs[2] == -1

    def test_observation_has_seven_features(self):
        world = make_world(width=10, height=10)
        agent = make_agent(x=5, y=5)
        agent.perception = perceive(agent, world)
        obs = build_observation(agent, world)
        assert len(obs) == 7


# ---------------------------------------------------------------------------
# apply_free_action()
# ---------------------------------------------------------------------------
class TestApplyFreeAction:
    def test_vote_migrate_sets_flag(self):
        agent = make_agent()
        assert apply_free_action(agent, ACTION_VOTE_MIGRATE) is True
        assert agent.vote_migrate is True

    def test_speak_sets_letter(self):
        agent = make_agent()
        ok = apply_free_action(agent, action_speak(0))
        assert ok is True
        assert agent.spoken_letter == config.ALPHABET[0]

    def test_speak_disabled_by_config(self):
        config.ENABLE_COMMUNICATION = False
        agent = make_agent()
        ok = apply_free_action(agent, action_speak(0))
        assert ok is False
        assert agent.spoken_letter is None

    def test_speak_out_of_range_index_fails_cleanly(self):
        agent = make_agent()
        huge = action_speak(len(config.ALPHABET) + 100)
        ok = apply_free_action(agent, huge)
        assert ok is False
        assert agent.spoken_letter is None

    def test_unknown_action_returns_false(self):
        agent = make_agent()
        assert apply_free_action(agent, -1) is False


# ---------------------------------------------------------------------------
# apply_timed_action()
# ---------------------------------------------------------------------------
class TestApplyTimedActionDrink:
    def test_drink_increases_thirst_up_to_max(self):
        world = make_world(width=5, height=5)
        agent = make_agent(x=2, y=2, thirst=config.MAX_THIRST - 1)
        apply_timed_action(agent, world, ACTION_DRINK)
        assert agent.thirst == config.MAX_THIRST

    def test_drink_disabled_is_noop(self):
        config.ENABLE_THIRST = False
        world = make_world(width=5, height=5)
        agent = make_agent(x=2, y=2, thirst=10)
        apply_timed_action(agent, world, ACTION_DRINK)
        assert agent.thirst == 10

    def test_dead_agent_action_is_noop(self):
        world = make_world(width=5, height=5)
        agent = make_agent(x=2, y=2, thirst=10, alive=False)
        apply_timed_action(agent, world, ACTION_DRINK)
        assert agent.thirst == 10


class TestApplyTimedActionInventory:
    def test_pickup_adds_food_to_inventory_and_removes_it_from_ground(self):
        world = make_world(width=5, height=5, food_amounts={(2, 2): 1})
        agent = make_agent(x=2, y=2)
        apply_timed_action(agent, world, ACTION_PICKUP)
        assert len(agent.inventory) == 1
        assert agent.inventory[0]["type"] == config.OBJECT_TYPE_FOOD
        assert world.food.food_map[(2, 2)] == 0

    def test_pickup_on_empty_ground_does_nothing(self):
        world = make_world(width=5, height=5)
        agent = make_agent(x=2, y=2)
        apply_timed_action(agent, world, ACTION_PICKUP)
        assert agent.inventory == []

    def test_pickup_respects_inventory_capacity(self):
        world = make_world(width=5, height=5, food_amounts={(2, 2): 5})
        agent = make_agent(x=2, y=2)
        agent.inventory = [{"type": config.OBJECT_TYPE_FOOD, "value": 1}] * config.INVENTORY_SIZE
        apply_timed_action(agent, world, ACTION_PICKUP)
        assert len(agent.inventory) == config.INVENTORY_SIZE  # inchangé, plein

    def test_pickup_disabled_by_config(self):
        config.ENABLE_INVENTORY = False
        world = make_world(width=5, height=5, food_amounts={(2, 2): 1})
        agent = make_agent(x=2, y=2)
        apply_timed_action(agent, world, ACTION_PICKUP)
        assert agent.inventory == []
        assert world.food.food_map[(2, 2)] == 1  # pas consommé non plus

    def test_eat_from_inventory_restores_energy_capped(self):
        world = make_world(width=5, height=5)
        agent = make_agent(x=2, y=2, energy=config.MAX_ENERGY - 1)
        agent.inventory = [{"type": config.OBJECT_TYPE_FOOD, "value": 50}]
        apply_timed_action(agent, world, ACTION_EAT)
        assert agent.energy == config.MAX_ENERGY
        assert agent.inventory == []

    def test_eat_empty_inventory_is_noop(self):
        world = make_world(width=5, height=5)
        agent = make_agent(x=2, y=2, energy=30)
        apply_timed_action(agent, world, ACTION_EAT)
        assert agent.energy == 30


class TestApplyTimedActionMovement:
    def test_move_updates_position(self):
        world = make_world(width=5, height=5)
        agent = make_agent(x=2, y=2)
        apply_timed_action(agent, world, ACTION_RIGHT)
        assert (agent.x, agent.y) == (3, 2)

    def test_move_into_water_is_blocked(self):
        world = make_world(width=5, height=5, overrides={(3, 2): config.BIOME_WATER})
        agent = make_agent(x=2, y=2)
        apply_timed_action(agent, world, ACTION_RIGHT)
        assert (agent.x, agent.y) == (2, 2)

    def test_move_costs_energy(self):
        world = make_world(width=5, height=5)
        agent = make_agent(x=2, y=2, energy=50)
        apply_timed_action(agent, world, ACTION_RIGHT)
        assert agent.energy == 50 - (config.MOVE_COST - config.IDLE_COST)

    def test_idle_does_not_cost_move_energy(self):
        world = make_world(width=5, height=5)
        agent = make_agent(x=2, y=2, energy=50)
        apply_timed_action(agent, world, ACTION_IDLE)
        assert (agent.x, agent.y) == (2, 2)
        assert agent.energy == 50

    def test_agent_dies_if_energy_drops_to_zero_from_move(self):
        world = make_world(width=5, height=5)
        agent = make_agent(x=2, y=2, energy=config.MOVE_COST - config.IDLE_COST)
        apply_timed_action(agent, world, ACTION_RIGHT)
        assert agent.alive is False

    def test_out_of_bounds_move_blocked_in_non_toroidal_world(self, monkeypatch):
        # NB: agent.py fait `from config import TOROIDAL_WORLD` (import direct),
        # donc c'est bien agent.TOROIDAL_WORLD qu'il faut patcher pour changer
        # le comportement à l'exécution — patcher config.TOROIDAL_WORLD seul
        # est sans effet ici. Voir test_config_propagation.py pour le détail
        # de cette particularité (bug réel de l'application).
        import agent as agent_module
        monkeypatch.setattr(agent_module, "TOROIDAL_WORLD", False)
        world = make_world(width=3, height=3)
        agent = make_agent(x=0, y=0)
        apply_timed_action(agent, world, ACTION_LEFT)
        assert (agent.x, agent.y) == (0, 0)

    def test_move_wraps_around_in_toroidal_world(self, monkeypatch):
        import agent as agent_module
        monkeypatch.setattr(agent_module, "TOROIDAL_WORLD", True)
        world = make_world(width=3, height=3)
        agent = make_agent(x=0, y=0)
        apply_timed_action(agent, world, ACTION_LEFT)
        assert (agent.x, agent.y) == (2, 0)

    def test_unknown_action_is_noop(self):
        world = make_world(width=5, height=5)
        agent = make_agent(x=2, y=2, energy=50)
        apply_timed_action(agent, world, 9999)
        assert (agent.x, agent.y) == (2, 2)
        assert agent.energy == 50


# ---------------------------------------------------------------------------
# _update_thirst()
# ---------------------------------------------------------------------------
class TestUpdateThirst:
    def test_thirst_decreases_by_normal_rate(self):
        world = make_world(width=5, height=5)
        agent = make_agent(x=2, y=2, thirst=50)
        _update_thirst(agent, world)
        assert agent.thirst == 50 - config.THIRST_RATE

    def test_desert_biome_increases_thirst_rate_during_day(self):
        world = make_world(width=5, height=5, default_biome=config.BIOME_DESERT, tick=0)
        agent = make_agent(x=2, y=2, thirst=50)
        _update_thirst(agent, world)
        assert agent.thirst == 50 - config.THIRST_RATE_DESERT

    def test_thirst_disabled_is_noop(self):
        config.ENABLE_THIRST = False
        world = make_world(width=5, height=5)
        agent = make_agent(x=2, y=2, thirst=50)
        _update_thirst(agent, world)
        assert agent.thirst == 50

    def test_biomes_disabled_uses_base_rate_even_in_desert(self):
        config.ENABLE_BIOMES = False
        world = make_world(width=5, height=5, default_biome=config.BIOME_DESERT)
        agent = make_agent(x=2, y=2, thirst=50)
        _update_thirst(agent, world)
        assert agent.thirst == 50 - config.THIRST_RATE

    def test_thirst_does_not_go_negative(self):
        world = make_world(width=5, height=5)
        agent = make_agent(x=2, y=2, thirst=0)
        _update_thirst(agent, world)
        assert agent.thirst == 0

    def test_zero_thirst_deals_energy_damage(self):
        world = make_world(width=5, height=5)
        agent = make_agent(x=2, y=2, thirst=0, energy=50)
        _update_thirst(agent, world)
        assert agent.energy == 50 - config.THIRST_DAMAGE

    def test_death_when_energy_exhausted_by_thirst_damage(self):
        world = make_world(width=5, height=5)
        agent = make_agent(x=2, y=2, thirst=0, energy=config.THIRST_DAMAGE - 1)
        _update_thirst(agent, world)
        assert agent.alive is False


# ---------------------------------------------------------------------------
# update_agent_life()
# ---------------------------------------------------------------------------
class TestUpdateAgentLife:
    def test_age_increments(self):
        world = make_world(width=5, height=5)
        agent = make_agent(x=2, y=2, age=5, energy=50)
        update_agent_life(agent, world)
        assert agent.age == 6

    def test_dies_of_old_age_when_enabled(self):
        config.ENABLE_AGE_DEATH = True
        world = make_world(width=5, height=5)
        agent = make_agent(x=2, y=2, age=config.MAX_AGE - 1, energy=50)
        update_agent_life(agent, world)
        assert agent.alive is False

    def test_does_not_die_of_old_age_when_disabled(self):
        config.ENABLE_AGE_DEATH = False
        world = make_world(width=5, height=5)
        agent = make_agent(x=2, y=2, age=config.MAX_AGE + 10, energy=50)
        update_agent_life(agent, world)
        assert agent.alive is True

    def test_dies_of_exhaustion(self):
        world = make_world(width=5, height=5)
        agent = make_agent(x=2, y=2, age=1, energy=0.01)
        update_agent_life(agent, world)
        assert agent.alive is False

    def test_thirst_not_updated_when_agent_already_dead_of_age(self):
        config.ENABLE_AGE_DEATH = True
        world = make_world(width=5, height=5)
        agent = make_agent(x=2, y=2, age=config.MAX_AGE - 1, energy=50, thirst=50)
        update_agent_life(agent, world)
        assert agent.thirst == 50  # _update_thirst() jamais appelée (return anticipé)

    def test_idle_cost_higher_at_night(self):
        config.ENABLE_DAY_NIGHT = True
        night_tick = int(config.DAY_DURATION * (1 - config.NIGHT_RATIO)) + 1
        world = make_world(width=5, height=5, tick=night_tick)
        assert world.is_night() is True
        agent = make_agent(x=2, y=2, age=0, energy=50, thirst=50)
        update_agent_life(agent, world)
        expected_loss = config.NIGHT_IDLE_COST + (1 / config.MAX_AGE) * 0.1
        assert agent.energy == 50 - expected_loss


# ---------------------------------------------------------------------------
# think()
# ---------------------------------------------------------------------------
class DummyPolicy:
    def __init__(self, free_actions=None, timed_action=ACTION_IDLE):
        self._free = free_actions or []
        self._timed = timed_action
        self.called_with = None

    def decide(self, agent, world):
        self.called_with = agent.id
        return self._free, self._timed


class TestThink:
    def test_resets_vote_and_spoken_letter_before_deciding(self):
        world = make_world(width=5, height=5)
        agent = make_agent(x=2, y=2)
        agent.vote_migrate = True
        agent.spoken_letter = "X"
        policy = DummyPolicy()
        think(agent, world, policy)
        assert agent.vote_migrate is False
        assert agent.spoken_letter is None

    def test_stores_prev_energy_and_thirst_before_decision(self):
        world = make_world(width=5, height=5)
        agent = make_agent(x=2, y=2, energy=42, thirst=17)
        think(agent, world, DummyPolicy())
        assert agent._prev_energy == 42
        assert agent._prev_thirst == 17

    def test_uses_agent_specific_policy_over_default(self):
        world = make_world(width=5, height=5)
        default_policy = DummyPolicy()
        specific_policy = DummyPolicy()
        agent = make_agent(x=2, y=2)
        agent.policy = specific_policy
        think(agent, world, default_policy)
        assert specific_policy.called_with == agent.id
        assert default_policy.called_with is None

    def test_falls_back_to_default_policy_when_agent_has_none(self):
        world = make_world(width=5, height=5)
        default_policy = DummyPolicy()
        agent = make_agent(x=2, y=2)
        think(agent, world, default_policy)
        assert default_policy.called_with == agent.id

    def test_sets_free_actions_and_pending_action_from_policy(self):
        world = make_world(width=5, height=5)
        policy = DummyPolicy(free_actions=[ACTION_VOTE_MIGRATE], timed_action=ACTION_DRINK)
        agent = make_agent(x=2, y=2)
        think(agent, world, policy)
        assert agent.free_actions == [ACTION_VOTE_MIGRATE]
        assert agent.pending_action == ACTION_DRINK
