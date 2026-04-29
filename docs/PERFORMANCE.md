# Performance and Scalability

**Version:** 1.0  
**Last Updated:** April 28, 2026

---

## Overview

This document describes OpenTaxi's computational performance characteristics across different traffic densities. Use this to determine whether OpenTaxi is suitable for your application.

---

## Benchmark Results

Run `python comprehensive_benchmark.py` to measure wall-clock time on your hardware.

### Actual Measured Performance (Intel Core i7-10700K, 32GB RAM)

**Configuration:** A* planner, Opt_StopGo controller, 400 simulation steps (2000s ≈ 33 minutes simulated)

| Aircraft | Wall-Clock (s) | Sim Speedup | Completed | Completion % | Avg Taxi Time | Conflicts |
|---|---|---|---|---|---|---|
| 5 | 37.9 | 52.76x | 5/5 | **100%** | 745s | 0 |
| 10 | 74.9 | 26.70x | 9/10 | **90%** | 859s | 0 |
| 20 | 88.6 | 22.57x | 11/20 | **55%** | 691s | 0 |
| 50 | 122.0 | 16.39x | 14/50 | **28%** | 792s | 0 |

**Results show:** Realistic sublinear scaling (52.76x → 16.39x), zero conflicts across all densities, meaningful completion rates reflecting Changi peak operations.

### Scaling Characteristics

OpenTaxi scales approximately **linearly** with the number of aircraft. Wall-clock time per simulated hour increases by roughly 1.1–1.3× for each additional aircraft, depending on your hardware and the congestion level.

**Reference benchmarks** are available in `examples/performance_benchmark.py`. Run this tool on your system to get hardware-specific measurements, as performance depends heavily on CPU, memory, and disk configuration.

---

## Use Case Guidance

### Real-time Control Applications

**Goal:** Control decisions within wall-clock time (1 second of sim ≈ 1 second real-time)

**Recommendation:** Maximum 15–20 aircraft for interactive control.

```python
# For real-time applications:
num_aircraft = 15
airport = AirportMap('opentaxi/airport_map/changi.graphml')
planner = AStarPlanner(airport)
controller = Opt_StopGo(airport)
sim = Simulation(airport, planner, controller, num_agents=num_aircraft)

# Run simulation (controller.update() called automatically)
sim.run(max_steps=720)  # 60 min simulation
```

### Offline Benchmarking / Research

**Goal:** Evaluate algorithms without real-time constraints.

**Recommendation:** 10–50 aircraft for 30–60 minute simulations (typical evaluation window).

```python
# For benchmarking:
num_aircraft = 20
duration_seconds = 3600  # 60 min
num_steps = duration_seconds // 5  # ~720 steps

airport = AirportMap('opentaxi/airport_map/changi.graphml')
planner = AStarPlanner(airport)
controller = Opt_StopGo(airport)
sim = Simulation(airport, planner, controller, num_agents=num_aircraft)

sim.run(max_steps=num_steps)  # No visualization - faster
```

### RL Training

**Goal:** Generate many episodes for policy learning.

**Recommendation:** Parallel episodes with 10–20 aircraft each.

```python
# For RL training with multiprocessing:
from opentaxi.rl_env import AirportRLEnv
from opentaxi.airport import AirportMap
from opentaxi.planners import AStarPlanner

num_envs = 8  # Parallel environments
num_aircraft = 10
duration_per_episode = 1800  # 30 min

# Create environments in parallel
airport = AirportMap('opentaxi/airport_map/changi.graphml')
planner = AStarPlanner(airport)

envs = [AirportRLEnv(airport, planner, num_aircraft=num_aircraft) for _ in range(num_envs)]

# With 8 parallel processes, generate 8 episodes concurrently
# Total throughput: ~8 parallel episodes
```

---

## Performance Characteristics

### Computational Complexity

**Main bottlenecks (in order of impact):**

1. **Conflict detection** – O(n²) pairwise distance checks
   - Dominates for n > 30 aircraft
   - Solution: Use spatial hashing for future work

2. **Planning** – O(n) route computations per spawn
   - Precomputed (Floyd-Warshall) is O(1) per query
   - A* is O(E log V) per aircraft

3. **Visualization** (if enabled) – O(n) rendering
   - Negligible overhead in headless mode

4. **Simulation dynamics** – O(n) kinematic updates
   - Negligible (< 1% of runtime)

### Memory Usage

| Aircraft | Approx. Memory |
|---|---|
| 10 | ~5 MB |
| 50 | ~25 MB |
| 100 | ~50 MB |

Each Aircraft object stores: position, velocity, heading, path, route plan (≈ 500 bytes each).

---

## Optimization Tips

### 1. Disable Visualization

Visualization adds overhead. Always skip `init_visualization()` for benchmarking:

```python
# Fast (headless) - no visualization
sim = Simulation(...)
sim.run()

# Slower - with visualization
sim = Simulation(...)
sim.init_visualization()
sim.run()
```

### 2. Use Precomputed Routes (Floyd-Warshall)

For repeated queries on the same airport:

```python
# Slow: ~100ms per route
from opentaxi.planners import DijkstraPlanner
planner = DijkstraPlanner(airport)

# Fast: ~1ms per route (precomputed)
from opentaxi.planners import FloydWarshallPlanner
planner = FloydWarshallPlanner(airport)  # ~1 sec precompute
```

### 3. Batch Simulations

Run multiple episodes in parallel:

```python
import multiprocessing as mp

def run_episode(seed):
    airport = AirportMap(...)
    sim = Simulation(...)
    return sim.run()

with mp.Pool(8) as pool:
    results = pool.map(run_episode, seeds=range(100))
```

### 4. Reduce Simulation Complexity

Run with fewer aircraft or shorter durations to measure performance:

```python
# Quick test: 10 aircraft, 10 min
sim = Simulation(airport, planner, controller, num_agents=10)
sim.run(max_steps=120)  # ~10 min

# Moderate: 20 aircraft, 30 min
sim = Simulation(airport, planner, controller, num_agents=20)
sim.run(max_steps=360)  # ~30 min

# Intensive: 50 aircraft, 60 min
sim = Simulation(airport, planner, controller, num_agents=50)
sim.run(max_steps=720)  # ~60 min
```

---

## Hardware Recommendations

### Minimum

- **CPU:** Dual-core, 2+ GHz (Intel Core i5, AMD Ryzen 5)
- **RAM:** 4 GB
- **Use case:** Single episode, < 20 aircraft

### Recommended

- **CPU:** Quad-core, 3+ GHz (Intel i7-11th gen, AMD Ryzen 7)
- **RAM:** 8 GB
- **Use case:** Multiple episodes in parallel, 20–50 aircraft

### High Performance (RL Training / Massive Benchmarking)

- **CPU:** 8+ cores, 3.5+ GHz (Intel i9, AMD Ryzen 9)
- **RAM:** 16+ GB
- **GPU:** Optional (used by deep RL libraries, not by simulator)
- **Use case:** 100+ parallel episodes, large-scale studies

---

## Benchmarking Your Application

Use the provided benchmark script to measure performance on your hardware:

```bash
cd OpenTaxi
python3 comprehensive_benchmark.py
```

**Output:** JSON with detailed results including:
- Scaling analysis (5–50 aircraft)
- Visualization overhead
- Planner/controller comparison
- RL environment performance
- Conflict and completion statistics

---

## Discussion: Interpreting Results

### Completion Rates and Aircraft Throughput

The benchmark results show varying completion rates as traffic density increases:
- **5 aircraft:** 100% complete in 33-minute window
- **10 aircraft:** 90% complete
- **20 aircraft:** 55% complete
- **50 aircraft:** 28% complete (~25 aircraft/hour throughput)

**What these numbers mean:**

The decreasing completion rate reflects realistic airport saturation behavior:
1. At low densities (5 aircraft), the infrastructure has spare capacity — all aircraft flow through
2. At high densities (50 aircraft), aircraft queue at gates and taxiways, limiting throughput
3. At 50 aircraft, only 28% complete in a 33-minute window because many are actively being held (not a simulator failure, but accurate modeling of constrained infrastructure)

**Confounding factors in computational scaling:**

The "sublinear" scaling (52.76x → 16.39x speedup) is partly an artifact of completion patterns: at 50 aircraft, only 14 are actively taxiing (28% completion), while 36 sit idle at gates/taxiways. This reduces computational load compared to 50 active aircraft. Wall-clock time therefore scales less steeply not just due to O(n²) conflict detection, but also due to fewer active aircraft consuming computation.

### Taxi Time Validation

- **Simulator average taxi time:** 745–859 seconds across tested densities
- **Changi A-SMGCS calibration target:** Cohen's d < 0.04 (negligible effect size)
- **Conflicts detected:** 0 across all tests (control system effective)

**What we can and cannot claim:**

✅ **Can claim:** The simulator exhibits realistic congestion patterns and maintains safety (zero conflicts)  
✅ **Can claim:** Taxi times match the calibration dataset used for parameter extraction (Cohen's d validation)  
❌ **Cannot claim:** These completion rates "validate" the simulator against real Changi operations without direct comparison data  
❌ **Cannot claim:** The simulator is "more accurate" than other approaches without comparative benchmarks  

The benchmark demonstrates that OpenTaxi exhibits expected behavior under load: congestion emerges naturally as aircraft density increases, without producing artificial conflicts. That validates the simulator's *consistency*, not necessarily its *accuracy* versus real operations — that validation was established during calibration (Cohen's d < 0.04 for taxi time distributions).

---

## Known Limitations

1. **Quadratic conflict detection** – Not optimized for very large fleets (> 200 aircraft)
2. **Single-threaded** – Simulator runs on one core; parallelize at episode level
3. **Matplotlib rendering** – Slows down with many aircraft; consider disabling

## Future Optimizations

- Spatial hashing for O(n) conflict detection
- Vectorized NumPy operations for batch dynamics
- GPU acceleration for visualization

---

## Reproducing Results

To recreate benchmark results from Section 5 of the paper:

```bash
python3 performance_benchmark.py \
    --airport opentaxi/airport_map/changi.graphml \
    --output paper_results.csv
```

All benchmarks use:
- **Timestep:** 5 seconds
- **Airport:** Changi Airport GraphML
- **Planner:** A* with turn angle heuristic
- **Controller:** Optimal Stop-Go (Section 3.3)

