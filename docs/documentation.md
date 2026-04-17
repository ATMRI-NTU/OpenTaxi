# OpenTaxi Documentation

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [Airport Map — `airport.py`](#3-airport-map)
4. [Aircraft Model — `aircraft.py`](#4-aircraft-model)
5. [Path Planners — `planners.py`](#5-path-planners)
6. [Conflict Controllers — `controller.py`](#6-conflict-controllers)
7. [Simulation Engine — `simulator.py`](#7-simulation-engine)
8. [Evaluation — `evaluation.py`](#8-evaluation)
9. [RL Environment — `rl_env.py`](#9-rl-environment)
10. [Utilities — `tools.py`](#10-utilities)
11. [Map Format Specification](#11-map-format-specification)
12. [Extending OpenTaxi](#12-extending-opentaxi)

---

## 1. Overview

OpenTaxi is a modular simulator for airport surface (taxiway) operations. It models the full pipeline from map loading, path planning, multi-aircraft conflict resolution, kinematic simulation, to performance evaluation.

The typical simulation flow is:

```
GraphML map file
      │
      ▼
  AirportMap          ← parses graph, builds UTM geometry
      │
      ├──► Planner    ← computes gate-to-runway paths
      │
      ├──► Aircraft[] ← each holds a path and kinematic state
      │
      ├──► Controller ← detects conflicts, issues yield commands
      │
      └──► Simulation ← step loop: controller → aircraft.step → visualise
               │
               ▼
          Evaluator   ← records conflicts, taxi times, throughput
```

All coordinates are in **UTM metres** (default EPSG:32648 for Changi Airport). The time step is **5 seconds** by default.

---

## 2. Architecture

OpenTaxi follows a modular design where each component has a single responsibility and communicates through well-defined interfaces.

### Module dependency graph

```
tools.py            ← pure geometry, no dependencies on other modules
    │
airport.py          ← uses tools for coordinate transforms
    │
planners.py         ← uses airport.py for graph queries
    │
aircraft.py         ← uses tools + airport + planner for path init
    │
controller.py       ← uses airport.py for edge queries
    │
simulator.py        ← orchestrates aircraft + controller + evaluator
    │
evaluation.py       ← reads aircraft state, computes metrics
    │
rl_env.py           ← wraps simulator as a Gymnasium environment
```

### Design principles

- **Separation of concerns.** The planner knows nothing about conflict resolution; the controller knows nothing about path planning. They are composed at the `Simulation` level.
- **Plug-and-play components.** All four planners share the same `plan_shortest_path(start, end) → (path, nodes)` interface. Both controllers share the same `update(aircrafts)` interface. Swapping components requires changing one line of setup code.
- **Arc-length parameterisation.** Aircraft positions are tracked as a scalar `curr_s` along a densified polyline path, which simplifies distance calculations, conflict prediction, and velocity control.

---

## 3. Airport Map

**Module:** `opentaxi/airport.py`  
**Class:** `AirportMap`

### What it does

Loads a GraphML file describing the airport taxiway network, converts all coordinates from WGS84 (lon/lat) to UTM metres, densifies edge geometries to 0.1 m resolution, and classifies nodes into special categories (runway, parking).

### Constructor

```python
AirportMap(graphml_path, utm_epsg="EPSG:32648")
```

- `graphml_path` — path to the `.graphml` file.
- `utm_epsg` — EPSG code for the UTM projection zone. Default is zone 48N (Singapore).

### Key attributes

| Attribute | Type | Description |
|---|---|---|
| `G` | `nx.DiGraph` | The full airport graph |
| `point_dict` | `dict[int, tuple]` | `{node_id: (x, y)}` in UTM metres |
| `way_dict` | `dict[str, list]` | Column-oriented edge store with keys: `id`, `oneway`, `aeroway`, `path`, `start_idx`, `end_idx`, `length`, `width`, `name`, `reversed` |
| `way_idxs` | `dict[tuple, list]` | `{(start, end): [edge_indices]}` lookup |
| `edge_headings` | `dict[tuple, tuple]` | `{(start, end): (start_heading, end_heading)}` in radians |
| `node_runway` | `set[int]` | Interior runway nodes (should not be traversed through) |
| `node_parking` | `set[int]` | Parking dead-end nodes (should not be entered as intermediate) |

### Key methods

| Method | Returns | Description |
|---|---|---|
| `get_point(node_idx)` | `(x, y)` | UTM position of a node |
| `get_neighbors(node_idx)` | `list[str]` | Adjacent node IDs in the graph |
| `get_edge_length(from_idx, to_idx)` | `float` | Edge length in metres |
| `get_edge_heading(from_idx, to_idx)` | `(float, float)` | Start and end headings in radians |
| `get_valid_parking_startpoints()` | `list[int]` | Valid gate nodes that can serve as start points |
| `get_valid_runway_endpoints()` | `list[int]` | Valid runway nodes that can serve as destinations |
| `get_excluded_nodes()` | `(set, set)` | `(runway_nodes, parking_nodes)` for planners |
| `get_bounds()` | `(x_min, x_max, y_min, y_max)` | Map bounding box |

### Node classification logic

The map classifies nodes automatically:

- **Runway nodes** — start nodes (`u`) of edges with `aeroway="runway"`. Planners should not route *through* these unless they are the designated start or end.
- **Parking nodes** — end nodes (`v`) of edges with `aeroway="parking_position"`. These are dead-end gates; planners should not enter them as intermediates.
- **Valid start points** — parking nodes that also appear as start nodes of non-parking edges (i.e., they connect to the taxiway network).
- **Valid end points** — runway nodes that also appear as end nodes of taxiway edges (i.e., reachable from the taxiway network).

---

## 4. Aircraft Model

**Module:** `opentaxi/aircraft.py`  
**Class:** `Aircraft`

### What it does

Each `Aircraft` instance represents one vehicle on the airport surface. It holds a planned path (as a dense polyline), tracks its kinematic state (position, velocity, heading, arc-length), and responds to yield commands from the controller.

### Constructor

```python
Aircraft(ac_id, airport_map, planner, seed=None,
         replay_mode=False, used_starts=None)
```

In simulation mode, the constructor automatically calls `init_path()` to find a random valid route. In replay mode, it starts with a dummy path and expects external position updates via `set_state_from_data()`.

### Kinematic state

| Attribute | Unit | Description |
|---|---|---|
| `x`, `y` | metres | Current UTM position |
| `yaw` | radians | Heading (0 = north, clockwise) |
| `curr_v` | km/h | Current velocity |
| `targ_v` | km/h | Target velocity |
| `curr_s` | metres | Arc-length position along path |
| `max_acc` | m/s² | Maximum acceleration (default 0.2) |
| `max_dec` | m/s² | Maximum deceleration (default 0.5) |

### Yield / conflict state

| Attribute | Description |
|---|---|
| `yield_flag` | `True` if the aircraft should slow down or stop |
| `wait_at_s` | Arc-length position to wait at (set by controller) |
| `wait_at_node` | Graph node to wait at |
| `conflict_with` | ID of the conflicting aircraft |
| `immediate_stop` | `True` for emergency stop |

### Completion state

| Attribute | Description |
|---|---|
| `arrived` | `True` when within `min_dist` of the destination |
| `arrival_time` | Timestep when arrival occurred |
| `departure_wait` | Hold time at destination before removal (default 90 s) |
| `done` | `True` after arrival + departure wait |

### Key methods

| Method | Description |
|---|---|
| `init_path(seed, used_starts=None)` | Find a random valid path from parking to runway |
| `init_path_with_endpoints(start, end)` | Set a specific path |
| `step(dura=5)` | Advance one time step: update velocity, arc-length, position, heading |
| `check_arrival(...)` | Check if destination reached; manage departure wait |
| `motion_update(dura)` | Kinematic model: returns `(distance, velocity)` |
| `update_target_velocity()` | Determine target speed based on yield state |
| `get_state()` | Return a dict snapshot of all state variables |

### Motion model

The motion model is a simple kinematic controller:

1. `update_target_velocity()` determines the desired speed based on yield commands and distance to the wait point.
2. If `|curr_v - targ_v| < 5 km/h`, maintain constant speed.
3. Otherwise, apply `max_acc` or `max_dec` over the time step.
4. The new arc-length `curr_s` is looked up in the path polyline to get the new `(x, y)`.

---

## 5. Path Planners

**Module:** `opentaxi/planners.py`

All planners share the same interface:

```python
planner.plan_shortest_path(start_idx, end_idx)
# Returns: (path, path_nodes) or (None, None)
#   path       — Nx2 numpy array of (x, y) waypoints
#   path_nodes — list of graph node IDs
```

### Planner comparison

| Planner | Algorithm | Precomputation | Optimality | Use case |
|---|---|---|---|---|
| `FloydWarshallPlanner` | Floyd-Warshall | O(V³) upfront | Optimal | Many queries on same map |
| `DijkstraPlanner` | Dijkstra | None | Optimal | Single queries |
| `GreedyPlanner` | Best-first (heuristic only) | None | Not optimal | Fast approximate |
| `AStarPlanner` | A* | None | Optimal | Default choice |

### A\* planner extras

`AStarPlanner` also provides:

- **`plan_minimum_turn_path(start, end)`** — A\* with a heading-change penalty (`turn_penalty_weight = 200` metres-equivalent per π radians of turn). Prefers straighter routes.
- **`compute_path_geometry(path)`** — returns `(arc_length, heading, curvature)` arrays.
- **`plan_velocity_profile(s, curvature)`** — curvature-limited velocity: `v = min(v_max, sqrt(a_lat / |κ|))`.
- **`compute_path_stats(path, nodes)`** — returns `{length, num_turns, total_turn_angle}`.
- **`detect_head_on_conflicts(trajectories)`** — checks for opposing edge usage.

### Node constraints

All planners enforce two constraints:

1. **Runway constraint:** Cannot depart from a runway-interior node (unless it is the designated start).
2. **Parking constraint:** Cannot enter a parking dead-end (unless it is the designated goal, or traversing within a parking chain).

The `FloydWarshallPlanner` additionally handles parking chains by BFS-traversing connected parking nodes to find the first reachable taxiway node.

---

## 6. Conflict Controllers

**Module:** `opentaxi/controller.py`

Both controllers share the same interface:

```python
controller.update(aircrafts)
# aircrafts: dict[int, Aircraft]
# Side effect: sets yield_flag, wait_at_s, etc. on each aircraft
```

### `StopGo` — FCFS prediction controller

**Algorithm:**
1. For each active aircraft, predict the reachable path segment over the next `predict_horizon` seconds using `[min_pred_v, max_pred_v]`.
2. For each pair of aircraft, check if predicted segments come within `collision_buffer` metres.
3. If conflict detected, the aircraft **farther** from the conflict point yields (FCFS: first to arrive has priority).
4. The yielding aircraft is told to stop at the **next graph node** ahead of its current position.

**Parameters:**

| Parameter | Default | Description |
|---|---|---|
| `predict_horizon` | 20.0 s | Look-ahead time |
| `collision_buffer` | 50.0 m | Minimum separation |

### `Opt_StopGo` — separation-maximising controller

**Algorithm:**
1. Calculate priority for each moving aircraft: closer to destination = higher priority.
2. Process aircraft in priority order. An aircraft can move if:
   - The concurrent movement limit (`max_concurrent`) is not exceeded.
   - It is farther than `min_separation` from all higher-priority aircraft (both moving and arrived/waiting).
   - Its predicted future path does not come within `min_separation` of any higher-priority moving aircraft.
3. Aircraft that cannot move get `immediate_stop = True`.
4. Aircraft that can move but have a nearby higher-priority aircraft ahead get a `wait_at_s` point.

**Parameters:**

| Parameter | Default | Description |
|---|---|---|
| `predict_horizon` | 20.0 s | Look-ahead time |
| `min_separation` | 150.0 m | Minimum separation |
| `max_concurrent` | 5 | Maximum aircraft moving at once |

---

## 7. Simulation Engine

**Module:** `opentaxi/simulator.py`  
**Class:** `Simulation`

### What it does

Orchestrates the step loop: runs the controller, advances each aircraft, checks arrivals, updates the evaluator, and redraws the visualisation.

### Constructor

```python
Simulation(airport_map, planner, controller, num_agents=3,
           replay_mode=False, hist_data=None, evaluator=None)
```

### Two modes

**Simulation mode** (default): Creates `num_agents` aircraft with random start/end points. Each step:
1. `controller.update(aircrafts)` — detect and resolve conflicts
2. `aircraft.step()` — advance kinematics (for non-arrived aircraft)
3. `aircraft.check_arrival()` — check if destination reached
4. `evaluator.update()` — record metrics

**Replay mode** (`replay_mode=True`): Reads from `hist_data` (a list of per-timestep observation arrays). Each row is `[aircraft_id, timestamp, lat, lon, alt]`. Aircraft are created lazily as they appear. Aircraft missing for 3 consecutive frames are marked done.

### Key methods

| Method | Description |
|---|---|
| `run(max_steps=10000)` | Full loop: init visualisation → step until done → close |
| `step()` | One simulation time step |
| `step_replay()` | One replay time step; returns `False` when data exhausted |
| `init_visualization()` | Set up matplotlib figure |
| `update_visualization()` | Redraw all aircraft |
| `check_all_done()` | `True` when all aircraft are done |
| `save_frame(output_dir, fmt)` | Save current frame as SVG/PNG/PDF |

### Visualisation layers

| Layer | Z-order | Content |
|---|---|---|
| Static map | 5 | Runways (black), taxiways (grey), parking (dark grey) |
| Planned paths | 6 | Green lines (simulation mode only) |
| Historical trails | 7 | Thick green lines |
| Start/end markers | 11 | Circle (start) and triangle (end) |
| Aircraft icons | 12 | Rotated SVG icons or coloured squares |
| ID labels | 13 | Aircraft ID text above each icon |

### Risk colouring

Aircraft icons change colour based on `risk_level` (set externally):

| Level | Colour | Meaning |
|---|---|---|
| 0 | light green | Safe |
| 1 | red | Warning |
| 2 | purple | Danger |
| 3 | black | Critical |

---

## 8. Evaluation

**Module:** `opentaxi/evaluation.py`

### `PlannerEvaluator` — path quality

Analyses individual planned paths. Key metrics:

| Metric | Description |
|---|---|
| `path_length` | Total path length in metres |
| `num_turns` | Number of turns exceeding the threshold (default 15°) |
| `total_turn_angle` | Sum of all turn angles in degrees |
| `avg_turn_angle` | Average turn angle |
| `max_turn_angle` | Largest single turn |
| `num_edges` | Number of graph edges traversed |
| `edge_occupancy_rate` | Fraction of total map edge length used |
| `path_smoothness` | Standard deviation of heading changes (lower = smoother) |

**Batch evaluation:**

```python
evaluator = PlannerEvaluator(airport_map, planner)
results = evaluator.evaluate_all_gates_to_runway(runway_node_idx=377)
evaluator.print_summary(results)
evaluator.save_to_csv(results)
```

### `SchedulerEvaluator` — simulation performance

Tracks runtime metrics during simulation. Register it at construction time:

```python
evaluator = SchedulerEvaluator(conflict_threshold=50.0)
sim = Simulation(..., evaluator=evaluator)
sim.run()
```

Key metrics:

| Metric | Description |
|---|---|
| `conflict_count` | Number of unique conflict pairs (distance < threshold) |
| `conflict_history` | Timestamped list of all conflicts |
| `completed_aircraft` | Number of aircraft that reached their destination |
| `avg_taxi_time` | Average taxi time in seconds |
| `throughput_per_hour` | Completion rate |

Conflicts within `start_ignore_distance` (default 100 m) of both aircraft's start positions are excluded (to ignore initial proximity at adjacent gates).

**Output formats:** `print_report()`, `export_to_csv(path)`, `export_to_json(path)`.

---

## 9. RL Environment

**Module:** `opentaxi/rl_env.py`

### `AirportRLEnv` — Gymnasium environment

A plug-and-play wrapper that replaces the rule-based controller with RL decisions. It does **not** modify any core simulation code.

```python
from opentaxi.rl_env import AirportRLEnv

env = AirportRLEnv(airport_map, planner,
                   num_aircraft=10, max_aircraft=50,
                   min_separation=50.0, max_steps=2000)
obs, info = env.reset()
action = env.action_space.sample()
obs, reward, terminated, truncated, info = env.step(action)
```

**Observation space:** `Box(0, 1, shape=(max_aircraft * 6,))`. Aircraft are **sorted by remaining path length** (shortest first) at each step. Per-aircraft features:

| Index | Feature | Normalisation |
|---|---|---|
| 0 | Remaining distance | / 2000 m |
| 1 | Spatial distance to predecessor | / 50 m, capped at 1 |
| 2 | Velocity | / 30 km/h |
| 3 | is_arrived | 0 or 1 |
| 4 | is_waiting | 0 or 1 |
| 5 | is_done | 0 or 1 |

The first aircraft in sorted order has no predecessor, so its predecessor distance is always 1.

**Action space:** `MultiBinary(max_aircraft)`. `action[i] = 1` means go, `0` means stop. A hard safety constraint forces stop when within `hard_stop_distance` (20 m) of the predecessor regardless of the action.

**Reward:** `r = r_progress + r_conflict`

- `r_progress` = average normalised distance travelled per moving aircraft.
- `r_conflict` = `−2 × (1 − dist/50)` for each aircraft within 50 m of its predecessor. Linear penalty: −2 at 0 m, 0 at 50 m.

**Termination:** all aircraft arrived. **Truncation:** `max_steps` reached.

### `RLController` — deploy a trained agent

Drop-in replacement for `StopGo` / `Opt_StopGo`:

```python
from stable_baselines3 import PPO
from opentaxi.rl_env import RLController

agent = PPO.load("path/to/model")
controller = RLController(airport_map, agent=agent)
sim = Simulation(airport_map, planner, controller, num_agents=10)
sim.run()
```

If `agent=None`, all aircraft are allowed to move freely (no control).

---

## 10. Utilities

**Module:** `opentaxi/tools.py`

Pure geometric functions with no dependency on other OpenTaxi modules.

| Function | Description |
|---|---|
| `wrap_angle(theta)` | Normalise angle to [−π, π] |
| `polyline_length(line)` | Cumulative arc-length array for a polyline |
| `dense_polyline2d(line, resolution)` | Densify a polyline by linear interpolation |
| `cartesian_to_frenet(x, y, line)` | Convert (x, y) to Frenet frame (s, d) |
| `find_waypoint_in_curve(s, path_s, path)` | Look up (x, y) at arc-length s |
| `parse_linestring(wkt)` | Parse WKT `LINESTRING (...)` to coordinate list |
| `lonlat_to_utm(transformer, points)` | Batch lon/lat → UTM conversion |
| `lonlat_to_webmercator(transformer, points)` | Batch lon/lat → Web Mercator conversion |
| `pointtilt(x, y, line)` | Tangent angle at closest point on polyline |
| `pointcurvature(x, y)` | Curvature from three points |
| `linecurvature(line)` | Curvature array along a polyline |

---

## 11. Map Format Specification

OpenTaxi reads airport maps in **GraphML** format. The included `changi.graphml` covers Singapore Changi Airport's taxiway network.

### Node attributes

| Attribute | Type | Description |
|---|---|---|
| `x` | float | Longitude (WGS84) |
| `y` | float | Latitude (WGS84) |

### Edge attributes

| Attribute | Type | Values | Description |
|---|---|---|---|
| `aeroway` | string | `taxiway`, `runway`, `parking_position` | Edge type |
| `oneway` | string | `True` / `False` | Directional constraint |
| `geometry` | string | WKT LINESTRING | Edge geometry in lon/lat |
| `length` | float | | Edge length in metres |
| `width` | float | | Edge width in metres |
| `ref` / `name` | string | | Taxiway identifier (e.g., `A1`, `T5`) |

### Adding a new airport

1. Prepare a GraphML file with the attributes above. You can export from OpenStreetMap or construct programmatically.
2. Set the correct `utm_epsg` for your airport's UTM zone:
   ```python
   airport_map = AirportMap("my_airport.graphml", utm_epsg="EPSG:32633")
   ```
3. The `TAXIWAY_NAME_FIXES` dict in `AirportMap` is Changi-specific; override or clear it for other airports.

---

## 12. Extending OpenTaxi

### Custom planner

Implement a class with:

```python
class MyPlanner:
    def __init__(self, airport_map):
        self.map = airport_map

    def plan_shortest_path(self, start_idx, end_idx):
        """Returns (path, path_nodes) or (None, None)."""
        # path: Nx2 numpy array of (x, y)
        # path_nodes: list of graph node ID strings
        ...
```

### Custom controller

Implement a class with:

```python
class MyController:
    def __init__(self, airport_map, **kwargs):
        self.airport_map = airport_map

    def update(self, aircrafts, timestep=None):
        """Set yield_flag, wait_at_s, immediate_stop on each aircraft."""
        for ac_id, ac in aircrafts.items():
            if ac.done:
                continue
            # Your logic here
            ac.yield_flag = False
            ac.immediate_stop = False
```

### Custom evaluator

The evaluator interface requires:

```python
class MyEvaluator:
    def register_aircraft(self, ac_id, path_length):
        ...
    def update(self, aircrafts, timestep):
        ...
    def finalize(self, aircrafts):
        ...
    def print_report(self):
        ...
```
