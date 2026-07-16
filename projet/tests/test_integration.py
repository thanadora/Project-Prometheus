"""
test_integration.py — Filet de sécurité de bout en bout.

Contrairement aux autres fichiers de tests (qui isolent chaque fonction avec
des cartes construites à la main pour rester déterministes), ce fichier fait
tourner la VRAIE boucle de simulation — génération de carte par bruit de
Perlin comprise — sur plusieurs centaines de ticks, avec la configuration par
défaut du projet. L'objectif n'est pas de vérifier un comportement précis,
mais de détecter les régressions structurelles : crash, valeurs qui sortent
de leurs bornes, états incohérents qui n'apparaîtraient qu'après un long
fonctionnement (ex: fuite d'agents dupliqués, nourriture négative, etc.).
"""
import random

import config
from world import initialize_world, world_phase
from policy import HardcodedPolicy, RandomPolicy


class TestFullSimulationRun:
    def test_runs_five_hundred_ticks_without_crashing(self):
        random.seed(2026)
        world = initialize_world()
        policy = HardcodedPolicy()
        for _ in range(500):
            world_phase(world, policy)

    def test_invariants_hold_throughout_a_long_run(self):
        random.seed(7)
        world = initialize_world()
        policy = HardcodedPolicy()
        for t in range(300):
            world_phase(world, policy)

            assert world.tick == t + 1

            for a in world.agents:
                assert a.alive is True, "un agent mort ne devrait pas rester dans world.agents"
                assert 0 <= a.energy <= config.MAX_ENERGY
                assert 0 <= a.thirst <= config.MAX_THIRST
                assert 0 <= a.age
                assert len(a.inventory) <= config.INVENTORY_SIZE
                assert 0 <= a.x < world.width or config.TOROIDAL_WORLD or world.infinite
                assert 0 <= a.y < world.height or config.TOROIDAL_WORLD or world.infinite

            ids = [a.id for a in world.agents]
            assert len(ids) == len(set(ids)), "des agents partagent le même id"

            for amount in world.food.food_map.values():
                assert amount >= 0

            assert world.death_count >= 0
            assert world.migration_count >= 0

    def test_population_never_goes_negative_even_if_everyone_dies(self):
        # Configuration hostile : pas de reproduction, pas de migration, pour
        # garantir que la population peut décroître jusqu'à zéro sans que
        # rien ne plante côté world.py / gui.py (qui itèrent sur world.agents).
        config.ENABLE_REPRODUCTION = False
        config.ENABLE_MIGRATION = False
        random.seed(3)
        world = initialize_world()
        for a in world.agents:
            a.energy = 1  # tout le monde va mourir vite
        policy = HardcodedPolicy()
        for _ in range(200):
            world_phase(world, policy)
        assert len(world.agents) >= 0  # jamais négatif, jamais d'exception

    def test_random_policy_does_not_crash_the_simulation_either(self):
        random.seed(11)
        world = initialize_world()
        for a in world.agents:
            a.policy = None  # utilise la policy par défaut passée à world_phase
        policy = RandomPolicy()
        for _ in range(200):
            world_phase(world, policy)

    def test_reproduction_grows_population_in_an_abundant_environment(self):
        config.ENABLE_REPRODUCTION = True
        config.ENABLE_MIGRATION = False
        random.seed(42)
        world = initialize_world()
        for a in world.agents:
            a.energy = config.MAX_ENERGY
            a.thirst = config.MAX_THIRST
        # Sature le monde en nourriture pour maximiser les chances de
        # reproduction sur la durée du test.
        for pos in list(world.food.food_map.keys()):
            biome = world.map.biome_map.get(pos)
            if biome in config.FOOD_TYPES:
                cap = config.FOOD_TYPES[biome]["capacity"]
                world.food.food_map[pos] = cap
                world.food.food_positions.add(pos)
        policy = HardcodedPolicy()
        start_count = len(world.agents)
        max_generation_seen = 0
        for _ in range(400):
            world_phase(world, policy)
            if world.agents:
                max_generation_seen = max(max_generation_seen,
                                           max(a.generation for a in world.agents))
        assert max_generation_seen > 0, "aucune reproduction n'a eu lieu en 400 ticks abondants"

    def test_migrations_can_happen_without_corrupting_world_state(self):
        config.ENABLE_MIGRATION = True
        config.MIGRATION_COOLDOWN = 5
        config.MIGRATION_VOTE_THRESHOLD = 0.01  # migration très facile à déclencher
        random.seed(99)
        world = initialize_world()
        policy = HardcodedPolicy()
        for a in world.agents:
            a.energy = 1  # -> vote_migrate=True via HardcodedPolicy._free_actions
        for _ in range(50):
            world_phase(world, policy)
            for a in world.agents:
                assert 0 <= a.energy <= config.MAX_ENERGY
        # Pas d'assertion sur le nombre de migrations : l'important est
        # qu'aucune exception ne soit levée et que l'état reste cohérent.
