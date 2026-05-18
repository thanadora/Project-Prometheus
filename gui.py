import tkinter as tk

from config import (
    CELL_SIZE,
    MARGIN,
    SIMULATION_DELAY_MS,
    BACKGROUND_COLOR,
    GRID_COLOR,
    WORLD_WIDTH,
    WORLD_HEIGHT,
    BIOME_COLORS,
    BIOME_WATER,
    BIOME_DESERT,
    BIOME_PRAIRIE,
    BIOME_FOREST,
    FOOD_TYPES,
    NIGHT_RATIO,
    SEASON_NAMES,
    WEATHER_NAMES,
    WEATHER_RAIN,
    WEATHER_STORM,
    WEATHER_DROUGHT,
    WEATHER_FROST,
)
from world import world_phase


def blend_color(hex_color, night_alpha, weather_alpha=0.0, weather_color=(0, 0, 0)):
    night_r, night_g, night_b = 0, 0, 40
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)

    r = int(r * (1 - night_alpha) + night_r * night_alpha)
    g = int(g * (1 - night_alpha) + night_g * night_alpha)
    b = int(b * (1 - night_alpha) + night_b * night_alpha)

    wr, wg, wb = weather_color
    r = int(r * (1 - weather_alpha) + wr * weather_alpha)
    g = int(g * (1 - weather_alpha) + wg * weather_alpha)
    b = int(b * (1 - weather_alpha) + wb * weather_alpha)

    return f"#{r:02x}{g:02x}{b:02x}"


def get_night_alpha(world):
    t = world.time_of_day()
    night_start = 1 - NIGHT_RATIO
    if t < 0.1:
        return 1.0 - (t / 0.1)
    elif t < night_start:
        return 0.0
    elif t < night_start + 0.1:
        return (t - night_start) / 0.1
    else:
        return 1.0


def get_weather_overlay(world):
    if world.weather == WEATHER_RAIN:
        return 0.25, (30, 50, 120)
    elif world.weather == WEATHER_STORM:
        return 0.45, (20, 20, 60)
    elif world.weather == WEATHER_DROUGHT:
        return 0.20, (120, 80, 20)
    elif world.weather == WEATHER_FROST:
        return 0.30, (180, 210, 240)   # teinte blanche glacée
    return 0.0, (0, 0, 0)




class SimulationGUI:
    def __init__(self, world):
        self.world = world

        self.root = tk.Tk()
        self.root.title("Simulation Vie Artificielle")

        canvas_width = WORLD_WIDTH * CELL_SIZE + MARGIN
        canvas_height = WORLD_HEIGHT * CELL_SIZE + MARGIN

        self.canvas_sim = tk.Canvas(
            self.root,
            width=canvas_width,
            height=canvas_height,
            bg=BACKGROUND_COLOR,
        )
        self.canvas_sim.pack()

        self.info_label = tk.Label(self.root, text="", font=("Arial", 12))
        self.info_label.pack()

        self.running = True
        self.update_loop()
        self.root.mainloop()

    # -----------------------------
    # BIOMES
    # -----------------------------
    def draw_biomes(self):
        if self.world.food is None or not self.world.food.biome_map:
            return

        night_alpha = get_night_alpha(self.world)
        weather_alpha, weather_color = get_weather_overlay(self.world)

        for y in range(WORLD_HEIGHT):
            for x in range(WORLD_WIDTH):
                biome = self.world.food.biome_map.get((x, y))
                base_color = BIOME_COLORS.get(biome, "#000000")
                color = blend_color(base_color, night_alpha, weather_alpha, weather_color)

                x1 = x * CELL_SIZE
                y1 = y * CELL_SIZE
                x2 = x1 + CELL_SIZE
                y2 = y1 + CELL_SIZE

                self.canvas_sim.create_rectangle(
                    x1, y1, x2, y2,
                    fill=color,
                    outline=""
                )

    # -----------------------------
    # GRILLE
    # -----------------------------
    def draw_grid(self):
        for x in range(WORLD_WIDTH + 1):
            self.canvas_sim.create_line(
                x * CELL_SIZE, 0,
                x * CELL_SIZE, WORLD_HEIGHT * CELL_SIZE,
                fill=GRID_COLOR
            )
        for y in range(WORLD_HEIGHT + 1):
            self.canvas_sim.create_line(
                0, y * CELL_SIZE,
                WORLD_WIDTH * CELL_SIZE, y * CELL_SIZE,
                fill=GRID_COLOR
            )

    # -----------------------------
    # MONDE
    # -----------------------------
    def draw_world(self):
        self.canvas_sim.delete("all")
        self.draw_biomes()
        self.draw_grid()
        self.draw_foods()
        self.draw_agents()

        food_count = sum(amount for _, _, amount in self.world.food.iter_food())
        hour_str = self.get_time_str()
        season_str = SEASON_NAMES[self.world.current_season()]
        weather_str = WEATHER_NAMES[self.world.weather]
        moisture_str = f"{self.world.soil_moisture:.2f}"

        self.info_label.config(
            text=(
                f"Tick: {self.world.tick} | "
                f"{season_str} | "
                f"{weather_str} | "
                f"Sol: {moisture_str} | "
                f"Heure: {hour_str} | "
                f"Agents: {len(self.world.agents)} | "
                f"Food: {food_count} | "
                f"Deaths: {self.world.death_count}"
            )
        )

    # -----------------------------
    # HEURE ESTIMÉE
    # -----------------------------
    def get_time_str(self):
        t = self.world.time_of_day()
        total_minutes = int(t * 24 * 60)
        hour = (6 + total_minutes // 60) % 24
        minute = total_minutes % 60
        return f"{hour:02d}:{minute:02d}"

    # -----------------------------
    # AGENTS
    # -----------------------------
    def draw_agents(self):
        for agent in self.world.agents:
            x1 = agent.x * CELL_SIZE + 2
            y1 = agent.y * CELL_SIZE + 2
            x2 = x1 + CELL_SIZE - 4
            y2 = y1 + CELL_SIZE - 4

            age_since_birth = self.world.tick - getattr(agent, "born_tick", 0)

            if age_since_birth < 5:
                color = "green"
            elif agent.thirst < 25:
                color = "yellow"
            elif agent.energy > 60:
                color = "cyan"
            elif agent.energy > 30:
                color = "orange"
            else:
                color = "red"

            self.canvas_sim.create_rectangle(
                x1, y1, x2, y2,
                fill=color,
                outline=""
            )

            self.canvas_sim.create_text(
                agent.x * CELL_SIZE + 7,
                agent.y * CELL_SIZE + 7,
                text=str(agent.generation),
                fill="white",
                font=("Arial", 6)
            )

    # -----------------------------
    # NOURRITURE
    # -----------------------------
    def draw_foods(self):
        for x, y, amount in self.world.food.iter_food():
            if amount <= 0:
                continue

            biome = self.world.food.biome_map.get((x, y))
            food_type = FOOD_TYPES.get(biome)
            if food_type is None:
                continue

            color = food_type["color"]
            capacity = food_type["capacity"]
            t = min(amount / capacity, 1.0)
            size = 2 + t * (CELL_SIZE - 4)

            cx = x * CELL_SIZE + CELL_SIZE / 2
            cy = y * CELL_SIZE + CELL_SIZE / 2

            self.canvas_sim.create_rectangle(
                cx - size / 2,
                cy - size / 2,
                cx + size / 2,
                cy + size / 2,
                fill=color,
                outline=""
            )

    # -----------------------------
    # BOUCLE
    # -----------------------------
    def update_loop(self):
        if not self.running:
            return

        if len(self.world.agents) > 0:
            world_phase(self.world)

        self.draw_world()
        self.root.after(SIMULATION_DELAY_MS, self.update_loop)