#!/usr/bin/env python3
"""Example: run a multi-aircraft simulation on Changi Airport.

Usage:
    python run_sim.py              # simulation mode (default)
    python run_sim.py --mode sim   # simulation mode
    python run_sim.py --agents 20  # 20 aircraft
"""

import argparse

from opentaxi.airport import AirportMap
from opentaxi.planners import AStarPlanner
from opentaxi.controller import Opt_StopGo
from opentaxi.evaluation import SchedulerEvaluator
from opentaxi.simulator import Simulation


def main():
    parser = argparse.ArgumentParser(
        description="OpenTaxi airport surface simulator")
    parser.add_argument(
        "--map", type=str,
        default="../opentaxi/airport_map/changi.graphml",
        help="Path to the airport GraphML map")
    parser.add_argument(
        "--agents", type=int, default=10,
        help="Number of aircraft")
    parser.add_argument(
        "--max-steps", type=int, default=10000,
        help="Maximum simulation steps")
    args = parser.parse_args()

    # Load map and build planner
    airport_map = AirportMap(args.map)
    planner = AStarPlanner(airport_map)

    # Conflict controller
    controller = Opt_StopGo(airport_map, predict_horizon=300.0)

    # Evaluator
    evaluator = SchedulerEvaluator()

    # Run simulation
    sim = Simulation(
        airport_map, planner, controller,
        num_agents=args.agents,
        evaluator=evaluator)
    sim.run(max_steps=args.max_steps)


if __name__ == "__main__":
    main()
