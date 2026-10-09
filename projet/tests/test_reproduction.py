import config
from actions import ACTION_IDLE
from reproduction import reproduce
from policy import HardcodedPolicy
from tests.conftest import make_world, make_agent


class AlwaysReproduce:
    def decide(self, agent, world):
        return [], ACTION_IDLE

    def decide_reproduce(self, agent, world):
        return True


class NeverReproduce:
    def decide(self, agent, world):
        return [], ACTION_IDLE

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

    def test_world_phase_uses_agents_own_policy_for_reproduction(self):
        """Corrige une incohérence réelle : world_phase() appelait
        reproduce(agent, world, policy) avec la policy *globale*, jamais
        agent.policy — contrairement à think(). Un agent dont la policy
        refuse de se reproduire ne doit pas se reproduire parce que la
        policy globale, elle, accepte."""
        from world import world_phase

        world = make_world(width=6, height=6,
                            food_amounts={(x, y): 3 for x in range(6) for y in range(6)})
        agent = make_agent(id=1, x=2, y=2, energy=95, thirst=95)
        agent.policy = NeverReproduce()  # la policy de l'agent refuse...
        world.agents = [agent]

        # ...la policy globale (HardcodedPolicy) accepterait, mais elle ne
        # doit plus être consultée pour la reproduction de cet agent.
        world_phase(world, HardcodedPolicy())

        assert len(world.agents) == 1  # aucun bébé : la policy de l'agent prime

    def test_world_phase_reproduces_when_agents_own_policy_accepts(self):
        from world import world_phase

        world = make_world(width=6, height=6,
                            food_amounts={(x, y): 3 for x in range(6) for y in range(6)})
        agent = make_agent(id=1, x=2, y=2, energy=95, thirst=95)
        agent.policy = AlwaysReproduce()
        world.agents = [agent]

        world_phase(world, HardcodedPolicy())

        assert len(world.agents) == 2
        assert {a.generation for a in world.agents} == {0, 1}

    def test_max_population_cap_blocks_reproduction(self):
        from world import world_phase

        config.MAX_POPULATION = 1
        world = make_world(width=6, height=6,
                            food_amounts={(x, y): 3 for x in range(6) for y in range(6)})
        agent = make_agent(id=1, x=2, y=2, energy=95, thirst=95)
        agent.policy = AlwaysReproduce()
        world.agents = [agent]

        world_phase(world, HardcodedPolicy())

        assert len(world.agents) == 1  # plafond atteint : pas de bébé

    def test_shared_occupied_set_excludes_other_agents_cells(self):
        world = make_world(width=5, height=5)
        agent = make_agent(id=1, x=2, y=2, energy=90)
        world.agents = [agent]
        occupied = {(1, 2), (3, 2), (2, 1), (2, 3)}  # les 4 voisins
        assert reproduce(agent, world, AlwaysReproduce(), occupied=occupied) is None
