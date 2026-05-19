import random
from dataclasses import dataclass, field
from config import (
    INITIAL_FOOD_COUNT,
    BIOME_WATER,
    FOOD_TYPES,
)


@dataclass
class FoodSystem:
    width: int
    height: int
    food_map: dict = field(default_factory=dict)

    def initialize(self, biome_map):
        self.food_map = {
            (x, y): 0
            for x in range(self.width)
            for y in range(self.height)
        }
        self._spawn_initial_food(biome_map)

    def _spawn_initial_food(self, biome_map):
        candidates = [
            pos for pos, biome in biome_map.items()
            if biome in FOOD_TYPES
        ]
        for _ in range(INITIAL_FOOD_COUNT):
            if not candidates:
                break
            pos      = random.choice(candidates)
            capacity = self._get_capacity(biome_map, pos)
            if self.food_map[pos] < capacity:
                self.food_map[pos] += 1

    def _get_capacity(self, biome_map, pos):
        biome = biome_map.get(pos)
        if biome not in FOOD_TYPES:
            return 0
        return FOOD_TYPES[biome]["capacity"]

    def grow_food(self, biome_map, soil_moisture=0.5):
        for y in range(self.height):
            for x in range(self.width):
                pos   = (x, y)
                biome = biome_map.get(pos)
                if biome not in FOOD_TYPES:
                    continue

                local_moisture = soil_moisture
                for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    if biome_map.get((x + dx, y + dy)) == BIOME_WATER:
                        local_moisture = min(1.0, soil_moisture + 0.3)
                        break

                food_type  = FOOD_TYPES[biome]
                capacity   = food_type["capacity"]
                current    = self.food_map[pos]
                saturation = current / capacity if capacity > 0 else 0
                growth     = food_type["respawn"] * local_moisture * (1 - saturation) ** 2
                if random.random() < growth:
                    self.food_map[pos] = current + 1

    def consume_food(self, biome_map, pos):
        if self.food_map.get(pos, 0) <= 0:
            return 0
        biome = biome_map.get(pos)
        if biome not in FOOD_TYPES:
            return 0
        self.food_map[pos] -= 1
        return FOOD_TYPES[biome]["gain"]

    def clear_position(self, pos):
        """Vide la nourriture d'une case (ex: case inondée)."""
        self.food_map[pos] = 0

    def iter_food(self):
        for (x, y), amount in self.food_map.items():
            if amount > 0:
                yield x, y, amount
