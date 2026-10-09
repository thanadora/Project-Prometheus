from config_gui import run_config_gui
from world import initialize_world
from policy_registry import default_policy_name, make_policy
from gui import SimulationGUI
from logger import reset_logger

if __name__ == "__main__":
    if not run_config_gui():
        exit()   # l'utilisateur a fermé sans lancer
    
    reset_logger()
    world  = initialize_world()
    policy = make_policy(default_policy_name())
    SimulationGUI(world, policy)