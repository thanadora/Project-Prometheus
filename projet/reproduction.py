"""
reproduction.py — Mécanique de reproduction des agents.
"""

import random
from logger import get_logger
from agent import Agent


def reproduce(agent, world, policy):
    """
    Tente de créer un enfant pour `agent`.
    La décision est déléguée à la policy ; la mécanique reste ici.
    Retourne un nouvel Agent ou None.
    """
    import config
    if not config.ENABLE_REPRODUCTION:
        return None
    if not policy.decide_reproduce(agent, world):
        return None

    infinite  = getattr(world, "infinite", False)
    occupied  = {(a.x, a.y) for a in world.agents}
    neighbors = [
        (agent.x + dx, agent.y + dy)
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]
        if (infinite or (0 <= agent.x + dx < world.width and 0 <= agent.y + dy < world.height))
        and (agent.x + dx, agent.y + dy) not in occupied
        and world.map.is_walkable(agent.x + dx, agent.y + dy)
    ]
    if not neighbors:
        return None

    x, y          = random.choice(neighbors)
    agent.energy -= 40
    get_logger().info(world.tick, f"Agent #{agent.id} se reproduit → bébé gén.{agent.generation + 1} en ({x},{y})")

    return Agent(
        id=-1,
        x=x, y=y,
        generation=agent.generation + 1,
        born_tick=world.tick,
        energy=40,
        thirst=50,
        policy=agent.policy,
    )