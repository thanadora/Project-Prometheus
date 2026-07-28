import tkinter as tk
from tkinter import ttk
import config
from policy_registry import REGISTRY

# Valeurs initiales pour FOOD_TYPES (pas dans config directement)
config._FOOD_DESERT_GAIN     = config.FOOD_TYPES[config.BIOME_DESERT]["gain"]
config._FOOD_DESERT_RESPAWN  = config.FOOD_TYPES[config.BIOME_DESERT]["respawn"]
config._FOOD_DESERT_CAP      = config.FOOD_TYPES[config.BIOME_DESERT]["capacity"]
config._FOOD_PRAIRIE_GAIN    = config.FOOD_TYPES[config.BIOME_PRAIRIE]["gain"]
config._FOOD_PRAIRIE_RESPAWN = config.FOOD_TYPES[config.BIOME_PRAIRIE]["respawn"]
config._FOOD_PRAIRIE_CAP     = config.FOOD_TYPES[config.BIOME_PRAIRIE]["capacity"]
config._FOOD_FOREST_GAIN     = config.FOOD_TYPES[config.BIOME_FOREST]["gain"]
config._FOOD_FOREST_RESPAWN  = config.FOOD_TYPES[config.BIOME_FOREST]["respawn"]
config._FOOD_FOREST_CAP      = config.FOOD_TYPES[config.BIOME_FOREST]["capacity"]


def run_config_gui():
    root = tk.Tk()
    root.title("Configuration — Simulation Vie Artificielle")
    root.resizable(False, False)
    launched = {"ok": False}

    BG       = "#1a1a2e"
    FG       = "#e0e0ff"
    ACCENT   = "#00cfff"

    root.configure(bg=BG)

    style = ttk.Style()
    style.theme_use("clam")
    style.configure("TNotebook",     background=BG, borderwidth=0)
    style.configure("TNotebook.Tab", background="#11112a", foreground=FG, padding=[10, 4])
    style.map("TNotebook.Tab",       background=[("selected", "#222244")])
    style.configure("TFrame",        background=BG)
    style.configure("TLabel",        background=BG, foreground=FG)
    style.configure("TScale",        background=BG, troughcolor="#333355")

    # ── helpers ──────────────────────────────────────────────────
    def make_tab(nb, title):
        frame = ttk.Frame(nb)
        nb.add(frame, text=title)
        canvas = tk.Canvas(frame, bg=BG, highlightthickness=0, width=560, height=400)
        sb = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        inner = ttk.Frame(canvas)
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        def on_configure(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(win_id, width=canvas.winfo_width())
        inner.bind("<Configure>", on_configure)
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win_id, width=e.width))
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(-1*(e.delta//120), "units"))
        return inner

    fields = {}

    def add_int(parent, row, label, attr, min_val, max_val):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=12, pady=4)
        var = tk.IntVar(value=getattr(config, attr))
        sl  = tk.Scale(parent, from_=min_val, to=max_val, orient=tk.HORIZONTAL,
                       variable=var, bg=BG, fg=FG, troughcolor="#333355",
                       highlightthickness=0, length=260)
        sl.grid(row=row, column=1, padx=8, pady=4)
        tk.Label(parent, textvariable=var, bg=BG, fg=ACCENT, width=5).grid(row=row, column=2, padx=4)
        fields[attr] = ("int", var)

    def add_float(parent, row, label, attr, min_val, max_val, resolution=0.01):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=12, pady=4)
        var = tk.DoubleVar(value=getattr(config, attr))
        sl  = tk.Scale(parent, from_=min_val, to=max_val, resolution=resolution,
                       orient=tk.HORIZONTAL, variable=var,
                       bg=BG, fg=FG, troughcolor="#333355",
                       highlightthickness=0, length=260)
        sl.grid(row=row, column=1, padx=8, pady=4)
        tk.Label(parent, textvariable=var, bg=BG, fg=ACCENT, width=6).grid(row=row, column=2, padx=4)
        fields[attr] = ("float", var)

    def add_bool(parent, row, label, attr):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=12, pady=4)
        var = tk.BooleanVar(value=getattr(config, attr))
        tk.Checkbutton(parent, variable=var, bg=BG, fg=FG,
                       activebackground=BG, selectcolor="#333355").grid(row=row, column=1, sticky="w", padx=8)
        fields[attr] = ("bool", var)

    def section(parent, row, title):
        tk.Label(parent, text=title, bg="#222244", fg=ACCENT,
                 font=("Arial", 10, "bold"), anchor="w"
                 ).grid(row=row, column=0, columnspan=3, sticky="ew", padx=4, pady=(10, 2))

    # ── Notebook ─────────────────────────────────────────────────
    nb = ttk.Notebook(root)
    nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # ── Onglet 1 : Monde ─────────────────────────────────────────
    t = make_tab(nb, "🌍 Monde")
    section(t, 0, "Dimensions")
    add_int  (t, 1, "Largeur",             "WORLD_WIDTH",         10, 100)
    add_int  (t, 2, "Hauteur",             "WORLD_HEIGHT",        10, 80)
    add_int  (t, 3, "Agents initiaux",     "INITIAL_AGENT_COUNT", 1,  50)
    add_bool (t, 4, "Monde toroïdal",      "TOROIDAL_WORLD")

    section(t, 5, "Monde infini")
    infinite_var = tk.BooleanVar(value=config.INFINITE_WORLD)
    tk.Checkbutton(
        t, text="🌐 Monde infini (façon Minecraft) — sans bords, générée à la demande",
        variable=infinite_var, bg=BG, fg=FG, activebackground=BG,
        selectcolor="#333355", font=("Arial", 10), anchor="w",
    ).grid(row=6, column=0, columnspan=3, sticky="w", padx=20, pady=(2, 0))
    tk.Label(
        t,
        text="Ignore Largeur/Hauteur/Toroïdal ci-dessus. Désactive automatiquement\n"
             "la migration (inutile sans bords). Les agents démarrent groupés au\n"
             "centre et peuvent ensuite s'étendre aussi loin qu'ils veulent.",
        bg=BG, fg="#888899", font=("Arial", 8), justify="left",
    ).grid(row=7, column=0, columnspan=3, sticky="w", padx=20, pady=(0, 6))

    section(t, 8, "Biomes — seuils de génération")
    add_float(t, 9,  "Seuil eau",           "WATER_THRESHOLD",     0.1, 0.8)
    add_float(t, 10, "Seuil forêt",         "FOREST_THRESHOLD",    0.1, 0.8)
    add_float(t, 11, "Seuil prairie",       "PRAIRIE_THRESHOLD",   0.1, 0.9)
    add_float(t, 12, "Influence humidité",  "HUMIDITY_INFLUENCE",  0.0, 1.0)

    # ── Onglet 2 : Énergie ───────────────────────────────────────
    t = make_tab(nb, "⚡ Énergie")
    section(t, 0, "Énergie & âge")
    add_int  (t, 1, "Énergie max",         "MAX_ENERGY",      10, 500)
    add_int  (t, 2, "Âge max",             "MAX_AGE",         50, 1000)
    add_int  (t, 3, "Rayon de vision",     "VISION_RADIUS",   1,  20)
    section(t, 4, "Coûts")
    add_float(t, 5, "Coût déplacement",    "MOVE_COST",       0.1, 5.0)
    add_float(t, 6, "Coût idle (jour)",    "IDLE_COST",       0.1, 3.0)
    add_float(t, 7, "Coût idle (nuit)",    "NIGHT_IDLE_COST", 0.1, 5.0)

    # ── Onglet 3 : Soif ──────────────────────────────────────────
    t = make_tab(nb, "💧 Soif")
    section(t, 0, "Soif")
    add_int  (t, 1, "Soif max",                "MAX_THIRST",          10, 300)
    add_float(t, 2, "Taux de soif (normal)",   "THIRST_RATE",         0.01, 2.0)
    add_float(t, 3, "Taux de soif (désert)",   "THIRST_RATE_DESERT",  0.01, 3.0)
    add_float(t, 4, "Taux de soif (nuit)",     "THIRST_RATE_NIGHT",   0.01, 2.0)
    add_float(t, 5, "Dégâts soif critique",    "THIRST_DAMAGE",       0.1, 5.0)
    add_float(t, 6, "Seuil critique (soif)",   "THIRST_CRITICAL",     5.0, 60.0, 1.0)
    add_float(t, 7, "Quantité bue par action", "DRINK_AMOUNT",        5.0, 100.0, 1.0)

    # ── Onglet 4 : Nourriture ────────────────────────────────────
    t = make_tab(nb, "🍎 Nourriture")
    section(t, 0, "Général")
    add_int  (t, 1,  "Nourriture initiale",  "INITIAL_FOOD_COUNT",    0, 300)
    add_int  (t, 2,  "Taille inventaire",    "INVENTORY_SIZE",         0, 10)
    section(t, 3, "Désert")
    add_int  (t, 4,  "Gain (désert)",        "_FOOD_DESERT_GAIN",      1, 100)
    add_float(t, 5,  "Respawn (désert)",     "_FOOD_DESERT_RESPAWN",   0.001, 0.05, 0.001)
    add_int  (t, 6,  "Capacité (désert)",    "_FOOD_DESERT_CAP",       1, 20)
    section(t, 7, "Prairie")
    add_int  (t, 8,  "Gain (prairie)",       "_FOOD_PRAIRIE_GAIN",     1, 100)
    add_float(t, 9,  "Respawn (prairie)",    "_FOOD_PRAIRIE_RESPAWN",  0.001, 0.05, 0.001)
    add_int  (t, 10, "Capacité (prairie)",   "_FOOD_PRAIRIE_CAP",      1, 20)
    section(t, 11, "Forêt")
    add_int  (t, 12, "Gain (forêt)",         "_FOOD_FOREST_GAIN",      1, 100)
    add_float(t, 13, "Respawn (forêt)",      "_FOOD_FOREST_RESPAWN",   0.001, 0.05, 0.001)
    add_int  (t, 14, "Capacité (forêt)",     "_FOOD_FOREST_CAP",       1, 20)

    # ── Onglet 5 : Jour/Nuit ─────────────────────────────────────
    t = make_tab(nb, "🌙 Jour/Nuit")
    section(t, 0, "Cycle")
    add_int  (t, 1, "Durée d'un jour (ticks)", "DAY_DURATION",       10, 200)
    add_float(t, 2, "Ratio nuit",               "NIGHT_RATIO",        0.1, 0.9)
    add_float(t, 3, "Vision nocturne (ratio)",  "NIGHT_VISION_RATIO", 0.1, 1.0)
    section(t, 4, "Saisons")
    add_int  (t, 5, "Durée d'une saison",       "SEASON_DURATION",    50, 500)

    # ── Onglet 6 : Météo ─────────────────────────────────────────
    t = make_tab(nb, "⛅ Météo")
    section(t, 0, "Général")
    add_float(t, 1, "Probabilité de changement", "WEATHER_CHANGE_PROB", 0.0, 1.0)
    section(t, 2, "Humidité du sol")
    add_float(t, 3, "Humidité initiale",          "SOIL_MOISTURE_INIT",  0.1, 1.0)
    add_float(t, 4, "Humidité min",               "SOIL_MOISTURE_MIN",   0.0, 0.5)
    add_float(t, 5, "Humidité max",               "SOIL_MOISTURE_MAX",   0.5, 1.0)

    # ── Onglet 7 : Migration ─────────────────────────────────────
    t = make_tab(nb, "🚶 Migration")
    add_float(t, 0, "Seuil vote migration",   "MIGRATION_VOTE_THRESHOLD",  0.1, 1.0)
    add_int  (t, 1, "Cooldown migration",      "MIGRATION_COOLDOWN",        50, 1000)
    add_float(t, 2, "Seuil détresse énergie",  "MIGRATION_DISTRESS_ENERGY", 1.0, 30.0, 0.5)
    add_float(t, 3, "Seuil détresse soif",     "MIGRATION_DISTRESS_THIRST", 1.0, 30.0, 0.5)
    add_int  (t, 4, "Seuil âge détresse",      "MIGRATION_AGE_THRESHOLD",   50, 1000)
    add_int  (t, 5, "Population max migrable", "MIGRATION_MAX_AGENTS",      3, 200)

    # ── Onglet 7bis : Communication ────────────────────────────
    t = make_tab(nb, "💬 Communication")
    section(t, 0, "Lettres")
    add_int(t, 1, "Taille de l'alphabet",  "ALPHABET_SIZE", 2, 10)
    add_int(t, 2, "Rayon d'écoute",        "COMM_RADIUS",   1, 20)
    tk.Label(
        t,
        text="Chaque agent peut \"dire\" une lettre par tick (action libre, gratuite).\n"
             "Les agents dans le rayon d'écoute la perçoivent. Aucun sens n'est\n"
             "câblé en dur — c'est juste le mécanisme brut.",
        bg=BG, fg="#888899", font=("Arial", 8), justify="left",
    ).grid(row=3, column=0, columnspan=3, sticky="w", padx=20, pady=(10, 0))

    # ── Onglet 8 : Modules ───────────────────────────────────────
    t = make_tab(nb, "🎮 Modules")
    module_vars = {}

    def add_module(parent, row, label, attr, depends_on=None):
        var = tk.BooleanVar(value=getattr(config, attr))
        module_vars[attr] = var
        cb = tk.Checkbutton(
            parent, text=label, variable=var,
            bg=BG, fg=FG, activebackground=BG,
            selectcolor="#333355", font=("Arial", 10),
            anchor="w",
        )
        cb.grid(row=row, column=0, sticky="w", padx=20, pady=6)
        if depends_on:
            tk.Label(parent, text=f"  ⚠ désactivé si {depends_on} est OFF",
                     bg=BG, fg="#888899", font=("Arial", 8)
                     ).grid(row=row, column=1, sticky="w", padx=4)
        return var, cb

    section(t, 0, "Modules actifs")
    add_module(t, 1, "🗺  Biomes (désert / prairie / forêt)", "ENABLE_BIOMES")
    add_module(t, 2, "💧 Soif",                               "ENABLE_THIRST",       "Biomes")
    add_module(t, 3, "⛅ Météo",                              "ENABLE_WEATHER",      "Biomes + Saisons")
    add_module(t, 4, "🍂 Saisons",                            "ENABLE_SEASONS",      "Biomes")
    add_module(t, 5, "🌙 Cycle jour/nuit",                    "ENABLE_DAY_NIGHT")
    add_module(t, 6, "🚶 Migration",                          "ENABLE_MIGRATION")
    add_module(t, 7, "🎒 Inventaire",                         "ENABLE_INVENTORY")
    add_module(t, 8, "👶 Reproduction",                       "ENABLE_REPRODUCTION")
    add_module(t, 9, "💀 Mort de vieillesse",                 "ENABLE_AGE_DEATH")
    add_module(t, 10, "💬 Communication (lettres)",           "ENABLE_COMMUNICATION")
    add_module(t, 11, "⛰ Altitude (ombrage du relief)",       "ENABLE_ALTITUDE")


    section(t, 13, "Logs")
    tk.Label(t, text="Niveau de log", bg=BG, fg=FG,
            font=("Arial", 10)).grid(row=14, column=0, sticky="w", padx=20, pady=6)
    log_level_var = tk.StringVar(value=config.LOG_LEVEL)
    for i, (level, desc) in enumerate([
        ("DEBUG",   "tout logger (actions, perceptions...)"),
        ("INFO",    "naissances, morts, migrations"),
        ("WARNING", "population critique, soif critique"),
        ("ERROR",   "erreurs uniquement"),
    ]):
        tk.Radiobutton(
            t, text=f"{level} — {desc}",
            variable=log_level_var, value=level,
            bg=BG, fg=FG, activebackground=BG, selectcolor="#333355",
            font=("Arial", 9), anchor="w",
        ).grid(row=15+i, column=0, columnspan=2, sticky="w", padx=30, pady=2)
        
    # Dépendances automatiques en cascade
    def on_biomes_toggle(*_):
        if not module_vars["ENABLE_BIOMES"].get():
            for attr in ("ENABLE_THIRST", "ENABLE_WEATHER", "ENABLE_SEASONS"):
                module_vars[attr].set(False)

    def on_seasons_toggle(*_):
        if not module_vars["ENABLE_SEASONS"].get():
            module_vars["ENABLE_WEATHER"].set(False)

    def on_altitude_toggle(*_):
        if not module_vars["ENABLE_ALTITUDE"].get():
            # Le relief 2.5D (réglable en jeu, plus dans cet écran) dépend
            # de l'altitude : on le désactive aussi si l'altitude l'est.
            config.ENABLE_ALTITUDE_2_5D = False

    module_vars["ENABLE_BIOMES"].trace_add("write", on_biomes_toggle)
    module_vars["ENABLE_SEASONS"].trace_add("write", on_seasons_toggle)
    module_vars["ENABLE_ALTITUDE"].trace_add("write", on_altitude_toggle)

    def on_infinite_toggle(*_):
        if infinite_var.get():
            module_vars["ENABLE_MIGRATION"].set(False)
    infinite_var.trace_add("write", on_infinite_toggle)
    # ── Onglet 9 : IA ────────────────────────────────────────────
    t = make_tab(nb, "🤖 IA")

    section(t, 0, "Distribution des policies")
    tk.Label(t, text="Répartition des agents par policy (total = 100%)",
            bg=BG, fg="#888899", font=("Arial", 9)
            ).grid(row=1, column=0, columnspan=3, sticky="w", padx=20, pady=(0,8))

    policy_sliders = {}
    for i, (name, info) in enumerate(REGISTRY.items()):
        row = 2 + i * 2
        tk.Label(t, text=f"{name}", bg=BG, fg=info["color"],
                font=("Arial", 10, "bold")).grid(row=row, column=0, sticky="w", padx=20, pady=(6,0))
        tk.Label(t, text=info["description"], bg=BG, fg="#888899",
                font=("Arial", 8)).grid(row=row, column=1, columnspan=2, sticky="w", padx=8)

        var = tk.IntVar(value=int(config.POLICY_DISTRIBUTION.get(name, 0) * 100))
        sl  = tk.Scale(t, from_=0, to=100, orient=tk.HORIZONTAL,
                    variable=var, bg=BG, fg=FG, troughcolor="#333355",
                    highlightthickness=0, length=260)
        sl.grid(row=row+1, column=0, columnspan=2, padx=20, pady=(0,4))
        tk.Label(t, textvariable=var, bg=BG, fg=info["color"], width=4
                ).grid(row=row+1, column=2)
        policy_sliders[name] = var

    # Indicateur total
    total_var = tk.StringVar(value="Total : 100%")
    total_lbl = tk.Label(t, textvariable=total_var, bg=BG, fg=ACCENT, font=("Arial", 10, "bold"))
    total_lbl.grid(row=2 + len(REGISTRY)*2, column=0, columnspan=3, pady=10)

    def update_total(*_):
        total = sum(v.get() for v in policy_sliders.values())
        color = ACCENT if total == 100 else "#ff4444"
        total_var.set(f"Total : {total}%")
        total_lbl.config(fg=color)

    for var in policy_sliders.values():
        var.trace_add("write", update_total)
        
    # ── Onglet : Contrôles (clavier + souris) ───────────────────
    t = make_tab(nb, "🎮 Contrôles")
    section(t, 0, "Clavier — cliquez sur une touche pour la réassigner")

    key_binding_vars = {}
    capture_state = {"active_action": None}

    def _format_event_as_binding(event):
        mods = []
        if event.state & 0x0004:
            mods.append("Control")
        if event.state & 0x0001:
            mods.append("Shift")
        if event.state & 0x0008 or event.state & 0x20000:
            mods.append("Alt")
        keysym = event.keysym
        if not mods:
            if keysym == "plus":
                return "+"
            if keysym == "minus":
                return "-"
            if len(keysym) == 1:
                return keysym.lower()
            return f"<{keysym}>"
        return f"<{'-'.join(mods)}-{keysym}>"

    def _on_key_captured(event):
        action = capture_state["active_action"]
        if action is None:
            return
        binding = _format_event_as_binding(event)
        key_binding_vars[action].set(binding)
        capture_state["active_action"] = None
        root.unbind("<KeyPress>", capture_state.get("bind_id"))
        return "break"

    def start_capture(action, btn):
        # Un seul réassignement à la fois
        if capture_state["active_action"] is not None:
            return
        capture_state["active_action"] = action
        btn.config(text="Appuyez sur une touche…")
        bind_id = root.bind("<KeyPress>", lambda e, a=action, b=btn: (_on_key_captured(e), b.config(text=key_binding_vars[a].get())))
        capture_state["bind_id"] = bind_id

    for i, (action, default) in enumerate(config.KEY_BINDINGS.items()):
        var = tk.StringVar(value=default)
        key_binding_vars[action] = var
        label = config.KEY_BINDING_LABELS.get(action, action)
        ttk.Label(t, text=label).grid(row=1 + i, column=0, sticky="w", padx=12, pady=3)
        btn = tk.Button(t, textvariable=var, width=16, bg="#222244", fg=ACCENT,
                         relief=tk.FLAT, activebackground="#333366")
        btn.grid(row=1 + i, column=1, padx=8, pady=3, sticky="w")
        btn.config(command=lambda a=action, b=btn: start_capture(a, b))

    row_after_keys = 1 + len(config.KEY_BINDINGS)
    section(t, row_after_keys, "Souris")

    mouse_select_var = tk.StringVar(value={1: "Clic gauche", 2: "Clic molette", 3: "Clic droit"}[config.MOUSE_SELECT_BUTTON])
    mouse_drag_var   = tk.StringVar(value={1: "Clic gauche", 2: "Clic molette", 3: "Clic droit"}[config.MOUSE_DRAG_BUTTON])
    mouse_options = ["Clic gauche", "Clic molette", "Clic droit"]

    ttk.Label(t, text="Sélectionner un agent").grid(row=row_after_keys + 1, column=0, sticky="w", padx=12, pady=3)
    ttk.Combobox(t, textvariable=mouse_select_var, values=mouse_options, state="readonly", width=14
                 ).grid(row=row_after_keys + 1, column=1, padx=8, pady=3, sticky="w")

    ttk.Label(t, text="Déplacer la caméra (glisser — monde infini)").grid(row=row_after_keys + 2, column=0, sticky="w", padx=12, pady=3)
    ttk.Combobox(t, textvariable=mouse_drag_var, values=mouse_options, state="readonly", width=14
                 ).grid(row=row_after_keys + 2, column=1, padx=8, pady=3, sticky="w")

    tk.Label(
        t,
        text="La molette zoome toujours (non réassignable).\n"
             "Sélection et glisser-caméra doivent utiliser des boutons différents.",
        bg=BG, fg="#888899", font=("Arial", 8), justify="left",
    ).grid(row=row_after_keys + 3, column=0, columnspan=3, sticky="w", padx=12, pady=(4, 6))

    def reset_controls():
        for action, default in config.KEY_BINDINGS.items():
            key_binding_vars[action].set(default)
        mouse_select_var.set("Clic gauche")
        mouse_drag_var.set("Clic droit")

    tk.Button(t, text="↺ Réinitialiser les contrôles", command=reset_controls,
              bg="#222244", fg=ACCENT, relief=tk.FLAT
              ).grid(row=row_after_keys + 4, column=0, columnspan=2, pady=8, sticky="w", padx=12)

    # ── Bouton Lancer ────────────────────────────────────────────
    def on_launch():
        for attr, (typ, var) in fields.items():
            if attr.startswith("_FOOD_"):
                continue
            if typ == "int":
                setattr(config, attr, int(var.get()))
            elif typ == "float":
                setattr(config, attr, float(var.get()))
            elif typ == "bool":
                setattr(config, attr, bool(var.get()))

        config.FOOD_TYPES = {
            config.BIOME_DESERT:  dict(
                gain     = int(fields["_FOOD_DESERT_GAIN"][1].get()),
                respawn  = float(fields["_FOOD_DESERT_RESPAWN"][1].get()),
                capacity = int(fields["_FOOD_DESERT_CAP"][1].get()),
                color    = config.FOOD_TYPES[config.BIOME_DESERT]["color"],
            ),
            config.BIOME_PRAIRIE: dict(
                gain     = int(fields["_FOOD_PRAIRIE_GAIN"][1].get()),
                respawn  = float(fields["_FOOD_PRAIRIE_RESPAWN"][1].get()),
                capacity = int(fields["_FOOD_PRAIRIE_CAP"][1].get()),
                color    = config.FOOD_TYPES[config.BIOME_PRAIRIE]["color"],
            ),
            config.BIOME_FOREST:  dict(
                gain     = int(fields["_FOOD_FOREST_GAIN"][1].get()),
                respawn  = float(fields["_FOOD_FOREST_RESPAWN"][1].get()),
                capacity = int(fields["_FOOD_FOREST_CAP"][1].get()),
                color    = config.FOOD_TYPES[config.BIOME_FOREST]["color"],
            ),
        }

        config.YEAR_DURATION  = config.SEASON_DURATION * 4
        config.ALPHABET       = list("ABCDEFGHIJ")[:config.ALPHABET_SIZE]
        config.INFINITE_WORLD = bool(infinite_var.get())

        for attr, var in module_vars.items():
            setattr(config, attr, bool(var.get()))

        config.LOG_LEVEL = log_level_var.get()
        # Validation distribution IA
        total = sum(v.get() for v in policy_sliders.values())
        if total != 100:
            tk.messagebox.showerror(
                "Distribution invalide",
                f"La somme des policies doit être 100% (actuellement {total}%)"
            )
            return

        # Applique la distribution
        config.POLICY_DISTRIBUTION = {
            name: var.get() / 100.0
            for name, var in policy_sliders.items()
            if var.get() > 0
}
        # Contrôles clavier / souris
        mouse_map = {"Clic gauche": 1, "Clic molette": 2, "Clic droit": 3}
        select_btn = mouse_map[mouse_select_var.get()]
        drag_btn   = mouse_map[mouse_drag_var.get()]
        if select_btn == drag_btn:
            tk.messagebox.showerror(
                "Contrôles invalides",
                "La sélection d'agent et le glisser-caméra doivent utiliser des boutons souris différents."
            )
            return
        config.MOUSE_SELECT_BUTTON = select_btn
        config.MOUSE_DRAG_BUTTON   = drag_btn
        config.KEY_BINDINGS = {action: var.get() for action, var in key_binding_vars.items()}

        launched["ok"] = True
        root.destroy()

    tk.Button(
        root, text="Lancer la simulation",
        command=on_launch,
        bg="#003355", fg=ACCENT,
        font=("Arial", 12, "bold"),
        relief=tk.FLAT, padx=20, pady=8,
        activebackground="#005588", activeforeground="white",
    ).pack(pady=10)

    root.mainloop()
    return launched["ok"]