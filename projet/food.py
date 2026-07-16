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
    food_positions: set = field(default_factory=set)

    def initialize(self, biome_map, infinite=False, game_map=None, center=(0, 0), radius=30):
        """Mode classique : biome_map est déjà entièrement rempli, on y pioche
        les candidats. Mode infini : on ne connaît pas toute la carte, donc on
        génère (via `game_map.get_biome`) un disque autour du point de spawn
        pour y placer la nourriture initiale, sans jamais toucher au reste du
        monde (encore inexistant)."""
        self.food_map = {} if infinite else {
            (x, y): 0
            for x in range(self.width)
            for y in range(self.height)
        }
        self.food_positions = set()
        if infinite:
            self._spawn_initial_food_infinite(game_map, center, radius)
        else:
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
                self._add_food(pos)

    def _spawn_initial_food_infinite(self, game_map, center, radius):
        cx, cy = center
        candidates = []
        for x in range(cx - radius, cx + radius + 1):
            for y in range(cy - radius, cy + radius + 1):
                if game_map.get_biome(x, y) in FOOD_TYPES:
                    candidates.append((x, y))
        for _ in range(INITIAL_FOOD_COUNT):
            if not candidates:
                break
            pos      = random.choice(candidates)
            capacity = self._get_capacity(game_map.biome_map, pos)
            if self.food_map.get(pos, 0) < capacity:
                self._add_food(pos)

    def _get_capacity(self, biome_map, pos):
        biome = biome_map.get(pos)
        if biome not in FOOD_TYPES:
            return 0
        return FOOD_TYPES[biome]["capacity"]

    def grow_food(self, biome_map, soil_moisture=0.5, cells=None):
        """Fait pousser la nourriture. Par défaut (mode classique), parcourt
        toutes les cases connues de `biome_map`. Si `cells` est fourni (mode
        infini), on se restreint à cet ensemble — typiquement les cases
        proches d'un agent — pour ne pas avoir à parcourir un monde infini."""
        if cells is not None:
            land_cells = [pos for pos in cells if biome_map.get(pos) in FOOD_TYPES]
        else:
            land_cells = [pos for pos, biome in biome_map.items() if biome in FOOD_TYPES]
        for pos in land_cells:
            x, y  = pos
            biome = biome_map[pos]
            local_moisture = soil_moisture
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                if biome_map.get((x + dx, y + dy)) == BIOME_WATER:
                    local_moisture = min(1.0, soil_moisture + 0.3)
                    break
            food_type  = FOOD_TYPES[biome]
            capacity   = food_type["capacity"]
            current    = self.food_map.get(pos, 0)
            if current >= capacity:
                continue
            saturation = current / capacity if capacity > 0 else 0
            growth     = food_type["respawn"] * local_moisture * (1 - saturation) ** 2
            if random.random() < growth:
                self._add_food(pos)

    def consume_food(self, biome_map, pos):
        if self.food_map.get(pos, 0) <= 0:
            return 0
        biome = biome_map.get(pos)
        if biome not in FOOD_TYPES:
            return 0
        self._remove_food(pos)
        return FOOD_TYPES[biome]["gain"]

    def clear_position(self, pos):
        amount = self.food_map.get(pos, 0)
        if amount > 0:
            self._remove_food(pos, amount)

    def iter_food(self):
        for pos in self.food_positions:
            yield pos[0], pos[1], self.food_map[pos]
    
    def _add_food(self, pos, amount=1):
        """Ajoute `amount` nourriture en pos et maintient food_positions à jour."""
        self.food_map[pos] = self.food_map.get(pos, 0) + amount
        if self.food_map[pos] > 0:
            self.food_positions.add(pos)

    def _remove_food(self, pos, amount=1):
        """Retire `amount` nourriture en pos et maintient food_positions à jour."""
        current = self.food_map.get(pos, 0)
        self.food_map[pos] = max(0, current - amount)
        if self.food_map[pos] == 0:
            self.food_positions.discard(pos)
