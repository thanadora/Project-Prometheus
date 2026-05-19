from world import initialize_world
from policy import HardcodedPolicy
from gui import SimulationGUI

if __name__ == "__main__":
    world  = initialize_world()
    policy = HardcodedPolicy()
    SimulationGUI(world, policy)
