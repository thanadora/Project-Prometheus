import random

import config
from policy import HardcodedPolicy, RandomPolicy
from actions import (
    ACTION_UP, ACTION_DOWN, ACTION_LEFT, ACTION_RIGHT, ACTION_IDLE,
    ACTION_DRINK, ACTION_PICKUP, ACTION_EAT, ACTION_VOTE_MIGRATE,
)

from tests.conftest import make_agent


def perception(**overrides):
    base = {
        "food_dx": 0, "food_dy": 0, "food_dist": -1,
        "water_dx": 0, "water_dy": 0, "water_dist": -1,
        "adjacent_water": False, "heard_letters": [],
    }
    base.update(overrides)
    return base


class TestHardcodedFreeActions:
    def test_votes_migrate_when_energy_low(self):
        agent = make_agent(energy=config.MIGRATION_DISTRESS_ENERGY - 1, thirst=50, age=0)
        assert HardcodedPolicy()._free_actions(agent) == [ACTION_VOTE_MIGRATE]

    def test_votes_migrate_when_thirst_low(self):
        agent = make_agent(energy=50, thirst=config.MIGRATION_DISTRESS_THIRST - 1, age=0)
        assert HardcodedPolicy()._free_actions(agent) == [ACTION_VOTE_MIGRATE]

    def test_votes_migrate_when_old(self):
        agent = make_agent(energy=50, thirst=50, age=config.MIGRATION_AGE_THRESHOLD)
        assert HardcodedPolicy()._free_actions(agent) == [ACTION_VOTE_MIGRATE]

    def test_no_vote_when_healthy(self):
        agent = make_agent(energy=50, thirst=50, age=0)
        assert HardcodedPolicy()._free_actions(agent) == []

    def test_no_vote_when_migration_disabled(self):
        config.ENABLE_MIGRATION = False
        agent = make_agent(energy=0, thirst=0, age=9999)
        assert HardcodedPolicy()._free_actions(agent) == []


class TestHardcodedDecideReproduce:
    def test_reproduces_when_thresholds_met(self):
        agent = make_agent(energy=81, thirst=41)
        assert HardcodedPolicy().decide_reproduce(agent, None) is True

    def test_does_not_reproduce_when_energy_too_low(self):
        agent = make_agent(energy=80, thirst=41)
        assert HardcodedPolicy().decide_reproduce(agent, None) is False

    def test_does_not_reproduce_when_thirst_too_low(self):
        agent = make_agent(energy=81, thirst=40)
        assert HardcodedPolicy().decide_reproduce(agent, None) is False

    def test_disabled_by_config(self):
        config.ENABLE_REPRODUCTION = False
        agent = make_agent(energy=100, thirst=100)
        assert HardcodedPolicy().decide_reproduce(agent, None) is False


class TestHardcodedTimedActionThirst:
    def test_drinks_when_critical_and_adjacent(self):
        agent = make_agent(thirst=config.THIRST_CRITICAL - 1)
        agent.perception = perception(adjacent_water=True, water_dist=1)
        assert HardcodedPolicy()._timed_action(agent) == ACTION_DRINK

    def test_moves_toward_water_when_critical_and_visible_not_adjacent(self):
        agent = make_agent(thirst=config.THIRST_CRITICAL - 1)
        agent.perception = perception(water_dx=3, water_dy=0, water_dist=3)
        assert HardcodedPolicy()._timed_action(agent) == ACTION_RIGHT

    def test_moves_vertically_toward_water_when_that_axis_dominates(self):
        agent = make_agent(thirst=config.THIRST_CRITICAL - 1)
        agent.perception = perception(water_dx=0, water_dy=-3, water_dist=3)
        assert HardcodedPolicy()._timed_action(agent) == ACTION_UP

    def test_thirst_not_critical_does_not_trigger_water_seeking(self):
        agent = make_agent(thirst=config.THIRST_CRITICAL + 10)
        agent.perception = perception(adjacent_water=True, water_dist=1)
        assert HardcodedPolicy()._timed_action(agent) != ACTION_DRINK

    def test_thirst_logic_skipped_when_thirst_disabled(self):
        config.ENABLE_THIRST = False
        agent = make_agent(thirst=0)
        agent.perception = perception(adjacent_water=True, water_dist=1)
        assert HardcodedPolicy()._timed_action(agent) != ACTION_DRINK


class TestHardcodedTimedActionInventory:
    def test_eats_from_inventory_when_energy_low_and_has_food(self):
        agent = make_agent(energy=30, thirst=100)
        agent.inventory = [{"type": config.OBJECT_TYPE_FOOD, "value": 10}]
        agent.perception = perception()
        assert HardcodedPolicy()._timed_action(agent) == ACTION_EAT

    def test_does_not_eat_from_empty_inventory(self):
        agent = make_agent(energy=30, thirst=100)
        agent.inventory = []
        agent.perception = perception()
        assert HardcodedPolicy()._timed_action(agent) != ACTION_EAT

    def test_picks_up_food_when_standing_on_it(self):
        agent = make_agent(energy=100, thirst=100)
        agent.inventory = []
        agent.perception = perception(food_dist=0)
        assert HardcodedPolicy()._timed_action(agent) == ACTION_PICKUP

    def test_does_not_pick_up_when_inventory_full(self):
        agent = make_agent(energy=100, thirst=100)
        agent.inventory = [{"type": config.OBJECT_TYPE_FOOD, "value": 1}] * config.INVENTORY_SIZE
        agent.perception = perception(food_dist=0)
        assert HardcodedPolicy()._timed_action(agent) != ACTION_PICKUP

    def test_inventory_logic_skipped_when_disabled(self):
        config.ENABLE_INVENTORY = False
        agent = make_agent(energy=100, thirst=100)
        agent.inventory = [{"type": config.OBJECT_TYPE_FOOD, "value": 10}]
        agent.perception = perception(food_dist=0)
        assert HardcodedPolicy()._timed_action(agent) != ACTION_PICKUP
        assert HardcodedPolicy()._timed_action(agent) != ACTION_EAT


class TestHardcodedTimedActionFoodSeeking:
    def test_moves_toward_food_horizontally(self):
        agent = make_agent(energy=100, thirst=100)
        agent.inventory = []
        agent.perception = perception(food_dx=5, food_dy=0, food_dist=5)
        assert HardcodedPolicy()._timed_action(agent) == ACTION_RIGHT

    def test_moves_toward_food_vertically(self):
        agent = make_agent(energy=100, thirst=100)
        agent.inventory = []
        agent.perception = perception(food_dx=0, food_dy=-5, food_dist=5)
        assert HardcodedPolicy()._timed_action(agent) == ACTION_UP

    def test_wanders_randomly_when_no_food_known(self, monkeypatch):
        agent = make_agent(energy=100, thirst=100)
        agent.inventory = []
        agent.perception = perception(food_dist=-1)
        monkeypatch.setattr(random, "choice", lambda seq: ACTION_IDLE)
        assert HardcodedPolicy()._timed_action(agent) == ACTION_IDLE


class TestRandomPolicy:
    def test_decide_returns_a_valid_movement_or_idle_action(self):
        agent = make_agent()
        valid = {ACTION_UP, ACTION_DOWN, ACTION_LEFT, ACTION_RIGHT, ACTION_IDLE}
        for _ in range(30):
            _, action = RandomPolicy().decide(agent, None)
            assert action in valid

    def test_never_speaks_when_communication_disabled(self):
        config.ENABLE_COMMUNICATION = False
        agent = make_agent()
        for _ in range(30):
            free_actions, _ = RandomPolicy().decide(agent, None)
            assert free_actions == []

    def test_can_speak_when_communication_enabled(self, monkeypatch):
        config.ENABLE_COMMUNICATION = True
        agent = make_agent()
        monkeypatch.setattr(random, "random", lambda: 0.0)  # < 0.3 -> parle
        monkeypatch.setattr(random, "randrange", lambda n: 0)
        free_actions, _ = RandomPolicy().decide(agent, None)
        assert len(free_actions) == 1

    def test_decide_reproduce_is_probabilistic_around_one_percent(self, monkeypatch):
        agent = make_agent()
        monkeypatch.setattr(random, "random", lambda: 0.005)
        assert RandomPolicy().decide_reproduce(agent, None) is True
        monkeypatch.setattr(random, "random", lambda: 0.5)
        assert RandomPolicy().decide_reproduce(agent, None) is False
