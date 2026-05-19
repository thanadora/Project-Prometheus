import os
import cv2
import numpy as np
from config import VIDEO_FPS_SCREEN, VIDEO_FPS_TICK, OUTPUT_DIR


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
            fps = VIDEO_FPS_SCREEN * time_scale
        else:
            fps = VIDEO_FPS_TICK

        fps = max(1.0, fps)
        out = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))

        for frame in self.frames:
            out.write(frame)
        out.release()
        self.frames = []
        return True

    def capture_world(self, world):
        """Génère une image depuis les données du monde, sans capturer l'écran."""
        from PIL import Image, ImageDraw
        from config import CELL_SIZE, BIOME_COLORS, FOOD_TYPES, WORLD_WIDTH, WORLD_HEIGHT

        w    = WORLD_WIDTH  * CELL_SIZE
        h    = WORLD_HEIGHT * CELL_SIZE
        img  = Image.new("RGB", (w, h), (0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Biomes
        for (x, y), biome in world.map.biome_map.items():
            hex_color = BIOME_COLORS.get(biome, "#000000")
            r = int(hex_color[1:3], 16)
            g = int(hex_color[3:5], 16)
            b = int(hex_color[5:7], 16)
            draw.rectangle(
                [x * CELL_SIZE, y * CELL_SIZE, (x+1) * CELL_SIZE, (y+1) * CELL_SIZE],
                fill=(r, g, b)
            )

        # Nourriture
        for x, y, amount in world.food.iter_food():
            if amount <= 0:
                continue
            biome     = world.map.biome_map.get((x, y))
            food_type = FOOD_TYPES.get(biome)
            if food_type is None:
                continue
            hex_color = food_type["color"]
            r        = int(hex_color[1:3], 16)
            g        = int(hex_color[3:5], 16)
            b        = int(hex_color[5:7], 16)
            capacity = food_type["capacity"]
            t        = min(amount / capacity, 1.0)
            size     = 2 + t * (CELL_SIZE - 4)
            cx       = x * CELL_SIZE + CELL_SIZE / 2
            cy       = y * CELL_SIZE + CELL_SIZE / 2
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
            x1 = agent.x * CELL_SIZE + 2
            y1 = agent.y * CELL_SIZE + 2
            x2 = x1 + CELL_SIZE - 4
            y2 = y1 + CELL_SIZE - 4
            draw.rectangle([x1, y1, x2, y2], fill=color)

        arr = np.array(img)
        return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)