import random
from dataclasses import dataclass, field
from typing import List

from config import (
    WORLD_WIDTH,
    WORLD_HEIGHT,
    INITIAL_AGENT_COUNT,
    MAX_ENERGY,
    DAY_DURATION,
    NIGHT_RATIO,
)
from entities import Agent
from food import FoodSystem
from agent import apply_action, think, update_agent_life, reproduce

# -----------------------------
# WORLD STRUCTURE
# -----------------------------
@dataclass
class World:
    width: int
    height: int
    agents: List[Agent] = field(default_factory=list)
    tick: int = 0
    death_count: int = 0
    food: FoodSystem = None
    _next_id: int = field(default=0, repr=False)

    def next_id(self):
        self._next_id += 1
        return self._next_id

    def time_of_day(self):
        return (self.tick % DAY_DURATION) / DAY_DURATION

    def is_night(self):
        return self.time_of_day() >= (1 - NIGHT_RATIO)

# -----------------------------
# UTILS
# -----------------------------
def random_position(world, occupied=None):
    if not occupied:
        return (
            random.randint(0, world.width - 1),
            random.randint(0, world.height - 1),
        )

    all_positions = [
        (x, y)
        for x in range(world.width)
        for y in range(world.height)
        if (x, y) not in occupied
    ]

    if not all_positions:
        return None

    return random.choice(all_positions)

# -----------------------------
# INIT WORLD
# -----------------------------
def initialize_world():
    world = World(width=WORLD_WIDTH, height=WORLD_HEIGHT)

    world.food = FoodSystem(world.width, world.height)
    world.food.initialize()

    occupied = set()
    walkable = [
        (x, y)
        for x in range(world.width)
        for y in range(world.height)
        if world.food.is_walkable(x, y)
    ]

    for _ in range(INITIAL_AGENT_COUNT):
        available = [pos for pos in walkable if pos not in occupied]
        if not available:
            break
        x, y = random.choice(available)
        occupied.add((x, y))
        world.agents.append(
            Agent(
                id=world.next_id(),
                x=x,
                y=y,
                energy=MAX_ENERGY / 2,
                generation=0,
                born_tick=0,
            )
        )

    return world

# -----------------------------
# COLLISIONS (AGENT <-> FOOD)
# -----------------------------
def resolve_collisions(world):
    agents = list(world.agents)
    random.shuffle(agents)

    already_eaten = set()

    for agent in agents:
        if not agent.alive:
            continue
        pos = (agent.x, agent.y)
        if pos in already_eaten:
            continue
        gain = world.food.consume_food(pos)
        if gain > 0:
            agent.energy = min(MAX_ENERGY, agent.energy + gain)
            already_eaten.add(pos)

# -----------------------------
# CLEAN DEAD AGENTS
# -----------------------------
def remove_dead_agents(world):
    alive_agents = [a for a in world.agents if a.alive]
    world.death_count += len(world.agents) - len(alive_agents)
    world.agents = alive_agents

# -----------------------------
# MAIN SIMULATION STEP
# -----------------------------
def world_phase(world):
    # 1. les agents pensent et préparent leur action
    for agent in world.agents:
        if not agent.alive:
            continue
        think(agent, world)

    # 2. les agents bougent
    for agent in world.agents:
        if not agent.alive:
            continue
        apply_action(agent, world, agent.pending_action)

    # 3. vieillissement et reproduction après le mouvement
    newborns = []
    for agent in world.agents:
        if not agent.alive:
            continue
        update_agent_life(agent, world)
        if not agent.alive:
            continue
        baby = reproduce(agent, world)
        if baby is not None:
            newborns.append(baby)

    # 4. interactions
    resolve_collisions(world)
    remove_dead_agents(world)

    # 5. ajout des bébés
    for baby in newborns:
        baby.id = world.next_id()
    world.agents.extend(newborns)

    # 6. nourriture
    world.food.grow_food()
    world.tick += 1