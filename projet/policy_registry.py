"""
policy_registry.py — Registre de toutes les policies disponibles.

Pour AJOUTER une IA :
    1. Implémenter une sous-classe de BasePolicy (dans policy.py ou un nouveau
       module — l'important est que decide() et decide_reproduce() répondent).
    2. L'ajouter à REGISTRY ci-dessous (class, description, color).
Le reste du projet (écran de config, graphes, couleurs des agents, sauvegarde)
lit REGISTRY dynamiquement : aucune autre modification n'est nécessaire.

Pour ENLEVER une IA : supprimer son entrée. Les sauvegardes qui la référencent
restent chargeables — les agents concernés retombent sur la policy par défaut
(voir default_policy_name()), avec un avertissement dans les logs.
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


def default_policy_name():
    """Nom de la policy de repli : « Hardcoded » si présente, sinon la
    première du registre. Utilisée quand une policy a été retirée du registre
    (sauvegardes anciennes) ou qu'aucune distribution valide n'est fournie."""
    if "Hardcoded" in REGISTRY:
        return "Hardcoded"
    return next(iter(REGISTRY))


def make_policy(name):
    """Instancie une policy par son nom.

    Une instance par agent (chaque policy peut ainsi garder son propre état).
    Modèle lourd : partager les poids entre instances (singleton de module,
    cache de classe...) plutôt que de les charger dans __init__, sinon une
    copie des poids est créée pour chaque agent.
    """
    if name not in REGISTRY:
        raise KeyError(
            f"Policy inconnue : {name!r} — disponibles : {', '.join(REGISTRY)}"
        )
    return REGISTRY[name]["class"]()


def policy_name(policy):
    """Retourne le nom d'une instance de policy, ou None si inconnue."""
    if policy is None:
        return None
    # Type exact d'abord : si une policy hérite d'une autre policy enregistrée,
    # on veut son propre nom, pas celui de sa classe parente.
    for name, entry in REGISTRY.items():
        if type(policy) is entry["class"]:
            return name
    for name, entry in REGISTRY.items():
        if isinstance(policy, entry["class"]):
            return name
    return None


def distribute_policies(agents, distribution):
    """
    Assigne une policy à chaque agent selon une distribution.
    distribution : dict  {"Hardcoded": 0.7, "Random": 0.3}

    Les entrées inconnues (policy retirée, config obsolète) sont ignorées ;
    s'il ne reste rien de valide, tout le monde reçoit la policy par défaut.
    """
    import random
    names = [n for n, weight in distribution.items() if n in REGISTRY and weight > 0]
    if not names:
        names = [default_policy_name()]
    weights = [distribution.get(n, 1.0) for n in names]
    for agent in agents:
        chosen = random.choices(names, weights=weights, k=1)[0]
        agent.policy = make_policy(chosen)
