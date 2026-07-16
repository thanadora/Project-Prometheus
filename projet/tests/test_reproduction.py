import config
from reproduction import reproduce
from tests.conftest import make_world, make_agent


class AlwaysReproduce:
    def decide_reproduce(self, agent, world):
        return True


class NeverReproduce:
    def decide_reproduce(self, agent, world):
        return False


class TestReproduce:
    def test_disabled_by_config_returns_none(self):
        config.ENABLE_REPRODUCTION = False
        world = make_world(width=5, height=5)
        agent = make_agent(x=2, y=2)
        world.agents = [agent]
        assert reproduce(agent, world, AlwaysReproduce()) is None

    def test_policy_refusal_returns_none(self):
        world = make_world(width=5, height=5)
        agent = make_agent(x=2, y=2)
        world.agents = [agent]
        assert reproduce(agent, world, NeverReproduce()) is None

    def test_no_free_neighbor_returns_none(self):
        # Un agent tout seul mais entouré d'eau de tous les côtés : aucune
        # case libre où poser le bébé.
        overrides = {(1, 2): config.BIOME_WATER, (3, 2): config.BIOME_WATER,
                     (2, 1): config.BIOME_WATER, (2, 3): config.BIOME_WATER}
        world = make_world(width=5, height=5, overrides=overrides)
        agent = make_agent(x=2, y=2)
        world.agents = [agent]
        assert reproduce(agent, world, AlwaysReproduce()) is None

    def test_occupied_neighbor_cells_are_excluded(self):
        # Les 4 voisins sont praticables mais tous déjà occupés par d'autres
        # agents : aucune place libre non plus.
        world = make_world(width=5, height=5)
        agent = make_agent(id=1, x=2, y=2)
        occupants = [
            make_agent(id=10, x=1, y=2), make_agent(id=11, x=3, y=2),
            make_agent(id=12, x=2, y=1), make_agent(id=13, x=2, y=3),
        ]
        world.agents = [agent] + occupants
        assert reproduce(agent, world, AlwaysReproduce()) is None

    def test_successful_reproduction_creates_baby_with_expected_fields(self):
        world = make_world(width=5, height=5, tick=42)
        agent = make_agent(x=2, y=2, energy=90, generation=3)
        world.agents = [agent]
        baby = reproduce(agent, world, AlwaysReproduce())
        assert baby is not None
        assert baby.generation == 4
        assert baby.born_tick == 42
        assert baby.energy == 40
        assert baby.thirst == 50
        assert (baby.x, baby.y) in [(1, 2), (3, 2), (2, 1), (2, 3)]

    def test_reproduction_costs_energy_to_parent(self):
        world = make_world(width=5, height=5)
        agent = make_agent(x=2, y=2, energy=90)
        world.agents = [agent]
        reproduce(agent, world, AlwaysReproduce())
        assert agent.energy == 50

    def test_baby_inherits_parents_specific_policy(self):
        world = make_world(width=5, height=5)
        specific_policy = AlwaysReproduce()
        agent = make_agent(x=2, y=2, energy=90)
        agent.policy = specific_policy
        world.agents = [agent]
        baby = reproduce(agent, world, AlwaysReproduce())
        assert baby.policy is specific_policy

    def test_baby_id_is_placeholder_until_world_assigns_one(self):
        # reproduction.py met id=-1 : c'est world.world_phase() qui appelle
        # world.next_id() plus tard pour lui donner un vrai id.
        world = make_world(width=5, height=5)
        agent = make_agent(x=2, y=2, energy=90)
        world.agents = [agent]
        baby = reproduce(agent, world, AlwaysReproduce())
        assert baby.id == -1

    def test_reproduction_decision_uses_the_passed_in_policy_not_agents_own(self):
        """Documente une incohérence réelle : world_phase() appelle toujours
        reproduce(agent, world, policy) avec la policy *globale* passée à
        world_phase, jamais agent.policy — contrairement à think() qui, lui,
        privilégie bien agent.policy s'il existe. Un agent avec une policy
        spécifique qui refuse de se reproduire peut donc quand même se
        reproduire si la policy globale, elle, l'accepte (et vice versa)."""
        world = make_world(width=5, height=5)
        agent = make_agent(x=2, y=2, energy=90)
        agent.policy = NeverReproduce()  # la policy de l'agent refuse...
        world.agents = [agent]
        # ...mais c'est la policy passée en paramètre qui est consultée.
        baby = reproduce(agent, world, AlwaysReproduce())
        assert baby is not None
