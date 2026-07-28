import random

import config
from weather import update_weather, _shrink_water, _expand_water
from map import GameMap
from food import FoodSystem
from world import World
from agent import Agent


def build_world(width, height, biome_overrides, weather=None, soil_moisture=None, tick=0):
    m = GameMap(width=width, height=height)
    m.biome_map = {(x, y): config.BIOME_PRAIRIE for x in range(width) for y in range(height)}
    m.altitude_map = {(x, y): 0.5 for x in range(width) for y in range(height)}
    for pos, biome in biome_overrides.items():
        m.biome_map[pos] = biome
    f = FoodSystem(width=width, height=height)
    f.initialize(m.biome_map)
    w = World(width=width, height=height, map=m, food=f, tick=tick)
    if weather is not None:
        w.weather = weather
    if soil_moisture is not None:
        w.soil_moisture = soil_moisture
    return w


class TestUpdateWeatherTiming:
    def test_weather_unchanged_between_day_boundaries(self, monkeypatch):
        w = build_world(3, 3, {}, weather=config.WEATHER_CLEAR, tick=1)
        # tick=1 n'est pas un multiple de DAY_DURATION (sauf si DAY_DURATION==1)
        assert config.DAY_DURATION > 1
        monkeypatch.setattr(random, "random", lambda: 0.0)  # forcerait un changement si testé
        update_weather(w)
        assert w.weather == config.WEATHER_CLEAR

    def test_moisture_still_updates_on_non_boundary_ticks(self):
        w = build_world(3, 3, {}, weather=config.WEATHER_RAIN, soil_moisture=0.5, tick=1)
        update_weather(w)
        expected = min(config.SOIL_MOISTURE_MAX,
                        0.5 + config.WEATHER_MOISTURE_DELTA[config.WEATHER_RAIN])
        assert w.soil_moisture == expected

    def test_soil_moisture_is_clamped_to_bounds(self):
        w = build_world(3, 3, {}, weather=config.WEATHER_DROUGHT,
                         soil_moisture=config.SOIL_MOISTURE_MIN, tick=1)
        update_weather(w)
        assert w.soil_moisture >= config.SOIL_MOISTURE_MIN

    def test_weather_can_change_on_day_boundary(self, monkeypatch):
        w = build_world(3, 3, {}, weather=config.WEATHER_CLEAR, tick=config.DAY_DURATION)
        monkeypatch.setattr(random, "random", lambda: 0.0)  # < WEATHER_CHANGE_PROB -> change
        monkeypatch.setattr(random, "choices", lambda pop, weights, k: [config.WEATHER_STORM])
        update_weather(w)
        assert w.weather == config.WEATHER_STORM

    def test_weather_stable_when_change_roll_fails(self, monkeypatch):
        w = build_world(3, 3, {}, weather=config.WEATHER_CLEAR, tick=config.DAY_DURATION)
        monkeypatch.setattr(random, "random", lambda: 0.999999)  # > WEATHER_CHANGE_PROB
        update_weather(w)
        assert w.weather == config.WEATHER_CLEAR


class TestExpandWater:
    def test_grows_water_into_adjacent_land(self):
        overrides = {(1, 1): config.BIOME_WATER}
        w = build_world(3, 3, overrides)
        _expand_water(w)
        assert w.map.biome_map[(1, 1)] == config.BIOME_WATER
        # les 4 voisins directs doivent être devenus de l'eau
        for pos in [(0, 1), (2, 1), (1, 0), (1, 2)]:
            assert w.map.biome_map[pos] == config.BIOME_WATER
        # le coin, non adjacent (diagonale), doit rester inchangé
        assert w.map.biome_map[(0, 0)] == config.BIOME_PRAIRIE

    def test_clears_food_on_newly_flooded_cells(self):
        overrides = {(1, 1): config.BIOME_WATER}
        w = build_world(3, 3, overrides)
        w.food.food_map[(0, 1)] = 5
        w.food.food_positions.add((0, 1))
        _expand_water(w)
        assert w.food.food_map[(0, 1)] == 0
        assert (0, 1) not in w.food.food_positions

    def test_drowns_agents_caught_by_expanding_water(self):
        overrides = {(1, 1): config.BIOME_WATER}
        w = build_world(3, 3, overrides)
        drowned = Agent(id=1, x=0, y=1, energy=50, thirst=50)
        safe = Agent(id=2, x=0, y=0, energy=50, thirst=50)
        w.agents = [drowned, safe]
        _expand_water(w)
        assert drowned.alive is False
        assert safe.alive is True

    def test_never_submerges_a_mountain(self):
        # Régression : une tempête qui fait grossir l'eau ne doit jamais
        # engloutir une montagne (rocheuse ou enneigée) -- sans quoi le
        # relief est perdu pour de bon (_shrink_water() ne sait pas
        # reconstruire une montagne, elle ne renvoie que de la prairie).
        overrides = {
            (1, 1): config.BIOME_WATER,
            (0, 1): config.BIOME_MOUNTAIN_ROCK,
            (2, 1): config.BIOME_MOUNTAIN_SNOW,
        }
        w = build_world(3, 3, overrides)
        _expand_water(w)
        assert w.map.biome_map[(0, 1)] == config.BIOME_MOUNTAIN_ROCK
        assert w.map.biome_map[(2, 1)] == config.BIOME_MOUNTAIN_SNOW
        # les autres voisins (non-montagne) continuent, eux, à être inondés
        assert w.map.biome_map[(1, 0)] == config.BIOME_WATER
        assert w.map.biome_map[(1, 2)] == config.BIOME_WATER

    def test_mountain_never_erased_across_full_flood_then_recede_cycle(self):
        # Le scénario exact du bug rapporté : un lac grossit contre une
        # montagne (storm), puis rétrécit (drought) -- la montagne doit
        # être exactement la même à la fin qu'au départ, jamais remplacée
        # par de la prairie.
        overrides = {(1, 1): config.BIOME_WATER, (0, 1): config.BIOME_MOUNTAIN_SNOW}
        w = build_world(3, 3, overrides)
        _expand_water(w)
        _shrink_water(w)
        assert w.map.biome_map[(0, 1)] == config.BIOME_MOUNTAIN_SNOW


class TestShrinkWater:
    def test_shrinks_border_water_to_prairie(self):
        overrides = {(1, 1): config.BIOME_WATER}
        w = build_world(3, 3, overrides)
        _shrink_water(w)
        assert w.map.biome_map[(1, 1)] == config.BIOME_PRAIRIE

    def test_only_shrinks_water_adjacent_to_land(self):
        # Un lac 2x2 entouré de terre : toutes les cases sont bordières ici
        # (dans une grille 4x4, le lac occupe (1,1)-(2,2)), donc tout doit
        # redevenir prairie en un seul appel.
        overrides = {(1, 1): config.BIOME_WATER, (2, 1): config.BIOME_WATER,
                     (1, 2): config.BIOME_WATER, (2, 2): config.BIOME_WATER}
        w = build_world(4, 4, overrides)
        _shrink_water(w)
        for pos in overrides:
            assert w.map.biome_map[pos] == config.BIOME_PRAIRIE

    def test_clears_food_on_newly_dried_cells(self):
        overrides = {(1, 1): config.BIOME_WATER}
        w = build_world(3, 3, overrides)
        # de la nourriture "orpheline" existante sur la case d'eau (cf. quirk food.py)
        w.food.food_map[(1, 1)] = 3
        w.food.food_positions.add((1, 1))
        _shrink_water(w)
        assert w.food.food_map[(1, 1)] == 0
        assert (1, 1) not in w.food.food_positions

    def test_isolated_lake_far_from_land_is_untouched(self):
        # Lac qui occupe TOUTE la carte : aucune case n'est adjacente à de la
        # terre, donc _shrink_water ne doit rien changer.
        m = GameMap(width=2, height=2)
        m.biome_map = {(x, y): config.BIOME_WATER for x in range(2) for y in range(2)}
        m.altitude_map = {(x, y): 0.5 for x in range(2) for y in range(2)}
        f = FoodSystem(width=2, height=2)
        f.initialize(m.biome_map)
        w = World(width=2, height=2, map=m, food=f)
        _shrink_water(w)
        assert all(b == config.BIOME_WATER for b in w.map.biome_map.values())


class TestFloodMemory:
    """flood()/unflood() (voir map.py) : une case inondée par une crue doit
    retrouver EXACTEMENT son relief d'origine à la décrue -- forêt, désert,
    prairie... -- pas systématiquement de la prairie comme avant."""

    def test_flooded_forest_recedes_back_to_forest(self):
        overrides = {(1, 1): config.BIOME_WATER, (0, 1): config.BIOME_FOREST}
        w = build_world(3, 3, overrides)
        _expand_water(w)
        assert w.map.biome_map[(0, 1)] == config.BIOME_WATER  # bien inondée entre-temps
        _shrink_water(w)
        assert w.map.biome_map[(0, 1)] == config.BIOME_FOREST

    def test_flooded_desert_recedes_back_to_desert(self):
        overrides = {(1, 1): config.BIOME_WATER, (0, 1): config.BIOME_DESERT}
        w = build_world(3, 3, overrides)
        _expand_water(w)
        _shrink_water(w)
        assert w.map.biome_map[(0, 1)] == config.BIOME_DESERT

    def test_never_flooded_water_still_falls_back_to_prairie(self):
        # Un vrai lac d'origine (jamais inondé par une crue) : on n'a aucune
        # mémoire de ce qu'il y avait "avant" puisqu'il n'y a jamais rien eu
        # d'autre -- comportement inchangé, retombe sur prairie neutre.
        overrides = {(1, 1): config.BIOME_WATER}
        w = build_world(3, 3, overrides)
        _shrink_water(w)
        assert w.map.biome_map[(1, 1)] == config.BIOME_PRAIRIE

    def test_repeated_flooding_keeps_the_original_biome_in_memory(self):
        # Si une case déjà inondée est floodée une seconde fois (crue qui
        # continue), on ne doit jamais écraser le tout premier relief connu
        # par un état intermédiaire (qui serait déjà de l'eau).
        m = GameMap(width=3, height=3)
        m.biome_map = {(x, y): config.BIOME_PRAIRIE for x in range(3) for y in range(3)}
        m.altitude_map = {(x, y): 0.5 for x in range(3) for y in range(3)}
        m.biome_map[(0, 1)] = config.BIOME_FOREST

        m.flood({(0, 1)})
        assert m.flood_memory[(0, 1)] == (config.BIOME_FOREST, 0.5)
        m.flood({(0, 1)})  # déjà de l'eau : ne doit rien réécrire
        assert m.flood_memory[(0, 1)] == (config.BIOME_FOREST, 0.5)

        m.unflood({(0, 1)})
        assert m.biome_map[(0, 1)] == config.BIOME_FOREST

    def test_unflood_pops_memory_so_it_is_not_reused_later(self):
        # Une fois restaurée, la case ne doit plus garder de mémoire de crue
        # "fantôme" qui referait surface sur un cycle inondation ultérieur
        # et différent.
        overrides = {(1, 1): config.BIOME_WATER, (0, 1): config.BIOME_FOREST}
        w = build_world(3, 3, overrides)
        _expand_water(w)
        _shrink_water(w)
        assert (0, 1) not in w.map.flood_memory

    def test_flood_memory_never_touches_altitude_map_when_module_disabled(self):
        # Rappel : ENABLE_ALTITUDE=False est une source de vérité absolue,
        # rien en aval ne doit remplir altitude_map dans ce mode -- voir le
        # même invariant testé pour get_altitude() dans test_map.py.
        config.ENABLE_ALTITUDE = False
        m = GameMap(width=3, height=3)
        m.biome_map = {(x, y): config.BIOME_PRAIRIE for x in range(3) for y in range(3)}
        m.biome_map[(1, 1)] = config.BIOME_WATER
        m.biome_map[(0, 1)] = config.BIOME_FOREST
        # altitude_map délibérément vide : c'est l'état réel quand le module
        # Altitude est désactivé (voir initialize() / _generate_cell()).
        f = FoodSystem(width=3, height=3)
        f.initialize(m.biome_map)
        w = World(width=3, height=3, map=m, food=f)
        _expand_water(w)
        _shrink_water(w)
        assert w.map.biome_map[(0, 1)] == config.BIOME_FOREST
        assert w.map.altitude_map == {}
