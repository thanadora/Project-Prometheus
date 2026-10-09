import random
from dataclasses import dataclass, field
import config


def freshness_for_age(age):
    """Fraîcheur (1.0 → FOOD_MIN_FRESHNESS) d'une nourriture selon son âge.

    Reste à 1.0 tant que l'âge ne dépasse pas FOOD_FRESH_TICKS, puis décroît
    linéairement sur FOOD_ROT_TICKS ticks ; ne descend jamais sous
    FOOD_MIN_FRESHNESS (c'est update_rot() qui décide de la faire disparaître
    une fois à ce stade)."""
    fresh_ticks = config.FOOD_FRESH_TICKS
    if age <= fresh_ticks:
        return 1.0
    rot_ticks = max(1, config.FOOD_ROT_TICKS)
    t = (age - fresh_ticks) / rot_ticks
    return max(config.FOOD_MIN_FRESHNESS, 1.0 - (1.0 - config.FOOD_MIN_FRESHNESS) * t)


@dataclass
class FoodSystem:
    width: int
    height: int
    food_map: dict = field(default_factory=dict)
    food_positions: set = field(default_factory=set)
    # Âge (en ticks) de la nourriture par case. Une case vide n'a pas d'entrée.
    food_age: dict = field(default_factory=dict)

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
        self.food_age = {}
        if infinite:
            self._spawn_initial_food_infinite(game_map, center, radius)
        else:
            self._spawn_initial_food(biome_map)

    def _spawn_initial_food(self, biome_map):
        candidates = [
            pos for pos, biome in biome_map.items()
            if biome in config.FOOD_TYPES
        ]
        for _ in range(config.INITIAL_FOOD_COUNT):
            if not candidates:
                break
            pos      = random.choice(candidates)
            capacity = self._get_capacity(biome_map, pos)
            if self.food_map[pos] < capacity:
                self._add_food(pos, allow_spoilage=False)

    def _spawn_initial_food_infinite(self, game_map, center, radius):
        cx, cy = center
        candidates = []
        for x in range(cx - radius, cx + radius + 1):
            for y in range(cy - radius, cy + radius + 1):
                if game_map.get_biome(x, y) in config.FOOD_TYPES:
                    candidates.append((x, y))
        for _ in range(config.INITIAL_FOOD_COUNT):
            if not candidates:
                break
            pos      = random.choice(candidates)
            capacity = self._get_capacity(game_map.biome_map, pos)
            if self.food_map.get(pos, 0) < capacity:
                self._add_food(pos, allow_spoilage=False)

    def _get_capacity(self, biome_map, pos):
        biome = biome_map.get(pos)
        food_type = config.FOOD_TYPES.get(biome)
        if food_type is None:
            return 0
        return food_type["capacity"]

    def grow_food(self, biome_map, soil_moisture=0.5, cells=None):
        """Fait pousser la nourriture. Par défaut (mode classique), parcourt
        toutes les cases connues de `biome_map`. Si `cells` est fourni (mode
        infini), on se restreint à cet ensemble — typiquement les cases
        proches d'un agent — pour ne pas avoir à parcourir un monde infini.

        N'est appelée que tous les FOOD_GROWTH_INTERVAL ticks (voir
        world_phase) : les probabilités sont multipliées d'autant pour garder
        la même espérance tout en divisant le coût par le même facteur."""
        food_types = config.FOOD_TYPES
        bm_get     = biome_map.get
        if cells is not None:
            land_cells = [pos for pos in cells if bm_get(pos) in food_types]
        else:
            land_cells = [pos for pos, biome in biome_map.items() if biome in food_types]
        interval   = max(1, config.FOOD_GROWTH_INTERVAL)
        needs_water_scan = soil_moisture < 1.0
        for pos in land_cells:
            x, y  = pos
            biome = biome_map[pos]
            if needs_water_scan:
                local_moisture = soil_moisture
                for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    if biome_map.get((x + dx, y + dy)) == config.BIOME_WATER:
                        local_moisture = min(1.0, soil_moisture + 0.3)
                        break
            else:
                local_moisture = 1.0
            food_type  = food_types[biome]
            capacity   = food_type["capacity"]
            current    = self.food_map.get(pos, 0)
            if current >= capacity:
                continue
            saturation = current / capacity if capacity > 0 else 0
            growth     = min(1.0, food_type["respawn"] * local_moisture
                             * (1 - saturation) ** 2 * interval)
            if random.random() < growth:
                self._add_food(pos)

    def update_rot(self):
        """Vieillit la nourriture au sol d'un tick et retire celle qui a
        complètement pourri (probabilité par tick une fois la fraîcheur
        minimale atteinte). Sans effet si ENABLE_FOOD_ROT est désactivé."""
        if not config.ENABLE_FOOD_ROT:
            return
        disappearing = []
        spoiled_age  = config.FOOD_FRESH_TICKS + config.FOOD_ROT_TICKS
        for pos in self.food_positions:
            age = self.food_age.get(pos, 0) + 1
            self.food_age[pos] = age
            if (age >= spoiled_age
                    and random.random() < config.FOOD_ROT_DISAPPEAR_CHANCE):
                disappearing.append(pos)
        for pos in disappearing:
            self.clear_position(pos)

    def freshness_at(self, pos):
        """Fraîcheur actuelle de la nourriture en `pos` (1.0 si pas de
        pourriture ou case vide — l'appelant vérifie la quantité lui-même)."""
        if not config.ENABLE_FOOD_ROT:
            return 1.0
        return freshness_for_age(self.food_age.get(pos, 0))

    def consume_food(self, biome_map, pos):
        if self.food_map.get(pos, 0) <= 0:
            return 0
        biome = biome_map.get(pos)
        if biome not in config.FOOD_TYPES:
            # Nourriture orpheline : le biome a changé sous elle (inondation,
            # expansion d'eau, incendie...). On la retire au lieu de la laisser
            # fantôme dans food_map — sinon elle réapparaîtrait si le biome
            # d'origine revient.
            self.clear_position(pos)
            return 0
        self._remove_food(pos)
        return config.FOOD_TYPES[biome]["gain"]

    def clear_position(self, pos):
        amount = self.food_map.get(pos, 0)
        if amount > 0:
            self._remove_food(pos, amount)

    def iter_food(self):
        for pos in self.food_positions:
            yield pos[0], pos[1], self.food_map[pos]

    def _add_food(self, pos, amount=1, allow_spoilage=True):
        """Ajoute `amount` nourriture en pos et maintient food_positions à jour.

        Une nouvelle pousse (case vide) repart fraîche (âge 0) — sauf petite
        chance qu'elle naisse déjà pourrie (FOOD_SPOIL_ON_GROWTH_CHANCE), ce
        qui garde la pourriture visible même quand les tas sont mangés avant
        d'avoir le temps de vieillir. L'âge est conservé quand la case contient
        déjà de la nourriture (la plus ancienne unité part la première).
        Les semis initiaux passent allow_spoilage=False : pas de monde qui
        démarre couvert de pourriture."""
        if pos not in self.food_positions:
            if (allow_spoilage and config.ENABLE_FOOD_ROT
                    and random.random() < config.FOOD_SPOIL_ON_GROWTH_CHANCE):
                self.food_age[pos] = config.FOOD_FRESH_TICKS + config.FOOD_ROT_TICKS
            else:
                self.food_age[pos] = 0
        self.food_map[pos] = self.food_map.get(pos, 0) + amount
        if self.food_map[pos] > 0:
            self.food_positions.add(pos)

    def _remove_food(self, pos, amount=1):
        """Retire `amount` nourriture en pos et maintient food_positions à jour."""
        current = self.food_map.get(pos, 0)
        self.food_map[pos] = max(0, current - amount)
        if self.food_map[pos] == 0:
            self.food_positions.discard(pos)
            self.food_age.pop(pos, None)
