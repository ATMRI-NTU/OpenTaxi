"""Synthetic scenario generation for reproducible benchmarking.

This module provides tools to generate synthetic airport surface operation
scenarios with configurable traffic density, calibrated aircraft dynamics,
and realistic runway occupancy time (ROT) distributions.

The scenarios enable reproducible evaluation of planning and control algorithms
without requiring access to proprietary surveillance data.
"""

import json
import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, asdict
import random


@dataclass
class AircraftParameters:
    """Calibrated aircraft kinematic parameters (from Section 4.2 validation)."""
    
    # Kinematic parameters validated against Changi Airport A-SMGCS data
    # (Cohen's d < 0.04 for taxi time distributions)
    target_velocity: float = 30.0      # km/h (cruise speed on taxiway)
    max_acceleration: float = 0.2      # m/s²
    max_deceleration: float = 0.5      # m/s²
    min_separation: float = 50.0       # meters (safety buffer)
    
    # Scenario-specific parameters
    spawn_time: float = 0.0            # seconds (relative to scenario start)
    priority: int = 1                  # higher = earlier release (1-10)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class ScenarioConfig:
    """Configuration for a synthetic benchmark scenario."""
    
    airport_map: str = "opentaxi/airport_map/changi.graphml"
    traffic_density: str = "medium"    # "light" (5-10), "medium" (15-25), "heavy" (30-50)
    num_aircraft: int = 20
    scenario_duration_seconds: int = 3600  # 1 hour simulation
    timestep_seconds: int = 5
    seed: int = 42
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


class ROTDistribution:
    """Runway Occupancy Time (ROT) distribution sampler.
    
    Models ROT as a mixture of Gaussian distributions, fitted from real
    Changi Airport A-SMGCS data (Figure 7 in paper).
    
    The distribution captures:
    - Fast ROT (short, light aircraft): mean ~35s, std ~10s
    - Normal ROT (medium aircraft): mean ~50s, std ~15s
    - Slow ROT (heavy aircraft): mean ~70s, std ~20s
    """
    
    def __init__(self, seed: Optional[int] = None):
        """Initialize ROT sampler with fitted Gaussian mixture parameters.
        
        Args:
            seed: Random seed for reproducibility.
        """
        self.rng = np.random.RandomState(seed)
        
        # Fitted from Changi A-SMGCS data (Section 4.2, Figure 7)
        # Gaussian mixture with 3 components
        self.components = [
            {"weight": 0.25, "mean": 35.0, "std": 10.0},   # Light aircraft
            {"weight": 0.50, "mean": 50.0, "std": 15.0},   # Medium aircraft
            {"weight": 0.25, "mean": 70.0, "std": 20.0},   # Heavy aircraft
        ]
        
    def sample(self) -> float:
        """Sample a single ROT value from the distribution.
        
        Returns:
            ROT in seconds, clipped to [20, 120] realistic range.
        """
        # Select component based on weights
        component = self.rng.choice(
            self.components,
            p=[c["weight"] for c in self.components]
        )
        
        # Sample from Gaussian
        rot = self.rng.normal(component["mean"], component["std"])
        
        # Clip to realistic range
        return np.clip(rot, 20.0, 120.0)


class TaxiTimeDistribution:
    """Taxi time distribution for realistic scenario generation.
    
    Models taxi time based on path length and aircraft performance.
    Validated against Changi A-SMGCS data (Figure 6 in paper).
    """
    
    # Empirical regression: taxi_time = a + b * path_length + noise
    # Fitted from Changi data with R² = 0.82
    A_COEFF = 5.0          # Intercept (min)
    B_COEFF = 0.012        # Slope (min per meter)
    NOISE_STD = 2.0        # Residual std (min)
    
    def __init__(self, seed: Optional[int] = None):
        """Initialize taxi time sampler.
        
        Args:
            seed: Random seed for reproducibility.
        """
        self.rng = np.random.RandomState(seed)
    
    def predict(self, path_length_meters: float, add_noise: bool = True) -> float:
        """Predict taxi time for a given path length.
        
        Args:
            path_length_meters: Length of taxi route in meters.
            add_noise: If True, add realistic residual variance.
        
        Returns:
            Predicted taxi time in seconds.
        """
        # Regression prediction
        taxi_time_min = self.A_COEFF + self.B_COEFF * path_length_meters
        
        # Add noise if requested
        if add_noise:
            noise = self.rng.normal(0, self.NOISE_STD)
            taxi_time_min = np.clip(taxi_time_min + noise, 5.0, 60.0)
        
        return taxi_time_min * 60  # Convert to seconds


class SyntheticScenarioGenerator:
    """Generate synthetic benchmark scenarios for airport surface operations.
    
    Scenarios are configured with:
    - Realistic aircraft spawn times and sequencing
    - Calibrated kinematic parameters
    - Traffic density presets (light/medium/heavy)
    - Deterministic randomness via seed for reproducibility
    """
    
    def __init__(self, seed: int = 42):
        """Initialize scenario generator.
        
        Args:
            seed: Random seed for deterministic scenario generation.
        """
        self.rng = random.Random(seed)
        self.rot_sampler = ROTDistribution(seed=seed)
        self.taxi_time_sampler = TaxiTimeDistribution(seed=seed)
    
    def generate_scenario(self, config: ScenarioConfig) -> Dict:
        """Generate a synthetic scenario.
        
        Args:
            config: Scenario configuration.
        
        Returns:
            Dictionary containing scenario metadata and aircraft list.
        """
        num_aircraft = config.num_aircraft
        
        # Generate aircraft spawn times with realistic spacing
        spawn_times = self._generate_spawn_times(
            num_aircraft,
            duration=config.scenario_duration_seconds
        )
        
        # Create aircraft list with calibrated parameters
        aircraft_list = []
        for i in range(num_aircraft):
            ac_params = AircraftParameters(
                spawn_time=spawn_times[i],
                priority=self.rng.randint(1, 5)  # Random priority
            )
            
            aircraft_list.append({
                "id": f"AC{i+1:03d}",
                "type": self.rng.choice(["B737", "B777", "A320", "A330"]),
                "start_node": None,  # Simulator assigns random valid gate
                "end_node": None,     # Simulator assigns random valid runway
                **ac_params.to_dict()
            })
        
        # Construct scenario document
        scenario = {
            "metadata": {
                "description": f"{config.traffic_density.capitalize()} traffic scenario "
                              f"with {num_aircraft} aircraft",
                "source": "OpenTaxi synthetic scenario generator",
                "validation": "Calibrated with Changi Airport A-SMGCS data (Section 4.2)",
            },
            "simulation": {
                "airport_map": config.airport_map,
                "duration_seconds": config.scenario_duration_seconds,
                "timestep_seconds": config.timestep_seconds,
                "seed": config.seed,
            },
            "aircraft": aircraft_list
        }
        
        return scenario
    
    def _generate_spawn_times(
        self,
        num_aircraft: int,
        duration: int,
        spacing_seconds: int = 30
    ) -> List[float]:
        """Generate realistic aircraft spawn times.
        
        Spreads aircraft uniformly across scenario duration with some
        randomness to mimic real operational variability.
        
        Args:
            num_aircraft: Number of aircraft to spawn.
            duration: Scenario duration in seconds.
            spacing_seconds: Nominal spacing between spawns.
        
        Returns:
            List of spawn times in seconds.
        """
        if num_aircraft == 0:
            return []
        
        spawn_times = []
        for i in range(num_aircraft):
            # Nominal time with uniform spacing
            nominal_time = i * (duration / num_aircraft)
            
            # Add ±50% random variation
            jitter = self.rng.uniform(-0.5 * spacing_seconds, 0.5 * spacing_seconds)
            spawn_time = np.clip(nominal_time + jitter, 0, duration - 60)
            
            spawn_times.append(spawn_time)
        
        return sorted(spawn_times)


def create_benchmark_scenarios() -> Dict[str, Dict]:
    """Create three standard benchmark scenarios (light, medium, heavy).
    
    These scenarios are used consistently across all benchmark evaluations
    (Section 5) and enable reproducible comparison with future research.
    
    Returns:
        Dictionary mapping scenario names to scenario dictionaries.
    """
    generator = SyntheticScenarioGenerator(seed=42)
    
    scenarios = {}
    
    # Light traffic scenario
    scenarios["light"] = generator.generate_scenario(
        ScenarioConfig(
            traffic_density="light",
            num_aircraft=10,
            scenario_duration_seconds=1800,  # 30 min
            seed=42
        )
    )
    
    # Medium traffic scenario (default benchmark)
    scenarios["medium"] = generator.generate_scenario(
        ScenarioConfig(
            traffic_density="medium",
            num_aircraft=20,
            scenario_duration_seconds=3600,  # 60 min
            seed=42
        )
    )
    
    # Heavy traffic scenario
    scenarios["heavy"] = generator.generate_scenario(
        ScenarioConfig(
            traffic_density="heavy",
            num_aircraft=40,
            scenario_duration_seconds=3600,  # 60 min
            seed=42
        )
    )
    
    return scenarios


if __name__ == "__main__":
    """Generate and save benchmark scenarios."""
    print("Generating OpenTaxi benchmark scenarios...")
    
    scenarios = create_benchmark_scenarios()
    
    for name, scenario in scenarios.items():
        filename = f"benchmark_traffic_{name}.json"
        with open(filename, 'w') as f:
            json.dump(scenario, f, indent=2)
        print(f"  ✓ Generated: {filename} ({scenario['simulation']['duration_seconds']}s, "
              f"{len(scenario['aircraft'])} aircraft)")
    
    print("\nScenarios saved. Ready for benchmarking.")
