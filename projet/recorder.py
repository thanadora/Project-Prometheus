import os
import cv2
import numpy as np
import config


def _hex_to_rgb(hex_color):
    return (int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16))


class Recorder:
    def __init__(self):
        self.recording = False
        self.mode      = None
        self.frames    = []

    def start(self, mode):
        self.recording = True
        self.mode      = mode
        self.frames    = []

    def stop(self, path, time_scale=1.0):
        """Assemble les frames en MP4. Retourne True si succès."""
        self.recording = False
        if not self.frames:
            return False

        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)

        h, w = self.frames[0].shape[:2]

        if self.mode == "screen":
            fps = config.VIDEO_FPS_SCREEN * time_scale
        else:
            fps = config.VIDEO_FPS_TICK

        fps = max(1.0, fps)
        out = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))

        for frame in self.frames:
            out.write(frame)
        out.release()
        self.frames = []
        return True

    def capture_world(self, world, view=None):
        """Génère une image depuis les données du monde, sans capturer l'écran.

        `view` = (x0, y0, w, h) en cases : fenêtre de caméra à capturer.
        Par défaut, capture tout le monde classique (0,0,WORLD_WIDTH,WORLD_HEIGHT),
        comme avant. En mode infini, on passe explicitement la fenêtre affichée
        à l'écran — impossible de "tout" capturer sur un monde sans bords."""
        from PIL import Image, ImageDraw

        cs = config.CELL_SIZE
        x0, y0, view_w, view_h = view if view is not None else (0, 0, config.WORLD_WIDTH, config.WORLD_HEIGHT)

        w    = view_w * cs
        h    = view_h * cs
        img  = Image.new("RGB", (w, h), (0, 0, 0))
        draw = ImageDraw.Draw(img)

        burning = getattr(world, "burning", {})
        flooded = getattr(world, "flooded", {})

        # Biomes (get_biome : génère à la demande si mode infini)
        for j in range(view_h):
            for i in range(view_w):
                wx, wy = x0 + i, y0 + j
                biome = world.map.get_biome(wx, wy)
                hex_color = config.BIOME_COLORS.get(biome, "#000000")
                if (wx, wy) in burning:
                    hex_color = "#ff5a00"
                elif (wx, wy) in flooded:
                    hex_color = "#2e6da4"
                r, g, b = _hex_to_rgb(hex_color)
                draw.rectangle(
                    [i * cs, j * cs, (i+1) * cs, (j+1) * cs],
                    fill=(r, g, b)
                )

        # Nourriture
        for x, y, amount in world.food.iter_food():
            i, j = x - x0, y - y0
            if not (0 <= i < view_w and 0 <= j < view_h) or amount <= 0:
                continue
            biome     = world.map.biome_map.get((x, y))
            food_type = config.FOOD_TYPES.get(biome)
            if food_type is None:
                continue
            r, g, b = _hex_to_rgb(food_type["color"])
            capacity = food_type["capacity"]
            t        = min(amount / capacity, 1.0)
            size     = 2 + t * (cs - 4)
            cx       = i * cs + cs / 2
            cy       = j * cs + cs / 2
            draw.rectangle(
                [cx - size/2, cy - size/2, cx + size/2, cy + size/2],
                fill=(r, g, b)
            )

        # Agents
        AGENT_COLORS = {
            "new":    (0,   255, 0),
            "thirst": (255, 255, 0),
            "high":   (0,   255, 255),
            "mid":    (255, 165, 0),
            "low":    (255, 0,   0),
        }
        for agent in world.agents:
            if not agent.alive:
                continue
            i, j = agent.x - x0, agent.y - y0
            if not (0 <= i < view_w and 0 <= j < view_h):
                continue
            age_since_birth = world.tick - agent.born_tick
            if age_since_birth < 5:
                color = AGENT_COLORS["new"]
            elif agent.thirst < 25:
                color = AGENT_COLORS["thirst"]
            elif agent.energy > 60:
                color = AGENT_COLORS["high"]
            elif agent.energy > 30:
                color = AGENT_COLORS["mid"]
            else:
                color = AGENT_COLORS["low"]
            x1 = i * cs + 2
            y1 = j * cs + 2
            x2 = x1 + cs - 4
            y2 = y1 + cs - 4
            draw.rectangle([x1, y1, x2, y2], fill=color)

        arr = np.array(img)
        return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
