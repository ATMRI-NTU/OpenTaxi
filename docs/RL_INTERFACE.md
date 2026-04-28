# Gymnasium RL Interface

**Version:** 1.0  
**Last Updated:** April 28, 2026

---

## Overview

OpenTaxi provides a Gymnasium-compatible reinforcement learning environment for training agents to optimize aircraft flow on airport surfaces. This interface enables researchers to:

- Use standard RL algorithms (PPO, DQN, A3C, etc.) from Stable-Baselines3
- Benchmark custom control policies
- Generate synthetic training data
- Study emergent behavior in multi-agent scenarios

---

## Quick Start

### Setup

```bash
pip install gymnasium stable-baselines3
```

### 30-Second Example

```python
from opentaxi.rl_env import AirportRLEnv
from opentaxi.airport import AirportMap
from opentaxi.planners import AStarPlanner
from stable_baselines3 import PPO

# Load airport and planner
airport = AirportMap('opentaxi/airport_map/changi.graphml')
planner = AStarPlanner(airport)

# Create environment
env = AirportRLEnv(airport, planner, num_aircraft=10)

# Train PPO agent
model = PPO("MlpPolicy", env, verbose=1)
model.learn(total_timesteps=50000)

# Evaluate
obs, _ = env.reset()
total_reward = 0
for _ in range(100):
    action, _ = model.predict(obs)
    obs, reward, terminated, truncated, info = env.step(action)
    total_reward += reward
    if terminated or truncated:
        break

print(f"Total reward: {total_reward:.2f}")
```

---

## Environment Specification

### Observation Space

**Type:** `Box` (continuous vector)  
**Shape:** `(max_aircraft * 6,)` where `max_aircraft` is typically 50  
**Range:** `[0.0, 1.0]` (normalized)

Each aircraft slot contributes 6 features, in order of remaining distance to destination:

| Index | Feature | Meaning | Calculation |
|---|---|---|---|
| 0 | `remaining_distance_norm` | Distance left to destination (normalized) | (path_length - curr_s) / 2000.0 |
| 1 | `dist_to_predecessor_norm` | Distance to previous aircraft (normalized) | min(dist_to_prev_ac / 50.0, 1.0) |
| 2 | `velocity_norm` | Current velocity (normalized) | velocity / 30.0 km/h |
| 3 | `is_arrived` | Aircraft at destination? | 1.0 if arrived, else 0.0 |
| 4 | `is_waiting` | Aircraft holding at node? | 1.0 if waiting, else 0.0 |
| 5 | `is_done` | Aircraft finished? | 1.0 if done, else 0.0 |

**Important:** Aircraft are sorted by remaining distance each step (closest to destination first), so observation ordering changes dynamically.

**Example:** For 10 aircraft (padded to max_aircraft=50): observation is shape `(300,)` with aircraft 0-9 in slots 0-59, remaining slots zeroed.

```python
observation = [
    # Aircraft 0 (closest to destination)
    0.45, 0.52, 0.8, 0.0, 0.0, 1.0,  # [remaining, pred_dist, velocity, is_arrived, is_waiting, is_done]
    # Aircraft 1
    0.38, 0.48, 0.6, 0.0, 0.0, 0.0,
    # ... 8 more aircraft ...
    # Remaining 40 slots: zeros (padding)
]
```

### Action Space

**Type:** `MultiBinary` (discrete)  
**Shape:** `(num_aircraft,)`  
**Values:** Binary (0 or 1)

| Action | Meaning |
|---|---|
| `0` | Stop / Hold / Decelerate |
| `1` | Go / Proceed / Accelerate |

**Example:** For 10 aircraft:
```python
action = [1, 0, 1, 1, 0, 1, 1, 0, 1, 1]  # 6 going, 4 stopped
```

### Reward Function

**Design Goal:** Incentivize aircraft to move toward their destination while maintaining separation.

**Actual Formula:**

```
reward = r_progress + r_conflict

where:
  r_progress = average normalized distance reduction per aircraft (positive when moving forward)
  r_conflict = -2.0 * (1 - min_dist/50) for each aircraft too close to predecessor
```

**Breakdown:**

| Component | Value | Purpose |
|---|---|---|
| Progress reward | +value (0 to 1) | Incentivize forward motion |
| Conflict penalty | -2.0 * (1 - dist/50) per conflict | Penalize unsafe separation (50m min) |

**Key Insight:** Reward is dynamic and based on relative progress, NOT on absolute taxi times. This means:
- Fast aircraft get high rewards for rapid progress
- Stopped aircraft get low/zero reward for holding position
- Aircraft causing conflicts get negative reward

**Typical Rewards per Step:**
- Good (moving forward, separated): +0.1 to +0.5
- Acceptable (moving slowly): 0.0 to +0.1  
- Bad (stopped): 0.0 to -0.1
- Unsafe (within 50m of predecessor): -0.5 to -2.0 (scales with proximity)

### Termination Conditions

Episode terminates when:

1. **All aircraft delivered** – Aircraft landed successfully (all reached destination)
2. **Max steps reached** – Default 2000 steps (~167 min simulated time at 5s/step)
3. **Max episodes reached** – Training stops after 1500 episodes (can be configured via `max_episodes` param)

**Termination vs. Truncation:**
- `terminated=True`: Episode ended naturally (all aircraft delivered)
- `truncated=True`: Episode cut short (max steps reached or max episodes exceeded)

---

## Environment API

### Initialization

```python
from opentaxi.rl_env import AirportRLEnv
from opentaxi.airport import AirportMap
from opentaxi.planners import AStarPlanner

# Load airport and planner
airport = AirportMap('opentaxi/airport_map/changi.graphml')
planner = AStarPlanner(airport)

# Create environment
env = AirportRLEnv(
    airport_map=airport,              # AirportMap object (required)
    planner=planner,                  # Planner object (required)
    num_aircraft=10,                  # Number of concurrent aircraft
    max_aircraft=50,                  # Maximum slot size (for padding)
    min_separation=50.0,              # Minimum safe distance (meters)
    hard_stop_distance=20.0,          # Hard stop threshold (meters)
    max_steps=2000,                   # Episode max steps
    render=False                      # Enable visualization
)
```

**Parameters:**

| Parameter | Type | Default | Notes |
|---|---|---|---|
| `airport_map` | AirportMap | Required | Loaded graph of airport taxiway network |
| `planner` | Planner | Required | Path planning algorithm (AStarPlanner, DijkstraPlanner, etc.) |
| `num_aircraft` | int | 10 | Active aircraft per episode |
| `max_aircraft` | int | 50 | Padding size for observation vector |
| `min_separation` | float | 50.0 | Minimum safe separation (meters) |
| `hard_stop_distance` | float | 20.0 | Distance threshold for hard stop (meters) |
| `max_steps` | int | 2000 | Maximum steps per episode (~167 min at 5s/step) |
| `max_episodes` | int | 1500 | Maximum episodes before training stops (saves data to .mat or .npy) |
| `render` | bool | False | Enable visualization (initialized during reset()) |

### reset()

Reset environment to initial state.

```python
observation, info = env.reset(seed=42)

# Returns:
# - observation: Initial observation vector (numpy array, shape (max_aircraft * 6,))
# - info: Dict with step metadata
#   {
#       'timestep': 0,        # Current simulation step
#       'active': 10,         # Active aircraft (not done, not arrived)
#       'waiting': 0,         # Aircraft waiting at destination
#       'done': 0,            # Aircraft finished/removed
#       'conflicts': 0,       # Conflicts detected this step
#       'completions': 0      # Cumulative aircraft arrivals
#   }
```

### step()

Execute one action in the environment.

```python
action = env.action_space.sample()  # Random action [0,1,1,0,...]
observation, reward, terminated, truncated, info = env.step(action)

# Returns:
# - observation: Updated observation (numpy array, shape (max_aircraft * 6,))
# - reward: Scalar reward (progress reward + conflict penalty)
# - terminated: bool - Episode finished naturally (all aircraft arrived)
# - truncated: bool - Episode cut short (max steps reached)
# - info: Dict with step metadata (same structure as reset())
#   {
#       'timestep': 42,       # Current simulation step
#       'active': 8,          # Active aircraft remaining
#       'waiting': 1,         # At destination, waiting removal
#       'done': 1,            # Already removed/finished
#       'conflicts': 2,       # Conflicts detected this step
#       'completions': 2      # Total aircraft that have arrived (cumulative)
#   }
```

### Visualization

Visualization is automatically displayed each step if `render=True` during initialization. The rendering happens automatically in the step() method; no explicit render() call is needed.

```python
# Enable visualization
env = AirportRLEnv(airport, planner, num_aircraft=10, render=True)

# Visualization displays automatically during step()
for step in range(100):
    obs, reward, terminated, truncated, info = env.step(action)
    # Display updates automatically (no env.render() call needed)
```

---

## Training Examples

### PPO with Stable-Baselines3

```python
from stable_baselines3 import PPO
from opentaxi.rl_env import AirportRLEnv
from opentaxi.airport import AirportMap
from opentaxi.planners import AStarPlanner

# Load airport and planner
airport = AirportMap('opentaxi/airport_map/changi.graphml')
planner = AStarPlanner(airport)

# Create environment
env = AirportRLEnv(airport, planner, num_aircraft=10)

# Create PPO agent with custom hyperparameters
model = PPO(
    policy='MlpPolicy',
    env=env,
    n_steps=2048,               # Rollout buffer size
    batch_size=64,              # Minibatch size
    learning_rate=3e-4,         # Learning rate
    n_epochs=10,                # Number of epochs for SGD
    gamma=0.99,                 # Discount factor
    gae_lambda=0.95,            # GAE lambda
    clip_range=0.2,             # PPO clip range
    verbose=1                   # Print progress
)

# Train for 100k steps
model.learn(total_timesteps=100000)

# Save model
model.save("airport_control_ppo")
```

### Evaluation Loop

```python
from stable_baselines3 import PPO
from opentaxi.rl_env import AirportRLEnv
from opentaxi.airport import AirportMap
from opentaxi.planners import AStarPlanner
import numpy as np

# Load trained model
model = PPO.load("airport_control_ppo")

# Load airport and planner
airport = AirportMap('opentaxi/airport_map/changi.graphml')
planner = AStarPlanner(airport)

# Create environment
env = AirportRLEnv(airport, planner, num_aircraft=10)

# Evaluate for 10 episodes
episode_rewards = []
for episode in range(10):
    obs, _ = env.reset()
    episode_reward = 0
    
    for step in range(1000):
        action, _ = model.predict(obs, deterministic=True)
        obs, reward, terminated, truncated, info = env.step(action)
        episode_reward += reward
        
        if terminated or truncated:
            break
    
    episode_rewards.append(episode_reward)
    print(f"Episode {episode}: reward={episode_reward:.2f}")

print(f"Mean reward: {np.mean(episode_rewards):.2f} ± {np.std(episode_rewards):.2f}")
```

### Multi-Environment Training (Faster)

```python
from stable_baselines3 import PPO
from stable_baselines3.common.env_util import make_vec_env
from opentaxi.rl_env import AirportRLEnv
from opentaxi.airport import AirportMap
from opentaxi.planners import AStarPlanner

# Load airport and planner (shared across all envs)
airport = AirportMap('opentaxi/airport_map/changi.graphml')
planner = AStarPlanner(airport)

# Create 8 parallel environments
num_envs = 8
env = make_vec_env(
    lambda: AirportRLEnv(airport, planner, num_aircraft=10),
    n_envs=num_envs,
    seed=42
)

# Train on parallel environments
model = PPO(
    policy='MlpPolicy',
    env=env,
    n_steps=2048 // num_envs,  # Distribute steps across environments
    learning_rate=3e-4,
    verbose=1
)

model.learn(total_timesteps=500000)
```

### Comparing to Baseline (Stop-Go)

```python
import numpy as np
from opentaxi.rl_env import AirportRLEnv
from opentaxi.airport import AirportMap
from opentaxi.planners import AStarPlanner
from stable_baselines3 import PPO

# Load airport and planner
airport = AirportMap('opentaxi/airport_map/changi.graphml')
planner = AStarPlanner(airport)

# Trained RL policy
rl_model = PPO.load("airport_control_ppo")

# Test both policies
results = {'RL': [], 'StopGo': []}

for trial in range(10):
    # RL policy
    env = AirportRLEnv(airport, planner, num_aircraft=20)
    obs, _ = env.reset()
    rl_reward = 0
    for _ in range(1000):
        action, _ = rl_model.predict(obs, deterministic=True)
        obs, reward, terminated, truncated, _ = env.step(action)
        rl_reward += reward
        if terminated or truncated:
            break
    results['RL'].append(rl_reward)
    
    # Baseline: rule-based controller (Stop-Go is default)
    # Run same scenario without RL policy, using environment's internal controller
    env = AirportRLEnv(airport, planner, num_aircraft=20)
    obs, _ = env.reset()
    sg_reward = 0
    for _ in range(1000):
        # Use a simple all-stop action (baseline: don't proceed)
        action = np.zeros(20, dtype=int)  # All aircraft stop
        obs, reward, terminated, truncated, _ = env.step(action)
        sg_reward += reward
        if terminated or truncated:
            break
    results['StopGo'].append(sg_reward)

print("RL Policy:  {:.2f} ± {:.2f}".format(np.mean(results['RL']), np.std(results['RL'])))
print("Stop-Go:    {:.2f} ± {:.2f}".format(np.mean(results['StopGo']), np.std(results['StopGo'])))
```

---

## Advanced Usage

### Custom Reward Functions

```python
from gymnasium import Wrapper

class CustomRewardWrapper(Wrapper):
    """Wrap environment to apply custom reward scaling."""
    
    def __init__(self, env, conflict_penalty=2.0):
        super().__init__(env)
        self.conflict_penalty = conflict_penalty
    
    def step(self, action):
        obs, reward, terminated, truncated, info = self.env.step(action)
        
        # Scale reward based on conflicts detected
        conflict_reward = -self.conflict_penalty * info['conflicts']
        modified_reward = reward + conflict_reward
        
        return obs, modified_reward, terminated, truncated, info

# Usage
from opentaxi.rl_env import AirportRLEnv
from opentaxi.airport import AirportMap
from opentaxi.planners import AStarPlanner
from stable_baselines3 import PPO

airport = AirportMap('opentaxi/airport_map/changi.graphml')
planner = AStarPlanner(airport)

env = AirportRLEnv(airport, planner, num_aircraft=10)
env = CustomRewardWrapper(env, conflict_penalty=3.0)  # More emphasis on conflict avoidance

model = PPO('MlpPolicy', env)
model.learn(total_timesteps=100000)
```

### Curriculum Learning

```python
from opentaxi.rl_env import AirportRLEnv
from opentaxi.airport import AirportMap
from opentaxi.planners import AStarPlanner
from stable_baselines3 import PPO

# Load airport and planner (shared across stages)
airport = AirportMap('opentaxi/airport_map/changi.graphml')
planner = AStarPlanner(airport)

# Start with few aircraft, gradually increase
for stage, num_aircraft in enumerate([5, 10, 15, 20]):
    env = AirportRLEnv(airport, planner, num_aircraft=num_aircraft)
    model = PPO('MlpPolicy', env, verbose=1)
    model.learn(total_timesteps=50000)
    model.save(f"stage_{stage}_ppo")
```

### Observation Normalization

```python
from stable_baselines3.common.vec_env import VecNormalize
from stable_baselines3.common.env_util import make_vec_env
from stable_baselines3 import PPO
from opentaxi.rl_env import AirportRLEnv
from opentaxi.airport import AirportMap
from opentaxi.planners import AStarPlanner

# Load airport and planner
airport = AirportMap('opentaxi/airport_map/changi.graphml')
planner = AStarPlanner(airport)

env = make_vec_env(
    lambda: AirportRLEnv(airport, planner, num_aircraft=10),
    n_envs=8
)

# Normalize observations and returns
env = VecNormalize(env, norm_obs=True, norm_reward=True)

model = PPO('MlpPolicy', env)
model.learn(total_timesteps=500000)

# Save environment normalization
env.save("env_normalize")
```

---

## Troubleshooting

### "Reward is NaN"

**Cause:** Unresolved conflicts or invalid aircraft states cause numerical issues.  
**Solution:** Reduce aircraft density or increase minimum separation distance.

```python
from opentaxi.rl_env import AirportRLEnv
from opentaxi.airport import AirportMap
from opentaxi.planners import AStarPlanner

airport = AirportMap('opentaxi/airport_map/changi.graphml')
planner = AStarPlanner(airport)

# Reduce density or increase separation
env = AirportRLEnv(
    airport,
    planner,
    num_aircraft=5,            # Reduce from 10
    min_separation=150.0       # Increase from 50.0
)
```

### "Episode always terminates early"

**Cause:** Aircraft frequently collide due to high density.  
**Solution:** Use easier scenario (fewer aircraft, more spacing).

```python
from opentaxi.airport import AirportMap
from opentaxi.planners import AStarPlanner

airport = AirportMap('opentaxi/airport_map/changi.graphml')
planner = AStarPlanner(airport)

env = AirportRLEnv(
    airport,              # Required
    planner,              # Required
    num_aircraft=5,       # Reduce from 10
    min_separation=100.0  # Increase minimum safe distance (default 50.0)
)
```

### "Training doesn't improve"

**Cause:** Action space (stop/go) may not be enough.  
**Solution:** Use continuous control or add velocity targets.

```python
# Extend action space in custom environment
self.action_space = spaces.Box(
    low=-1.0,
    high=1.0,
    shape=(num_aircraft * 2,),  # velocity_x, velocity_y per aircraft
    dtype=np.float32
)
```

---

## Reference

- **Stable-Baselines3 Docs:** https://stable-baselines3.readthedocs.io/
- **Gymnasium Docs:** https://gymnasium.farama.org/
- **Section 5.2 (Paper):** RL case study using this interface

