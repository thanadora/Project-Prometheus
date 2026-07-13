"""
policy_registry.py — Registre de toutes les policies disponibles.
Pour ajouter une nouvelle IA : l'importer et l'ajouter à REGISTRY.
"""
from policy import HardcodedPolicy, RandomPolicy

REGISTRY = {
    "Hardcoded": {
        "class":       HardcodedPolicy,
        "description": "Règles de survie codées en dur (baseline)",
        "color":       "#00cfff",
    },
    "Random": {
        "class":       RandomPolicy,
        "description": "Actions aléatoires — baseline basse",
        "color":       "#ff9944",
    },
}


def make_policy(name):
    """Instancie une policy par son nom."""
    return REGISTRY[name]["class"]()


def policy_name(policy):
    """Retourne le nom d'une instance de policy, ou None si inconnue."""
    for name, entry in REGISTRY.items():
        if isinstance(policy, entry["class"]):
            return name
    return None


def distribute_policies(agents, distribution):
    """
    Assigne une policy à chaque agent selon une distribution.
    distribution : dict  {"Hardcoded": 0.7, "Random": 0.3}
    """
    import random
    names  = list(distribution.keys())
    weights = [distribution[n] for n in names]
    for agent in agents:
        chosen = random.choices(names, weights=weights, k=1)[0]
        agent.policy = make_policy(chosen)