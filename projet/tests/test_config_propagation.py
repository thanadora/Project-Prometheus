"""
test_config_propagation.py — Vérifie que la configuration est bien LUE
DYNAMIQUEMENT par tous les modules.

Historiquement, les modules faisaient `from config import X` : la valeur
était copiée au moment de l'import, or `main.py` importait `world`/`agent`
AVANT d'afficher l'écran de configuration. Résultat : la quasi-totalité des
curseurs de l'écran de démarrage étaient sans effet en jeu (seuls les
booléens lus via `config.X` réagissaient).

La correction : les modules utilisent désormais `config.X` aux points
d'usage (avec des lectures locales dans les boucles chaudes), donc modifier
`config` à l'exécution change réellement le comportement — et ce fichier de
tests le vérifie module par module.
"""
import random

import config
from actions import ACTION_LEFT, ACTION_RIGHT
from policy import HardcodedPolicy


def test_no_module_keeps_a_frozen_copy_of_tunable_constants():
    """Aucun module de logique ne doit exposer de copie figée des constantes
    réglables (c'est exactement le piège qui rendait l'écran de config
    inopérant). On vérifie quelques constantes emblématiques."""
    import agent as agent_module
    import world as world_module
    import policy as policy_module
    import food as food_module

    frozen_names = ["TOROIDAL_WORLD", "MOVE_COST", "VISION_RADIUS",
                    "THIRST_RATE", "MAX_ENERGY", "FOOD_TYPES"]
    for module in (agent_module, world_module, policy_module, food_module):
        for name in frozen_names:
            assert not hasattr(module, name), (
                f"{module.__name__} garde une copie figée de {name} — "
                f"l'écran de configuration n'aurait aucun effet dessus"
            )


def test_changing_toroidal_world_changes_agent_behaviour():
    """La case 'Monde toroïdal' de l'écran de config doit réellement agir
    sur les déplacements, y compris si le module agent a déjà été importé."""
    from tests.conftest import make_world, make_agent
    from agent import apply_timed_action

    world = make_world(width=3, height=3)
    agent = make_agent(x=0, y=0)

    config.TOROIDAL_WORLD = False
    apply_timed_action(agent, world, ACTION_LEFT)
    assert (agent.x, agent.y) == (0, 0)  # bloqué au bord

    config.TOROIDAL_WORLD = True
    apply_timed_action(agent, world, ACTION_LEFT)
    assert (agent.x, agent.y) == (2, 0)  # passé par l'autre bord


def test_changing_move_cost_changes_energy_consumption():
    from tests.conftest import make_world, make_agent
    from agent import apply_timed_action

    world = make_world(width=5, height=5)
    agent = make_agent(x=2, y=2, energy=50)

    config.MOVE_COST = 2.0
    config.IDLE_COST = 0.5
    apply_timed_action(agent, world, ACTION_RIGHT)
    assert agent.energy == 50 - (2.0 - 0.5)


def test_changing_vision_radius_changes_perception():
    from tests.conftest import make_world, make_agent
    from agent import perceive

    world = make_world(width=30, height=30, food_amounts={(10, 10): 1})
    agent = make_agent(x=10, y=16)  # à 6 cases de la nourriture

    config.VISION_RADIUS = 3
    assert perceive(agent, world)["food_dist"] == -1

    config.VISION_RADIUS = 10
    assert perceive(agent, world)["food_dist"] == 6


def test_changing_thirst_rate_reaches_agent_life():
    from tests.conftest import make_world, make_agent
    from agent import _update_thirst

    world = make_world(width=5, height=5)
    agent = make_agent(x=2, y=2, thirst=50)

    config.THIRST_RATE = 1.5
    _update_thirst(agent, world)
    assert agent.thirst == 50 - 1.5


def test_changing_food_types_reaches_food_growth(monkeypatch):
    from tests.conftest import make_food, make_map
    from food import FoodSystem

    map_ = make_map(width=2, height=1)
    food = make_food(map_, {(0, 0): 0})
    config.FOOD_TYPES = dict(config.FOOD_TYPES)
    config.FOOD_TYPES[config.BIOME_PRAIRIE] = dict(gain=99, respawn=1.0, capacity=5, color="#fff")

    monkeypatch.setattr(random, "random", lambda: 0.0)  # toujours < respawn
    food.grow_food(map_.biome_map, soil_moisture=1.0)
    assert food.food_map[(0, 0)] == 1
    # Le gain vient bien de la config modifiée au runtime.
    assert food.consume_food(map_.biome_map, (0, 0)) == 99
