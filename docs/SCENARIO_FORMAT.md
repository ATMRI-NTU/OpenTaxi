# Scenario Format Specification

**Version:** 1.0  
**Last Updated:** April 28, 2026

---

## Overview

OpenTaxi scenarios are defined as JSON files that specify:
- **Static configuration**: Airport map, simulation parameters, timestep
- **Dynamic configuration**: Aircraft definitions, spawn times, initial conditions
- **Metadata**: Description, validation notes, source information

This format enables:
- **Reproducibility**: Scenarios are version-controlled and shareable
- **Transparency**: All parameters are human-readable and inspectable
- **Extensibility**: New fields can be added without breaking existing scenarios

## JSON Schema

```json
{
  "metadata": {
    "description": "string - Human-readable description of the scenario",
    "source": "string - Where this scenario came from (e.g., real data, synthetic)",
    "validation": "string - Validation information or data source"
  },
  "simulation": {
    "airport_map": "string - Path to airport GraphML file",
    "duration_seconds": "number - Total simulation duration",
    "timestep_seconds": "number - Simulation step duration",
    "seed": "number - Random seed for reproducibility"
  },
  "aircraft": [
    {
      "id": "string - Unique aircraft identifier (e.g., AC001)",
      "type": "string - Aircraft type (e.g., B737, A320)",
      "start_node": "string or null - Starting gate node ID (null = random valid gate)",
      "end_node": "string or null - Destination runway entry node (null = random valid runway)",
      "target_velocity": "number - Cruise speed (km/h)",
      "max_acceleration": "number - Maximum acceleration (m/s²)",
      "max_deceleration": "number - Maximum deceleration (m/s²)",
      "min_separation": "number - Minimum safe separation from other aircraft (m)",
      "spawn_time": "number - Time aircraft enters simulation (seconds)",
      "priority": "number - Priority level (1-10, higher = earlier release)"
    },
    ...
  ]
}
```

---

## Field Descriptions

### Metadata Section

| Field | Type | Description |
|---|---|---|
| `description` | string | Human-readable description. Use for documenting the scenario's purpose. |
| `source` | string | Origin of scenario data (e.g., "Changi Airport A-SMGCS", "Synthetic benchmark") |
| `validation` | string | Reference to validation methodology or dataset (e.g., "Calibrated with Section 4.2") |

### Simulation Section

| Field | Type | Description | Typical Values |
|---|---|---|---|
| `airport_map` | string | Path to GraphML airport file | `opentaxi/airport_map/changi.graphml` |
| `duration_seconds` | int | Total simulation duration | 1800–3600 (30–60 min) |
| `timestep_seconds` | int | Simulation step duration | 5–10 |
| `seed` | int | Random seed for reproducibility | 42, 123, etc. |

### Aircraft Section

Each aircraft is defined with kinematic parameters and scenario-specific settings:

| Field | Type | Description | Typical Values |
|---|---|---|---|
| `id` | string | Unique identifier | `AC001`, `FDX001` |
| `type` | string | Aircraft type | `B737`, `B777`, `A320`, `A330` |
| `start_node` | string\|null | Gate node ID; `null` = random | `GATE_A1`, `null` |
| `end_node` | string\|null | Runway node ID; `null` = random | `RWY_EAST`, `null` |
| `target_velocity` | float | Cruise speed (km/h) | 20–30 |
| `max_acceleration` | float | Acceleration (m/s²) | 0.15–0.25 |
| `max_deceleration` | float | Deceleration (m/s²) | 0.4–0.6 |
| `min_separation` | float | Safety buffer (m) | 50 |
| `spawn_time` | float | Entry time (seconds) | 0–duration |
| `priority` | int | Priority (higher = earlier release) | 1–10 |

---

## Examples

### Minimal Scenario (5 aircraft)

```json
{
  "metadata": {
    "description": "Minimal test scenario with 5 aircraft",
    "source": "OpenTaxi tutorial",
    "validation": "For testing purposes only"
  },
  "simulation": {
    "airport_map": "opentaxi/airport_map/changi.graphml",
    "duration_seconds": 600,
    "timestep_seconds": 5,
    "seed": 42
  },
  "aircraft": [
    {
      "id": "AC001",
      "type": "B737",
      "start_node": null,
      "end_node": null,
      "target_velocity": 30.0,
      "max_acceleration": 0.2,
      "max_deceleration": 0.5,
      "min_separation": 50.0,
      "spawn_time": 0.0,
      "priority": 1
    },
    {
      "id": "AC002",
      "type": "A320",
      "start_node": null,
      "end_node": null,
      "target_velocity": 25.0,
      "max_acceleration": 0.18,
      "max_deceleration": 0.48,
      "min_separation": 50.0,
      "spawn_time": 60.0,
      "priority": 2
    }
  ]
}
```

### Benchmark Scenario (with fixed gates)

Use when comparing algorithm performance on the same traffic setup:

```json
{
  "metadata": {
    "description": "Routing benchmark with fixed gate assignments",
    "source": "OpenTaxi benchmark suite (Section 5.1)",
    "validation": "Calibrated with Changi Airport A-SMGCS data"
  },
  "simulation": {
    "airport_map": "opentaxi/airport_map/changi.graphml",
    "duration_seconds": 1800,
    "timestep_seconds": 5,
    "seed": 42
  },
  "aircraft": [
    {
      "id": "AC001",
      "type": "B777",
      "start_node": "GATE_01",
      "end_node": "RWY_E_ENTRY",
      "target_velocity": 30.0,
      "max_acceleration": 0.2,
      "max_deceleration": 0.5,
      "min_separation": 50.0,
      "spawn_time": 0.0,
      "priority": 1
    }
  ]
}
```

---

## Loading Scenarios in Python

```python
import json
from opentaxi.airport import AirportMap
from opentaxi.simulator import Simulation
from opentaxi.planners import AStarPlanner
from opentaxi.controller import Opt_StopGo

# Load scenario
with open('examples/scenarios/benchmark_traffic_medium.json') as f:
    scenario = json.load(f)

# Extract configuration
config = scenario['simulation']
aircraft_list = scenario['aircraft']

# Build simulator with loaded scenario
airport = AirportMap(config['airport_map'])
planner = AStarPlanner(airport)
controller = Opt_StopGo(airport)

sim = Simulation(airport, planner, controller, num_agents=len(aircraft_list))

# Run simulation
results = sim.run(max_steps=config['duration_seconds'] // config['timestep_seconds'])
```

---

## Best Practices

1. **Always include metadata**: Document what the scenario is for and where it came from.
2. **Use consistent seeds**: Set `seed` to a fixed value for reproducibility.
3. **Validate against real data**: When possible, ensure synthetic scenarios have plausible distributions.
4. **Keep aircraft counts reasonable**: Most airports don't exceed 50 simultaneous movements; very large scenarios may not be realistic.
5. **Document calibration**: Reference Section 4.2 for validated parameter ranges.

---

## Pre-built Scenarios

OpenTaxi includes three standard benchmark scenarios in `examples/scenarios/`:

- **`benchmark_traffic_light.json`** – Light traffic (10 aircraft, 30 min)
  - Use for: Testing, unit tests, quick validation
- **`benchmark_traffic_medium.json`** – Medium traffic (20 aircraft, 60 min)
  - Use for: Standard benchmarking (default for research)
- **`benchmark_traffic_heavy.json`** – Heavy traffic (40 aircraft, 60 min)
  - Use for: Stress testing, scalability evaluation

All three scenarios are calibrated with kinematic parameters validated against Changi Airport data (Section 4.2).

---

## Future Extensions

Possible extensions to this format (not yet implemented):
- **Weather conditions**: Visibility, runway closures
- **Procedural parameters**: Route restrictions, mandatory holding points
- **Multi-agent scenarios**: Coordinated gate assignments or shared resource scenarios
- **Dynamic parameters**: Parameters that change during simulation (e.g., closed taxiways)

