"""
policy.py — Politique de décision des agents.

C'est le SEUL fichier à remplacer pour brancher une vraie IA.

L'environnement appelle à chaque tick :
    free_actions, timed_action = policy.decide(agent, world)
    should_reproduce           = policy.decide_reproduce(agent, world)

Entrées disponibles dans agent :
    agent.observation  → vecteur normalisé (indices OBS_* dans agent.py)
    agent.perception   → dict brut (distances, cases adjacentes, etc.)
    agent.energy, agent.thirst, agent.age, agent.generation, ...

Sorties attendues :
    decide()           → (list[int], int)   free_actions + action principale
    decide_reproduce() → bool               True = l'agent se reproduit ce tick
"""

import random
import config
from agent import (
    ACTION_UP, ACTION_DOWN, ACTION_LEFT, ACTION_RIGHT,
    ACTION_IDLE, ACTION_DRINK, ACTION_VOTE_MIGRATE, ACTION_PICKUP, ACTION_EAT,
)
from config import (
    MAX_AGE,
    THIRST_CRITICAL,
    MIGRATION_DISTRESS_ENERGY,
    MIGRATION_DISTRESS_THIRST,
    MIGRATION_AGE_THRESHOLD,
    INVENTORY_SIZE,
)


class BasePolicy:
    def decide(self, agent, world):
        raise NotImplementedError

    def decide_reproduce(self, agent, world):
        raise NotImplementedError


class HardcodedPolicy(BasePolicy):

    def decide(self, agent, world):
        return self._free_actions(agent), self._timed_action(agent)

    def decide_reproduce(self, agent, world):
        if not config.ENABLE_REPRODUCTION:
            return False
        return agent.energy > 80 and agent.thirst > 40

    def _free_actions(self, agent):
        free = []
        if not config.ENABLE_MIGRATION:
            return free
        if (agent.energy < MIGRATION_DISTRESS_ENERGY
                or agent.thirst < MIGRATION_DISTRESS_THIRST
                or agent.age >= MIGRATION_AGE_THRESHOLD):
            free.append(ACTION_VOTE_MIGRATE)
        return free

    def _timed_action(self, agent):
        p         = agent.perception
        food_dx   = p["food_dx"]
        food_dy   = p["food_dy"]
        food_dist = p["food_dist"]
        water_dx  = p["water_dx"]
        water_dy  = p["water_dy"]

        # Soif
        if config.ENABLE_THIRST and config.ENABLE_BIOMES:
            if agent.thirst < THIRST_CRITICAL and p["adjacent_water"]:
                return ACTION_DRINK
            if agent.thirst < THIRST_CRITICAL and p["water_dist"] != -1:
                if abs(water_dx) > abs(water_dy):
                    return ACTION_RIGHT if water_dx > 0 else ACTION_LEFT
                return ACTION_DOWN if water_dy > 0 else ACTION_UP

        # Inventaire
        if config.ENABLE_INVENTORY:
            if agent.energy < 40 and agent.inventory:
                return ACTION_EAT
            if food_dist == 0 and len(agent.inventory) < INVENTORY_SIZE:
                return ACTION_PICKUP

        # Nourriture
        if food_dist == -1:
            return random.choice([ACTION_UP, ACTION_DOWN, ACTION_LEFT, ACTION_RIGHT, ACTION_IDLE])

        if abs(food_dx) > abs(food_dy):
            return ACTION_RIGHT if food_dx > 0 else ACTION_LEFT
        return ACTION_DOWN if food_dy > 0 else ACTION_UP
