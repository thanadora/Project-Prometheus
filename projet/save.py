import json
import config
from world import World
from map import GameMap
from food import FoodSystem
from agent import Agent
from policy_registry import REGISTRY, default_policy_name, make_policy, policy_name
from logger import get_logger


class SaveFileError(Exception):
    """Fichier de sauvegarde introuvable, illisible, invalide ou tronqué.

    Levée par load_world() avec un message explicite ; la GUI l'attrape pour
    afficher une erreur propre au lieu de laisser remonter un KeyError/JSON
    brut de l'intérieur de la mécanique de chargement.
    """


def _parse_pos_key(key):
    x, y = key.split(",")
    return (int(x), int(y))


def _require(data, key):
    if key not in data:
        raise SaveFileError(f"Sauvegarde invalide : champ obligatoire manquant « {key} »")
    return data[key]


def _pos_map_to_str(pos_map):
    return {f"{x},{y}": value for (x, y), value in pos_map.items()}


def save_world(world, path):
    data = {
        "tick":                 world.tick,
        "width":                world.width,
        "height":               world.height,
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
                "fatigue":    a.fatigue,
                "sick_ticks": a.sick_ticks,
                "age":        a.age,
                "alive":      a.alive,
                "generation": a.generation,
                "born_tick":  a.born_tick,
                "inventory":  a.inventory,
                "policy":     policy_name(a.policy),
            }
            for a in world.agents
        ],
        "biome_map": _pos_map_to_str(world.map.biome_map),
        "food_map":  _pos_map_to_str(world.food.food_map),
        "food_age":  _pos_map_to_str(world.food.food_age),
        "burning":   _pos_map_to_str(world.burning),
        "burnt":     _pos_map_to_str(world.burnt),
        "flooded":   _pos_map_to_str(world.flooded),
    }
    try:
        with open(path, "w") as f:
            json.dump(data, f)
    except OSError as e:
        raise SaveFileError(f"Impossible d'écrire la sauvegarde {path} : {e}") from e


def load_world(path):
    try:
        with open(path) as f:
            data = json.load(f)
    except FileNotFoundError as e:
        raise SaveFileError(f"Fichier introuvable : {path}") from e
    except json.JSONDecodeError as e:
        raise SaveFileError(f"Sauvegarde illisible (JSON invalide) : {e}") from e
    except OSError as e:
        raise SaveFileError(f"Impossible de lire la sauvegarde {path} : {e}") from e

    if not isinstance(data, dict):
        raise SaveFileError("Sauvegarde invalide : le contenu racine n'est pas un objet JSON")

    # Les dimensions sont relues depuis le fichier : une sauvegarde faite avec
    # une autre taille de monde que la config actuelle reste chargée correctement.
    width    = int(data.get("width",  config.WORLD_WIDTH))
    height   = int(data.get("height", config.WORLD_HEIGHT))
    infinite = data.get("infinite", False)

    world                    = World(width=width, height=height, infinite=infinite)
    world.tick               = _require(data, "tick")
    world.weather            = data.get("weather", config.WEATHER_CLEAR)
    world.soil_moisture      = data.get("soil_moisture", config.SOIL_MOISTURE_INIT)
    world.death_count        = data.get("death_count", 0)
    world.migration_count    = data.get("migration_count", 0)
    world.last_migration_tick = data.get("last_migration_tick", -9999)
    world._next_id           = data.get("_next_id", 0)

    world.map = GameMap(width=width, height=height, infinite=infinite)
    # Réutilise exactement le même bruit qu'à la sauvegarde, pour que les zones
    # pas encore visitées se génèrent identiques à ce qu'elles auraient été.
    world.map.initialize(
        offset_x=data.get("map_offset_x"),
        offset_y=data.get("map_offset_y"),
    )
    try:
        world.map.biome_map = {
            _parse_pos_key(k): v
            for k, v in _require(data, "biome_map").items()
        }
    except (ValueError, AttributeError) as e:
        raise SaveFileError(f"biome_map invalide dans la sauvegarde : {e}") from e

    world.food = FoodSystem(width=width, height=height)
    try:
        world.food.food_map = {
            _parse_pos_key(k): v
            for k, v in _require(data, "food_map").items()
        }
        world.food.food_age = {
            _parse_pos_key(k): v
            for k, v in data.get("food_age", {}).items()
        }
        world.burning = {
            _parse_pos_key(k): v
            for k, v in data.get("burning", {}).items()
        }
        world.burnt = {
            _parse_pos_key(k): v
            for k, v in data.get("burnt", {}).items()
        }
        world.flooded = {
            _parse_pos_key(k): v
            for k, v in data.get("flooded", {}).items()
        }
    except (ValueError, AttributeError) as e:
        raise SaveFileError(f"Données de nourriture/catastrophes invalides : {e}") from e
    world.food.food_positions = {
        pos for pos, amount in world.food.food_map.items()
        if amount > 0
    }

    default_name = default_policy_name()
    agents = []
    for i, a in enumerate(_require(data, "agents")):
        try:
            # Policy inconnue = IA retirée du registre depuis la sauvegarde :
            # on ne bloque pas le chargement, l'agent retombe sur la policy
            # par défaut avec un avertissement.
            saved_policy = a.get("policy")
            if saved_policy not in REGISTRY:
                if saved_policy:
                    get_logger().warning(
                        data.get("tick", 0),
                        f"Policy « {saved_policy} » introuvable dans le registre — "
                        f"repli sur « {default_name} » pour l'agent #{a.get('id', '?')}",
                    )
                saved_policy = default_name
            agents.append(Agent(
                id=a["id"],
                x=a["x"],
                y=a["y"],
                energy=a["energy"],
                thirst=a["thirst"],
                fatigue=a.get("fatigue", 0.0),
                sick_ticks=a.get("sick_ticks", 0),
                age=a["age"],
                alive=a["alive"],
                generation=a["generation"],
                born_tick=a["born_tick"],
                inventory=[
                    it if isinstance(it, dict) else {"type": config.OBJECT_TYPE_FOOD, "value": it}
                    for it in a.get("inventory", [])
                ],
                policy=make_policy(saved_policy),
            ))
        except (KeyError, TypeError) as e:
            raise SaveFileError(f"Agent #{i} invalide dans la sauvegarde : {e}") from e
    world.agents = agents

    world._land_cache       = {}
    world._land_cache_valid = True
    world._cells_for_pos    = {}
    world._active_cells_sig = None

    return world
