from world import initialize_world, world_phase
from gui import SimulationGUI

if __name__ == "__main__":
    world = initialize_world()
    SimulationGUI(world)