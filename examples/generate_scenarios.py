#!/usr/bin/env python3
"""Generate OpenTaxi benchmark scenarios and save to examples/scenarios/"""

import json
import os
from pathlib import Path

# Add parent directory to path so we can import opentaxi
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from opentaxi.synthetic_scenarios import create_benchmark_scenarios


def main():
    """Generate and save benchmark scenarios."""
    
    # Ensure scenarios directory exists
    scenarios_dir = Path(__file__).parent / "scenarios"
    scenarios_dir.mkdir(exist_ok=True)
    
    print("=" * 70)
    print("OpenTaxi Benchmark Scenario Generator")
    print("=" * 70)
    print()
    
    # Generate scenarios
    print("Generating synthetic scenarios with calibrated parameters...")
    print("(Calibration based on Changi Airport A-SMGCS data, Section 4.2)")
    print()
    
    scenarios = create_benchmark_scenarios()
    
    # Save each scenario
    for name, scenario in scenarios.items():
        filename = scenarios_dir / f"benchmark_traffic_{name}.json"
        
        with open(filename, 'w') as f:
            json.dump(scenario, f, indent=2)
        
        num_ac = len(scenario['aircraft'])
        duration = scenario['simulation']['duration_seconds'] / 60
        
        print(f"✓ Generated: {filename.name}")
        print(f"  - Traffic density: {name.upper()}")
        print(f"  - Aircraft: {num_ac}")
        print(f"  - Duration: {duration:.0f} minutes")
        print(f"  - Description: {scenario['metadata']['description']}")
        print()
    
    print("=" * 70)
    print("Scenario generation complete!")
    print()
    print("Usage in Python:")
    print("  from opentaxi.simulator import Simulation")
    print("  import json")
    print("  ")
    print("  with open('examples/scenarios/benchmark_traffic_medium.json') as f:")
    print("      scenario = json.load(f)")
    print("  ")
    print("  sim = Simulation(...)")
    print("  sim.run()")
    print()
    print("These scenarios enable reproducible benchmarking without proprietary data.")
    print("=" * 70)


if __name__ == "__main__":
    main()
