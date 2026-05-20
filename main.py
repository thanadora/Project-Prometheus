from config_gui import run_config_gui
from world import initialize_world
from policy import HardcodedPolicy
from gui import SimulationGUI

if __name__ == "__main__":
    if not run_config_gui():
        exit()   # l'utilisateur a fermé sans lancer
    world  = initialize_world()
    policy = HardcodedPolicy()
    SimulationGUI(world, policy)