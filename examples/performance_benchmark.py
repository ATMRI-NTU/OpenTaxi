#!/usr/bin/env python3
"""Performance benchmarking for OpenTaxi simulator scalability.

Measures wall-clock time per simulated hour across different traffic
densities (5–100 aircraft). Documents computational requirements for
practitioners evaluating whether OpenTaxi is suitable for their use case.

Usage:
    python3 performance_benchmark.py [--output results.csv]

Results are written to CSV and printed as formatted table.
"""

import time
import numpy as np
import csv
import argparse
from pathlib import Path

# Add parent directory to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from opentaxi.airport import AirportMap
from opentaxi.simulator import Simulation
from opentaxi.planners import AStarPlanner
from opentaxi.controller import Opt_StopGo


def run_benchmark(num_aircraft, airport_path, duration_seconds=600, timestep_seconds=5):
    """Run single benchmark trial.
    
    Args:
        num_aircraft: Number of concurrent aircraft.
        airport_path: Path to airport GraphML.
        duration_seconds: Simulation duration in seconds (not wall-clock).
        timestep_seconds: Simulation step size.
    
    Returns:
        Dictionary with benchmark metrics:
        - num_aircraft: Aircraft count
        - wall_clock_time_sec: Actual elapsed time
        - simulated_hours: Simulated time
        - wall_clock_per_simulated_hour: Computational cost
        - throughput: Aircraft per simulated hour
    """
    
    # Load airport and planners
    airport = AirportMap(airport_path)
    planner = AStarPlanner(airport)
    controller = Opt_StopGo(airport)
    
    # Create simulator with specified number of aircraft
    # Note: Visualization is disabled by default in headless mode.
    # To enable visualization, uncomment: sim.init_visualization()
    sim = Simulation(
        airport,
        planner,
        controller,
        num_agents=num_aircraft
    )
    
    # Time the simulation
    start_time = time.time()
    results = sim.run(max_steps=duration_seconds // timestep_seconds)
    end_time = time.time()
    
    wall_clock_time = end_time - start_time
    simulated_hours = duration_seconds / 3600.0
    wall_clock_per_hour = wall_clock_time / simulated_hours if simulated_hours > 0 else 0
    
    return {
        'num_aircraft': num_aircraft,
        'wall_clock_time_sec': wall_clock_time,
        'simulated_hours': simulated_hours,
        'wall_clock_per_simulated_hour': wall_clock_per_hour,
        'throughput': num_aircraft / simulated_hours if simulated_hours > 0 else 0
    }


def main():
    """Run full benchmark suite."""
    
    parser = argparse.ArgumentParser(
        description="OpenTaxi performance benchmarking"
    )
    parser.add_argument(
        '--output', '-o',
        default='performance_benchmark_results.csv',
        help='Output CSV file'
    )
    parser.add_argument(
        '--airport', '-a',
        default='opentaxi/airport_map/changi.graphml',
        help='Airport GraphML path'
    )
    args = parser.parse_args()
    
    # Benchmark configurations
    num_aircraft_list = [5, 10, 20, 50, 100]
    duration_seconds = 600  # 10 min simulated time
    
    print("=" * 80)
    print("OpenTaxi Performance Benchmark")
    print("=" * 80)
    print()
    print(f"Airport: {args.airport}")
    print(f"Simulated duration: {duration_seconds}s per trial")
    print(f"Test aircraft counts: {num_aircraft_list}")
    print()
    print("Running benchmarks (this may take 5-10 minutes)...")
    print()
    
    results = []
    
    for num_aircraft in num_aircraft_list:
        print(f"Testing {num_aircraft:3d} aircraft...", end=" ", flush=True)
        
        try:
            trial_result = run_benchmark(
                num_aircraft,
                args.airport,
                duration_seconds=duration_seconds,
                timestep_seconds=5
            )
            results.append(trial_result)
            
            wall_clock = trial_result['wall_clock_time_sec']
            wall_clock_per_hour = trial_result['wall_clock_per_simulated_hour']
            
            print(f"✓ {wall_clock:.2f}s wall-clock ({wall_clock_per_hour:.1f}s per sim-hour)")
            
        except Exception as e:
            print(f"✗ FAILED: {e}")
            # Continue with other tests
    
    print()
    print("=" * 80)
    print("RESULTS SUMMARY")
    print("=" * 80)
    print()
    
    # Print formatted table
    print(f"{'Aircraft':>12} {'Wall-Clock (s)':>18} {'Per Sim-Hour (s)':>20} {'Throughput (ac/hr)':>20}")
    print("-" * 70)
    
    for result in results:
        ac = result['num_aircraft']
        wc = result['wall_clock_time_sec']
        wc_per_hr = result['wall_clock_per_simulated_hour']
        throughput = result['throughput']
        
        print(f"{ac:>12d} {wc:>18.2f} {wc_per_hr:>20.1f} {throughput:>20.1f}")
    
    print()
    print("INTERPRETATION:")
    print("-" * 70)
    print("Wall-Clock (s):        Actual time to run the simulation")
    print("Per Sim-Hour (s):      Seconds of wall-clock time per hour of")
    print("                       simulated time (lower is better)")
    print("Throughput (ac/hr):    Number of aircraft per simulated hour")
    print()
    
    # Estimate scaling
    if len(results) >= 2:
        ac1, wc1 = results[0]['num_aircraft'], results[0]['wall_clock_per_simulated_hour']
        ac2, wc2 = results[-1]['num_aircraft'], results[-1]['wall_clock_per_simulated_hour']
        
        scaling_factor = (wc2 / wc1) / (ac2 / ac1)
        print(f"Computational Scaling: {scaling_factor:.2f}x")
        
        if scaling_factor < 1.5:
            print("  ✓ Sub-linear scaling (efficient)")
        elif scaling_factor < 2.5:
            print("  ~ Near-linear scaling (expected)")
        else:
            print("  ⚠ Super-linear scaling (consider optimization)")
    
    print()
    print("=" * 80)
    print()
    
    # Save to CSV
    output_path = Path(args.output)
    with open(output_path, 'w', newline='') as csvfile:
        fieldnames = [
            'num_aircraft',
            'wall_clock_time_sec',
            'simulated_hours',
            'wall_clock_per_simulated_hour',
            'throughput'
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    
    print(f"Results saved to: {output_path}")
    print()
    print("Recommendations:")
    print("-" * 70)
    print("• For real-time control (wall-clock ≤ sim-time):")
    print("  Keep aircraft count < 20 or use faster hardware")
    print()
    print("• For RL training (parallel episodes):")
    print("  Each episode simulates 10-60 min with 10-50 aircraft")
    print("  Run multiple episodes in parallel on different cores")
    print()
    print("• For validation/benchmarking:")
    print("  10-50 aircraft for 10-60 min is comfortable range")
    print()


if __name__ == "__main__":
    main()
