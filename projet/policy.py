"""
policy.py — Politique de décision des agents.

C'est le SEUL fichier à remplacer pour brancher une vraie IA.

L'environnement appelle à chaque tick :
    free_actions, timed_action = policy.decide(agent, world)
    should_reproduce           = policy.decide_reproduce(agent, world)

Entrées disponibles dans agent :
    agent.observation  → vecteur normalisé (indices OBS_* dans actions.py)
    agent.perception   → dict brut (distances, cases adjacentes, etc.)
    agent.energy, agent.thirst, agent.age, agent.generation, agent.fatigue, ...

Sorties attendues :
    decide()           → (list[int], int)   free_actions + action principale
    decide_reproduce() → bool               True = l'agent se reproduit ce tick
"""

import random
import config
from actions import (
    ACTION_UP, ACTION_DOWN, ACTION_LEFT, ACTION_RIGHT,
    ACTION_IDLE, ACTION_DRINK, ACTION_VOTE_MIGRATE,
    ACTION_PICKUP, ACTION_EAT, ACTION_SLEEP, action_speak,
)


class BasePolicy:
    def decide(self, agent, world):
        raise NotImplementedError

    def decide_reproduce(self, agent, world):
        raise NotImplementedError


class HardcodedPolicy(BasePolicy):

    def decide(self, agent, world):
        return self._free_actions(agent), self._timed_action(agent, world)

    def decide_reproduce(self, agent, world):
        if not config.ENABLE_REPRODUCTION:
            return False
        return agent.energy > 80 and agent.thirst > 40

    def _free_actions(self, agent):
        if not config.ENABLE_MIGRATION:
            return []
        if (agent.energy < config.MIGRATION_DISTRESS_ENERGY
                or agent.thirst < config.MIGRATION_DISTRESS_THIRST
                or agent.age >= config.MIGRATION_AGE_THRESHOLD):
            return [ACTION_VOTE_MIGRATE]
        return []

    def _timed_action(self, agent, world=None):
        p         = agent.perception
        food_dx   = p["food_dx"]
        food_dy   = p["food_dy"]
        food_dist = p["food_dist"]
        water_dx  = p["water_dx"]
        water_dy  = p["water_dy"]

        # Soif critique → aller boire
        if config.ENABLE_THIRST and config.ENABLE_BIOMES:
            if agent.thirst < config.THIRST_CRITICAL and p["adjacent_water"]:
                return ACTION_DRINK
            if agent.thirst < config.THIRST_CRITICAL and p["water_dist"] != -1:
                if abs(water_dx) > abs(water_dy):
                    return ACTION_RIGHT if water_dx > 0 else ACTION_LEFT
                return ACTION_DOWN if water_dy > 0 else ACTION_UP

        # Inventaire
        if config.ENABLE_INVENTORY:
            if agent.energy < 40 and agent.inventory:
                return ACTION_EAT
            if food_dist == 0 and len(agent.inventory) < config.INVENTORY_SIZE:
                return ACTION_PICKUP

        # Sommeil : dormir quand la fatigue est haute — naturellement la nuit,
        # ou en urgence si l'épuisement devient critique de jour. Après boire
        # et manger : on ne dort pas en mourant de soif ou de faim.
        if config.ENABLE_FATIGUE:
            is_night = world.is_night() if world is not None else False
            want_sleep = (
                agent.fatigue >= config.MAX_FATIGUE * 0.85
                or (is_night and agent.fatigue >= config.SLEEP_FATIGUE_THRESHOLD)
            )
            if want_sleep:
                return ACTION_SLEEP

        # Nourriture
        if food_dist == -1:
            return random.choice([ACTION_UP, ACTION_DOWN, ACTION_LEFT, ACTION_RIGHT, ACTION_IDLE])

        if abs(food_dx) > abs(food_dy):
            return ACTION_RIGHT if food_dx > 0 else ACTION_LEFT
        return ACTION_DOWN if food_dy > 0 else ACTION_UP


class RandomPolicy(BasePolicy):
    """Actions aléatoires — sert de baseline basse.

    NOTE : parle aussi une lettre au hasard de temps en temps si la communication
    est activée — c'est juste pour visualiser/tester le mécanisme (aucune logique,
    pure baseline aléatoire, comme le reste de cette policy). À retirer si tu veux
    une baseline totalement silencieuse.
    """

    def decide(self, agent, world):
        choices = [ACTION_UP, ACTION_DOWN, ACTION_LEFT, ACTION_RIGHT, ACTION_IDLE]
        if config.ENABLE_FATIGUE:
            choices.append(ACTION_SLEEP)
        action = random.choice(choices)
        free_actions = []
        if config.ENABLE_COMMUNICATION and config.ALPHABET and random.random() < 0.3:
            free_actions.append(action_speak(random.randrange(len(config.ALPHABET))))
        return free_actions, action

    def decide_reproduce(self, agent, world):
        return random.random() < 0.01
