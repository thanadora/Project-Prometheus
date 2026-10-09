"""
benchmark.py — Mesure la vitesse de la boucle de simulation, sans GUI.

Sert à objectiver les optimisations (et plus tard, à entraîner/évaluer des
policies en masse sans ouvrir de fenêtre Tkinter).

Usage :
    python tools/benchmark.py                     # modes classique + infini
    python tools/benchmark.py --mode classic --agents 60 --width 60 --height 40 --ticks 2000
    python tools/benchmark.py --mode infinite --agents 30 --ticks 1000
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402  (après le sys.path)


def run(mode, agents, width, height, ticks):
    config.INFINITE_WORLD       = (mode == "infinite")
    config.WORLD_WIDTH          = width
    config.WORLD_HEIGHT         = height
    config.INITIAL_AGENT_COUNT  = agents
    config.ENABLE_MIGRATION     = False
    config.ENABLE_REPRODUCTION  = False

    # Imports ici : les modules lisent config au moment de la construction.
    from world import initialize_world, world_phase
    from policy_registry import default_policy_name, make_policy

    world  = initialize_world()
    policy = make_policy(default_policy_name())
    n0     = len(world.agents)

    start = time.perf_counter()
    done  = 0
    for _ in range(ticks):
        world_phase(world, policy)
        done += 1
        if not world.agents:
            break
    elapsed = time.perf_counter() - start

    cells = len(world.map.biome_map)
    print(f"[{mode:8s}] {done:5d} ticks | {agents:3d} agents | "
          f"{elapsed:6.2f}s | {done / elapsed:7.1f} ticks/s | "
          f"agents finaux: {len(world.agents):3d} | cases générées: {cells}")


def main():
    parser = argparse.ArgumentParser(description="Benchmark de la boucle de simulation")
    parser.add_argument("--mode", choices=["classic", "infinite", "both"], default="both")
    parser.add_argument("--agents", type=int, default=60)
    parser.add_argument("--width", type=int, default=60)
    parser.add_argument("--height", type=int, default=40)
    parser.add_argument("--ticks", type=int, default=2000)
    args = parser.parse_args()

    if args.mode in ("classic", "both"):
        run("classic", args.agents, args.width, args.height, args.ticks)
    if args.mode in ("infinite", "both"):
        run("infinite", args.agents, args.width, args.height, args.ticks)


if __name__ == "__main__":
    main()
