import json
import config
from world import World
from map import GameMap
from food import FoodSystem
from agent import Agent
from policy_registry import make_policy, policy_name


def save_world(world, path):
    data = {
        "tick":                 world.tick,
        "weather":              world.weather,
        "soil_moisture":        world.soil_moisture,
        "death_count":          world.death_count,
        "migration_count":      world.migration_count,
        "last_migration_tick":  world.last_migration_tick,
        "_next_id":             world._next_id,
        "infinite":             getattr(world, "infinite", False),
        "map_offset_x":         world.map._offset_x,
        "map_offset_y":         world.map._offset_y,
        "agents": [
            {
                "id":         a.id,
                "x":          a.x,
                "y":          a.y,
                "energy":     a.energy,
                "thirst":     a.thirst,
                "age":        a.age,
                "alive":      a.alive,
                "generation": a.generation,
                "born_tick":  a.born_tick,
                "inventory":  a.inventory,
                "policy":     policy_name(a.policy),
            }
            for a in world.agents
        ],
        "biome_map": {
            f"{x},{y}": biome
            for (x, y), biome in world.map.biome_map.items()
        },
        "food_map": {
            f"{x},{y}": amount
            for (x, y), amount in world.food.food_map.items()
        },
    }
    with open(path, "w") as f:
        json.dump(data, f)


def load_world(path):
    with open(path) as f:
        data = json.load(f)

    from config import WORLD_WIDTH, WORLD_HEIGHT

    infinite = data.get("infinite", False)

    world                    = World(width=WORLD_WIDTH, height=WORLD_HEIGHT, infinite=infinite)
    world.tick               = data["tick"]
    world.weather            = data["weather"]
    world.soil_moisture      = data["soil_moisture"]
    world.death_count        = data["death_count"]
    world.migration_count    = data["migration_count"]
    world.last_migration_tick = data["last_migration_tick"]
    world._next_id           = data["_next_id"]

    world.map = GameMap(width=WORLD_WIDTH, height=WORLD_HEIGHT, infinite=infinite)
    # Réutilise exactement le même bruit qu'à la sauvegarde, pour que les zones
    # pas encore visitées se génèrent identiques à ce qu'elles auraient été.
    world.map.initialize(
        offset_x=data.get("map_offset_x"),
        offset_y=data.get("map_offset_y"),
    )
    world.map.biome_map = {
        (int(k.split(",")[0]), int(k.split(",")[1])): v
        for k, v in data["biome_map"].items()
    }

    world.food = FoodSystem(width=WORLD_WIDTH, height=WORLD_HEIGHT)
    world.food.food_map = {
        (int(k.split(",")[0]), int(k.split(",")[1])): v
        for k, v in data["food_map"].items()
    }
    world.food.food_positions = {
        pos for pos, amount in world.food.food_map.items()
        if amount > 0
    }
    world.agents = [
        Agent(
            id=a["id"],
            x=a["x"],
            y=a["y"],
            energy=a["energy"],
            thirst=a["thirst"],
            age=a["age"],
            alive=a["alive"],
            generation=a["generation"],
            born_tick=a["born_tick"],
            inventory=[
                it if isinstance(it, dict) else {"type": config.OBJECT_TYPE_FOOD, "value": it}
                for it in a.get("inventory", [])
            ],
            policy=make_policy(a["policy"]) if a.get("policy") else make_policy("Hardcoded"),
        )
        for a in data["agents"]
    ]

    world._land_cache       = {}
    world._land_cache_valid = True
    
    return world