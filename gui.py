
import tkinter as tk
import os
from tkinter import messagebox
from tkinter import filedialog
from save import save_world, load_world
from config import SAVE_CRITICAL_AGENTS, SAVE_CRITICAL_RECOVERY
from tkinter import filedialog
from recorder import Recorder
from config import VIDEO_FPS_SCREEN, VIDEO_FPS_TICK
from config import (
    OUTPUT_DIR,
    CELL_SIZE,
    MARGIN,
    SIMULATION_DELAY_MS,
    BACKGROUND_COLOR,
    GRID_COLOR,
    WORLD_WIDTH,
    WORLD_HEIGHT,
    BIOME_COLORS,
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


# =========================================================
# UTILS
# =========================================================

def blend_color(hex_color, night_alpha, weather_alpha=0.0, weather_color=(0, 0, 0)):
    night_r, night_g, night_b = 0, 0, 40

    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)

    # Overlay nuit
    r = int(r * (1 - night_alpha) + night_r * night_alpha)
    g = int(g * (1 - night_alpha) + night_g * night_alpha)
    b = int(b * (1 - night_alpha) + night_b * night_alpha)

    # Overlay météo
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
        return 0.30, (180, 210, 240)

    return 0.0, (0, 0, 0)


# =========================================================
# GUI
# =========================================================

class SimulationGUI:
    def __init__(self, world, policy):
        self.world  = world
        self.policy = policy

        self.paused = False
        self.time_scale = 1.0
        self.base_delay = SIMULATION_DELAY_MS

        self.fast_mode = False
        self.target_tick = None
        self.running = True
        self.selected_agent = None
        self.critical_saved = False
        self.recorder       = Recorder()

        # -------------------------------------------------
        # Fenêtre
        # -------------------------------------------------
        self.root = tk.Tk()
        self.root.title("Simulation Vie Artificielle")

        self.record_mode    = tk.StringVar(value="screen")

        # Raccourcis clavier
        self.root.bind("<space>", self.toggle_pause)
        self.root.bind("+", self.speed_up)
        self.root.bind("-", self.slow_down)
        self.root.bind("f", self.fast_forward)

        # -------------------------------------------------
        # Canvas
        # -------------------------------------------------
        canvas_width = WORLD_WIDTH * CELL_SIZE + MARGIN
        canvas_height = WORLD_HEIGHT * CELL_SIZE + MARGIN

        self.canvas_sim = tk.Canvas(
            self.root,
            width=canvas_width,
            height=canvas_height,
            bg=BACKGROUND_COLOR,
        )
        self.canvas_sim.pack()
        self.canvas_sim.bind("<Button-1>", self.on_canvas_click)

        # -------------------------------------------------
        # Panneau agent sélectionné
        # -------------------------------------------------
        self.agent_label = tk.Label(self.root, text="", font=("Courier", 10), justify=tk.LEFT, anchor="w")
        self.agent_label.pack(fill=tk.X, padx=10)

        # -------------------------------------------------
        # Boutons (fix 1)
        # -------------------------------------------------
        controls = tk.Frame(self.root)
        controls.pack(pady=5)

        tk.Button(
            controls,
            text="⏸ Pause",
            command=self.toggle_pause
        ).pack(side=tk.LEFT, padx=5)

        tk.Button(
            controls,
            text="➕ Speed",
            command=self.speed_up
        ).pack(side=tk.LEFT, padx=5)

        tk.Button(
            controls,
            text="➖ Slow",
            command=self.slow_down
        ).pack(side=tk.LEFT, padx=5)

        tk.Button(
            controls,
            text="⏩ Fast Forward",
            command=self.fast_forward
        ).pack(side=tk.LEFT, padx=5)

        tk.Button(
            controls,
            text="💾 Sauvegarder",
            command=self.on_save
        ).pack(side=tk.LEFT, padx=5)

        tk.Button(
            controls,
            text="📂 Charger",
            command=self.on_load
        ).pack(side=tk.LEFT, padx=5)

        self.record_btn = tk.Button(
            controls,
            text="⏺ Enregistrer",
            command=self.on_record_toggle,
            bg="#550000", fg="white",
        )
        self.record_btn.pack(side=tk.LEFT, padx=5)

        tk.Radiobutton(
            controls, text="Écran (vitesse réelle)",
            variable=self.record_mode, value="screen",
        ).pack(side=tk.LEFT)

        tk.Radiobutton(
            controls, text="Tick par tick",
            variable=self.record_mode, value="tick",
        ).pack(side=tk.LEFT)

        # -------------------------------------------------
        # Infos
        # -------------------------------------------------
        self.info_label = tk.Label(self.root, text="", font=("Arial", 12))
        self.info_label.pack()

        # -------------------------------------------------
        # Graphe population (fenêtre séparée)
        # -------------------------------------------------
        self.graph = PopulationGraph(self.root)

        # -------------------------------------------------
        # Démarrage
        # -------------------------------------------------
        self.update_loop()
        self.root.mainloop()

    # =====================================================
    # SIMULATION
    # =====================================================

    def run_until_tick(self, target_tick):
        self.fast_mode = True
        self.target_tick = target_tick


    def toggle_pause(self, event=None):
        self.paused = not self.paused

    # =====================================================
    # SÉLECTION D'AGENT
    # =====================================================

    def on_canvas_click(self, event):
        cx = event.x // CELL_SIZE
        cy = event.y // CELL_SIZE
        # Trouver l'agent vivant le plus proche du clic
        best = None
        best_dist = float("inf")
        for agent in self.world.agents:
            if not agent.alive:
                continue
            d = abs(agent.x - cx) + abs(agent.y - cy)
            if d < best_dist:
                best_dist = d
                best = agent
        # Désélectionner si clic loin de tout agent (> 3 cases)
        self.selected_agent = best if best_dist <= 3 else None

    def on_save(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
            initialfile=f"{OUTPUT_DIR}/save_tick{self.world.tick}.json",
        )
        if path:
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            save_world(self.world, path)

    def on_load(self):
        path = filedialog.askopenfilename(
            filetypes=[("JSON", "*.json")]
        )
        if path:
            self.world          = load_world(path)
            self.selected_agent = None
            self.critical_saved = False
            self.graph.history  = []
    
    def on_record_toggle(self):
        if not self.recorder.recording:
            self.recorder.start(self.record_mode.get())
            self.record_btn.config(text="⏹ Stop", bg="#990000")
        else:
            path = filedialog.asksaveasfilename(
                defaultextension=".mp4",
                filetypes=[("MP4", "*.mp4")],
                initialfile=f"{OUTPUT_DIR}/simulation_tick{self.world.tick}.mp4",
            )
            if path:
                ok = self.recorder.stop(path, time_scale=self.time_scale)
                if ok:
                    tk.messagebox.showinfo("Enregistrement", f"Vidéo sauvegardée :\n{path}")
            else:
                # annulé — on arrête quand même l'enregistrement
                self.recorder.stop("/dev/null", time_scale=self.time_scale)
            self.record_btn.config(text="⏺ Enregistrer", bg="#550000")

    def draw_agent_panel(self):
        a = self.selected_agent
        # Vérifier que l'agent est encore vivant
        if a is None or not a.alive:
            self.selected_agent = None
            self.agent_label.config(text="")
            return

        from agent import ACTION_UP, ACTION_DOWN, ACTION_LEFT, ACTION_RIGHT, ACTION_IDLE, ACTION_DRINK, ACTION_VOTE_MIGRATE
        action_names = {
            ACTION_UP: "↑ Haut", ACTION_DOWN: "↓ Bas",
            ACTION_LEFT: "← Gauche", ACTION_RIGHT: "→ Droite",
            ACTION_IDLE: "· Idle", ACTION_DRINK: "💧 Boire",
            ACTION_VOTE_MIGRATE: "🚶 Vote migration",
        }
        action_str = action_names.get(a.pending_action, "?")
        free_str   = ", ".join(action_names.get(fa, "?") for fa in a.free_actions) or "—"
        vote_str   = "Oui" if a.vote_migrate else "Non"

        self.agent_label.config(text=(
            f"[ Agent #{a.id} ]  "
            f"Pos: ({a.x},{a.y})  "
            f"Énergie: {a.energy:.1f}  "
            f"Soif: {a.thirst:.1f}  "
            f"Âge: {a.age}  "
            f"Gén: {a.generation}  "
            f"Action: {action_str}  "
            f"Libres: {free_str}  "
            f"Vote migr.: {vote_str}  "
            f"Reward: {a.last_reward:+.2f}"
        ))


    def speed_up(self, event=None):
        self.time_scale *= 1.25

        if self.time_scale > 10:
            self.time_scale = 10


    def slow_down(self, event=None):
        self.time_scale /= 1.25

        if self.time_scale < 0.1:
            self.time_scale = 0.1


    # =====================================================
    # FAST FORWARD
    # =====================================================

    def fast_forward(self, event=None):
        popup = tk.Toplevel(self.root)
        popup.title("Fast Forward")
        popup.transient(self.root)
        popup.grab_set()

        tk.Label(
            popup,
            text="Aller jusqu'à quel tick ?"
        ).pack(padx=10, pady=10)

        entry = tk.Entry(popup)
        entry.pack(padx=10, pady=5)

        entry.insert(0, str(self.world.tick + 10000))
        entry.focus()

        def start():
            try:
                target = int(entry.get())
            except ValueError:
                popup.destroy()
                return

            self.run_until_tick(target)
            popup.destroy()

        tk.Button(
            popup,
            text="Go",
            command=start
        ).pack(pady=10)

        popup.bind("<Return>", lambda event: start())


    def fast_step(self):
        """
        Fast simulation.

        Fusion des 2 fixes :
        - Fast-forward massif
        - STOP automatique si trop peu d'agents
        - STOP si tick atteint
        """

        steps_per_frame = 100000

        for _ in range(steps_per_frame):

            # STOP : plus assez d'agents
            if len(self.world.agents) < 5:
                self.fast_mode = False
                self.target_tick = None
                return True

            # STOP : tick atteint
            if (
                self.target_tick is None
                or self.world.tick >= self.target_tick
            ):
                self.fast_mode = False
                self.target_tick = None
                return True

            world_phase(self.world, self.policy)
            if self.recorder.recording and self.recorder.mode == "tick":
                self.recorder.frames.append(self.recorder.capture_world(self.world))

        return False


    # =====================================================
    # BOUCLE PRINCIPALE
    # =====================================================

    def update_loop(self):
        if not self.running:
            return

        if self.fast_mode:
            finished = self.fast_step()

            # redraw uniquement à la fin
            if finished:
                self.draw_world()

        else:
            if not self.paused and len(self.world.agents) > 0:
                world_phase(self.world, self.policy)
            
            n = len(self.world.agents)
            if n <= SAVE_CRITICAL_AGENTS and not self.critical_saved:
                os.makedirs(OUTPUT_DIR, exist_ok=True)
                save_world(self.world, f"{OUTPUT_DIR}/save_critical_tick{self.world.tick}.json")
                self.critical_saved = True
            elif n >= SAVE_CRITICAL_RECOVERY and self.critical_saved:
                self.critical_saved = False

            if self.recorder.recording and self.recorder.mode == "tick":
                frame = self.recorder.capture_world(self.world)
                self.recorder.frames.append(frame)

            self.draw_world()

        delay = int(self.base_delay / self.time_scale)
        delay = max(1, delay)

        self.root.after(delay, self.update_loop)


    # =====================================================
    # BIOMES
    # =====================================================

    def draw_biomes(self):
        if self.world.food is None or not self.world.map.biome_map:
            return

        night_alpha = get_night_alpha(self.world)
        weather_alpha, weather_color = get_weather_overlay(self.world)

        for y in range(WORLD_HEIGHT):
            for x in range(WORLD_WIDTH):

                biome = self.world.map.biome_map.get((x, y))
                base_color = BIOME_COLORS.get(biome, "#000000")

                color = blend_color(
                    base_color,
                    night_alpha,
                    weather_alpha,
                    weather_color,
                )

                x1 = x * CELL_SIZE
                y1 = y * CELL_SIZE
                x2 = x1 + CELL_SIZE
                y2 = y1 + CELL_SIZE

                self.canvas_sim.create_rectangle(
                    x1,
                    y1,
                    x2,
                    y2,
                    fill=color,
                    outline=""
                )


    # =====================================================
    # GRILLE
    # =====================================================

    def draw_grid(self):
        for x in range(WORLD_WIDTH + 1):
            self.canvas_sim.create_line(
                x * CELL_SIZE,
                0,
                x * CELL_SIZE,
                WORLD_HEIGHT * CELL_SIZE,
                fill=GRID_COLOR,
            )

        for y in range(WORLD_HEIGHT + 1):
            self.canvas_sim.create_line(
                0,
                y * CELL_SIZE,
                WORLD_WIDTH * CELL_SIZE,
                y * CELL_SIZE,
                fill=GRID_COLOR,
            )


    # =====================================================
    # MONDE
    # =====================================================

    def draw_world(self):
        self.canvas_sim.delete("all")

        self.draw_biomes()
        self.draw_grid()
        self.draw_foods()
        self.draw_agents()
        self.draw_agent_panel()

        food_count = sum(
            amount
            for _, _, amount in self.world.food.iter_food()
        )

        hour_str = self.get_time_str()
        season_str = SEASON_NAMES[self.world.current_season()]
        weather_str = WEATHER_NAMES[self.world.weather]
        moisture_str = f"{self.world.soil_moisture:.2f}"

        ticks_since_migration = (
            self.world.tick - self.world.last_migration_tick
        )

        if (
            self.world.migration_count > 0
            and ticks_since_migration < 60
        ):
            migration_str = (
                f"  🚶 MIGRATION #{self.world.migration_count} !"
            )
        else:
            migration_str = (
                f"  Migrations: {self.world.migration_count}"
            )

        self.info_label.config(
            text=(
                f"Speed: {self.time_scale:.2f}x | "
                f"Tick: {self.world.tick} | "
                f"{season_str} | "
                f"{weather_str} | "
                f"Sol: {moisture_str} | "
                f"Heure: {hour_str} | "
                f"Agents: {len(self.world.agents)} | "
                f"Food: {food_count} | "
                f"Deaths: {self.world.death_count}"
                f"{migration_str}"
            )
        )

        food_count_val = sum(amount for _, _, amount in self.world.food.iter_food())
        self.graph.update(self.world.tick, len(self.world.agents), food_count_val, self.world.death_count)

        if self.recorder.recording and self.recorder.mode == "screen":
            frame = self.recorder.capture_world(self.world)
            self.recorder.frames.append(frame)

    # =====================================================
    # HEURE
    # =====================================================

    def get_time_str(self):
        t = self.world.time_of_day()

        total_minutes = int(t * 24 * 60)
        hour = (6 + total_minutes // 60) % 24
        minute = total_minutes % 60

        return f"{hour:02d}:{minute:02d}"


    # =====================================================
    # AGENTS
    # =====================================================

    def draw_agents(self):
        from config import VISION_RADIUS, NIGHT_VISION_RATIO, WEATHER_VISION

        for agent in self.world.agents:

            x1 = agent.x * CELL_SIZE + 2
            y1 = agent.y * CELL_SIZE + 2
            x2 = x1 + CELL_SIZE - 4
            y2 = y1 + CELL_SIZE - 4

            age_since_birth = (
                self.world.tick
                - getattr(agent, "born_tick", 0)
            )

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

            is_selected = (self.selected_agent is not None and agent.id == self.selected_agent.id)

            self.canvas_sim.create_rectangle(
                x1, y1, x2, y2,
                fill=color,
                outline="white" if is_selected else "",
                width=2 if is_selected else 0,
            )

            self.canvas_sim.create_text(
                agent.x * CELL_SIZE + 7,
                agent.y * CELL_SIZE + 7,
                text=str(agent.generation),
                fill="white",
                font=("Arial", 6)
            )

            # Rayon de vision pour l'agent sélectionné
            if is_selected:
                night_ratio   = NIGHT_VISION_RATIO if self.world.is_night() else 1.0
                weather_ratio = WEATHER_VISION.get(self.world.weather, 1.0)
                radius_cells  = VISION_RADIUS * night_ratio * weather_ratio
                radius_px     = radius_cells * CELL_SIZE
                cx = agent.x * CELL_SIZE + CELL_SIZE / 2
                cy = agent.y * CELL_SIZE + CELL_SIZE / 2
                self.canvas_sim.create_oval(
                    cx - radius_px, cy - radius_px,
                    cx + radius_px, cy + radius_px,
                    outline="white", dash=(4, 4), width=1,
                )


    # =====================================================
    # FOOD
    # =====================================================

    def draw_foods(self):
        for x, y, amount in self.world.food.iter_food():

            if amount <= 0:
                continue

            biome = self.world.map.biome_map.get((x, y))
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


# =========================================================
# GRAPHE DE POPULATION
# =========================================================

class PopulationGraph:
    HISTORY   = 500   # nombre de ticks conservés
    W, H      = 500, 220
    PAD_L     = 45
    PAD_R     = 10
    PAD_T     = 10
    PAD_B     = 30

    COLORS = {
        "agents": "#00cfff",
        "food":   "#90ee90",
        "deaths": "#ff6666",
    }

    def __init__(self, master):
        self.win = tk.Toplevel(master)
        self.win.title("Population")
        self.win.resizable(False, False)
        # Empêche la fermeture — la fenêtre vit tant que la simu tourne
        self.win.protocol("WM_DELETE_WINDOW", lambda: None)

        self.canvas = tk.Canvas(self.win, width=self.W, height=self.H, bg="#1a1a2e")
        self.canvas.pack()

        # légende
        legend = tk.Frame(self.win, bg="#1a1a2e")
        legend.pack(fill=tk.X, padx=5, pady=2)
        for label, color in [("Agents", "#00cfff"), ("Nourriture /10", "#90ee90"), ("Morts /10", "#ff6666")]:
            tk.Label(legend, text=f"— {label}", fg=color, bg="#1a1a2e", font=("Arial", 9)).pack(side=tk.LEFT, padx=8)

        self.history = []   # list de (tick, agents, food, deaths)

    def update(self, tick, agents, food, deaths):
        self.history.append((tick, agents, food // 10, deaths // 10))
        if len(self.history) > self.HISTORY:
            self.history.pop(0)
        self._draw()

    def _draw(self):
        c = self.canvas
        c.delete("all")

        if len(self.history) < 2:
            return

        pl = self.PAD_L
        pr = self.PAD_R
        pt = self.PAD_T
        pb = self.PAD_B
        w  = self.W - pl - pr
        h  = self.H - pt - pb

        # Fond grille
        c.create_rectangle(pl, pt, pl + w, pt + h, fill="#11112a", outline="#333355")
        for i in range(5):
            y = pt + i * h // 4
            c.create_line(pl, y, pl + w, y, fill="#333355", dash=(2, 4))

        # Valeurs max pour normaliser
        max_val = max(
            max((v for _, v, _, _ in self.history), default=1),
            max((v for _, _, v, _ in self.history), default=1),
            max((v for _, _, _, v in self.history), default=1),
            1
        )

        n = len(self.history)

        def to_xy(i, val):
            x = pl + int(i / (n - 1) * w)
            y = pt + h - int(val / max_val * h)
            return x, y

        for key, idx in [("agents", 1), ("food", 2), ("deaths", 3)]:
            color  = self.COLORS[key]
            points = [to_xy(i, row[idx]) for i, row in enumerate(self.history)]
            for j in range(len(points) - 1):
                c.create_line(points[j], points[j + 1], fill=color, width=1)

        # Axe Y — valeurs
        for i in range(5):
            val = int(max_val * (4 - i) / 4)
            y   = pt + i * h // 4
            c.create_text(pl - 4, y, text=str(val), fill="#aaaacc", font=("Arial", 7), anchor="e")

        # Tick courant
        if self.history:
            last_tick = self.history[-1][0]
            first_tick = self.history[0][0]
            c.create_text(pl + w, pt + h + 15, text=f"tick {last_tick}", fill="#aaaacc", font=("Arial", 8), anchor="e")
            c.create_text(pl,     pt + h + 15, text=f"tick {first_tick}", fill="#aaaacc", font=("Arial", 8), anchor="w")
