import random
from config import (
    VISION_RADIUS,
    TOROIDAL_WORLD,
    MOVE_COST,
    IDLE_COST,
    MAX_ENERGY,
    MAX_AGE,
    NIGHT_VISION_RATIO,
    NIGHT_IDLE_COST,
    MAX_THIRST,
    THIRST_RATE,
    THIRST_RATE_DESERT,
    THIRST_RATE_NIGHT,
    THIRST_DAMAGE,
    DRINK_AMOUNT,
    THIRST_CRITICAL,
    BIOME_DESERT,
    BIOME_WATER,
    WEATHER_VISION,
    WEATHER_MOVE_COST,
)
from entities import Agent

# -----------------------------
# ACTIONS / ÉTATS
# -----------------------------
ACTION_UP    = 0
ACTION_DOWN  = 1
ACTION_LEFT  = 2
ACTION_RIGHT = 3
ACTION_IDLE  = 4
ACTION_DRINK = 5

STATE_FOOD_DX   = 0
STATE_FOOD_DY   = 1
STATE_FOOD_DIST = 2
STATE_ENERGY    = 3
STATE_THIRST    = 4
STATE_WATER_DX  = 5
STATE_WATER_DY  = 6

ACTION_TO_DELTA = {
    ACTION_UP:    (0, -1),
    ACTION_DOWN:  (0,  1),
    ACTION_LEFT:  (-1, 0),
    ACTION_RIGHT: (1,  0),
    ACTION_IDLE:  (0,  0),
    ACTION_DRINK: (0,  0),
}

# -----------------------------
# PERCEPTION
# -----------------------------
def perceive(agent, world):
    min_food_dist  = float("inf")
    closest_food   = None
    min_water_dist = float("inf")
    closest_water  = None

    night_ratio   = NIGHT_VISION_RATIO if world.is_night() else 1.0
    weather_ratio = WEATHER_VISION.get(world.weather, 1.0)
    current_radius = VISION_RADIUS * night_ratio * weather_ratio
    vision_sq = current_radius * current_radius

    if world.food is None:
        return {
            "food_dx": 0, "food_dy": 0, "food_dist": -1,
            "water_dx": 0, "water_dy": 0, "water_dist": -1,
            "adjacent_water": False,
        }

    for x, y, amount in world.food.iter_food():
        if not world.food.is_walkable(x, y):
            continue
        dx = x - agent.x
        dy = y - agent.y
        if TOROIDAL_WORLD:
            if dx > world.width // 2: dx -= world.width
            elif dx < -world.width // 2: dx += world.width
            if dy > world.height // 2: dy -= world.height
            elif dy < -world.height // 2: dy += world.height
        dist = dx * dx + dy * dy
        if dist > vision_sq:
            continue
        if dist < min_food_dist:
            min_food_dist = dist
            closest_food = (dx, dy)

    adjacent_water = False
    for x in range(max(0, agent.x - int(current_radius)),
                   min(world.width, agent.x + int(current_radius) + 1)):
        for y in range(max(0, agent.y - int(current_radius)),
                       min(world.height, agent.y + int(current_radius) + 1)):
            if world.food.biome_map.get((x, y)) != BIOME_WATER:
                continue
            dx = x - agent.x
            dy = y - agent.y
            dist = dx * dx + dy * dy
            if dist > vision_sq:
                continue
            if dist < min_water_dist:
                min_water_dist = dist
                closest_water = (dx, dy)
            if dist == 1:
                adjacent_water = True

    result = {
        "food_dx": 0, "food_dy": 0, "food_dist": -1,
        "water_dx": 0, "water_dy": 0, "water_dist": -1,
        "adjacent_water": adjacent_water,
    }

    if closest_food is not None:
        dx, dy = closest_food
        result["food_dx"] = dx
        result["food_dy"] = dy
        result["food_dist"] = min_food_dist ** 0.5

    if closest_water is not None:
        dx, dy = closest_water
        result["water_dx"] = dx
        result["water_dy"] = dy
        result["water_dist"] = min_water_dist ** 0.5

    return result

# -----------------------------
# STATE / DÉCISION
# -----------------------------
def build_state_vector(agent, world):
    p = agent.perception
    max_dist = max(world.width, world.height)
    return [
        p["food_dx"] / world.width,
        p["food_dy"] / world.height,
        p["food_dist"] / max_dist if p["food_dist"] != -1 else -1,
        agent.energy / MAX_ENERGY,
        agent.thirst / MAX_THIRST,
        p["water_dx"] / world.width,
        p["water_dy"] / world.height,
    ]

def decide_action(agent):
    s = agent.state_vector
    food_dx   = s[STATE_FOOD_DX]
    food_dy   = s[STATE_FOOD_DY]
    food_dist = s[STATE_FOOD_DIST]
    thirst    = s[STATE_THIRST] * MAX_THIRST
    water_dx  = s[STATE_WATER_DX]
    water_dy  = s[STATE_WATER_DY]

    if thirst < THIRST_CRITICAL and agent.perception["adjacent_water"]:
        return ACTION_DRINK

    if thirst < THIRST_CRITICAL and agent.perception["water_dist"] != -1:
        if abs(water_dx) > abs(water_dy):
            return ACTION_RIGHT if water_dx > 0 else ACTION_LEFT
        return ACTION_DOWN if water_dy > 0 else ACTION_UP

    if food_dist == -1:
        return random.choice([
            ACTION_UP, ACTION_DOWN, ACTION_LEFT, ACTION_RIGHT, ACTION_IDLE
        ])

    if abs(food_dx) > abs(food_dy):
        return ACTION_RIGHT if food_dx > 0 else ACTION_LEFT
    return ACTION_DOWN if food_dy > 0 else ACTION_UP

# -----------------------------
# ACTIONS
# -----------------------------
def apply_action(agent, world, action):
    if not agent.alive:
        return

    if action == ACTION_DRINK:
        agent.thirst = min(MAX_THIRST, agent.thirst + DRINK_AMOUNT)
        return

    dx, dy = ACTION_TO_DELTA[action]
    new_x = agent.x + dx
    new_y = agent.y + dy

    if TOROIDAL_WORLD:
        new_x %= world.width
        new_y %= world.height
    else:
        if not (0 <= new_x < world.width and 0 <= new_y < world.height):
            return

    if world.food is not None and not world.food.is_walkable(new_x, new_y):
        return

    agent.x = new_x
    agent.y = new_y

    if dx != 0 or dy != 0:
        weather_extra = WEATHER_MOVE_COST.get(world.weather, 0.0)
        agent.energy -= (MOVE_COST - IDLE_COST) + weather_extra
    if agent.energy <= 0:
        agent.alive = False

# -----------------------------
# SOIF
# -----------------------------
def update_thirst(agent, world):
    biome = world.food.biome_map.get((agent.x, agent.y))

    if world.is_night():
        rate = THIRST_RATE_NIGHT
    elif biome == BIOME_DESERT:
        rate = THIRST_RATE_DESERT
    else:
        rate = THIRST_RATE

    agent.thirst = max(0, agent.thirst - rate)

    if agent.thirst <= 0:
        agent.energy -= THIRST_DAMAGE
        if agent.energy <= 0:
            agent.alive = False

# -----------------------------
# VIE / REPRODUCTION
# -----------------------------
def update_agent_life(agent, world):
    agent.age += 1
    idle_cost = NIGHT_IDLE_COST if world.is_night() else IDLE_COST
    agent.energy -= idle_cost + (agent.age / MAX_AGE) * 0.1
    if agent.age >= MAX_AGE or agent.energy <= 0:
        agent.alive = False
        return
    update_thirst(agent, world)

def reproduce(agent, world):
    if agent.energy <= 80 or agent.thirst <= 40:
        return None

    occupied = {(a.x, a.y) for a in world.agents}

    neighbors = [
        (agent.x + dx, agent.y + dy)
        for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]
        if 0 <= agent.x + dx < world.width
        and 0 <= agent.y + dy < world.height
        and (agent.x + dx, agent.y + dy) not in occupied
        and world.food.is_walkable(agent.x + dx, agent.y + dy)
    ]

    if not neighbors:
        return None

    x, y = random.choice(neighbors)
    agent.energy -= 40

    return Agent(
        id=-1,
        x=x,
        y=y,
        generation=agent.generation + 1,
        born_tick=world.tick,
        energy=40,
        thirst=50,
        age=0,
        alive=True,
    )

# -----------------------------
# THINK
# -----------------------------
def think(agent, world):
    agent.perception = perceive(agent, world)
    agent.state_vector = build_state_vector(agent, world)
    agent.pending_action = decide_action(agent)

# -----------------------------
# PHASE AGENT
# -----------------------------
def agent_phase(world):
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
        think(agent, world)
    return newborns