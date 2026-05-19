import random
import noise
from dataclasses import dataclass, field
from config import (
    BIOME_WATER,
    BIOME_DESERT,
    BIOME_PRAIRIE,
    BIOME_FOREST,
    WATER_THRESHOLD,
    PRAIRIE_THRESHOLD,
    FOREST_THRESHOLD,
)


def _fertility_to_biome(fertility):
    if fertility < WATER_THRESHOLD:
        return BIOME_WATER
    elif fertility < FOREST_THRESHOLD:
        return BIOME_FOREST
    elif fertility < PRAIRIE_THRESHOLD:
        return BIOME_PRAIRIE
    else:
        return BIOME_DESERT


@dataclass
class GameMap:
    width: int
    height: int
    biome_map: dict = field(default_factory=dict)

    def initialize(self):
        scale    = 10.0
        offset_x = random.uniform(0, 1000)
        offset_y = random.uniform(0, 1000)

        # fertility_map calculé localement puis jeté — pas besoin de le stocker
        for y in range(self.height):
            for x in range(self.width):
                n = noise.pnoise2(
                    (x + offset_x) / scale,
                    (y + offset_y) / scale,
                    octaves=3,
                    persistence=0.5,
                    lacunarity=2.0,
                )
                fertility = (n + 1) / 2
                self.biome_map[(x, y)] = _fertility_to_biome(fertility)

    def is_walkable(self, x, y):
        return self.biome_map.get((x, y)) != BIOME_WATER

    def update_biomes(self, positions, biome_type):
        for pos in positions:
            self.biome_map[pos] = biome_type
