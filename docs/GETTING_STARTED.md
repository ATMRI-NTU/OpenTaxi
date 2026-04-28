# Getting Started with OpenTaxi

A step-by-step guide to install OpenTaxi and run your first simulation in **10 minutes**.

---

## 1. Installation

### Prerequisites
- Python 3.8+
- pip or conda package manager
- ~500 MB disk space

### Option A: From PyPI (Recommended)
```bash
pip install opentaxi
```

### Option B: From Source (Development)
```bash
git clone https://github.com/ATMRI-NTU/OpenTaxi.git
cd OpenTaxi
pip install -e .
```

### Verify Installation
```bash
python3 -c "import opentaxi; print(opentaxi.__version__)"
```

Expected output: `0.2.0` (or current version)

---

## 2. Your First Simulation (5 Minutes)

Create a file called `first_simulation.py`:

```python
from opentaxi.airport import AirportMap
from opentaxi.simulator import Simulation
from opentaxi.planners import AStarPlanner
from opentaxi.controller import Opt_StopGo

# Load Changi Airport map
airport = AirportMap("opentaxi/airport_map/changi.graphml")

# Create planner and controller
planner = AStarPlanner(airport)
controller = Opt_StopGo(airport)

# Create simulation with 10 aircraft
sim = Simulation(
    airport,
    planner,
    controller,
    num_agents=10
)

# Run simulation for 600 steps (10 minutes simulated time)
print("Running simulation...")
sim.run(max_steps=600)
print("Simulation complete! Window will close in 3 seconds...")
```

### Run it:
```bash
python3 first_simulation.py
```

Note: `sim.run()` returns `None`; results are printed to console and simulation window closes automatically.

---

## 3. Visualize the Simulation

To see aircraft moving on the airport surface, enable visualization:

```python
from opentaxi.airport import AirportMap
from opentaxi.simulator import Simulation
from opentaxi.planners import AStarPlanner
from opentaxi.controller import Opt_StopGo

airport = AirportMap("opentaxi/airport_map/changi.graphml")
planner = AStarPlanner(airport)
controller = Opt_StopGo(airport)

sim = Simulation(airport, planner, controller, num_agents=10)

# Initialize visualization (interactive display)
sim.init_visualization()

# Run with visualization
print("Running simulation with visualization...")
sim.run(max_steps=600)
```

### What You'll See
- **Green aircraft:** Active aircraft on taxiway
- **Red paths:** Planned routes
- **Yellow zones:** Conflict areas
- **Live metrics:** Top-right corner shows simulation stats

### Controls
- **Mouse drag:** Pan the display
- **Scroll:** Zoom in/out
- **Space:** Pause/resume
- **Q:** Quit

---

## 4. Run a Benchmark Scenario

OpenTaxi includes pre-built scenarios with different traffic densities:

```python
import json
from opentaxi.airport import AirportMap
from opentaxi.simulator import Simulation
from opentaxi.planners import AStarPlanner
from opentaxi.controller import Opt_StopGo

# Load a benchmark scenario
with open("examples/scenarios/benchmark_traffic_light.json") as f:
    scenario = json.load(f)

# Extract aircraft from scenario
num_aircraft = len(scenario['aircraft'])

# Create and run simulation
airport = AirportMap(scenario['simulation']['airport_map'])
planner = AStarPlanner(airport)
controller = Opt_StopGo(airport)

sim = Simulation(airport, planner, controller, num_agents=num_aircraft)
sim.run(max_steps=scenario['simulation']['max_steps'])
```

### Available Scenarios
- `benchmark_traffic_light.json` — 10 aircraft, 30 min (quick test)
- `benchmark_traffic_medium.json` — 20 aircraft, 60 min (typical)
- `benchmark_traffic_heavy.json` — 40 aircraft, 60 min (stress test)

All scenarios use **seed=42** for reproducibility.

## 5. Extract and Interpret Results

`sim.run()` prints results to the terminal and visualizes them in real-time. To capture results programmatically, use the `SchedulerEvaluator`:

```python
from opentaxi.evaluation import SchedulerEvaluator

# Create evaluator to track metrics
evaluator = SchedulerEvaluator(conflict_threshold=50.0)
sim = Simulation(airport, planner, controller, num_agents=10, evaluator=evaluator)

# Register aircraft for tracking
for ac_id in range(10):
    evaluator.register_aircraft(f"AC{ac_id}", path_length=2000)

# Run simulation
sim.run(max_steps=600)
evaluator.finalize(sim.aircrafts)

# Access results via get_metrics()
metrics = evaluator.get_metrics()
print(f"Total conflicts: {metrics['conflict_count']}")
print(f"Total arrived: {metrics['completed_aircraft']}")
print(f"Simulation time: {metrics['simulation_time']:.1f}s")

# Or use the formatted report
evaluator.print_report()
```

### Key Metrics You Can Extract

| Metric | How to Access | Good Value |
|---|---|---|
| **Taxi time** | `aircraft.taxi_time` | < 1500s |
| **Conflicts** | `aircraft.num_conflicts` | 0 (best) |
| **Path length** | `aircraft.path_s[-1]` if complete | Varies by airport |
| **Arrival time** | `aircraft.arrival_time` | Complete before max_steps |

---

## 6. Common Tasks

### A. Run Multiple Simulations with Different Planners

```python
from opentaxi.planners import AStarPlanner, DijkstraPlanner, GreedyPlanner

planners = {
    'A*': AStarPlanner(airport),
    'Dijkstra': DijkstraPlanner(airport),
    'Greedy': GreedyPlanner(airport),
}

for name, planner in planners.items():
    sim = Simulation(airport, planner, controller, num_agents=10)
    sim.run(max_steps=600)
    print(f"{name}: Simulation complete")
```

### B. Run Simulation Without Visualization (Faster)

```python
# Don't call sim.init_visualization()
# Runs significantly faster without rendering
sim = Simulation(airport, planner, controller, num_agents=20)
sim.run(max_steps=1000)  # Much faster than with visualization
```

### C. Access Aircraft State After Simulation

```python
sim = Simulation(airport, planner, controller, num_agents=10)
sim.run(max_steps=600)

# After run() completes, access aircraft objects
for ac_id, aircraft in sim.aircrafts.items():
    print(f"Aircraft {ac_id}: finished={aircraft.done}, "
          f"position=({aircraft.x:.1f}, {aircraft.y:.1f})")
```

### D. Custom Scenario Generation

```python
from opentaxi.synthetic_scenarios import SyntheticScenarioGenerator, ScenarioConfig

generator = SyntheticScenarioGenerator(seed=123)
config = ScenarioConfig(
    num_aircraft=25,
    scenario_duration_seconds=1800,
    traffic_density='medium',
    seed=123
)
scenario = generator.generate_scenario(config)

# Scenario is a dict - can be saved/loaded for reproducibility
import json
with open('my_scenario.json', 'w') as f:
    json.dump(scenario, f)
```

---

## 7. Troubleshooting

### Problem: "ModuleNotFoundError: No module named 'opentaxi'"
**Solution:** Reinstall from source
```bash
pip uninstall opentaxi
git clone https://github.com/ATMRI-NTU/OpenTaxi.git
cd OpenTaxi
pip install -e .
```

### Problem: "FileNotFoundError: changi.graphml"
**Solution:** Ensure you're in the OpenTaxi directory or specify full path
```python
airport = AirportMap("./opentaxi/airport_map/changi.graphml")
```

### Problem: "No display name and no $DISPLAY environment variable"
**Solution:** Use headless mode (no visualization)
```python
# Don't call sim.init_visualization()
sim.run(max_steps=600)  # Returns None; results printed to stdout
```

### Problem: Simulation runs very slowly
**Solution:** 
1. Reduce `max_steps` (or `num_agents`)
2. Don't use visualization (`init_visualization()`)
3. Use headless backend: `matplotlib.use('Agg')`

---

## 8. Next Steps

Once you're comfortable with the basics:

1. **Read the API documentation:** [docs/INTERFACES.md](INTERFACES.md)
2. **Understand scenario format:** [docs/SCENARIO_FORMAT.md](SCENARIO_FORMAT.md)
3. **Explore performance:** [docs/PERFORMANCE.md](PERFORMANCE.md)
4. **Integrate RL:** [docs/RL_INTERFACE.md](RL_INTERFACE.md)
5. **Understand visualization:** [docs/VISUALIZATION.md](VISUALIZATION.md)

---

## 9. Getting Help

### Documentation
- **Technical APIs:** [INTERFACES.md](INTERFACES.md)
- **Scenario Format:** [SCENARIO_FORMAT.md](SCENARIO_FORMAT.md)
- **Performance Tips:** [PERFORMANCE.md](PERFORMANCE.md)

### GitHub Issues
Report bugs or request features: https://github.com/ATMRI-NTU/OpenTaxi/issues

### Citation
If you use OpenTaxi in your research, please cite:
```bibtex
@article{Ali2026OpenTaxi,
  title={OpenTaxi: An Open-Source Modular Simulator for Airport Surface Operations},
  author={Ali, Hasnain and Yang, Haohan and Pham, Duc-Thinh and Alam, Sameer},
  journal={Journal of Open Aviation Science},
  year={2026}
}
```

---

## Expected Learning Curve

| Task | Time | Experience |
|---|---|---|
| Installation | 2 min | Beginner |
| First simulation | 3 min | Beginner |
| Visualization | 2 min | Beginner |
| Run benchmark scenario | 3 min | Beginner |
| Custom scenario | 10 min | Intermediate |
| Implement custom planner | 30 min | Advanced |
| RL training | 45 min | Advanced |

**Total for this guide: ~10 minutes to get your first simulation running.**

Happy simulating! 🚁✈️

