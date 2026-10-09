import random

from policy_registry import (
    REGISTRY, default_policy_name, make_policy, policy_name, distribute_policies,
)
from policy import HardcodedPolicy, RandomPolicy, BasePolicy

from tests.conftest import make_agent


class TestRegistryContents:
    def test_registry_contains_builtin_policies(self):
        # Sous-ensemble et non égalité exacte : ajouter une IA au REGISTRY
        # (le moyen documenté d'intégrer un modèle) ne doit pas casser la
        # suite de tests.
        assert {"Hardcoded", "Random"} <= set(REGISTRY.keys())

    def test_each_entry_has_class_description_and_color(self):
        for entry in REGISTRY.values():
            assert "class" in entry and "description" in entry and "color" in entry
            assert issubclass(entry["class"], BasePolicy)


class TestMakePolicy:
    def test_returns_correct_instance_type(self):
        assert isinstance(make_policy("Hardcoded"), HardcodedPolicy)
        assert isinstance(make_policy("Random"), RandomPolicy)

    def test_unknown_name_raises_key_error(self):
        try:
            make_policy("DoesNotExist")
            assert False, "aurait dû lever KeyError"
        except KeyError:
            pass


class TestPolicyName:
    def test_returns_registered_name(self):
        assert policy_name(HardcodedPolicy()) == "Hardcoded"
        assert policy_name(RandomPolicy()) == "Random"

    def test_returns_none_for_unregistered_instance(self):
        class CustomPolicy(BasePolicy):
            def decide(self, agent, world):
                return [], 0
            def decide_reproduce(self, agent, world):
                return False
        assert policy_name(CustomPolicy()) is None

    def test_returns_none_for_none_input(self):
        assert policy_name(None) is None


class TestDistributePolicies:
    def test_single_choice_distribution_assigns_to_everyone(self):
        agents = [make_agent(id=i) for i in range(10)]
        distribute_policies(agents, {"Hardcoded": 1.0})
        assert all(isinstance(a.policy, HardcodedPolicy) for a in agents)

    def test_mixed_distribution_uses_both_policies(self, monkeypatch):
        agents = [make_agent(id=i) for i in range(4)]
        seq = iter(["Hardcoded", "Random", "Hardcoded", "Random"])
        monkeypatch.setattr(random, "choices", lambda pop, weights, k: [next(seq)])
        distribute_policies(agents, {"Hardcoded": 0.5, "Random": 0.5})
        assert isinstance(agents[0].policy, HardcodedPolicy)
        assert isinstance(agents[1].policy, RandomPolicy)
        assert isinstance(agents[2].policy, HardcodedPolicy)
        assert isinstance(agents[3].policy, RandomPolicy)

    def test_each_agent_gets_its_own_policy_instance(self):
        agents = [make_agent(id=i) for i in range(2)]
        distribute_policies(agents, {"Hardcoded": 1.0})
        assert agents[0].policy is not agents[1].policy

    def test_empty_agent_list_does_not_raise(self):
        distribute_policies([], {"Hardcoded": 1.0})  # ne doit pas lever

    def test_unknown_policy_names_are_ignored(self):
        # Une policy retirée du registre ne doit pas faire planter la
        # distribution : elle est ignorée au profit des noms valides.
        agents = [make_agent(id=i) for i in range(4)]
        distribute_policies(agents, {"PolicyRetirée": 1.0, "Hardcoded": 0.5})
        assert all(isinstance(a.policy, HardcodedPolicy) for a in agents)

    def test_distribution_with_only_unknown_names_falls_back_to_default(self):
        agents = [make_agent(id=0)]
        distribute_policies(agents, {"PolicyRetirée": 1.0})
        assert policy_name(agents[0].policy) == default_policy_name()
