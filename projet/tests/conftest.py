"""
conftest.py — Fixtures partagées pour toute la suite de tests.

Principes :
- `config.py` est un module global mutable (des tests activent/désactivent des
  ENABLE_* ou changent des seuils) : on snapshot/restaure son contenu après
  CHAQUE test pour qu'aucun test ne puisse en polluer un autre.
- Le hasard (module `random`) est global lui aussi : on le seed avant chaque
  test pour des résultats reproductibles par défaut ; les tests qui ont besoin
  d'un contrôle plus fin re-seedent localement.
- On fournit des constructeurs de World/GameMap/FoodSystem "à la main" (sans
  bruit de Perlin) pour des tests unitaires déterministes, indépendants de la
  génération procédurale — qui, elle, est testée séparément dans test_map.py.
"""
import copy
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from map import GameMap
from food import FoodSystem
from world import World
from agent import Agent


# ---------------------------------------------------------------------------
# Isolation
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _isolate_config():
    """Sauvegarde config.py avant le test, le restaure après — y compris les
    valeurs mutables (dicts/listes) qu'un test pourrait modifier en place."""
    snapshot = copy.deepcopy({k: v for k, v in vars(config).items() if not k.startswith("__")})
    yield
    for k, v in snapshot.items():
        setattr(config, k, v)
    for k in list(vars(config).keys()):
        if k not in snapshot and not k.startswith("__"):
            delattr(config, k)


@pytest.fixture(autouse=True)
def _seed_random():
    """Résultats reproductibles par défaut ; re-seed localement si besoin d'une
    séquence aléatoire précise dans un test donné."""
    random.seed(1234)
    yield


# ---------------------------------------------------------------------------
# Constructeurs déterministes (pas de bruit de Perlin)
# ---------------------------------------------------------------------------
def make_map(width=10, height=10, default_biome=None, overrides=None):
    """GameMap entièrement pré-remplie à la main, sans passer par initialize()
    (donc sans générateur de bruit) — comportement 100% déterministe."""
    if default_biome is None:
        default_biome = config.BIOME_PRAIRIE
    game_map = GameMap(width=width, height=height)
    game_map.biome_map = {
        (x, y): default_biome for x in range(width) for y in range(height)
    }
    game_map.altitude_map = {
        (x, y): 0.5 for x in range(width) for y in range(height)
    }
    if overrides:
        for pos, biome in overrides.items():
            game_map.biome_map[pos] = biome
    return game_map


def make_food(game_map, food_amounts=None):
    """FoodSystem à zéro partout, avec uniquement les quantités précises
    déposées aux positions indiquées par `food_amounts` (dict pos -> amount).
    NB: on ne passe pas par FoodSystem.initialize() car celle-ci sème aussi
    de la nourriture aléatoire (INITIAL_FOOD_COUNT) — indésirable ici, où
    on veut un contrôle déterministe total pour les tests."""
    food = FoodSystem(width=game_map.width, height=game_map.height)
    food.food_map = {
        (x, y): 0 for x in range(game_map.width) for y in range(game_map.height)
    }
    food.food_positions = set()
    if food_amounts:
        for pos, amount in food_amounts.items():
            if amount > 0:
                food.food_map[pos] = amount
                food.food_positions.add(pos)
    return food


def make_world(width=10, height=10, default_biome=None, overrides=None, food_amounts=None, **kwargs):
    game_map = make_map(width, height, default_biome, overrides)
    food = make_food(game_map, food_amounts)
    world = World(width=width, height=height, map=game_map, food=food, **kwargs)
    return world


def make_agent(id=1, x=0, y=0, energy=50.0, thirst=50.0, age=0, alive=True,
               generation=0, policy=None, **kwargs):
    return Agent(id=id, x=x, y=y, energy=energy, thirst=thirst, age=age,
                 alive=alive, generation=generation, policy=policy, **kwargs)


@pytest.fixture
def world_factory():
    return make_world


@pytest.fixture
def agent_factory():
    return make_agent


@pytest.fixture
def small_world():
    """Monde 10x10, entièrement praire, sans eau ni nourriture — base neutre
    pour les tests qui n'ont besoin d'aucun relief particulier."""
    return make_world(width=10, height=10)
