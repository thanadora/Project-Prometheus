"""
renderer.py — Fonctions de rendu du monde sur le canvas Tkinter.

Séparé de gui.py pour que SimulationGUI ne gère que
les événements et la boucle de simulation.
"""

import colorsys
import config
from config import (
    CELL_SIZE,
    WORLD_WIDTH,
    WORLD_HEIGHT,
    BIOME_COLORS,
    FOOD_TYPES,
    NIGHT_RATIO,
    WEATHER_RAIN,
    WEATHER_STORM,
    WEATHER_DROUGHT,
    WEATHER_FROST,
    GRID_COLOR,
    VISION_RADIUS,
    NIGHT_VISION_RATIO,
    WEATHER_VISION,
    INVENTORY_SIZE,
    ENABLE_COMMUNICATION,
    ALTITUDE_SHADE_STRENGTH,
    ALTITUDE_MAX_OFFSET,
    ALTITUDE_BANDS,
    ALTITUDE_CONTOUR_COLOR,
    ALTITUDE_PEAK_COLOR,
    ALTITUDE_PEAK_BLEND,
    ALTITUDE_VALLEY_COLOR,
    ALTITUDE_VALLEY_BLEND,
)
from actions import action_label
from policy_registry import REGISTRY, policy_name
from map import stretch_altitude, altitude_band


# =========================================================
# OVERLAYS JOUR/NUIT ET MÉTÉO
# =========================================================

# Marge réservée en haut du canvas pour laisser de la place aux cases
# surélevées en mode 2.5D. Dimensionnée pour le zoom max (voir gui.py,
# zoom_max = 2.5). Nulle quand le 2.5D est désactivé, pour que l'affichage
# reste identique au pixel près à l'ancien rendu plat.
TOP_MARGIN = int(ALTITUDE_MAX_OFFSET * 3)


def top_margin():
    """Marge courante à appliquer en haut du canvas — 0 si le relief 2.5D
    n'est pas actif, pour ne rien changer à l'affichage plat d'origine."""
    if config.ENABLE_ALTITUDE and config.ENABLE_ALTITUDE_2_5D:
        return TOP_MARGIN
    return 0


def _band_factor(band):
    """Facteur de luminosité associé à un palier, régulièrement espacé
    autour de 1.0 sur toute l'amplitude ALTITUDE_SHADE_STRENGTH."""
    if ALTITUDE_BANDS <= 1:
        return 1.0
    t = band / (ALTITUDE_BANDS - 1)  # 0..1
    return 1.0 + (t - 0.5) * 2 * ALTITUDE_SHADE_STRENGTH


def shade_by_altitude(hex_color, altitude):
    """Assombrit/éclaircit une couleur selon le palier d'altitude de la case.

    Travaille en HSL et ne touche qu'à la luminosité (L), en gardant teinte
    (H) et saturation (S) intactes. Un simple facteur multiplicatif sur R/G/B
    peut faire dériver la teinte d'un biome vers celle d'un autre (ex : une
    forêt éclaircie qui se met à ressembler à une prairie) — ce qui rendait
    le relief illisible en le confondant avec un changement de biome.
    """
    if not config.ENABLE_ALTITUDE:
        return hex_color
    factor = _band_factor(altitude_band(altitude))
    r = int(hex_color[1:3], 16) / 255
    g = int(hex_color[3:5], 16) / 255
    b = int(hex_color[5:7], 16) / 255
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    l = max(0.0, min(1.0, l * factor))
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return f"#{int(round(r * 255)):02x}{int(round(g * 255)):02x}{int(round(b * 255)):02x}"


def _blend_hex(hex_a, hex_b, t):
    """Mélange deux couleurs hexadécimales (t=0 -> hex_a, t=1 -> hex_b)."""
    ra, ga, ba = int(hex_a[1:3], 16), int(hex_a[3:5], 16), int(hex_a[5:7], 16)
    rb, gb, bb = int(hex_b[1:3], 16), int(hex_b[3:5], 16), int(hex_b[5:7], 16)
    r = round(ra + (rb - ra) * t)
    g = round(ga + (gb - ga) * t)
    b = round(ba + (bb - ba) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


def apply_relief_tint(hex_color, band):
    """Au palier le plus haut, tire la couleur vers un gris rocheux (sommet) ;
    au plus bas, vers un bleu-gris sombre (creux). Rend le relief extrême
    reconnaissable indépendamment du biome, et prépare un futur biome
    montagne dédié. Doit rester désactivable avec le reste du module :
    sans ce garde-fou, décocher "Altitude" laissait quand même apparaître
    cette teinte sur les cases extrêmes."""
    if not config.ENABLE_ALTITUDE:
        return hex_color
    if band == ALTITUDE_BANDS - 1:
        return _blend_hex(hex_color, ALTITUDE_PEAK_COLOR, ALTITUDE_PEAK_BLEND)
    if band == 0:
        return _blend_hex(hex_color, ALTITUDE_VALLEY_COLOR, ALTITUDE_VALLEY_BLEND)
    return hex_color


def get_y_offset(world, x, y, cs):
    """Décalage vertical (px) à appliquer à une case en mode 2.5D, 0 sinon.
    `cs` est la taille de case courante (dépend du zoom en monde infini),
    pour que le relief reste proportionné en cas de zoom/dézoom."""
    if not (config.ENABLE_ALTITUDE and config.ENABLE_ALTITUDE_2_5D):
        return 0
    altitude = world.map.get_altitude(x, y)
    band     = altitude_band(altitude)
    t        = band / (ALTITUDE_BANDS - 1) if ALTITUDE_BANDS > 1 else 1.0
    return t * ALTITUDE_MAX_OFFSET * (cs / CELL_SIZE)


def blend_color(hex_color, night_alpha, weather_alpha=0.0, weather_color=(0, 0, 0)):
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    r = int(r * (1 - night_alpha) + 0  * night_alpha)
    g = int(g * (1 - night_alpha) + 0  * night_alpha)
    b = int(b * (1 - night_alpha) + 40 * night_alpha)
    wr, wg, wb = weather_color
    r = int(r * (1 - weather_alpha) + wr * weather_alpha)
    g = int(g * (1 - weather_alpha) + wg * weather_alpha)
    b = int(b * (1 - weather_alpha) + wb * weather_alpha)
    return f"#{r:02x}{g:02x}{b:02x}"


def get_night_alpha(world):
    if not config.ENABLE_DAY_NIGHT:
        return 0.0
    t           = world.time_of_day()
    night_start = 1 - NIGHT_RATIO
    if t < 0.1:
        return 1.0 - (t / 0.1)
    if t < night_start:
        return 0.0
    if t < night_start + 0.1:
        return (t - night_start) / 0.1
    return 1.0


def get_weather_overlay(world):
    overlays = {
        WEATHER_RAIN:    (0.25, (30,  50, 120)),
        WEATHER_STORM:   (0.45, (20,  20,  60)),
        WEATHER_DROUGHT: (0.20, (120, 80,  20)),
        WEATHER_FROST:   (0.30, (180, 210, 240)),
    }
    return overlays.get(world.weather, (0.0, (0, 0, 0)))


# =========================================================
# DESSIN
# =========================================================

def draw_biomes(canvas, world, view_x0=0, view_y0=0, view_w=None, view_h=None, cell_size=None):
    """Dessine les biomes visibles dans la fenêtre de caméra [view_x0, view_x0+view_w[
    x [view_y0, view_y0+view_h[. Par défaut (mode classique), la fenêtre couvre tout
    le monde comme avant. En mode infini, `get_biome` génère à la demande les cases
    regardées — regarder l'écran "charge" la zone, comme des chunks Minecraft.
    `cell_size` permet de zoomer/dézoomer (mode infini) sans changer CELL_SIZE global."""
    view_w = WORLD_WIDTH  if view_w is None else view_w
    view_h = WORLD_HEIGHT if view_h is None else view_h
    cs     = CELL_SIZE if cell_size is None else cell_size
    night_alpha           = get_night_alpha(world)
    weather_alpha, w_col  = get_weather_overlay(world)
    two_five_d            = config.ENABLE_ALTITUDE and config.ENABLE_ALTITUDE_2_5D
    show_contours          = config.ENABLE_ALTITUDE and not two_five_d

    bands = {}  # (i, j) -> palier d'altitude, réutilisé pour les lignes de niveau

    for j in range(view_h):
        for i in range(view_w):
            x, y     = view_x0 + i, view_y0 + j
            biome    = world.map.get_biome(x, y)
            base_hex = BIOME_COLORS.get(biome, "#000000")
            altitude = world.map.get_altitude(x, y)
            band     = altitude_band(altitude)
            bands[(i, j)] = band
            shaded   = shade_by_altitude(base_hex, altitude)
            shaded   = apply_relief_tint(shaded, band)
            color    = blend_color(shaded, night_alpha, weather_alpha, w_col)

            x1 = i * cs
            x2 = x1 + cs
            base_y1 = top_margin() + j * cs
            base_y2 = base_y1 + cs

            if two_five_d:
                t          = band / (ALTITUDE_BANDS - 1) if ALTITUDE_BANDS > 1 else 1.0
                offset     = t * ALTITUDE_MAX_OFFSET * (cs / CELL_SIZE)
                side_color = blend_color(
                    apply_relief_tint(
                        shade_by_altitude(base_hex, 0.5 - (stretch_altitude(altitude) - 0.5) * 0.6),
                        band,
                    ),
                    night_alpha, weather_alpha, w_col,
                )
                # Face latérale (le "flanc" du bloc).
                canvas.create_rectangle(x1, base_y2 - offset, x2, base_y2, fill=side_color, outline="")
                # Face du dessus, décalée vers le haut selon l'altitude.
                canvas.create_rectangle(x1, base_y1 - offset, x2, base_y2 - offset, fill=color, outline="")
            else:
                canvas.create_rectangle(x1, base_y1, x2, base_y2, fill=color, outline="")

    if show_contours:
        top = top_margin()
        for j in range(view_h):
            for i in range(view_w):
                b = bands[(i, j)]
                # Frontière avec la case de droite
                if i + 1 < view_w and bands[(i + 1, j)] != b:
                    x = (i + 1) * cs
                    canvas.create_line(x, top + j * cs, x, top + (j + 1) * cs,
                                        fill=ALTITUDE_CONTOUR_COLOR, width=1)
                # Frontière avec la case du dessous
                if j + 1 < view_h and bands[(i, j + 1)] != b:
                    y = top + (j + 1) * cs
                    canvas.create_line(i * cs, y, (i + 1) * cs, y,
                                        fill=ALTITUDE_CONTOUR_COLOR, width=1)


def draw_grid(canvas, view_w=None, view_h=None, cell_size=None):
    # En mode 2.5D, la grille classique case-par-case n'a plus de sens visuel
    # (les cases sont décalées individuellement) : on ne la dessine pas.
    if config.ENABLE_ALTITUDE and config.ENABLE_ALTITUDE_2_5D:
        return
    view_w = WORLD_WIDTH  if view_w is None else view_w
    view_h = WORLD_HEIGHT if view_h is None else view_h
    cs     = CELL_SIZE if cell_size is None else cell_size
    top    = 0
    for x in range(view_w + 1):
        canvas.create_line(x * cs, top, x * cs, top + view_h * cs, fill=GRID_COLOR)
    for y in range(view_h + 1):
        canvas.create_line(0, top + y * cs, view_w * cs, top + y * cs, fill=GRID_COLOR)


def draw_foods(canvas, world, view_x0=0, view_y0=0, view_w=None, view_h=None, cell_size=None):
    view_w = WORLD_WIDTH  if view_w is None else view_w
    view_h = WORLD_HEIGHT if view_h is None else view_h
    cs     = CELL_SIZE if cell_size is None else cell_size
    for x, y, amount in world.food.iter_food():
        i, j = x - view_x0, y - view_y0
        if not (0 <= i < view_w and 0 <= j < view_h):
            continue
        biome     = world.map.biome_map.get((x, y))
        food_type = FOOD_TYPES.get(biome)
        if food_type is None:
            continue
        t      = min(amount / food_type["capacity"], 1.0)
        size   = 2 + t * (cs - 4)
        offset = get_y_offset(world, x, y, cs)
        cx     = i * cs + cs / 2
        cy     = top_margin() + j * cs + cs / 2 - offset
        canvas.create_rectangle(
            cx - size / 2, cy - size / 2,
            cx + size / 2, cy + size / 2,
            fill=food_type["color"], outline="",
        )


def draw_agents(canvas, world, selected_agent, view_x0=0, view_y0=0, view_w=None, view_h=None, cell_size=None):
    view_w = WORLD_WIDTH  if view_w is None else view_w
    view_h = WORLD_HEIGHT if view_h is None else view_h
    cs     = CELL_SIZE if cell_size is None else cell_size
    for agent in world.agents:
        i, j = agent.x - view_x0, agent.y - view_y0
        if not (0 <= i < view_w and 0 <= j < view_h):
            continue
        offset = get_y_offset(world, agent.x, agent.y, cs)
        base_y = top_margin() + j * cs - offset
        x1 = i * cs + 2
        y1 = base_y + 2
        x2 = x1 + cs - 4
        y2 = y1 + cs - 4

        age_since_birth = world.tick - getattr(agent, "born_tick", 0)
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

        is_selected  = selected_agent is not None and agent.id == selected_agent.id
        border_color = REGISTRY.get(policy_name(agent.policy), {}).get("color", "white")

        canvas.create_rectangle(
            x1, y1, x2, y2,
            fill=color,
            outline=border_color if is_selected else "",
            width=2 if is_selected else 0,
        )
        if cs >= 8:
            canvas.create_text(
                i * cs + min(7, cs / 2),
                base_y + min(7, cs / 2),
                text=str(agent.generation),
                fill="white",
                font=("Arial", max(5, int(cs * 0.4))),
            )

        if ENABLE_COMMUNICATION and agent.spoken_letter and cs >= 8:
            canvas.create_text(
                x2 - 4,
                y1 + 5,
                text=agent.spoken_letter,
                fill="#ffff00",
                font=("Arial", max(5, int(cs * 0.45)), "bold"),
            )

        if is_selected:
            night_ratio   = NIGHT_VISION_RATIO if world.is_night() else 1.0
            weather_ratio = WEATHER_VISION.get(world.weather, 1.0)
            radius_px     = VISION_RADIUS * night_ratio * weather_ratio * cs
            cx = i * cs + cs / 2
            cy = base_y + cs / 2
            canvas.create_oval(
                cx - radius_px, cy - radius_px,
                cx + radius_px, cy + radius_px,
                outline="white", dash=(4, 4), width=1,
            )


def _inventory_str(agent):
    if not agent.inventory:
        return "vide"
    counts = {}
    for item in agent.inventory:
        counts[item["type"]] = counts.get(item["type"], 0) + 1
    parts = []
    for obj_type, n in counts.items():
        info = config.OBJECT_TYPES.get(obj_type, {"icon": "?"})
        parts.append(f"{info['icon']}x{n}")
    return " ".join(parts)


def agent_panel_text(agent, world):
    """Retourne la chaîne d'info de l'agent sélectionné, ou '' si aucun."""
    if agent is None or not agent.alive:
        return ""

    inv_str    = f"{len(agent.inventory)}/{INVENTORY_SIZE} [{_inventory_str(agent)}]"
    action_str = action_label(agent.pending_action)
    free_str   = ", ".join(action_label(fa) for fa in agent.free_actions) or "—"

    speak_str  = agent.spoken_letter or "—"
    heard_str  = ", ".join(
        f"{h['letter']}({h['dx']:+d},{h['dy']:+d})" for h in agent.heard_letters
    ) or "—"

    return (
        f"[ Agent #{agent.id} ]  "
        f"Pos: ({agent.x},{agent.y})  "
        f"Énergie: {agent.energy:.1f}  "
        f"Soif: {agent.thirst:.1f}  "
        f"Inventaire: {inv_str}  "
        f"Âge: {agent.age}  "
        f"Gén: {agent.generation}  "
        f"IA: {policy_name(agent.policy) or '?'}  "
        f"Action: {action_str}  "
        f"Libres: {free_str}  "
        f"Vote migr.: {'Oui' if agent.vote_migrate else 'Non'}  "
        f"Dit: {speak_str}  "
        f"Entend: {heard_str}  "
        f"Reward: {agent.last_reward:+.2f}"
    )