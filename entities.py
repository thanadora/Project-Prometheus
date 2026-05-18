from dataclasses import dataclass, field

@dataclass
class Agent:
    id: int
    x: int
    y: int
    # Environnement interne
    energy: float = 50.0
    thirst: float = 50.0
    age: int = 0
    alive: bool = True
    generation: int = 0
    born_tick: int = 0
    # Perception / observation (remplis par think())
    perception: dict = field(default_factory=dict)
    observation: list = field(default_factory=list)   # vecteur normalisé → entrée IA
    # Décision (remplis par policy.decide(), consommés par world_phase)
    free_actions: list = field(default_factory=list)   # actions gratuites ce tick
    pending_action: int = 0                            # action principale ce tick
    vote_migrate: bool = False                         # posé par ACTION_VOTE_MIGRATE
    # Apprentissage
    last_reward: float = 0.0                           # récompense du tick précédent
    _prev_energy: float = 0.0                          # snapshot avant action (interne)
    _prev_thirst: float = 0.0
