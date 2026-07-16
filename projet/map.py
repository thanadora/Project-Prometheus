import math
import random
import noise
import config
from dataclasses import dataclass, field
from config import (
    BIOME_WATER,
    BIOME_DESERT,
    BIOME_PRAIRIE,
    BIOME_FOREST,
    BIOME_MOUNTAIN_ROCK,
    BIOME_MOUNTAIN_SNOW,
    WATER_THRESHOLD,
    PRAIRIE_THRESHOLD,
    FOREST_THRESHOLD,
    ALTITUDE_NOISE_SCALE,
    ALTITUDE_CONTRAST,
    ALTITUDE_BANDS,
    MOUNTAIN_ROCK_THRESHOLD,
    MOUNTAIN_SNOW_THRESHOLD,
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


def stretch_altitude(altitude):
    """Étire l'écart à la moyenne (0.5) pour compenser le fait que le bruit
    de Perlin reste naturellement proche de 0.5 — sans ça, les différences
    de relief sont quasi invisibles à l'écran. Utilisé uniquement pour
    l'affichage (ombrage/paliers) — la décision "montagne ou pas" se base
    sur l'altitude brute, voir MOUNTAIN_ROCK_THRESHOLD/MOUNTAIN_SNOW_THRESHOLD."""
    dev  = altitude - 0.5
    span = math.tanh(0.5 * ALTITUDE_CONTRAST)
    stretched_dev = math.tanh(dev * ALTITUDE_CONTRAST) / span * 0.5
    return 0.5 + stretched_dev


def altitude_band(altitude):
    """Quantifie l'altitude en un palier discret (0..ALTITUDE_BANDS-1), pour
    l'ombrage/les lignes de niveau — façon carte topographique."""
    stretched = stretch_altitude(altitude)
    band = int(stretched * ALTITUDE_BANDS)
    return min(ALTITUDE_BANDS - 1, band)


@dataclass
class GameMap:
    width: int
    height: int
    biome_map: dict = field(default_factory=dict)
    # Valeur de bruit brute (0..1) par case, conservée pour l'affichage
    # (ombrage / relief 2.5D) et pour décider des cases de montagne.
    # Purement cosmétique côté logique de jeu : is_walkable() n'en tient pas
    # compte, seule la valeur de biome_map (déjà tranchée) compte.
    altitude_map: dict = field(default_factory=dict)
    infinite: bool = False
    _scale: float = 10.0
    _offset_x: float = 0.0
    _offset_y: float = 0.0
    # Bruit d'altitude : complètement séparé de celui des biomes (voir
    # _compute_altitude). Une chaîne de montagnes peut ainsi traverser une
    # forêt, une prairie ou un désert — sans ce découplage, l'altitude la
    # plus haute coïncidait presque toujours avec le désert (même bruit,
    # mêmes valeurs hautes), d'où des "déserts en montagne".
    _alt_offset_x: float = 0.0
    _alt_offset_y: float = 0.0

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
        # Décalage fixe (et grand) par rapport au bruit de fertilité : le champ
        # de Perlin n'étant pas répétitif à cette distance, ça suffit à obtenir
        # un relief décorrélé des biomes sans avoir à sauvegarder d'offset en plus.
        self._alt_offset_x = self._offset_x + 5000.0
        self._alt_offset_y = self._offset_y + 5000.0

        if self.infinite:
            return

        for y in range(self.height):
            for x in range(self.width):
                self._generate_cell(x, y)

    def _generate_cell(self, x, y):
        """Calcule et mémorise le biome (+ l'altitude si le module est actif)
        d'une case. Centralisé ici pour que le mode classique (initialize)
        et le mode infini (get_biome à la demande) appliquent exactement la
        même règle de superposition montagne."""
        pos = (x, y)
        fertility = self._compute_fertility(x, y)
        base_biome = _fertility_to_biome(fertility)
        if config.ENABLE_ALTITUDE:
            altitude = self._compute_altitude(x, y)
            self.altitude_map[pos] = altitude
            biome = self._apply_mountain(base_biome, altitude)
        else:
            biome = base_biome
        self.biome_map[pos] = biome
        return biome

    def _compute_fertility(self, x, y):
        n = noise.pnoise2(
            (x + self._offset_x) / self._scale,
            (y + self._offset_y) / self._scale,
            octaves=3,
            persistence=0.5,
            lacunarity=2.0,
        )
        return (n + 1) / 2

    def _compute_altitude(self, x, y):
        n = noise.pnoise2(
            (x + self._alt_offset_x) / ALTITUDE_NOISE_SCALE,
            (y + self._alt_offset_y) / ALTITUDE_NOISE_SCALE,
            octaves=3,
            persistence=0.5,
            lacunarity=2.0,
        )
        return (n + 1) / 2

    @staticmethod
    def _apply_mountain(base_biome, altitude):
        """L'eau reste toujours prioritaire (un lac reste un lac même en
        altitude) ; sinon, au-delà d'un certain seuil de relief, le biome
        climatique (désert/prairie/forêt) laisse place à de la montagne —
        rocheuse, puis enneigée plus haut encore."""
        if base_biome == BIOME_WATER:
            return base_biome
        if altitude >= MOUNTAIN_SNOW_THRESHOLD:
            return BIOME_MOUNTAIN_SNOW
        if altitude >= MOUNTAIN_ROCK_THRESHOLD:
            return BIOME_MOUNTAIN_ROCK
        return base_biome

    def get_biome(self, x, y):
        """Retourne le biome en (x, y), en le générant et le mettant en cache
        au besoin (mode infini). En mode classique, `biome_map` est déjà
        entièrement rempli donc ceci revient à un simple accès dict."""
        pos = (x, y)
        biome = self.biome_map.get(pos)
        if biome is None:
            biome = self._generate_cell(x, y)
        return biome

    def get_altitude(self, x, y):
        """Retourne l'altitude (0..1) d'une case, en la générant au besoin
        (mode infini) — 0.5 (neutre) si la case a été transformée et n'a
        plus de relief naturel connu.

        Si le module Altitude est désactivé, retourne toujours 0.5 (case
        parfaitement plate, donc jamais de montagne) sans même regarder le
        bruit généré : c'est la seule source de vérité pour l'altitude, donc
        rien en aval (ombrage, lignes de niveau, relief 2.5D, montagnes...)
        ne peut faire réapparaître du relief tant que ce module est coché
        OFF, quel que soit l'état des autres réglages d'affichage."""
        if not config.ENABLE_ALTITUDE:
            return 0.5
        pos = (x, y)
        altitude = self.altitude_map.get(pos)
        if altitude is None:
            # Assure la cohérence : la même case doit avoir le même biome
            # et la même altitude, qu'on l'ait d'abord regardée via get_biome
            # ou via get_altitude.
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
