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
    # Valeur de bruit brute (0..1) par case, conservée pour l'affichage
    # (ombrage / relief 2.5D). Purement cosmétique : la logique de jeu
    # continue de se baser uniquement sur biome_map.
    altitude_map: dict = field(default_factory=dict)
    infinite: bool = False
    _scale: float = 10.0
    _offset_x: float = 0.0
    _offset_y: float = 0.0

    def initialize(self, offset_x=None, offset_y=None):
        """Prépare le générateur de bruit.

        Mode classique : remplit `biome_map` en entier (comportement inchangé).
        Mode infini     : ne fait que fixer le bruit (offset) — les cases sont
                          calculées à la demande via `get_biome()`, pour ne
                          jamais avoir à générer une grille de taille infinie.
        """
        self._scale    = 10.0
        self._offset_x = offset_x if offset_x is not None else random.uniform(0, 1000)
        self._offset_y = offset_y if offset_y is not None else random.uniform(0, 1000)

        if self.infinite:
            return

        for y in range(self.height):
            for x in range(self.width):
                biome, fertility = self._compute_biome(x, y)
                self.biome_map[(x, y)]    = biome
                self.altitude_map[(x, y)] = fertility

    def _compute_biome(self, x, y):
        # Même champ de bruit pour le biome et pour l'altitude cosmétique :
        # une carte de relief indépendante, à trop grande échelle, peut par
        # malchance ne former qu'une seule zone géante sur toute la carte
        # (un "blob" illisible). Réutiliser le champ des biomes garantit que
        # le relief est toujours découpé en autant de zones que les biomes
        # eux-mêmes — un résultat déjà validé visuellement.
        n = noise.pnoise2(
            (x + self._offset_x) / self._scale,
            (y + self._offset_y) / self._scale,
            octaves=3,
            persistence=0.5,
            lacunarity=2.0,
        )
        fertility = (n + 1) / 2
        return _fertility_to_biome(fertility), fertility

    def get_biome(self, x, y):
        """Retourne le biome en (x, y), en le générant et le mettant en cache
        au besoin (mode infini). En mode classique, `biome_map` est déjà
        entièrement rempli donc ceci revient à un simple accès dict."""
        pos = (x, y)
        biome = self.biome_map.get(pos)
        if biome is None:
            biome, fertility = self._compute_biome(x, y)
            self.biome_map[pos]    = biome
            self.altitude_map[pos] = fertility
        return biome

    def get_altitude(self, x, y):
        """Retourne l'altitude (0..1) d'une case, en la générant au besoin
        (mode infini) — 0.5 (neutre) si la case a été transformée et n'a
        plus de relief naturel connu."""
        pos = (x, y)
        altitude = self.altitude_map.get(pos)
        if altitude is None:
            self.get_biome(x, y)
            altitude = self.altitude_map.get(pos, 0.5)
        return altitude

    def is_walkable(self, x, y):
        return self.get_biome(x, y) != BIOME_WATER

    def update_biomes(self, positions, biome_type, world=None):
        for pos in positions:
            self.biome_map[pos] = biome_type
            # Case transformée (migration, terraformation...) : on ne connaît
            # plus son relief naturel, on retombe sur une valeur neutre plutôt
            # que de garder une altitude périmée.
            self.altitude_map[pos] = 0.5
        if world is not None:
            world._land_cache_valid = False
