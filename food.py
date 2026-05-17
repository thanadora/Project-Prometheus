import random
import noise
from dataclasses import dataclass, field
from config import (
    INITIAL_FOOD_COUNT,
    BIOME_WATER,
    BIOME_DESERT,
    BIOME_PRAIRIE,
    BIOME_FOREST,
    WATER_THRESHOLD,
    PRAIRIE_THRESHOLD,
    FOREST_THRESHOLD,
    FOOD_TYPES,
)

# -----------------------------
# UTILS
# -----------------------------
def fertility_to_biome(fertility):
    if fertility < WATER_THRESHOLD:
        return BIOME_WATER
    elif fertility < FOREST_THRESHOLD:
        return BIOME_FOREST
    elif fertility < PRAIRIE_THRESHOLD:
        return BIOME_PRAIRIE
    else:
        return BIOME_DESERT

# -----------------------------
# FOOD SYSTEM
# -----------------------------
@dataclass
class FoodSystem:
    width: int
    height: int
    fertility_map: list = field(default_factory=list)
    biome_map: dict = field(default_factory=dict)
    food_map: dict = field(default_factory=dict)

    # -----------------------------
    # INIT
    # -----------------------------
    def initialize(self):
        self.compute_fertility()
        self.compute_biomes()
        self.init_food_map()

    def compute_fertility(self, scale=10.0):
        offset_x = random.uniform(0, 1000)
        offset_y = random.uniform(0, 1000)
        self.fertility_map = []
        for y in range(self.height):
            row = []
            for x in range(self.width):
                n = noise.pnoise2(
                    (x + offset_x) / scale,
                    (y + offset_y) / scale,
                    octaves=3,
                    persistence=0.5,
                    lacunarity=2.0
                )
                fertility = (n + 1) / 2
                row.append(fertility)
            self.fertility_map.append(row)

    def compute_biomes(self):
        self.biome_map = {}
        for y in range(self.height):
            for x in range(self.width):
                fertility = self.fertility_map[y][x]
                self.biome_map[(x, y)] = fertility_to_biome(fertility)

    def init_food_map(self):
        self.food_map = {
            (x, y): 0
            for x in range(self.width)
            for y in range(self.height)
        }
        self.spawn_initial_food()

    # -----------------------------
    # LOGIC
    # -----------------------------
    def get_capacity(self, pos):
        biome = self.biome_map.get(pos)
        if biome not in FOOD_TYPES:
            return 0
        return FOOD_TYPES[biome]["capacity"]

    def spawn_initial_food(self):
        candidates = [
            pos for pos, biome in self.biome_map.items()
            if biome in FOOD_TYPES
        ]
        for _ in range(INITIAL_FOOD_COUNT):
            if not candidates:
                break
            pos = random.choice(candidates)
            capacity = self.get_capacity(pos)
            if self.food_map[pos] < capacity:
                self.food_map[pos] += 1

    def grow_food(self):
        for y in range(self.height):
            for x in range(self.width):
                pos = (x, y)
                biome = self.biome_map.get(pos)
                if biome not in FOOD_TYPES:
                    continue
                food_type = FOOD_TYPES[biome]
                capacity = food_type["capacity"]
                current = self.food_map[pos]
                saturation = current / capacity if capacity > 0 else 0
                growth = food_type["respawn"] * (1 - saturation) ** 2
                if random.random() < growth:
                    self.food_map[pos] = current + 1

    def consume_food(self, pos):
        if self.food_map.get(pos, 0) <= 0:
            return 0
        biome = self.biome_map.get(pos)
        if biome not in FOOD_TYPES:
            return 0
        self.food_map[pos] -= 1
        return FOOD_TYPES[biome]["gain"]

    def iter_food(self):
        for (x, y), amount in self.food_map.items():
            if amount > 0:
                yield x, y, amount

    def is_walkable(self, x, y):
        return self.biome_map.get((x, y)) != BIOME_WATER