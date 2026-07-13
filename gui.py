import tkinter as tk
import os
from collections import deque, Counter
from tkinter import filedialog, messagebox, ttk

import config
from save import save_world, load_world
from recorder import Recorder
from world import world_phase
from renderer import draw_biomes, draw_grid, draw_foods, draw_agents, agent_panel_text, TOP_MARGIN, top_margin
from policy_registry import REGISTRY, policy_name
from logger import get_logger
from config import (
    OUTPUT_DIR,
    CELL_SIZE,
    MARGIN,
    SIMULATION_DELAY_MS,
    BACKGROUND_COLOR,
    WORLD_WIDTH,
    WORLD_HEIGHT,
    INFINITE_VIEW_WIDTH,
    INFINITE_VIEW_HEIGHT,
    SEASON_NAMES,
    WEATHER_NAMES,
    SAVE_CRITICAL_AGENTS,
    SAVE_CRITICAL_RECOVERY,
)


# =========================================================
# GUI PRINCIPALE
# =========================================================

class SimulationGUI:
    def __init__(self, world, policy):
        self.world  = world
        self.policy = policy

        self.paused       = False
        self.time_scale   = 1.0
        self.base_delay   = SIMULATION_DELAY_MS
        self.fast_mode    = False
        self.target_tick  = None
        self.running      = True
        self.selected_agent  = None
        self.critical_saved  = False
        self.recorder     = Recorder()

        # ── Caméra (utile uniquement en monde infini — en monde classique
        # elle reste figée à (0,0) et couvre tout le monde comme avant) ──
        self.view_w = INFINITE_VIEW_WIDTH  if self.world.infinite else WORLD_WIDTH
        self.view_h = INFINITE_VIEW_HEIGHT if self.world.infinite else WORLD_HEIGHT
        self.camera_x, self.camera_y = 0, 0
        self.zoom = 1.0        # 1.0 = taille normale ; <1 = dézoomé, >1 = zoomé
        self.zoom_min, self.zoom_max = 0.25, 2.5
        if self.world.infinite:
            self._center_camera_on(self._first_alive_agent())
        self._drag_start = None

        self.root = tk.Tk()
        self.root.title("Simulation Vie Artificielle")
        self.root.geometry("1000x750")
        self.record_mode      = tk.StringVar(value="screen")
        self.debug_visible_var = tk.BooleanVar(value=False)
        self.altitude_var       = tk.BooleanVar(value=config.ENABLE_ALTITUDE)
        self.altitude_2_5d_var  = tk.BooleanVar(value=config.ENABLE_ALTITUDE_2_5D)

        # PanedWindow vertical : le panneau du haut (carte + contrôles) est toujours là,
        # le panneau du bas (debug/observation) s'ajoute/s'enlève à la demande, avec une
        # poignée pour le redimensionner — comme le panneau de terminal dans VS Code.
        self.paned = tk.PanedWindow(self.root, orient=tk.VERTICAL,
                                     sashrelief=tk.RAISED, sashwidth=6, bg="#0f0f1e")
        self.paned.pack(fill=tk.BOTH, expand=True)

        self.top_frame = tk.Frame(self.paned)
        self.paned.add(self.top_frame, stretch="always")

        self._bind_keys()
        self._build_menu()
        self._build_canvas()
        self.debug_panel = DebugPanel(self.paned, config.ENABLE_COMMUNICATION)
        self._build_toolbar()
        self._build_info()

        self.update_loop()
        self.root.mainloop()

    # =====================================================
    # CONSTRUCTION DES WIDGETS
    # =====================================================

    def _bind_keys(self):
        kb = config.KEY_BINDINGS
        self.root.bind(kb["pause"],        self.toggle_pause)
        self.root.bind(kb["speed_up"],     self.speed_up)
        self.root.bind(kb["speed_down"],   self.slow_down)
        self.root.bind(kb["fast_forward"], self.fast_forward)
        self.root.bind(kb["toggle_debug"], lambda e: self.toggle_debug_panel())
        self.root.bind(kb["save"],         lambda e: self.on_save())
        self.root.bind(kb["load"],         lambda e: self.on_load())

        # Caméra libre (monde infini uniquement) : flèches pour se déplacer,
        # Tab / Maj+Tab pour sauter d'agent en agent (même isolé, hors écran).
        self.root.bind(kb["pan_left"],   lambda e: self._pan_camera(-1, 0))
        self.root.bind(kb["pan_right"],  lambda e: self._pan_camera(1, 0))
        self.root.bind(kb["pan_up"],     lambda e: self._pan_camera(0, -1))
        self.root.bind(kb["pan_down"],   lambda e: self._pan_camera(0, 1))
        self.root.bind(kb["next_agent"], lambda e: self._cycle_agent(1))
        self.root.bind(kb["prev_agent"], lambda e: self._cycle_agent(-1))

    @staticmethod
    def _pretty_key(binding):
        """Transforme une séquence de bind Tkinter en libellé lisible pour l'UI."""
        if binding in ("+", "-"):
            return binding
        return binding.strip("<>").replace("-", "+")

    def _build_menu(self):
        """Barre de menu pour les actions occasionnelles (fichier, enregistrement...),
        pour ne garder dans la barre d'outils que les actions temps réel fréquentes."""
        kb = config.KEY_BINDINGS
        menubar = tk.Menu(self.root)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="💾 Sauvegarder…", command=self.on_save, accelerator=self._pretty_key(kb["save"]))
        file_menu.add_command(label="📂 Charger…",     command=self.on_load, accelerator=self._pretty_key(kb["load"]))
        menubar.add_cascade(label="Fichier", menu=file_menu)

        sim_menu = tk.Menu(menubar, tearoff=0)
        sim_menu.add_command(label="⏸ Pause / Reprendre", command=self.toggle_pause, accelerator=self._pretty_key(kb["pause"]))
        sim_menu.add_command(label="➕ Accélérer",         command=self.speed_up,    accelerator=self._pretty_key(kb["speed_up"]))
        sim_menu.add_command(label="➖ Ralentir",          command=self.slow_down,   accelerator=self._pretty_key(kb["speed_down"]))
        sim_menu.add_separator()
        sim_menu.add_command(label="⏩ Avance rapide…",    command=self.fast_forward, accelerator=self._pretty_key(kb["fast_forward"]))
        menubar.add_cascade(label="Simulation", menu=sim_menu)

        rec_menu = tk.Menu(menubar, tearoff=0)
        rec_menu.add_command(label="⏺ Démarrer / Arrêter l'enregistrement", command=self.on_record_toggle)
        rec_menu.add_separator()
        rec_menu.add_radiobutton(label="Mode écran (vitesse réelle)", variable=self.record_mode, value="screen")
        rec_menu.add_radiobutton(label="Mode tick par tick",          variable=self.record_mode, value="tick")
        menubar.add_cascade(label="Enregistrement", menu=rec_menu)

        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_checkbutton(label="🐞 Panneau Debug / Graphes", variable=self.debug_visible_var,
                                   command=self.toggle_debug_panel, accelerator=self._pretty_key(kb["toggle_debug"]))
        view_menu.add_separator()
        view_menu.add_checkbutton(label="⛰ Altitude (ombrage)", variable=self.altitude_var,
                                   command=self.toggle_altitude)
        view_menu.add_checkbutton(label="🧊 Relief 2.5D", variable=self.altitude_2_5d_var,
                                   command=self.toggle_altitude_2_5d)
        menubar.add_cascade(label="Affichage", menu=view_menu)

        self.root.config(menu=menubar)

    def _build_canvas(self):
        self.canvas_px_w = self.view_w * CELL_SIZE + MARGIN
        self.canvas_px_h = self.view_h * CELL_SIZE + MARGIN + TOP_MARGIN
        self.canvas_sim = tk.Canvas(self.top_frame, width=self.canvas_px_w, height=self.canvas_px_h, bg=BACKGROUND_COLOR)
        self.canvas_sim.pack()
        self.canvas_sim.bind(f"<Button-{config.MOUSE_SELECT_BUTTON}>", self.on_canvas_click)

        if self.world.infinite:
            # Glisser-déposer pour une caméra vraiment libre, en plus des flèches.
            db = config.MOUSE_DRAG_BUTTON
            self.canvas_sim.bind(f"<ButtonPress-{db}>", self._on_drag_start)
            self.canvas_sim.bind(f"<B{db}-Motion>",     self._on_drag_move)
            # Molette pour zoomer/dézoomer (Windows/Mac : <MouseWheel>, Linux : Button-4/5)
            self.canvas_sim.bind("<MouseWheel>", self._on_mouse_wheel)
            self.canvas_sim.bind("<Button-4>",   lambda e: self._on_mouse_wheel(e, delta=1))
            self.canvas_sim.bind("<Button-5>",   lambda e: self._on_mouse_wheel(e, delta=-1))

        self.agent_label = tk.Label(self.top_frame, text="", font=("Courier", 10), justify=tk.LEFT, anchor="w")
        self.agent_label.pack(fill=tk.X, padx=10)

    def _build_toolbar(self):
        """Barre d'outils fine : uniquement les actions temps réel, tout le reste est
        dans la barre de menu (Fichier / Simulation / Enregistrement / Affichage)."""
        toolbar = tk.Frame(self.top_frame)
        toolbar.pack(fill=tk.X, pady=6, padx=8)

        self.pause_btn = tk.Button(toolbar, text="⏸ Pause", width=10, command=self.toggle_pause)
        self.pause_btn.pack(side=tk.LEFT, padx=(0, 10))

        speed_frame = tk.Frame(toolbar)
        speed_frame.pack(side=tk.LEFT, padx=(0, 10))
        tk.Button(speed_frame, text="➖", width=2, command=self.slow_down).pack(side=tk.LEFT)
        self.speed_label = tk.Label(speed_frame, text="1.00x", width=6, font=("Courier", 10))
        self.speed_label.pack(side=tk.LEFT, padx=4)
        tk.Button(speed_frame, text="➕", width=2, command=self.speed_up).pack(side=tk.LEFT)

        tk.Button(toolbar, text="⏩ Fast Forward", command=self.fast_forward).pack(side=tk.LEFT, padx=(0, 10))

        self.debug_btn = tk.Button(toolbar, text=f"🐞 Debug ({self._pretty_key(config.KEY_BINDINGS['toggle_debug'])})", command=self.toggle_debug_panel)
        self.debug_btn.pack(side=tk.LEFT, padx=(0, 10))

        if self.world.infinite:
            tk.Button(toolbar, text=f"🎯 Agent suivant ({self._pretty_key(config.KEY_BINDINGS['next_agent'])})",
                      command=lambda: self._cycle_agent(1)).pack(side=tk.LEFT, padx=(0, 10))

        self.record_btn = tk.Button(toolbar, text="⏺ Enregistrer",
                                    command=self.on_record_toggle, bg="#550000", fg="white")
        self.record_btn.pack(side=tk.RIGHT)

    def _build_info(self):
        self.info_label = tk.Label(self.top_frame, text="", font=("Arial", 12))
        self.info_label.pack()

    # =====================================================
    # ÉVÉNEMENTS
    # =====================================================

    def toggle_debug_panel(self):
        """Point d'entrée unique pour montrer/cacher le panneau debug — utilisé par le
        bouton, le raccourci 'd' et la case à cocher du menu Affichage, pour qu'ils
        restent toujours synchronisés entre eux."""
        self.debug_panel.toggle()
        self.debug_visible_var.set(self.debug_panel._visible)

    def toggle_pause(self, event=None):
        self.paused = not self.paused

    def speed_up(self, event=None):
        self.time_scale = min(self.time_scale * 1.25, 10)

    def slow_down(self, event=None):
        self.time_scale = max(self.time_scale / 1.25, 0.1)

    def on_canvas_click(self, event):
        cs = self.cell_size
        cx = int(event.x // cs) + self.camera_x
        cy = int(max(0, event.y - top_margin()) // cs) + self.camera_y
        best, best_dist = None, float("inf")
        for agent in self.world.agents:
            if not agent.alive:
                continue
            d = abs(agent.x - cx) + abs(agent.y - cy)
            if d < best_dist:
                best_dist, best = d, agent
        self.selected_agent = best if best_dist <= 3 else None

    def toggle_altitude(self):
        config.ENABLE_ALTITUDE = self.altitude_var.get()
        if not config.ENABLE_ALTITUDE:
            # Le relief 2.5D dépend de l'ombrage : pas de sens de l'un sans l'autre.
            config.ENABLE_ALTITUDE_2_5D = False
            self.altitude_2_5d_var.set(False)
        self._draw_world()

    def toggle_altitude_2_5d(self):
        if self.altitude_2_5d_var.get() and not config.ENABLE_ALTITUDE:
            # Impossible d'activer le 2.5D sans l'altitude : on réactive les deux.
            config.ENABLE_ALTITUDE = True
            self.altitude_var.set(True)
        config.ENABLE_ALTITUDE_2_5D = self.altitude_2_5d_var.get()
        self._draw_world()

    # =====================================================
    # CAMÉRA (monde infini)
    # =====================================================

    @property
    def cell_size(self):
        return CELL_SIZE * self.zoom if self.world.infinite else CELL_SIZE

    def _recompute_view_dims(self):
        if not self.world.infinite:
            return
        cs = self.cell_size
        self.view_w = max(4, int(self.canvas_px_w / cs) + 1)
        self.view_h = max(4, int(self.canvas_px_h / cs) + 1)

    def _on_mouse_wheel(self, event, delta=None):
        if not self.world.infinite:
            return
        d = delta if delta is not None else (1 if event.delta > 0 else -1)

        # Zoome vers le point sous le curseur plutôt que vers le coin de la caméra.
        old_cs  = self.cell_size
        world_x = self.camera_x + event.x / old_cs
        world_y = self.camera_y + (event.y - top_margin()) / old_cs

        factor    = 1.1 if d > 0 else (1 / 1.1)
        self.zoom = max(self.zoom_min, min(self.zoom_max, self.zoom * factor))
        self._recompute_view_dims()

        new_cs = self.cell_size
        self.camera_x = int(round(world_x - event.x / new_cs))
        self.camera_y = int(round(world_y - (event.y - top_margin()) / new_cs))

    def _first_alive_agent(self):
        for agent in self.world.agents:
            if agent.alive:
                return agent
        return None

    def _center_camera_on(self, agent):
        if agent is None:
            return
        self.camera_x = agent.x - self.view_w // 2
        self.camera_y = agent.y - self.view_h // 2

    def _pan_camera(self, dx, dy):
        if not self.world.infinite:
            return  # caméra figée en monde classique, comme avant
        step = max(1, self.view_w // 8)
        self.camera_x += dx * step
        self.camera_y += dy * step

    def _on_drag_start(self, event):
        self._drag_start = (event.x, event.y, self.camera_x, self.camera_y)

    def _on_drag_move(self, event):
        if self._drag_start is None:
            return
        sx, sy, start_cam_x, start_cam_y = self._drag_start
        cs = self.cell_size
        self.camera_x = int(round(start_cam_x - (event.x - sx) / cs))
        self.camera_y = int(round(start_cam_y - (event.y - sy) / cs))

    def _cycle_agent(self, direction):
        """Passe à l'agent vivant suivant/précédent (par id) et centre la caméra
        dessus — permet de retrouver un agent isolé même hors champ de vision."""
        if not self.world.infinite:
            return
        alive = sorted((a for a in self.world.agents if a.alive), key=lambda a: a.id)
        if not alive:
            return
        if self.selected_agent in alive:
            idx = alive.index(self.selected_agent)
            nxt = alive[(idx + direction) % len(alive)]
        else:
            nxt = alive[0]
        self.selected_agent = nxt
        self._center_camera_on(nxt)

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
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if path:
            self.world          = load_world(path)
            self.selected_agent = None
            self.critical_saved = False
            self.debug_panel.graph.history = []

            self.view_w = INFINITE_VIEW_WIDTH  if self.world.infinite else WORLD_WIDTH
            self.view_h = INFINITE_VIEW_HEIGHT if self.world.infinite else WORLD_HEIGHT
            self.zoom = 1.0
            self.camera_x, self.camera_y = 0, 0
            if self.world.infinite:
                self._center_camera_on(self._first_alive_agent())

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
                    messagebox.showinfo("Enregistrement", f"Vidéo sauvegardée :\n{path}")
            else:
                self.recorder.stop("/dev/null", time_scale=self.time_scale)
            self.record_btn.config(text="⏺ Enregistrer", bg="#550000")

    # =====================================================
    # FAST FORWARD
    # =====================================================

    def fast_forward(self, event=None):
        popup = tk.Toplevel(self.root)
        popup.title("Fast Forward")
        popup.transient(self.root)
        popup.grab_set()

        tk.Label(popup, text="Aller jusqu'à quel tick ?").pack(padx=10, pady=10)
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
            self.fast_mode   = True
            self.target_tick = target
            popup.destroy()

        tk.Button(popup, text="Go", command=start).pack(pady=10)
        popup.bind("<Return>", lambda e: start())

    def fast_step(self):
        for _ in range(100_000):
            if len(self.world.agents) < 5 or self.target_tick is None or self.world.tick >= self.target_tick:
                self.fast_mode   = False
                self.target_tick = None
                return True
            world_phase(self.world, self.policy)
            if self.recorder.recording and self.recorder.mode == "tick":
                self.recorder.frames.append(self.recorder.capture_world(self.world, view=(self.camera_x, self.camera_y, self.view_w, self.view_h)))
        return False

    # =====================================================
    # BOUCLE PRINCIPALE
    # =====================================================

    def update_loop(self):
        if not self.running:
            return

        if self.fast_mode:
            if self.fast_step():
                self._draw_world()
        else:
            if not self.paused and self.world.agents:
                world_phase(self.world, self.policy)

            n = len(self.world.agents)
            if n <= SAVE_CRITICAL_AGENTS and not self.critical_saved:
                os.makedirs(OUTPUT_DIR, exist_ok=True)
                save_world(self.world, f"{OUTPUT_DIR}/save_critical_tick{self.world.tick}.json")
                self.critical_saved = True
            elif n >= SAVE_CRITICAL_RECOVERY and self.critical_saved:
                self.critical_saved = False

            if self.recorder.recording and self.recorder.mode == "tick":
                self.recorder.frames.append(self.recorder.capture_world(self.world, view=(self.camera_x, self.camera_y, self.view_w, self.view_h)))

            self._draw_world()

        delay = max(1, int(self.base_delay / self.time_scale))
        self.root.after(delay, self.update_loop)

    # =====================================================
    # RENDU
    # =====================================================

    def _draw_world(self):
        self.pause_btn.config(text="▶ Reprendre" if self.paused else "⏸ Pause")
        self.speed_label.config(text=f"{self.time_scale:.2f}x")

        self.canvas_sim.delete("all")
        cs = self.cell_size
        draw_biomes(self.canvas_sim, self.world, self.camera_x, self.camera_y, self.view_w, self.view_h, cs)
        draw_grid(self.canvas_sim, self.view_w, self.view_h, cs)
        draw_foods(self.canvas_sim, self.world, self.camera_x, self.camera_y, self.view_w, self.view_h, cs)
        draw_agents(self.canvas_sim, self.world, self.selected_agent, self.camera_x, self.camera_y, self.view_w, self.view_h, cs)

        # Panel agent sélectionné
        if self.selected_agent and not self.selected_agent.alive:
            self.selected_agent = None
        self.agent_label.config(text=agent_panel_text(self.selected_agent, self.world))

        # Barre d'info
        food_count  = sum(amount for _, _, amount in self.world.food.iter_food())
        ticks_since = self.world.tick - self.world.last_migration_tick
        if self.world.migration_count > 0 and ticks_since < 60:
            migration_str = f"  🚶 MIGRATION #{self.world.migration_count} !"
        else:
            migration_str = f"  Migrations: {self.world.migration_count}"

        camera_str = f"  🌐 Cam: ({self.camera_x},{self.camera_y}) x{self.zoom:.2f}" if self.world.infinite else ""
        self.info_label.config(text=(
            f"Speed: {self.time_scale:.2f}x | "
            f"Tick: {self.world.tick} | "
            f"{SEASON_NAMES[self.world.current_season()]} | "
            f"{WEATHER_NAMES[self.world.weather]} | "
            f"Sol: {self.world.soil_moisture:.2f} | "
            f"Heure: {self._time_str()} | "
            f"Agents: {len(self.world.agents)} | "
            f"Food: {food_count} | "
            f"Deaths: {self.world.death_count}"
            f"{migration_str}"
            f"{camera_str}"
        ))

        # Graphe population + logs + lettres (fenêtre unique, mise à jour même si cachée)
        policy_counts = {name: 0 for name in REGISTRY}
        for agent in self.world.agents:
            name = policy_name(agent.policy)
            if name in policy_counts:
                policy_counts[name] += 1
        self.debug_panel.update_all(self.world, self.world.tick, policy_counts, food_count, self.world.death_count)


        if self.recorder.recording and self.recorder.mode == "screen":
            self.recorder.frames.append(self.recorder.capture_world(self.world, view=(self.camera_x, self.camera_y, self.view_w, self.view_h)))

    def _time_str(self):
        t             = self.world.time_of_day()
        total_minutes = int(t * 24 * 60)
        hour          = (6 + total_minutes // 60) % 24
        minute        = total_minutes % 60
        return f"{hour:02d}:{minute:02d}"


# =========================================================
# GRAPHE DE POPULATION
# =========================================================

class PopulationGraph:
    HISTORY = 500
    W, H    = 560, 250
    PAD_L   = 45
    PAD_R   = 10
    PAD_T   = 10
    PAD_B   = 30

    def __init__(self, master):
        self.canvas = tk.Canvas(master, width=self.W, height=self.H, bg="#1a1a2e")
        self.canvas.pack()

        legend = tk.Frame(master, bg="#1a1a2e")
        legend.pack(fill=tk.X, padx=5, pady=2)
        for name, info in REGISTRY.items():
            tk.Label(legend, text=f"— {name}", fg=info["color"],
                     bg="#1a1a2e", font=("Arial", 9)).pack(side=tk.LEFT, padx=8)
        tk.Label(legend, text="— Nourriture /10", fg="#90ee90",
                 bg="#1a1a2e", font=("Arial", 9)).pack(side=tk.LEFT, padx=8)
        tk.Label(legend, text="— Morts /10", fg="#ff6666",
                 bg="#1a1a2e", font=("Arial", 9)).pack(side=tk.LEFT, padx=8)

        self.history = []  # (tick, {policy_name: count}, food//10, deaths//10)

    def update(self, tick, policy_counts, food, deaths):
        self.history.append((tick, dict(policy_counts), food // 10, deaths // 10))
        if len(self.history) > self.HISTORY:
            self.history.pop(0)
        self._draw()

    def _draw(self):
        c = self.canvas
        c.delete("all")
        if len(self.history) < 2:
            return

        pl, pr, pt, pb = self.PAD_L, self.PAD_R, self.PAD_T, self.PAD_B
        w = self.W - pl - pr
        h = self.H - pt - pb

        c.create_rectangle(pl, pt, pl + w, pt + h, fill="#11112a", outline="#333355")
        for i in range(5):
            y = pt + i * h // 4
            c.create_line(pl, y, pl + w, y, fill="#333355", dash=(2, 4))

        all_vals = [
            val
            for _, counts, food, deaths in self.history
            for val in [sum(counts.values()), food, deaths]
        ]
        max_val = max(max(all_vals, default=1), 1)
        n       = len(self.history)

        def to_xy(i, val):
            x = pl + int(i / (n - 1) * w)
            y = pt + h - int(val / max_val * h)
            return x, y

        for name, info in REGISTRY.items():
            pts = [to_xy(i, row[1].get(name, 0)) for i, row in enumerate(self.history)]
            for j in range(len(pts) - 1):
                c.create_line(pts[j], pts[j + 1], fill=info["color"], width=2)

        for color, idx in [("#90ee90", 2), ("#ff6666", 3)]:
            pts = [to_xy(i, row[idx]) for i, row in enumerate(self.history)]
            for j in range(len(pts) - 1):
                c.create_line(pts[j], pts[j + 1], fill=color, width=1)

        for i in range(5):
            val = int(max_val * (4 - i) / 4)
            c.create_text(pl - 4, pt + i * h // 4, text=str(val),
                          fill="#aaaacc", font=("Arial", 7), anchor="e")

        if self.history:
            c.create_text(pl + w, pt + h + 15, text=f"tick {self.history[-1][0]}",
                          fill="#aaaacc", font=("Arial", 8), anchor="e")
            c.create_text(pl,     pt + h + 15, text=f"tick {self.history[0][0]}",
                          fill="#aaaacc", font=("Arial", 8), anchor="w")


# =========================================================
# PANNEAU DE LOGS
# =========================================================

class LogPanel:
    """Fenêtre affichant en direct les messages du logger, filtrables par niveau."""

    LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR"]
    COLORS = {
        "DEBUG":   "#888899",
        "INFO":    "#e0e0e0",
        "WARNING": "#ffcc66",
        "ERROR":   "#ff6666",
    }

    def __init__(self, master):
        top = tk.Frame(master, bg="#1a1a2e")
        top.pack(fill=tk.X, padx=5, pady=5)

        tk.Label(top, text="Niveau min :", bg="#1a1a2e", fg="#ccccdd",
                 font=("Arial", 9)).pack(side=tk.LEFT)
        self.level_var = tk.StringVar(value=config.LOG_LEVEL if config.LOG_LEVEL in self.LEVELS else "INFO")
        # Rebuild complet à chaque changement de filtre : sinon les messages en dessous
        # du seuil restent marqués "déjà vus" et ne réapparaissent jamais si on rebaisse le filtre.
        self.level_var.trace_add("write", lambda *_: self._full_rebuild())
        tk.OptionMenu(top, self.level_var, *self.LEVELS).pack(side=tk.LEFT, padx=5)

        self.autoscroll_var = tk.BooleanVar(value=True)
        tk.Checkbutton(top, text="Auto-scroll", variable=self.autoscroll_var,
                       bg="#1a1a2e", fg="#ccccdd", activebackground="#1a1a2e",
                       selectcolor="#333355", font=("Arial", 9)).pack(side=tk.LEFT, padx=10)

        tk.Button(top, text="Effacer", command=self.clear).pack(side=tk.LEFT, padx=5)

        self.text = tk.Text(master, width=100, height=18, bg="#11112a", fg="#e0e0e0",
                             font=("Courier", 9), state="disabled", wrap="none")
        self.text.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))
        for level, color in self.COLORS.items():
            self.text.tag_configure(level, foreground=color)

        self._seen_seq    = -1   # dernier seq déjà inséré dans le widget Text
        self._cleared_seq = -1   # seq à partir duquel on réaffiche (après un "Effacer")

    def _insert(self, records):
        min_idx = self.LEVELS.index(self.level_var.get())
        self.text.config(state="normal")
        for level, msg in records:
            if level in self.LEVELS and self.LEVELS.index(level) < min_idx:
                continue
            self.text.insert(tk.END, msg + "\n", level if level in self.COLORS else "INFO")
        self.text.config(state="disabled")
        if self.autoscroll_var.get():
            self.text.see(tk.END)

    def clear(self):
        self.text.config(state="normal")
        self.text.delete("1.0", tk.END)
        self.text.config(state="disabled")
        self._cleared_seq = get_logger().get_last_seq()
        self._seen_seq    = self._cleared_seq

    def _full_rebuild(self):
        """Réaffiche tout ce qui est encore en mémoire depuis le dernier 'Effacer', avec
        le filtre actuel — appelé quand on change le niveau minimum affiché."""
        new, self._seen_seq = get_logger().get_new_records(self._cleared_seq)
        self.text.config(state="normal")
        self.text.delete("1.0", tk.END)
        self.text.config(state="disabled")
        self._insert(new)

    def update(self):
        new, self._seen_seq = get_logger().get_new_records(self._seen_seq)
        if new:
            self._insert(new)


# =========================================================
# PANNEAU DE FRÉQUENCE DES LETTRES
# =========================================================

class LetterPanel:
    """Histogramme des lettres parlées par les agents, sur une fenêtre glissante.

    Pur outil d'observation (aucune IA) : sert à repérer si certaines lettres
    deviennent dominantes une fois qu'une policy apprenante sera branchée.
    """

    WINDOW = 200   # nombre de ticks gardés dans la fenêtre glissante
    W, H   = 420, 230

    def __init__(self, master):
        self.canvas = tk.Canvas(master, width=self.W, height=self.H, bg="#1a1a2e")
        self.canvas.pack()

        self.history = deque(maxlen=self.WINDOW)  # une entrée par tick : liste des lettres dites

    def update(self, world):
        letters = [a.spoken_letter for a in world.agents if a.alive and a.spoken_letter]
        self.history.append(letters)
        self._draw()

    def _draw(self):
        c = self.canvas
        c.delete("all")

        alphabet = config.ALPHABET
        if not alphabet:
            c.create_text(self.W / 2, self.H / 2, text="Alphabet vide",
                          fill="#888899", font=("Arial", 10))
            return

        counts = Counter()
        for letters in self.history:
            counts.update(letters)

        pad_b    = 30
        pad_t    = 24
        max_count = max(counts.values(), default=0) or 1
        bar_w    = (self.W - 20) / len(alphabet)

        for i, letter in enumerate(alphabet):
            count = counts.get(letter, 0)
            bar_h = (count / max_count) * (self.H - pad_t - pad_b)
            x0 = 10 + i * bar_w
            x1 = x0 + bar_w * 0.7
            y1 = self.H - pad_b
            y0 = y1 - bar_h
            c.create_rectangle(x0, y0, x1, y1, fill="#66ccff", outline="")
            c.create_text((x0 + x1) / 2, y1 + 10, text=letter,
                          fill="#e0e0e0", font=("Arial", 10, "bold"))
            if count:
                c.create_text((x0 + x1) / 2, y0 - 8, text=str(count),
                              fill="#aaaacc", font=("Arial", 8))

        c.create_text(self.W / 2, 10,
                      text=f"Occurrences sur les {len(self.history)} derniers ticks",
                      fill="#ccccdd", font=("Arial", 9))


# =========================================================
# FENÊTRE UNIQUE DE DEBUG / OBSERVATION (à onglets)
# =========================================================

class DebugPanel:
    """Regroupe le graphe de population, les logs et l'histogramme de lettres dans
    un panneau à onglets intégré sous la carte (comme le panneau de terminal de
    VS Code) : replié par défaut, dépliable via un bouton ou la touche 'd', et
    redimensionnable en glissant la poignée."""

    def __init__(self, paned, enable_communication):
        self.paned = paned
        self.frame = tk.Frame(paned, bg="#1a1a2e")

        notebook = ttk.Notebook(self.frame)
        notebook.pack(fill=tk.BOTH, expand=True)

        tab_pop = tk.Frame(notebook, bg="#1a1a2e")
        notebook.add(tab_pop, text="📊 Population")
        self.graph = PopulationGraph(tab_pop)

        tab_log = tk.Frame(notebook, bg="#1a1a2e")
        notebook.add(tab_log, text="📜 Logs")
        self.log_panel = LogPanel(tab_log)

        self.letter_panel = None
        if enable_communication:
            tab_letters = tk.Frame(notebook, bg="#1a1a2e")
            notebook.add(tab_letters, text="🔤 Lettres")
            self.letter_panel = LetterPanel(tab_letters)

        self._visible = False   # replié par défaut : pas encore ajouté au PanedWindow

    def toggle(self):
        self.hide() if self._visible else self.show()

    def show(self):
        if not self._visible:
            self.paned.add(self.frame, minsize=120, height=260)
            self._visible = True

    def hide(self):
        if self._visible:
            self.paned.forget(self.frame)
            self._visible = False

    def update_all(self, world, tick, policy_counts, food_count, deaths):
        """Toujours appelée, même panneau replié : l'historique continue de s'accumuler
        pour que graphe/logs/lettres soient à jour dès qu'on le déplie."""
        self.graph.update(tick, policy_counts, food_count, deaths)
        self.log_panel.update()
        if self.letter_panel:
            self.letter_panel.update(world)