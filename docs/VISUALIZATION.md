# Visualization and Rendering

**Version:** 1.0  
**Last Updated:** April 28, 2026

---

## Overview

OpenTaxi uses Matplotlib for 2D visualization of airport surface operations. This document describes the visualization system, supported backends, and headless mode for high-throughput simulations.

---

## Quick Start

### Display Visualization (Interactive)

```python
from opentaxi.airport import AirportMap
from opentaxi.simulator import Simulation
from opentaxi.planners import AStarPlanner
from opentaxi.controller import Opt_StopGo

airport = AirportMap('opentaxi/airport_map/changi.graphml')
planner = AStarPlanner(airport)
controller = Opt_StopGo(airport)

# Create simulator
sim = Simulation(
    airport,
    planner,
    controller,
    num_agents=10
)

# Enable visualization and run
sim.init_visualization()
sim.run(max_steps=720)
```

### Headless Mode (No Display)

```python
# For benchmarking / batch processing (fastest)
sim = Simulation(
    airport,
    planner,
    controller,
    num_agents=10
)

# Simply call run() without init_visualization()
sim.run(max_steps=720)
```

---

## Visualization Features

### What's Displayed

The live visualization shows:

- **Airport topology**: Taxiways (gray), gates (green), runways (red)
- **Aircraft**: Colored dots with callsigns
- **Planned routes**: Blue lines from current position to destination
- **Conflicts**: Red lines between conflicting aircraft
- **Separation radius**: Dashed circles around each aircraft

### Interactive Controls

During simulation:

| Control | Action |
|---|---|
| `Space` | Pause/resume simulation |
| `Right Arrow` | Next step (while paused) |
| `Left Arrow` | Previous step (while paused) |
| `+` / `-` | Zoom in/out |
| `Pan` | Click and drag to pan view |
| `S` | Save current frame to PNG |
| `Q` | Quit |

---

## Backend Configuration

OpenTaxi uses Matplotlib's backend system. Configure based on your environment:

### GUI Backends (Interactive Display)

**Default for Desktop/Laptop:**

```python
import matplotlib
matplotlib.use('Qt5Agg')  # Best for interactive use
# or
matplotlib.use('TkAgg')   # Alternative (usually installed)
```

**Configuration in `.matplotlibrc`:**

```ini
backend : Qt5Agg
```

### Headless Backends (No Display)

**For remote servers / CI/CD:**

```python
import matplotlib
matplotlib.use('Agg')  # Non-interactive, writes to files

# Requires: sudo apt install libfreetype6-dev libpng-dev
```

**Configuration in `.matplotlibrc`:**

```ini
backend : Agg
```

### Verify Backend

```python
import matplotlib
print(f"Current backend: {matplotlib.get_backend()}")

# Change at runtime (must be before importing pyplot)
matplotlib.use('Agg')
import matplotlib.pyplot as plt
```

---

## Saving Visualizations

### Save Single Frame

```python
# During simulation, press 'S' to save PNG
# Saves to: frame_NNNN.png (incrementing)
```

### Save All Frames (Post-Processing)

```python
from opentaxi.simulator import Simulation
import matplotlib
matplotlib.use('Agg')  # Headless backend

sim = Simulation(...)
sim.init_visualization()
sim.run(max_steps=720)  # Frames are saved to disk during execution

# Frames are automatically saved as PNG files in the current directory
```

### Create Video from Frames

**Using FFmpeg:**

```bash
ffmpeg -framerate 4 -i frame_%04d.png -c:v libx264 -pix_fmt yuv420p simulation.mp4
```

**Using Python:**

```python
import cv2
import numpy as np
from pathlib import Path

frames = sorted(Path('.').glob('frame_*.png'))
video = cv2.VideoWriter(
    'simulation.mp4',
    cv2.VideoWriter_fourcc(*'mp4v'),
    fps=4,
    frameSize=(1024, 1024)
)

for frame_path in frames:
    frame = cv2.imread(str(frame_path))
    video.write(frame)

video.release()
```

---

## Customizing Visualization

### Adjust Figure Size

```python
sim = Simulation(...)
sim.init_visualization()  # Figure size defaults to (12, 10)
sim.run(max_steps=720)
```

### Disable Real-time Display (Batch Mode)

```python
import matplotlib
matplotlib.use('Agg')  # Must be before importing pyplot

sim = Simulation(...)
sim.init_visualization()  # Will save frames to disk, not display
sim.run()

# Frames are saved to PNG files in the current directory
```

### Change Colors / Styling

Edit `opentaxi/simulator.py` to customize colors:

```python
# In Simulation.render() method:
COLORS = {
    'taxiway': '#cccccc',      # Gray
    'gate': '#00cc00',         # Green
    'runway': '#ff0000',       # Red
    'aircraft': '#0066ff',     # Blue
    'conflict': '#ff00ff',     # Magenta
}
```

---

## Performance Implications

### Visualization Overhead

Visualization adds modest overhead for interactive display, but headless mode (no visualization) runs significantly faster:

- **Without visualization** (headless): Fastest mode, suitable for batch processing
- **With visualization** (interactive): Adds overhead, suitable for real-time inspection

Visualization overhead depends on your hardware and matplotlib backend (Qt5Agg interactive is slower than Agg headless).

### Optimization

For high-throughput scenarios:

```python
# Fast path: Disable visualization entirely
sim = Simulation(...)
sim.run(max_steps=10000)  # Very fast, no visualization

# Medium path: Save frames to disk (headless)
import matplotlib
matplotlib.use('Agg')
sim = Simulation(...)
sim.init_visualization()
sim.run(max_steps=10000)  # Saves frames to PNG files

# Slow path: Interactive display
sim = Simulation(...)
sim.init_visualization()  # Interactive mode (pauses for user input)
sim.run(max_steps=10000)
```

---

## Troubleshooting Visualization

### "No display" Error on Remote Server

```python
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend (must be before pyplot import)

sim = Simulation(...)
sim.init_visualization()
sim.run()
# Frames saved to disk, no X11 required
```

### "Backend Qt5Agg not found"

**Solution:** Install PyQt5

```bash
pip install PyQt5
# or on macOS with Homebrew:
brew install pyqt5
```

### Slow Rendering

**Solution:** Disable visualization during simulation for faster execution

```python
# Skip visualization during simulation (fastest)
sim = Simulation(...)
sim.run()

# Or use headless backend to save frames:
import matplotlib
matplotlib.use('Agg')
sim = Simulation(...)
sim.init_visualization()
sim.run()  # Faster than interactive, saves to disk
```

### Memory Issues with Long Simulations

For long simulations (> 1000 steps), minimize memory usage:

```python
# Option 1: Disable visualization entirely (lowest memory)
sim = Simulation(...)
sim.run()  # No frames stored

# Option 2: Use headless backend (saves frames to disk, not memory)
import matplotlib
matplotlib.use('Agg')  # Headless backend saves directly to PNG
sim = Simulation(...)
sim.init_visualization()
sim.run()  # Frames streamed to disk
```

---

## Example: Custom Visualization

```python
import matplotlib.pyplot as plt
from opentaxi.simulator import Simulation
from opentaxi.evaluation import SchedulerEvaluator

# Run simulation WITHOUT built-in visualization
sim = Simulation(...)
evaluator = SchedulerEvaluator(conflict_threshold=50.0)
sim.evaluator = evaluator
sim.run()

# Access evaluation results via evaluator
# Extract taxi times and conflicts from aircraft
taxi_times = [ac.taxi_time for ac in sim.aircrafts.values()]
conflicts = getattr(evaluator, 'conflicts', [])

# Create custom visualization
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

# Left: Taxi time distribution
ax1.hist(taxi_times, bins=20)
ax1.set_xlabel('Taxi Time (seconds)')
ax1.set_ylabel('Count')
ax1.set_title('Taxi Time Distribution')

# Right: Conflict statistics
ax2.bar(['Conflicts'], [len(conflicts)])
ax2.set_ylabel('Count')
ax2.set_title('Total Conflicts')

plt.tight_layout()
plt.savefig('analysis.png', dpi=150)
plt.show()
```

---

## Video Generation Workflow

Complete example: Simulate, save frames, create video

```bash
#!/bin/bash
# simulate_and_render.sh

# 1. Run Python simulation (saves PNG frames with headless backend)
python3 << 'EOF'
import matplotlib
matplotlib.use('Agg')
from opentaxi.simulator import Simulation
sim = Simulation(...)
sim.init_visualization()
sim.run()
EOF

# 2. Convert frames to video
ffmpeg -framerate 4 \
    -i frame_%04d.png \
    -c:v libx264 \
    -pix_fmt yuv420p \
    -preset slow \
    output.mp4

# 3. Cleanup
rm frame_*.png
```

---

## Environment Variables

Control visualization via environment:

```bash
# Use Agg backend (no display)
MPLBACKEND=Agg python3 simulation.py

# Use default backend
python3 simulation.py
```

---

## API Reference

### Simulation Constructor

```python
sim = Simulation(
    airport_map,               # AirportMap instance
    planner,                   # Planner instance
    controller,                # Controller instance
    num_agents=3,              # Number of aircraft
    replay_mode=False,         # Replay vs. simulation mode
    hist_data=None,            # Historical trajectory data (for replay)
    evaluator=None,            # Evaluator instance (optional)
)
```

### Visualization Methods

```python
# Initialize visualization (must be called before run())
sim.init_visualization()

# Run the simulation loop
sim.run(max_steps=10000)

# Update visualization (called automatically in run())
sim.update_visualization()
```

