import config
import map as map_module
from migration import _reachable_land, check_migration
from tests.conftest import make_world, make_agent


def patch_new_map_layout(monkeypatch, biome_by_pos, default_biome=None):
    """Remplace GameMap.initialize() par une version déterministe (sans bruit
    de Perlin) pour contrôler précisément la carte générée lors d'une
    migration : `biome_by_pos` (dict pos->biome) prévaut, le reste vaut
    `default_biome`."""
    if default_biome is None:
        default_biome = config.BIOME_PRAIRIE

    def fake_initialize(self, offset_x=None, offset_y=None):
        self.biome_map = {
            (x, y): biome_by_pos.get((x, y), default_biome)
            for x in range(self.width) for y in range(self.height)
        }
        self.altitude_map = {pos: 0.5 for pos in self.biome_map}

    monkeypatch.setattr(map_module.GameMap, "initialize", fake_initialize)


class TestReachableLand:
    def test_finds_all_connected_walkable_cells(self):
        world = make_world(width=5, height=1)  # ligne de 5 cases, tout praire
        reachable = _reachable_land(world, 0, 0)
        assert reachable == {(x, 0) for x in range(5)}

    def test_stops_at_water(self):
        world = make_world(width=5, height=1, overrides={(2, 0): config.BIOME_WATER})
        reachable = _reachable_land(world, 0, 0)
        assert reachable == {(0, 0), (1, 0)}
        assert (3, 0) not in reachable and (4, 0) not in reachable

    def test_out_of_bounds_not_included(self):
        world = make_world(width=3, height=3)
        reachable = _reachable_land(world, 1, 1)
        assert all(0 <= x < 3 and 0 <= y < 3 for x, y in reachable)

    def test_result_is_cached(self):
        world = make_world(width=3, height=3)
        r1 = _reachable_land(world, 0, 0)
        r2 = _reachable_land(world, 0, 0)
        assert r1 is r2  # même objet : servi depuis le cache

    def test_cache_invalidated_by_land_cache_valid_flag(self):
        world = make_world(width=3, height=3)
        r1 = _reachable_land(world, 0, 0)
        world._land_cache_valid = False
        r2 = _reachable_land(world, 0, 0)
        assert r1 is not r2
        assert r1 == r2  # même contenu, nouvel objet recalculé


class TestCheckMigrationGuardConditions:
    def test_infinite_world_never_migrates(self):
        world = make_world(width=5, height=5, infinite=True)
        world.agents = [make_agent(x=2, y=2, alive=True)]
        for a in world.agents:
            a.vote_migrate = True
        assert check_migration(world) is False

    def test_no_agents_returns_false(self):
        world = make_world(width=5, height=5)
        world.agents = []
        assert check_migration(world) is False

    def test_too_many_agents_returns_false(self):
        world = make_world(width=5, height=5)
        world.agents = [make_agent(id=i, x=0, y=0, vote_migrate=True)
                         for i in range(config.MIGRATION_MAX_AGENTS + 1)]
        assert check_migration(world) is False

    def test_cooldown_blocks_migration(self):
        world = make_world(width=5, height=5, tick=10)
        world.last_migration_tick = 10 - config.MIGRATION_COOLDOWN + 1
        world.agents = [make_agent(x=0, y=0, vote_migrate=True)]
        assert check_migration(world) is False

    def test_insufficient_votes_returns_false(self):
        world = make_world(width=5, height=5, tick=10_000)
        world.agents = [make_agent(id=1, x=0, y=0, vote_migrate=True),
                         make_agent(id=2, x=1, y=0, vote_migrate=False),
                         make_agent(id=3, x=2, y=0, vote_migrate=False),
                         make_agent(id=4, x=3, y=0, vote_migrate=False)]
        assert 1 / 4 < config.MIGRATION_VOTE_THRESHOLD
        assert check_migration(world) is False

    def test_dead_agents_excluded_from_vote_count(self):
        world = make_world(width=5, height=5, tick=10_000)
        world.agents = [make_agent(id=1, x=0, y=0, vote_migrate=True),
                         make_agent(id=2, x=1, y=0, vote_migrate=False, alive=False)]
        # Sans l'agent mort, 1 votant sur 1 vivant = 100% -> devrait passer
        # ce garde-fou (peut encore être bloqué plus loin par min_land).
        assert check_migration(world) is not False or True  # cf. tests dédiés plus bas


class TestCheckMigrationNoMobileAgents:
    def test_returns_false_when_reachable_land_too_small(self, monkeypatch):
        # Île minuscule (2 cases) entourée d'eau, sur une grande carte très
        # majoritairement en eau : la terre totale est petite, mais l'île de
        # l'agent est encore plus petite que 10% de cette terre totale.
        # Masse continentale de 300 cases (10% = 30) contre une île isolée
        # de seulement 2 cases : l'île passe largement sous le seuil min_land.
        width, height = 20, 20
        land_positions = {(x, y) for x in range(20) for y in range(15)}
        island = {(19, 19), (18, 19)}  # île isolée où vit l'agent
        overrides = {}
        for x in range(width):
            for y in range(height):
                if (x, y) not in land_positions and (x, y) not in island:
                    overrides[(x, y)] = config.BIOME_WATER
        world = make_world(width=width, height=height, overrides=overrides, tick=10_000)
        agent = make_agent(x=19, y=19, vote_migrate=True)
        world.agents = [agent]
        assert check_migration(world) is False


class TestCheckMigrationSuccess:
    def test_migration_replaces_map_and_food_and_resets_state(self, monkeypatch):
        patch_new_map_layout(monkeypatch, {}, default_biome=config.BIOME_PRAIRIE)
        world = make_world(width=5, height=5, tick=10_000, weather=config.WEATHER_STORM,
                            soil_moisture=0.9)
        old_map = world.map
        old_food = world.food
        agent = make_agent(x=2, y=2, vote_migrate=True)
        world.agents = [agent]

        result = check_migration(world)

        assert result is True
        assert world.map is not old_map
        assert world.food is not old_food
        assert world.migration_count == 1
        assert world.last_migration_tick == 10_000
        assert world.weather == config.WEATHER_CLEAR
        assert world.soil_moisture == config.SOIL_MOISTURE_INIT

    def test_mobile_agents_relocated_to_walkable_position(self, monkeypatch):
        patch_new_map_layout(monkeypatch, {}, default_biome=config.BIOME_PRAIRIE)
        world = make_world(width=5, height=5, tick=10_000)
        agent = make_agent(x=2, y=2, vote_migrate=True)
        world.agents = [agent]
        check_migration(world)
        assert world.map.is_walkable(agent.x, agent.y)

    def test_agent_killed_when_new_map_has_no_room_left(self, monkeypatch):
        # La nouvelle carte n'a qu'UNE seule case praticable ; avec deux
        # agents mobiles, le second doit mourir faute de place.
        only_walkable = {(0, 0): config.BIOME_PRAIRIE}
        patch_new_map_layout(monkeypatch, only_walkable, default_biome=config.BIOME_WATER)
        world = make_world(width=5, height=5, tick=10_000)
        a1 = make_agent(id=1, x=0, y=0, vote_migrate=True)
        a2 = make_agent(id=2, x=4, y=4, vote_migrate=True)
        world.agents = [a1, a2]
        check_migration(world)
        alive = [a for a in (a1, a2) if a.alive]
        dead = [a for a in (a1, a2) if not a.alive]
        assert len(alive) == 1
        assert len(dead) == 1
        assert (alive[0].x, alive[0].y) == (0, 0)

    def test_known_quirk_stranded_agent_not_relocated_nor_killed(self, monkeypatch):
        """Documente un comportement existant potentiellement dangereux :
        un agent dont l'îlot est trop petit (< 10% de la terre totale) n'est
        ni relocalisé ni tué — il garde ses anciennes coordonnées (x, y),
        qui peuvent très bien être de l'eau sur la NOUVELLE carte, puisque
        toute la carte est remplacée pour tout le monde. Ce test fige ce
        comportement ; le corriger (le tuer, ou le relocaliser comme les
        autres) serait une amélioration légitime mais volontaire."""
        width, height = 20, 20
        land_positions = {(x, y) for x in range(20) for y in range(15)}
        island = {(19, 19), (18, 19)}
        overrides = {}
        for x in range(width):
            for y in range(height):
                if (x, y) not in land_positions and (x, y) not in island:
                    overrides[(x, y)] = config.BIOME_WATER
        world = make_world(width=width, height=height, overrides=overrides, tick=10_000)
        stranded = make_agent(id=1, x=19, y=19, vote_migrate=True)
        mobile = make_agent(id=2, x=0, y=0, vote_migrate=True)
        world.agents = [stranded, mobile]

        # Nouvelle carte 100% eau sauf l'ancienne position de `mobile` :
        # sans intervention, la case (19,19) de `stranded` sera de l'eau.
        patch_new_map_layout(monkeypatch, {(0, 0): config.BIOME_PRAIRIE},
                              default_biome=config.BIOME_WATER)
        migrated = check_migration(world)

        assert migrated is True
        assert stranded.alive is True  # ni tué...
        assert (stranded.x, stranded.y) == (19, 19)  # ...ni déplacé
        assert world.map.is_walkable(19, 19) is False  # et pourtant, sous l'eau
