"""
test_renderer.py — Tests du rendu sans tkinter.

renderer.py n'était pas testé (module d'interface) ; la plupart de ses
fonctions ne touchent pourtant que des données pures et un objet "canvas".
On fournit ici un faux canvas qui enregistre les appels : ça permet de
vérifier les couleurs (feux, crues, nourriture pourrie), les overlays et le
texte du panneau agent sans avoir besoin d'un display.
"""

import config
from actions import ACTION_SLEEP
from renderer import (
    draw_biomes, draw_grid, draw_foods, draw_agents, agent_panel_text,
    top_margin, _blend_hex,
)

from tests.conftest import make_world, make_agent


class FakeCanvas:
    def __init__(self):
        self.rects = []
        self.lines = []
        self.texts = []
        self.ovals = []

    def create_rectangle(self, *a, **k):
        self.rects.append((a, k))

    def create_line(self, *a, **k):
        self.lines.append((a, k))

    def create_text(self, *a, **k):
        self.texts.append((a, k))

    def create_oval(self, *a, **k):
        self.ovals.append((a, k))


class TestDrawBiomes:
    def test_one_rect_per_cell_when_flat(self):
        config.ENABLE_ALTITUDE = False
        config.ENABLE_DAY_NIGHT = False
        world = make_world(width=3, height=2)
        canvas = FakeCanvas()
        draw_biomes(canvas, world, 0, 0, 3, 2, config.CELL_SIZE)
        assert len(canvas.rects) == 6

    def test_burning_cell_uses_fire_color(self):
        config.ENABLE_ALTITUDE = False
        config.ENABLE_DAY_NIGHT = False
        world = make_world(width=2, height=1)
        world.burning[(0, 0)] = 5
        canvas = FakeCanvas()
        draw_biomes(canvas, world, 0, 0, 2, 1, config.CELL_SIZE)
        fills = [k["fill"] for _, k in canvas.rects]
        assert "#ff5a00" in fills

    def test_burning_cell_shows_fire_marker(self):
        config.ENABLE_ALTITUDE = False
        config.ENABLE_DAY_NIGHT = False
        world = make_world(width=2, height=1)
        world.burning[(1, 0)] = 5
        canvas = FakeCanvas()
        draw_biomes(canvas, world, 0, 0, 2, 1, config.CELL_SIZE)
        # Marqueur 🔥 explicite, visible même de nuit ou sous la pluie.
        assert any(k.get("text") == "🔥" for _, k in canvas.texts)

    def test_flooded_cell_uses_flood_color(self):
        config.ENABLE_ALTITUDE = False
        config.ENABLE_DAY_NIGHT = False
        world = make_world(width=2, height=1)
        world.flooded[(1, 0)] = 30
        canvas = FakeCanvas()
        draw_biomes(canvas, world, 0, 0, 2, 1, config.CELL_SIZE)
        fills = [k["fill"] for _, k in canvas.rects]
        assert "#2e6da4" in fills

    def test_burnt_biome_has_its_own_color(self):
        config.ENABLE_ALTITUDE = False
        config.ENABLE_DAY_NIGHT = False
        world = make_world(width=1, height=1,
                           overrides={(0, 0): config.BIOME_BURNT})
        canvas = FakeCanvas()
        draw_biomes(canvas, world, 0, 0, 1, 1, config.CELL_SIZE)
        assert canvas.rects[0][1]["fill"] == config.BIOME_COLORS[config.BIOME_BURNT]

    def test_view_offsets_apply(self):
        config.ENABLE_ALTITUDE = False
        config.ENABLE_DAY_NIGHT = False
        world = make_world(width=10, height=10)
        canvas = FakeCanvas()
        draw_biomes(canvas, world, 5, 5, 2, 2, config.CELL_SIZE)
        assert len(canvas.rects) == 4


class TestDrawGrid:
    def test_no_grid_in_2_5d(self):
        config.ENABLE_ALTITUDE = True
        config.ENABLE_ALTITUDE_2_5D = True
        canvas = FakeCanvas()
        draw_grid(canvas, 3, 2, config.CELL_SIZE)
        assert canvas.lines == []

    def test_grid_when_flat(self):
        config.ENABLE_ALTITUDE = False
        canvas = FakeCanvas()
        draw_grid(canvas, 3, 2, config.CELL_SIZE)
        assert len(canvas.lines) == (3 + 1) + (2 + 1)


class TestTopMargin:
    def test_zero_when_2_5d_disabled(self):
        config.ENABLE_ALTITUDE_2_5D = False
        assert top_margin() == 0

    def test_positive_when_2_5d_enabled(self):
        config.ENABLE_ALTITUDE = True
        config.ENABLE_ALTITUDE_2_5D = True
        config.ALTITUDE_MAX_OFFSET = 10
        assert top_margin() == 30


class TestDrawFoods:
    def test_fresh_food_uses_biome_color(self):
        config.ENABLE_DAY_NIGHT = False
        world = make_world(width=3, height=1, food_amounts={(1, 0): 1})
        canvas = FakeCanvas()
        draw_foods(canvas, world, 0, 0, 3, 1, config.CELL_SIZE)
        assert len(canvas.rects) == 1
        assert canvas.rects[0][1]["fill"] == config.FOOD_TYPES[config.BIOME_PRAIRIE]["color"]

    def test_rotting_food_color_shifts_toward_brown(self):
        config.ENABLE_DAY_NIGHT = False
        config.ENABLE_FOOD_ROT = True
        world = make_world(width=3, height=1, food_amounts={(1, 0): 1})
        # Mi-pourriture : fraîcheur > seuil de la tête de mort, mais < 1.
        world.food.food_age[(1, 0)] = config.FOOD_FRESH_TICKS + config.FOOD_ROT_TICKS // 4
        canvas = FakeCanvas()
        draw_foods(canvas, world, 0, 0, 3, 1, config.CELL_SIZE)
        fresh = config.FOOD_TYPES[config.BIOME_PRAIRIE]["color"]
        assert canvas.rects[0][1]["fill"] != fresh

    def test_rotten_food_is_marked_with_skull(self):
        config.ENABLE_DAY_NIGHT = False
        config.ENABLE_FOOD_ROT = True
        world = make_world(width=3, height=1, food_amounts={(1, 0): 1})
        world.food.food_age[(1, 0)] = config.FOOD_FRESH_TICKS + config.FOOD_ROT_TICKS
        canvas = FakeCanvas()
        draw_foods(canvas, world, 0, 0, 3, 1, config.CELL_SIZE)
        # La case pourrie est dessinée avec 💀, plus aucun carré de nourriture.
        assert any(k.get("text") == "💀" for _, k in canvas.texts)
        assert canvas.rects == []

    def test_food_rot_disabled_shows_no_skull(self):
        config.ENABLE_DAY_NIGHT = False
        config.ENABLE_FOOD_ROT = False
        world = make_world(width=3, height=1, food_amounts={(1, 0): 1})
        world.food.food_age[(1, 0)] = 10 ** 6
        canvas = FakeCanvas()
        draw_foods(canvas, world, 0, 0, 3, 1, config.CELL_SIZE)
        assert canvas.texts == []
        assert len(canvas.rects) == 1

    def test_food_outside_view_not_drawn(self):
        world = make_world(width=5, height=1, food_amounts={(4, 0): 1})
        canvas = FakeCanvas()
        draw_foods(canvas, world, 0, 0, 2, 1, config.CELL_SIZE)
        assert canvas.rects == []


class TestDrawAgents:
    def test_agent_outside_view_not_drawn(self):
        world = make_world(width=5, height=5)
        world.agents = [make_agent(x=4, y=4)]
        canvas = FakeCanvas()
        draw_agents(canvas, world, None, 0, 0, 2, 2, config.CELL_SIZE)
        assert canvas.rects == []

    def test_selected_agent_gets_vision_oval(self):
        world = make_world(width=5, height=5)
        agent = make_agent(x=2, y=2)
        world.agents = [agent]
        canvas = FakeCanvas()
        draw_agents(canvas, world, agent, 0, 0, 5, 5, config.CELL_SIZE)
        assert len(canvas.ovals) == 1

    def test_sleeping_agent_shows_zzz_marker(self):
        world = make_world(width=5, height=5)
        agent = make_agent(x=2, y=2)
        agent.pending_action = ACTION_SLEEP
        world.agents = [agent]
        canvas = FakeCanvas()
        draw_agents(canvas, world, None, 0, 0, 5, 5, config.CELL_SIZE)
        assert any(k.get("text") == "💤" for _, k in canvas.texts)

    def test_sick_agent_shows_nausea_marker(self):
        world = make_world(width=5, height=5)
        agent = make_agent(x=2, y=2)
        agent.sick_ticks = 10
        world.agents = [agent]
        canvas = FakeCanvas()
        draw_agents(canvas, world, None, 0, 0, 5, 5, config.CELL_SIZE)
        assert any(k.get("text") == "🤢" for _, k in canvas.texts)


class TestAgentPanelText:
    def test_panel_contains_fatigue_and_freshness(self):
        world = make_world(width=5, height=5)
        agent = make_agent(x=2, y=2, fatigue=12.5)
        agent.inventory = [{"type": config.OBJECT_TYPE_FOOD, "value": 10, "freshness": 0.75}]
        text = agent_panel_text(agent, world)
        assert "Fatigue: 12.5" in text
        assert "0.75" in text

    def test_panel_contains_sickness(self):
        world = make_world(width=5, height=5)
        agent = make_agent(x=2, y=2)
        agent.sick_ticks = 33
        assert "Malade: 33 ticks" in agent_panel_text(agent, world)
        agent.sick_ticks = 0
        assert "Malade: non" in agent_panel_text(agent, world)

    def test_no_selection_returns_empty(self):
        world = make_world(width=5, height=5)
        assert agent_panel_text(None, world) == ""


class TestBlendHex:
    def test_endpoints(self):
        assert _blend_hex("#000000", "#ffffff", 0.0) == "#000000"
        assert _blend_hex("#000000", "#ffffff", 1.0) == "#ffffff"

    def test_midpoint(self):
        assert _blend_hex("#000000", "#ffffff", 0.5) in ("#7f7f7f", "#808080")
