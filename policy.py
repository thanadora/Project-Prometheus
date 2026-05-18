"""
policy.py — Politique de décision des agents.

C'est le SEUL fichier à remplacer pour brancher une vraie IA.
L'interface à respecter est celle de BasePolicy.decide().

L'environnement appelle :
    free_actions, timed_action = policy.decide(agent, world)

Entrées disponibles dans agent :
    agent.observation  → vecteur normalisé (voir OBS_* dans agent.py)
    agent.perception   → dict brut (distances, cases adjacentes, etc.)
    agent.energy, agent.thirst, agent.age, agent.generation, ...

Sorties attendues :
    free_actions  → list[int]  actions gratuites (peut être vide)
    timed_action  → int        une seule action principale
"""

import random
from agent import (
    ACTION_UP, ACTION_DOWN, ACTION_LEFT, ACTION_RIGHT,
    ACTION_IDLE, ACTION_DRINK, ACTION_VOTE_MIGRATE,
    OBS_ENERGY, OBS_THIRST, OBS_FOOD_DX, OBS_FOOD_DY,
    OBS_FOOD_DIST, OBS_WATER_DX, OBS_WATER_DY,
)
from config import (
    MAX_ENERGY, MAX_THIRST, MAX_AGE,
    THIRST_CRITICAL,
    MIGRATION_DISTRESS_ENERGY,
    MIGRATION_DISTRESS_THIRST,
    MIGRATION_AGE_THRESHOLD,
)


class BasePolicy:
    """Interface à implémenter pour toute politique (règles ou IA)."""

    def decide(self, agent, world):
        """
        Retourne (free_actions: list[int], timed_action: int).
        Ne doit pas modifier l'état du monde ni de l'agent.
        """
        raise NotImplementedError


class HardcodedPolicy(BasePolicy):
    """
    Politique de survie codée en dur.
    Sert de baseline et de référence comportementale pour l'IA.
    """

    def decide(self, agent, world):
        free_actions = self._decide_free(agent)
        timed_action = self._decide_timed(agent)
        return free_actions, timed_action

    # --------------------------------------------------
    def _decide_free(self, agent):
        free = []
        if (agent.energy < MIGRATION_DISTRESS_ENERGY or
                agent.thirst < MIGRATION_DISTRESS_THIRST or
                agent.age   >= MIGRATION_AGE_THRESHOLD):
            free.append(ACTION_VOTE_MIGRATE)
        return free

    def _decide_timed(self, agent):
        p = agent.perception

        thirst   = agent.thirst
        food_dx  = p["food_dx"]
        food_dy  = p["food_dy"]
        food_dist = p["food_dist"]
        water_dx = p["water_dx"]
        water_dy = p["water_dy"]

        # Priorité 1 : boire si soif critique et eau adjacente
        if thirst < THIRST_CRITICAL and p["adjacent_water"]:
            return ACTION_DRINK

        # Priorité 2 : se diriger vers l'eau si soif critique
        if thirst < THIRST_CRITICAL and p["water_dist"] != -1:
            if abs(water_dx) > abs(water_dy):
                return ACTION_RIGHT if water_dx > 0 else ACTION_LEFT
            return ACTION_DOWN if water_dy > 0 else ACTION_UP

        # Priorité 3 : se diriger vers la nourriture
        if food_dist == -1:
            return random.choice([
                ACTION_UP, ACTION_DOWN, ACTION_LEFT, ACTION_RIGHT, ACTION_IDLE
            ])
        if abs(food_dx) > abs(food_dy):
            return ACTION_RIGHT if food_dx > 0 else ACTION_LEFT
        return ACTION_DOWN if food_dy > 0 else ACTION_UP
