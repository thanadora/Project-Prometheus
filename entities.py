from dataclasses import dataclass, field

@dataclass
class Agent:
    id: int
    x: int
    y: int
    state_vector: list = field(default_factory=list)
    perception: dict = field(default_factory=dict)
    energy: float = 50.0
    age: int = 0
    alive: bool = True
    generation: int = 0
    born_tick: int = 0
    pending_action: int = 0