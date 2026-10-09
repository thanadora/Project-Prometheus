"""
flood.py — Inondations temporaires déclenchées par la pluie et la tempête.

Pendant un épisode pluvieux, des berges (cases praticables adjacentes à
l'eau) sont recouvertes : elles deviennent infranchissables, puis l'eau se
retire au bout de FLOOD_DURATION ticks. S'appuie sur GameMap.flood()/
unflood(), qui mémorisent le biome d'origine pour le restaurer à la décrue.

État sauvegardé dans le World :
  flooded : {(x, y): ticks restants avant décrue}
"""

import random
from logger import get_logger
import config

_NEIGHBORS = [(-1, 0), (1, 0), (0, -1), (0, 1)]


def _in_bounds(world, pos):
    if getattr(world, "infinite", False):
        return True
    return 0 <= pos[0] < world.width and 0 <= pos[1] < world.height


def _find_shore_cell(world, radius):
    """Cherche une case praticable adjacente à l'eau, près d'un agent (monde
    infini) ou n'importe où (monde classique). Échantillonnage aléatoire borné :
    pas de scan complet de la carte à chaque tick."""
    infinite = getattr(world, "infinite", False)

    if infinite:
        agents = [a for a in world.agents if a.alive]
        if not agents:
            return None
        a = random.choice(agents)
        x_min, x_max = a.x - radius, a.x + radius
        y_min, y_max = a.y - radius, a.y + radius
    else:
        x_min, x_max = 0, world.width - 1
        y_min, y_max = 0, world.height - 1

    for _ in range(24):
        x = random.randint(x_min, x_max)
        y = random.randint(y_min, y_max)
        if (x, y) in world.flooded:
            continue
        if world.map.get_biome(x, y) == config.BIOME_WATER:
            continue
        if any(_in_bounds(world, (x + dx, y + dy))
               and world.map.get_biome(x + dx, y + dy) == config.BIOME_WATER
               for dx, dy in _NEIGHBORS):
            return (x, y)
    return None


def update_floods(world):
    """Un tick d'inondation : décrue des cases en cours puis montée éventuelle
    selon la météo. Appelé par world_phase() quand ENABLE_FLOODS est actif."""
    log = get_logger()

    # 1. Décrue : les cases dont le timer est écoulé redeviennent normales.
    receding = [pos for pos, remaining in world.flooded.items() if remaining <= 1]
    if receding:
        world.map.unflood(receding, world)
        for pos in receding:
            del world.flooded[pos]
    for pos in world.flooded:
        world.flooded[pos] -= 1

    # 2. Montée : seulement sous la pluie / la tempête, avec un plafond global.
    chance = 0.0
    if world.weather == config.WEATHER_RAIN:
        chance = config.FLOOD_CHANCE_RAIN
    elif world.weather == config.WEATHER_STORM:
        chance = config.FLOOD_CHANCE_STORM
    if chance <= 0 or len(world.flooded) >= config.FLOOD_MAX_CELLS:
        return
    if random.random() >= chance:
        return

    flooded_now = 0
    for _ in range(config.FLOOD_CELLS_PER_EVENT):
        if len(world.flooded) >= config.FLOOD_MAX_CELLS:
            break
        pos = _find_shore_cell(world, config.FLOOD_RADIUS)
        if pos is None:
            continue
        world.map.flood([pos], world)
        world.food.clear_position(pos)
        world.flooded[pos] = config.FLOOD_DURATION
        flooded_now += 1
    if flooded_now:
        log.info(world.tick, f"🌊 Crue : {flooded_now} case(s) inondée(s) "
                             f"({len(world.flooded)} au total)")
