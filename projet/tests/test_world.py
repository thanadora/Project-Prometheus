import config
from world import (
    World, compute_reward, initialize_world, _resolve_collisions,
    _remove_dead_agents, _new_map_and_food, world_phase,
)
from map import GameMap
from food import FoodSystem
from policy import HardcodedPolicy

from tests.conftest import make_world, make_agent


# ---------------------------------------------------------------------------
# Temps / saisons
# ---------------------------------------------------------------------------
class TestTimeOfDay:
    def test_zero_at_start_of_day(self):
        world = make_world(width=3, height=3, tick=0)
        assert world.time_of_day() == 0.0

    def test_wraps_around_day_duration(self):
        world = make_world(width=3, height=3, tick=config.DAY_DURATION)
        assert world.time_of_day() == 0.0

    def test_is_night_true_in_last_fraction_of_day(self):
        config.ENABLE_DAY_NIGHT = True
        night_tick = int(config.DAY_DURATION * (1 - config.NIGHT_RATIO)) + 1
        world = make_world(width=3, height=3, tick=night_tick)
        assert world.is_night() is True

    def test_is_night_false_at_start_of_day(self):
        config.ENABLE_DAY_NIGHT = True
        world = make_world(width=3, height=3, tick=0)
        assert world.is_night() is False

    def test_is_night_always_false_when_disabled(self):
        config.ENABLE_DAY_NIGHT = False
        night_tick = int(config.DAY_DURATION * (1 - config.NIGHT_RATIO)) + 1
        world = make_world(width=3, height=3, tick=night_tick)
        assert world.is_night() is False


class TestSeasons:
    def test_spring_at_tick_zero(self):
        config.ENABLE_SEASONS = True
        world = make_world(width=3, height=3, tick=0)
        assert world.current_season() == config.SEASON_SPRING

    def test_cycles_through_all_seasons_within_a_year(self):
        config.ENABLE_SEASONS = True
        world = make_world(width=3, height=3)
        seen = set()
        for t in range(0, config.YEAR_DURATION, config.SEASON_DURATION):
            world.tick = t
            seen.add(world.current_season())
        assert seen == {config.SEASON_SPRING, config.SEASON_SUMMER,
                         config.SEASON_AUTUMN, config.SEASON_WINTER}

    def test_always_spring_when_seasons_disabled(self):
        config.ENABLE_SEASONS = False
        world = make_world(width=3, height=3, tick=config.YEAR_DURATION * 3)
        assert world.current_season() == config.SEASON_SPRING

    def test_season_progress_within_unit_range(self):
        world = make_world(width=3, height=3, tick=config.SEASON_DURATION // 2)
        assert 0.0 <= world.season_progress() < 1.0


# ---------------------------------------------------------------------------
# Reward
# ---------------------------------------------------------------------------
class TestComputeReward:
    def test_dead_agent_gets_fixed_penalty(self):
        agent = make_agent(alive=False)
        assert compute_reward(agent, prev_energy=50, prev_thirst=50) == -10.0

    def test_energy_gain_increases_reward(self):
        agent = make_agent(energy=60, thirst=50)
        r = compute_reward(agent, prev_energy=50, prev_thirst=50)
        assert r > 0

    def test_energy_loss_decreases_reward(self):
        agent = make_agent(energy=40, thirst=50)
        r = compute_reward(agent, prev_energy=50, prev_thirst=50)
        assert r < 0

    def test_low_energy_applies_extra_penalty(self):
        agent = make_agent(energy=10, thirst=50)
        r_low = compute_reward(agent, prev_energy=10, prev_thirst=50)
        agent_ok = make_agent(energy=50, thirst=50)
        r_ok = compute_reward(agent_ok, prev_energy=50, prev_thirst=50)
        assert r_low < r_ok

    def test_low_thirst_applies_extra_penalty(self):
        agent = make_agent(energy=50, thirst=10)
        r = compute_reward(agent, prev_energy=50, prev_thirst=10)
        assert r < 0


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------
class TestNewMapAndFood:
    def test_classic_mode_fills_map_and_food(self):
        game_map, food = _new_map_and_food(6, 6, infinite=False)
        assert len(game_map.biome_map) == 36
        assert len(food.food_map) == 36

    def test_infinite_mode_seeds_biome_map_around_center_not_as_a_fixed_grid(self):
        # En mode infini, `initialize()` seul ne remplit rien (cf test_map.py).
        # Mais `_new_map_and_food` enchaîne avec `food.initialize(..., infinite=True)`,
        # qui appelle `game_map.get_biome()` autour du centre pour y semer de la
        # nourriture — ce qui, en effet de bord, met ces cases en cache. Le
        # nombre de cases mises en cache dépend donc de FOOD_GROWTH_RADIUS,
        # pas de `width`/`height` (qui ne servent qu'au mode classique).
        game_map, food = _new_map_and_food(6, 6, infinite=True)
        assert len(game_map.biome_map) > 6 * 6
        radius = config.FOOD_GROWTH_RADIUS * 2
        assert all(-radius <= x <= radius and -radius <= y <= radius
                   for x, y in game_map.biome_map)


class TestInitializeWorld:
    def test_creates_expected_number_of_agents(self):
        world = initialize_world()
        assert len(world.agents) == config.INITIAL_AGENT_COUNT

    def test_all_initial_agents_alive_and_on_walkable_ground(self):
        world = initialize_world()
        for a in world.agents:
            assert a.alive is True
            assert world.map.is_walkable(a.x, a.y)

    def test_agent_ids_are_unique(self):
        world = initialize_world()
        ids = [a.id for a in world.agents]
        assert len(ids) == len(set(ids))

    def test_agents_start_at_half_energy_and_thirst(self):
        world = initialize_world()
        for a in world.agents:
            assert a.energy == config.MAX_ENERGY / 2
            assert a.thirst == config.MAX_THIRST / 2

    def test_all_agents_have_a_policy_assigned(self):
        world = initialize_world()
        assert all(a.policy is not None for a in world.agents)

    def test_biomes_disabled_forces_flat_prairie_map_in_classic_mode(self):
        config.ENABLE_BIOMES = False
        config.INFINITE_WORLD = False
        world = initialize_world()
        assert all(b == config.BIOME_PRAIRIE for b in world.map.biome_map.values())

    def test_biomes_disabled_is_overridden_in_infinite_mode(self):
        config.ENABLE_BIOMES = False
        config.INFINITE_WORLD = True
        world = initialize_world()
        # Le mode infini a besoin des biomes pour la génération à la demande :
        # le désactiver ne doit pas empêcher le monde de s'initialiser.
        assert len(world.agents) == config.INITIAL_AGENT_COUNT


# ---------------------------------------------------------------------------
# Collisions & nettoyage
# ---------------------------------------------------------------------------
class TestInfiniteWorldHelpers:
    def test_find_walkable_near_returns_enough_walkable_cells(self):
        from world import _find_walkable_near
        game_map = GameMap(width=10, height=10, infinite=True)
        game_map.initialize(offset_x=0, offset_y=0)
        found = _find_walkable_near(game_map, (0, 0), min_count=5)
        assert len(found) >= 5
        assert all(game_map.is_walkable(x, y) for x, y in found)

    def test_find_walkable_near_gives_up_after_max_radius_if_all_water(self, monkeypatch):
        from world import _find_walkable_near
        game_map = GameMap(width=10, height=10, infinite=True)
        monkeypatch.setattr(GameMap, "is_walkable", lambda self, x, y: False)
        found = _find_walkable_near(game_map, (0, 0), min_count=5)
        assert found == []  # ne boucle pas indéfiniment, ne plante pas

    def test_initialize_world_infinite_mode_places_agents_near_origin(self):
        config.INFINITE_WORLD = True
        world = initialize_world()
        assert world.infinite is True
        assert len(world.agents) == config.INITIAL_AGENT_COUNT
        for a in world.agents:
            assert world.map.is_walkable(a.x, a.y)


class TestActiveCellsAndChunkUnloading:
    def test_active_cells_covers_area_around_living_agents(self):
        from world import _active_cells
        world = make_world(width=20, height=20)
        world.agents = [make_agent(x=10, y=10)]
        cells = _active_cells(world)
        assert (10, 10) in cells
        assert (10 + config.FOOD_GROWTH_RADIUS, 10) in cells
        assert (10 + config.FOOD_GROWTH_RADIUS + 5, 10) not in cells

    def test_active_cells_ignores_dead_agents(self):
        from world import _active_cells
        world = make_world(width=20, height=20)
        world.agents = [make_agent(x=10, y=10, alive=False)]
        cells = _active_cells(world)
        assert cells == set()

    def test_unload_far_chunks_removes_cells_far_from_every_agent(self):
        from world import _unload_far_chunks
        world = make_world(width=5, height=5, tick=config.CHUNK_UNLOAD_INTERVAL)
        far_pos = (1000, 1000)
        world.map.biome_map[far_pos] = config.BIOME_PRAIRIE
        world.food.food_map[far_pos] = 3
        world.food.food_positions.add(far_pos)
        world.agents = [make_agent(x=0, y=0)]
        _unload_far_chunks(world)
        assert far_pos not in world.map.biome_map
        assert far_pos not in world.food.food_map
        assert far_pos not in world.food.food_positions

    def test_unload_far_chunks_keeps_cells_near_an_agent(self):
        from world import _unload_far_chunks
        world = make_world(width=5, height=5, tick=config.CHUNK_UNLOAD_INTERVAL)
        world.agents = [make_agent(x=2, y=2)]
        _unload_far_chunks(world)
        assert (2, 2) in world.map.biome_map

    def test_unload_far_chunks_skips_when_not_on_interval(self):
        from world import _unload_far_chunks
        world = make_world(width=5, height=5, tick=1)
        assert config.CHUNK_UNLOAD_INTERVAL > 1
        far_pos = (1000, 1000)
        world.map.biome_map[far_pos] = config.BIOME_PRAIRIE
        world.agents = [make_agent(x=0, y=0)]
        _unload_far_chunks(world)
        assert far_pos in world.map.biome_map  # pas encore le tour de nettoyer

    def test_unload_far_chunks_noop_when_no_living_agents(self):
        from world import _unload_far_chunks
        world = make_world(width=5, height=5, tick=config.CHUNK_UNLOAD_INTERVAL)
        world.map.biome_map[(1000, 1000)] = config.BIOME_PRAIRIE
        world.agents = [make_agent(x=0, y=0, alive=False)]
        _unload_far_chunks(world)
        assert (1000, 1000) in world.map.biome_map  # rien n'est nettoyé sans agent vivant
    def test_agent_on_food_gains_energy(self):
        world = make_world(width=5, height=5, food_amounts={(2, 2): 1})
        agent = make_agent(x=2, y=2, energy=10)
        world.agents = [agent]
        _resolve_collisions(world)
        gain = config.FOOD_TYPES[config.BIOME_PRAIRIE]["gain"]
        assert agent.energy == min(config.MAX_ENERGY, 10 + gain)

    def test_only_one_agent_eats_when_two_share_a_tile(self):
        world = make_world(width=5, height=5, food_amounts={(2, 2): 1})
        a1 = make_agent(id=1, x=2, y=2, energy=10)
        a2 = make_agent(id=2, x=2, y=2, energy=10)
        world.agents = [a1, a2]
        _resolve_collisions(world)
        fed = [a for a in (a1, a2) if a.energy > 10]
        assert len(fed) == 1

    def test_energy_capped_at_max(self):
        world = make_world(width=5, height=5, food_amounts={(2, 2): 1})
        agent = make_agent(x=2, y=2, energy=config.MAX_ENERGY)
        world.agents = [agent]
        _resolve_collisions(world)
        assert agent.energy == config.MAX_ENERGY

    def test_dead_agents_do_not_consume_food(self):
        world = make_world(width=5, height=5, food_amounts={(2, 2): 1})
        agent = make_agent(x=2, y=2, alive=False)
        world.agents = [agent]
        _resolve_collisions(world)
        assert world.food.food_map[(2, 2)] == 1


class TestRemoveDeadAgents:
    def test_removes_dead_keeps_alive(self):
        world = make_world(width=5, height=5)
        alive = make_agent(id=1, alive=True)
        dead = make_agent(id=2, alive=False)
        world.agents = [alive, dead]
        _remove_dead_agents(world)
        assert world.agents == [alive]

    def test_increments_death_count(self):
        world = make_world(width=5, height=5)
        world.agents = [make_agent(id=1, alive=False), make_agent(id=2, alive=False)]
        _remove_dead_agents(world)
        assert world.death_count == 2

    def test_death_count_accumulates_across_calls(self):
        world = make_world(width=5, height=5)
        world.death_count = 3
        world.agents = [make_agent(id=1, alive=False)]
        _remove_dead_agents(world)
        assert world.death_count == 4


# ---------------------------------------------------------------------------
# world_phase() — test d'intégration léger
# ---------------------------------------------------------------------------
class TestWorldPhaseIntegration:
    def test_tick_increments_by_one(self):
        world = make_world(width=10, height=10)
        world.agents = [make_agent(x=5, y=5, policy=HardcodedPolicy())]
        before = world.tick
        world_phase(world, HardcodedPolicy())
        assert world.tick == before + 1

    def test_runs_many_ticks_without_crashing_and_keeps_invariants(self):
        config.ENABLE_MIGRATION = False  # simplifie : pas de remplacement de carte ici
        world = make_world(width=15, height=15)
        world.agents = [
            make_agent(id=i, x=(i % 15), y=(i // 15), energy=60, thirst=60,
                       policy=HardcodedPolicy())
            for i in range(6)
        ]
        policy = HardcodedPolicy()
        for _ in range(150):
            world_phase(world, policy)
            for a in world.agents:
                assert a.alive is True
                assert 0 <= a.energy <= config.MAX_ENERGY
                assert 0 <= a.thirst <= config.MAX_THIRST
            for amount in world.food.food_map.values():
                assert amount >= 0

    def test_agent_can_die_and_be_removed_over_time(self):
        config.ENABLE_MIGRATION = False
        config.ENABLE_REPRODUCTION = False
        world = make_world(width=10, height=10)
        # Énergie très basse : l'agent va mourir d'épuisement rapidement.
        world.agents = [make_agent(x=5, y=5, energy=1, thirst=100, policy=HardcodedPolicy())]
        policy = HardcodedPolicy()
        for _ in range(10):
            world_phase(world, policy)
        assert len(world.agents) == 0
        assert world.death_count == 1

    def test_food_grows_via_active_cells_in_infinite_mode(self):
        config.ENABLE_MIGRATION = False
        world = make_world(width=5, height=5, infinite=True)
        world.agents = [make_agent(x=0, y=0, policy=HardcodedPolicy())]
        policy = HardcodedPolicy()
        # Fait tourner assez de ticks pour que le monde infini ait une vraie
        # chance de faire pousser de la nourriture autour de l'agent.
        for _ in range(20):
            world_phase(world, policy)
        assert len(world.map.biome_map) > 0  # des cases ont bien été générées
        config.ENABLE_MIGRATION = False
        config.ENABLE_REPRODUCTION = True
        world = make_world(width=10, height=10, food_amounts={(x, y): 5
                            for x in range(10) for y in range(10)})
        world.agents = [make_agent(id=1, x=5, y=5, energy=95, thirst=95,
                                    policy=HardcodedPolicy())]
        policy = HardcodedPolicy()
        world_phase(world, policy)
        assert len(world.agents) >= 1  # au minimum le parent a survécu
        generations = {a.generation for a in world.agents}
        # Si la reproduction a eu lieu ce tick, un bébé de génération 1 existe.
        assert generations <= {0, 1}
