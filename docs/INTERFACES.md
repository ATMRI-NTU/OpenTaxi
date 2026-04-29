# OpenTaxi Interface Specifications

**Version:** 1.1 — CORRECTED  
**Last Updated:** April 28, 2026  
**Note:** This document specifies the *actual* interfaces in OpenTaxi. See `documentation.md` for detailed implementation notes.

---

## Overview

OpenTaxi is built on well-defined interfaces that separate concerns and enable swapping components:
- **Planner interface**: Route planning algorithms
- **Controller interface**: Conflict detection and resolution  
- **AirportMap interface**: Airport topology and geographic utilities
- **RL Environment interface**: Gymnasium compatibility

This document specifies these interfaces to enable researchers to implement custom algorithms.

---

## Core Interfaces

### Planner Interface

**Purpose:** Route planning from departure gate to arrival runway.

**Actual Method Signature (Python):**

```python
class Planner:
    """Base class for routing algorithms.
    
    A Planner computes collision-free taxi routes given the airport
    graph and a start/end node pair.
    """
    
    def __init__(self, airport: 'AirportMap'):
        """Initialize planner with airport topology.
        
        Args:
            airport: AirportMap instance with graph and node coordinates.
        """
        pass
    
    def plan_shortest_path(self, start_idx, end_idx):
        """Compute taxi route from start to end node.
        
        Args:
            start_idx: Node index or string ID of starting gate/parking area.
            end_idx: Node index or string ID of destination runway.
        
        Returns:
            Tuple: (path, path_nodes)
                - path: numpy array of shape (N, 2) with UTM coordinates [x, y]
                - path_nodes: List of node IDs from start to end (inclusive)
                
        Returns (None, None) if no valid path exists.
        """
        pass
```

**Contract:**
- Routes must be collision-free (no illegal turns or shortcuts)
- Routes must exist in the airport graph
- Shorter routes are preferable
- Method name is `plan_shortest_path`, NOT `plan`

**Built-in Implementations:**

| Class | Algorithm | Complexity | Best For |
|---|---|---|---|
| `FloydWarshallPlanner` | Precomputed all-pairs | O(1) query, O(V³) precompute | Repeated queries (production) |
| `AStarPlanner` | A* with heuristic | O((V+E)log V) | Balanced speed/quality |
| `DijkstraPlanner` | Dijkstra's shortest path | O((V+E)log V) | Optimal path finding |
| `GreedyPlanner` | Greedy best-first search | O(V+E) | Fast approximation |

**Example Usage:**

```python
from opentaxi.airport import AirportMap
from opentaxi.planners import AStarPlanner

airport = AirportMap('opentaxi/airport_map/changi.graphml')
planner = AStarPlanner(airport)

# Get route from gate to runway (returns path coordinates and node IDs)
path, path_nodes = planner.plan_shortest_path(start_idx='GATE_01', end_idx='RWY_EAST')
print(f"Route nodes: {' -> '.join(path_nodes)}")
print(f"Path coordinates shape: {path.shape}")  # (N, 2) numpy array
```

---

### Controller Interface

**Purpose:** Detect conflicts and make stop/go decisions for aircraft.

**Actual Method Signature:**

```python
class Controller:
    """Base class for conflict resolution strategies.
    
    A Controller monitors aircraft positions and decides which aircraft
    should stop/go to avoid collisions while maximizing throughput.
    """
    
    def __init__(self, airport: 'AirportMap', min_separation: float = 50.0):
        """Initialize controller.
        
        Args:
            airport: AirportMap instance.
            min_separation: Minimum safe separation in meters.
        """
        pass
    
    def update(self, aircrafts):
        """Run one control cycle and set stop/go flags on aircraft.
        
        Args:
            aircrafts: Dict mapping aircraft_id -> Aircraft object.
                      Each Aircraft has state: x, y, curr_s, path_s, path, done, etc.
        
        Returns:
            None (modifies aircraft objects in-place)
            
        Side effects:
            - Sets aircraft.yield_flag: bool (True = stop, False = go)
            - Sets aircraft.wait_at_node: str or None (which node to wait at)
            - Sets aircraft.wait_at_s: float or None (arc-length position to wait at)
            - Sets aircraft.conflict_with: str or None (conflicting aircraft ID)
        """
        pass
```

**Contract:**
- Method is called `update`, NOT `compute_actions`
- Method returns None, NOT a dictionary
- All decisions are communicated via aircraft object mutations
- Controller must resolve conflicts by setting yield_flag appropriately

**Built-in Implementations:**

| Class | Strategy | Safety | Throughput |
|---|---|---|---|
| `StopGo` | First-Come-First-Served (FCFS) | High | Moderate |
| `Opt_StopGo` | Maximize separation while allowing motion | High | High |

**Example Usage:**

```python
from opentaxi.controller import Opt_StopGo
from opentaxi.simulator import Simulation

controller = Opt_StopGo(airport)
sim = Simulation(airport, planner, controller, num_agents=10)

# During simulation, controller.update() is called each step:
for step in range(100):
    controller.update(sim.aircrafts)  # Modifies sim.aircrafts in place
    
    # Check aircraft flags (set by controller)
    for ac_id, aircraft in sim.aircrafts.items():
        if aircraft.yield_flag:
            print(f"AC {ac_id} waiting at node {aircraft.wait_at_node}")
```

---

### AirportMap Interface

**Purpose:** Parse airport topology and provide geographic utilities.

**Public Method Signature:**

```python
class AirportMap:
    """Airport topology and geographic utilities.
    
    Loads airport from GraphML format, provides geographic transformation,
    and graph traversal utilities.
    """
    
    def __init__(self, graphml_path: str, utm_epsg: str = "EPSG:32648"):
        """Load airport from GraphML file.
        
        Args:
            graphml_path: Path to .graphml file with airport topology.
            utm_epsg: EPSG code for UTM zone (default: Singapore zone 48N).
        
        Attributes:
            G: NetworkX DiGraph with UTM coordinates for each node.
            way_dict: Dict with airport geometry ("aeroway", "path" lists).
        """
        pass
    
    def get_neighbors(self, node: str) -> List[str]:
        """Get adjacent nodes reachable from this node.
        
        Args:
            node: Node ID (string).
        
        Returns:
            List of node IDs reachable via outgoing edges.
        """
        pass
    
    def get_edge_length(self, node1: str, node2: str) -> float:
        """Euclidean distance along edge in meters.
        
        Args:
            node1, node2: Node IDs.
        
        Returns:
            Distance in meters.
        """
        pass
    
    def get_node_position(self, node: str) -> Tuple[float, float]:
        """Get UTM coordinates of node.
        
        Args:
            node: Node ID (string).
        
        Returns:
            (utm_east, utm_north) in meters.
        """
        pass
    
    def get_bounds(self) -> Tuple[float, float, float, float]:
        """Get bounding box of airport.
        
        Returns:
            (x_min, x_max, y_min, y_max) in UTM meters.
        """
        pass
    
    def get_excluded_nodes(self) -> Tuple[Set, Set]:
        """Get nodes that aircraft cannot depart from or arrive at.
        
        Returns:
            (runway_nodes, parking_nodes) - sets of node IDs to exclude
            from certain path calculations.
        """
        pass
```

**Graph Format (GraphML):**

Each node in the airport graph includes:
- **id**: Unique node identifier (string)
- **x, y**: WGS84 coordinates (lon, lat)
- **type**: Node classification (gate, runway, taxiway_node, parking, etc.)

The coordinates are automatically converted to UTM during loading.

---

### RL Environment Interface (Gymnasium)

**Purpose:** Standardized RL training environment for airport control problems.

**Actual Class Signature:**

```python
import gymnasium as gym
from gymnasium import spaces
import numpy as np

class AirportRLEnv(gym.Env):
    """Gymnasium environment for airport surface operations RL.
    
    Trains agents to optimize aircraft flow using reinforcement learning.
    Action space: Binary control (stop/go) per aircraft.
    Observation space: Aircraft state vectors (normalized).
    Reward: Progress toward destination minus conflict penalties.
    """
    
    def __init__(
        self,
        airport_map,
        planner,
        num_aircraft: int = 10,
        max_aircraft: int = 50,
        min_separation: float = 50.0,
        hard_stop_distance: float = 20.0,
        max_steps: int = 2000,
        render: bool = False
    ):
        """Initialize RL environment.
        
        Args:
            airport_map: AirportMap instance.
            planner: Planner instance (for route planning).
            num_aircraft: Number of concurrent aircraft in simulation.
            max_aircraft: Maximum possible aircraft (for fixed obs space).
            min_separation: Minimum safe separation in meters.
            hard_stop_distance: Force stop if closer than this (meters).
            max_steps: Maximum steps per episode.
            render: Enable visualization.
        """
        super().__init__()
        self.airport_map = airport_map
        self.planner = planner
        self.num_aircraft = num_aircraft
        self.max_aircraft = max_aircraft
        
        # Observation space: 6 features per aircraft slot
        self.obs_dim = 6
        self.observation_space = spaces.Box(
            low=0.0,
            high=1.0,
            shape=(max_aircraft * self.obs_dim,),
            dtype=np.float32
        )
        
        # Action space: Binary per aircraft (stop=0, go=1)
        self.action_space = spaces.MultiBinary(max_aircraft)
    
    def reset(self, seed=None, options=None):
        """Reset environment to initial state.
        
        Returns:
            observation: Observation vector (normalized, shape (max_aircraft*6,))
            info: Auxiliary info dictionary
        """
        pass
    
    def step(self, action: np.ndarray):
        """Execute one simulation step.
        
        Args:
            action: Array of binary decisions (0=stop, 1=go) per aircraft.
        
        Returns:
            observation: Updated observation (normalized).
            reward: Scalar reward (float).
            terminated: True if episode finished (all aircraft landed).
            truncated: True if max steps reached.
            info: Auxiliary info (episode statistics, etc.).
        """
        pass
```

**Observation Space Details:**

Per-aircraft features (6 values), normalized to [0, 1]:

| Index | Feature | Formula |
|---|---|---|
| 0 | `remaining_distance_norm` | (path_length - curr_s) / 2000 |
| 1 | `dist_to_predecessor_norm` | min(dist_to_prev_ac / 50, 1.0) |
| 2 | `velocity_norm` | velocity / 30 km/h |
| 3 | `is_arrived` | 1.0 if reached destination, else 0.0 |
| 4 | `is_waiting` | 1.0 if holding at node, else 0.0 |
| 5 | `is_done` | 1.0 if aircraft finished, else 0.0 |

Aircraft are sorted by remaining distance each step (closest to destination first).

**Reward Design:**

```python
reward = r_progress + r_conflict

where:
  r_progress = sum of normalized distance reduction per aircraft
  r_conflict = -2.0 * (1 - min_dist/50) for each aircraft too close to predecessor
```

**Example Training Code:**

```python
from opentaxi.rl_env import AirportRLEnv
from opentaxi.airport import AirportMap
from opentaxi.planners import AStarPlanner
from stable_baselines3 import PPO

# Create environment
airport = AirportMap('opentaxi/airport_map/changi.graphml')
planner = AStarPlanner(airport)
env = AirportRLEnv(airport, planner, num_aircraft=10)

# Train with PPO
model = PPO(
    "MlpPolicy",
    env,
    n_steps=2048,
    batch_size=64,
    learning_rate=3e-4,
    verbose=1
)
model.learn(total_timesteps=100000)

# Evaluate
obs, _ = env.reset()
for _ in range(100):
    action, _ = model.predict(obs)
    obs, reward, terminated, truncated, info = env.step(action)
    if terminated or truncated:
        break
```

---

## Implementing Custom Components

### Custom Planner Example

```python
from opentaxi.planners import AStarPlanner
import numpy as np

class MyCustomPlanner(AStarPlanner):
    """Example: Planner that applies a routing penalty."""
    
    def __init__(self, airport, penalty_weight=1.5):
        super().__init__(airport)
        self.penalty_weight = penalty_weight
    
    def plan_shortest_path(self, start_idx, end_idx):
        # Call parent to get base path
        path, path_nodes = super().plan_shortest_path(start_idx, end_idx)
        
        if path is None:
            return None, None
        
        # Apply custom logic here (e.g., add waypoint, apply penalty)
        # For now, just return parent result
        return path, path_nodes
```

### Custom Controller Example

```python
from opentaxi.controller import StopGo

class MyCustomController(StopGo):
    """Example: Controller that uses custom conflict prediction."""
    
    def __init__(self, airport, predict_horizon=20.0, collision_buffer=50.0):
        super().__init__(airport, predict_horizon, collision_buffer)
    
    def update(self, aircrafts):
        # Call parent to get base resolution
        super().update(aircrafts)
        
        # Add custom logic here if needed
        # (e.g., apply priority rules, safety margins, etc.)
```

---

## Key Differences from v0.1

- **Planner method name changed:** `plan()` → `plan_shortest_path()`
- **Planner return type changed:** `List[str]` → `(path: np.ndarray, path_nodes: List[str])`
- **Controller method name changed:** `compute_actions()` → `update()`
- **Controller return type changed:** `Dict[str, bool]` → `None` (mutations via aircraft objects)
- **RL observation features changed:** Actual features are distance/conflict/arrival related, not position/velocity
- **RL reward changed:** Actual reward is progress-based, not time/conflict based

---

## Interface Compliance Testing

Check that custom implementations meet interface requirements:

```python
# Verify planner produces valid routes
path, path_nodes = planner.plan_shortest_path('GATE_01', 'RWY_EAST')
assert path is not None and path_nodes is not None
assert isinstance(path, np.ndarray) and path.shape[1] == 2  # (N, 2)
assert isinstance(path_nodes, list)
assert path_nodes[0] == 'GATE_01'
assert path_nodes[-1] == 'RWY_EAST'

# Verify controller modifies aircraft objects
aircraft_ids = list(aircrafts.keys())
controller.update(aircrafts)

# Check that controller set flags on aircrafts
for ac_id in aircraft_ids:
    assert hasattr(aircrafts[ac_id], 'yield_flag')
    assert isinstance(aircrafts[ac_id].yield_flag, (bool, np.bool_))
```

---
