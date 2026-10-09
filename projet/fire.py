"""
fire.py — Incendies de forêt.

Module purement environnemental : un feu démarre aléatoirement quand les
conditions s'y prêtent (été, sécheresse), se propage de forêt en forêt,
détruit la nourriture des cases touchées, blesse les agents qui s'y trouvent,
puis laisse une cendre fertile (BIOME_BURNT) qui redevient prairie.

Tout l'état vit dans le World (`burning`, `burnt`) pour être sauvegardable :
  burning : {(x, y): ticks de combustion restants}
  burnt   : {(x, y): ticks de cendre fertile restants}
"""

import random
from logger import get_logger
import config

_NEIGHBORS = [(-1, 0), (1, 0), (0, -1), (0, 1)]


def _in_bounds(world, pos):
    if getattr(world, "infinite", False):
        return True
    return 0 <= pos[0] < world.width and 0 <= pos[1] < world.height


def _weather_mult(world):
    return config.FIRE_WEATHER_MULT.get(world.weather, 1.0)


def _season_mult(world):
    return config.FIRE_SEASON_MULT.get(world.current_season(), 1.0)


def _ignite(world, pos):
    """Allume une case si c'est de la forêt et si le garde-fou le permet."""
    if pos in world.burning:
        return False
    if len(world.burning) >= config.FIRE_MAX_ACTIVE:
        return False
    if world.map.get_biome(*pos) != config.BIOME_FOREST:
        return False
    world.burning[pos] = config.FIRE_BURN_DURATION
    world.food.clear_position(pos)
    return True


def _pick_forest_cell(world, attempts=40):
    """Cherche une case de forêt où démarrer un feu.

    Sans ça, le départ tirait une case uniformément sur la carte : comme la
    forêt ne couvre qu'une petite fraction du monde, la plupart des
    "départs" échouaient silencieusement et les feux étaient quasi
    invisibles en jeu. En monde infini, on échantillonne autour d'un agent
    (là où le terrain est chargé) ; en monde classique, sur toute la carte."""
    infinite = getattr(world, "infinite", False)
    if infinite:
        agents = [a for a in world.agents if a.alive]
        if not agents:
            return None
        a = random.choice(agents)
        r = config.FOOD_GROWTH_RADIUS
        for _ in range(attempts):
            pos = (a.x + random.randint(-r, r), a.y + random.randint(-r, r))
            if world.map.get_biome(*pos) == config.BIOME_FOREST:
                return pos
        return None
    for _ in range(attempts):
        pos = (random.randrange(world.width), random.randrange(world.height))
        if world.map.get_biome(*pos) == config.BIOME_FOREST:
            return pos
    return None


def _try_ignition(world):
    """Départ de feu aléatoire. La météo et la saison modulent la probabilité ;
    sous la pluie/le gel elle est nulle (ou presque)."""
    mult = _weather_mult(world) * _season_mult(world)
    if mult <= 0:
        return
    if random.random() >= config.FIRE_IGNITION_CHANCE * mult:
        return

    pos = _pick_forest_cell(world)
    if pos is None:
        return
    if _ignite(world, pos):
        get_logger().info(
            world.tick,
            f"🔥 Départ de feu en {pos} — météo : "
            f"{config.WEATHER_NAMES.get(world.weather, '?')}",
        )


def update_fires(world):
    """Un tick de feu : départ éventuel, propagation, combustion, cendre,
    dégâts aux agents. Appelé par world_phase() quand ENABLE_FIRES est actif."""
    log = get_logger()

    # 1. Départ aléatoire (indépendant des feux déjà en cours).
    _try_ignition(world)

    # 2. Propagation aux forêts voisines.
    spread = config.FIRE_SPREAD_CHANCE * _weather_mult(world)
    if spread > 0:
        newly = []
        for pos in list(world.burning):
            x, y = pos
            for dx, dy in _NEIGHBORS:
                npos = (x + dx, y + dy)
                if not _in_bounds(world, npos):
                    continue
                if npos in world.burning:
                    continue
                if world.map.get_biome(*npos) != config.BIOME_FOREST:
                    continue
                if random.random() < spread:
                    newly.append(npos)
        for pos in newly:
            _ignite(world, pos)

    # 3. Combustion : progression, extinction par la pluie, transformation en cendre.
    extinguish = (config.FIRE_EXTINGUISH_CHANCE_RAIN
                  if world.weather in (config.WEATHER_RAIN, config.WEATHER_STORM)
                  else 0.0)
    burned_out = []
    for pos in list(world.burning):
        if extinguish and random.random() < extinguish:
            del world.burning[pos]
            log.debug(world.tick, f"🔥 Pluie : feu éteint en {pos}")
            continue
        remaining = world.burning[pos] - 1
        if remaining <= 0:
            burned_out.append(pos)
        else:
            world.burning[pos] = remaining

    for pos in burned_out:
        del world.burning[pos]
        world.map.biome_map[pos] = config.BIOME_BURNT
        world.burnt[pos] = config.FIRE_ASH_DURATION
        world._cells_for_pos = {}   # le biome a changé : cache des cases actives périmé
        log.debug(world.tick, f"🔥→🌱 Case brûlée en {pos} (cendre fertile)")

    # 4. La cendre fertile redevient prairie. Les cases qui viennent de brûler
    #    ce tick ne vieillissent pas immédiatement (elles ont leur durée pleine).
    just_burnt = set(burned_out)
    for pos in list(world.burnt):
        if pos in just_burnt:
            continue
        world.burnt[pos] -= 1
        if world.burnt[pos] <= 0:
            del world.burnt[pos]
            world.map.biome_map[pos] = config.BIOME_PRAIRIE
            world._cells_for_pos = {}

    # 5. Dégâts : un agent dans les flammes perd de l'énergie.
    if world.burning and config.FIRE_DAMAGE > 0:
        for agent in world.agents:
            if agent.alive and (agent.x, agent.y) in world.burning:
                agent.energy -= config.FIRE_DAMAGE
                if agent.energy <= 0:
                    agent.alive = False
                    log.info(world.tick, f"Agent #{agent.id} mort dans les flammes en ({agent.x},{agent.y})")
