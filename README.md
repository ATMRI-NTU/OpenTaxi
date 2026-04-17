# OpenTaxi – Open-Source Airport Surface Movement Simulator

OpenTaxi is an open-source simulator for airport surface (taxiway) operations. It models multi-aircraft movement from parking positions to runway thresholds on a realistic airport graph network, with conflict detection and resolution.

OpenTaxi is meant as a research tool for studying airport surface traffic management, path planning algorithms, and reinforcement learning–based control. It is distributed under the **MIT License** and can be freely used, modified, and cited without restrictions.

> **Note:** This release includes the airport map (Changi Airport taxiway network) but does **not** include surveillance data. The simulator can run in full simulation mode with synthetic traffic.

## Features

- **Graph-based airport map** – taxiway network parsed from GraphML with UTM coordinate projection
- **Multiple path planners** – Dijkstra, Greedy Best-First, A\*, Floyd-Warshall (precomputed), and A\* with turn penalty
- **Conflict detection & resolution** – prediction-based FCFS controller and separation-maximising controller
- **Kinematic aircraft model** – acceleration/deceleration limits, arc-length tracking, heading computation
- **Real-time visualisation** – matplotlib-based 2D rendering with aircraft icons and trajectory trails
- **Evaluation framework** – path quality metrics (length, turns, smoothness) and simulation performance metrics (conflicts, taxi time, throughput)
- **RL environment** – Gymnasium-compatible environment for training RL-based taxi controllers
- **Replay mode** – replay historical surveillance data (data not included)

## Project Structure

```
OpenTaxi/
├── opentaxi/                  # Core package
│   ├── __init__.py
│   ├── airport.py             # Airport map loader (GraphML → graph)
│   ├── aircraft.py            # Aircraft state & kinematics
│   ├── planners.py            # Path planning algorithms
│   ├── controller.py          # Conflict detection & resolution
│   ├── simulator.py           # Simulation engine & visualisation
│   ├── evaluation.py          # Evaluation metrics
│   ├── rl_env.py              # Gymnasium RL environment
│   ├── tools.py               # Geometric utilities
│   └── airport_map/           # Map data
│       ├── changi.graphml     # Changi Airport taxiway network
│       └── ac_logo.svg        # Aircraft icon
├── examples/
│   ├── run_sim.py             # Run simulation example
│   └── train_rl.py            # RL training example
├── setup.py
├── requirements.txt
├── LICENSE
└── README.md
```

## Installation

### From source

```bash
git clone https://github.com/your-org/OpenTaxi.git
cd OpenTaxi
pip install -e .
```

### With optional dependencies

```bash
# Visualisation support (aircraft icons)
pip install -e ".[vis]"

# RL training support
pip install -e ".[rl]"

# Everything
pip install -e ".[full]"
```

## Quick Start

### Run a simulation

```bash
cd OpenTaxi
python examples/run_sim.py --agents 10
```

### Use as a library

```python
from opentaxi.airport import AirportMap
from opentaxi.planners import AStarPlanner
from opentaxi.controller import Opt_StopGo
from opentaxi.simulator import Simulation

# Load map
airport_map = AirportMap("opentaxi/airport_map/changi.graphml")

# Set up planner and controller
planner = AStarPlanner(airport_map)
controller = Opt_StopGo(airport_map, predict_horizon=300.0)

# Run simulation with 10 aircraft
sim = Simulation(airport_map, planner, controller, num_agents=10)
sim.run()
```

### Train an RL controller

```bash
pip install stable-baselines3 gymnasium
python examples/train_rl.py train --map_path opentaxi/airport_map/changi.graphml
```

## Dependencies

| Package | Purpose |
|---|---|
| numpy | Numerical computation |
| networkx | Graph data structure |
| pyproj | Coordinate projection |
| matplotlib | Visualisation |
| cairosvg *(optional)* | SVG icon rendering |
| Pillow *(optional)* | Image processing |
| gymnasium *(optional)* | RL environment interface |
| stable-baselines3 *(optional)* | RL training algorithms |

## Architecture

OpenTaxi follows a modular architecture inspired by [BlueSky](https://github.com/TUDelft-CNS-ATM/bluesky):

- **AirportMap** parses the GraphML taxiway network into a directed graph with UTM-projected node positions and edge geometries.
- **Planners** operate on the graph to find paths from parking gates to runway thresholds, respecting constraints (no traversal through runway interiors, no entering parking dead-ends as intermediates).
- **Aircraft** instances track kinematic state (position, velocity, heading) along their planned paths using arc-length parameterisation.
- **Controllers** detect pairwise conflicts between aircraft and issue yield/stop commands to maintain separation.
- **Simulation** orchestrates the step loop, calling the controller, stepping each aircraft, and updating the visualisation.

## Citation

If you use OpenTaxi in your research, please cite:

```bibtex
@software{opentaxi2025,
  title  = {OpenTaxi: Open-Source Airport Surface Movement Simulator},
  year   = {2025},
  url    = {https://github.com/your-org/OpenTaxi}
}
```

## License

MIT License. See [LICENSE](LICENSE) for details.

## Acknowledgements

- Airport map data derived from OpenStreetMap.
- Project structure inspired by [BlueSky ATC Simulator](https://github.com/TUDelft-CNS-ATM/bluesky) (Hoekstra & Ellerbroek, ICRAT 2016).
