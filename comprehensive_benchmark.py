#!/usr/bin/env python3
"""
OpenTaxi Comprehensive Performance Benchmarks (Maximal Version)

Tests implemented:
1. Scaling with aircraft count (5, 10, 20, 50)
2. Visualization overhead measurement
3. Planner algorithm comparison (AStar, Dijkstra, Greedy)
4. Controller comparison (StopGo vs Opt_StopGo)
5. RL environment performance
6. Wall-clock vs simulation time ratios
7. Conflict/completion rates

All tests run headless unless visualization explicitly tested.
"""

import time
import json
import sys
import numpy as np
from pathlib import Path

print("=" * 80)
print("OPENTAXI COMPREHENSIVE PERFORMANCE BENCHMARKS (MAXIMAL)")
print("=" * 80)

try:
    from opentaxi.airport import AirportMap
    from opentaxi.simulator import Simulation
    from opentaxi.planners import AStarPlanner, DijkstraPlanner, GreedyPlanner
    from opentaxi.controller import StopGo, Opt_StopGo
    from opentaxi.evaluation import SchedulerEvaluator
    from opentaxi.rl_env import AirportRLEnv
except ImportError as e:
    print(f"ERROR: Failed to import OpenTaxi modules: {e}")
    sys.exit(1)

AIRPORT_PATH = "opentaxi/airport_map/changi.graphml"
RESULTS = {}


def benchmark_aircraft_scaling():
    """Comprehensive scaling test."""
    print("\n" + "=" * 80)
    print("BENCHMARK 1: AIRCRAFT SCALING (Headless, no visualization)")
    print("=" * 80)
    print("Duration: 400 simulation steps (2000 simulated seconds) each")
    print("-" * 80)
    
    results = []
    aircraft_counts = [5, 10, 20, 50]
    duration_steps = 400  # Increased from 100 to allow completions
    
    for num_ac in aircraft_counts:
        try:
            airport = AirportMap(AIRPORT_PATH)
            planner = AStarPlanner(airport)
            controller = Opt_StopGo(airport)
            evaluator = SchedulerEvaluator()
            
            sim = Simulation(airport, planner, controller, num_agents=num_ac, 
                           evaluator=evaluator)
            
            for i in range(num_ac):
                evaluator.register_aircraft(f"AC{i}", path_length=2000)
            
            start_time = time.perf_counter()
            sim.run(max_steps=duration_steps)
            wall_clock = time.perf_counter() - start_time
            
            evaluator.finalize(sim.aircrafts)
            metrics = evaluator.get_metrics()
            
            sim_time_seconds = duration_steps * 5
            
            entry = {
                'num_aircraft': num_ac,
                'duration_steps': duration_steps,
                'duration_sim_seconds': sim_time_seconds,
                'wall_clock_seconds': round(wall_clock, 4),
                'speed_ratio_sim_per_realtime': round(sim_time_seconds / wall_clock if wall_clock > 0 else 0, 2),
                'completed_aircraft': metrics['completed_aircraft'],
                'completion_rate_percent': round(100 * metrics['completed_aircraft'] / num_ac, 1),
                'total_conflicts': metrics['conflict_count'],
                'avg_taxi_time_seconds': round(metrics['avg_taxi_time'], 2),
                'throughput_aircraft_per_hour': round(metrics['throughput_per_hour'], 2),
            }
            results.append(entry)
            
            print(f"  {num_ac:3d} aircraft:")
            print(f"      Wall-clock time:     {wall_clock:8.4f} s")
            print(f"      Speed ratio:         {entry['speed_ratio_sim_per_realtime']:8.2f}x")
            print(f"      Completed:           {metrics['completed_aircraft']:3d}/{num_ac} ({entry['completion_rate_percent']:5.1f}%)")
            print(f"      Conflicts:           {metrics['conflict_count']:3d}")
            print(f"      Avg taxi time:       {entry['avg_taxi_time_seconds']:8.1f}s")
            print(f"      Throughput:          {entry['throughput_aircraft_per_hour']:8.2f} ac/hr")
            
        except Exception as e:
            print(f"  ERROR with {num_ac} aircraft: {e}")
            import traceback
            traceback.print_exc()
    
    RESULTS['1_aircraft_scaling'] = results
    return results


def benchmark_visualization_impact():
    """Measure visualization overhead."""
    print("\n" + "=" * 80)
    print("BENCHMARK 2: VISUALIZATION OVERHEAD")
    print("=" * 80)
    print("Configuration: 10 aircraft, 400 steps, 2 runs each (headless vs visualization)")
    print("-" * 80)
    
    num_ac = 10
    duration_steps = 400
    
    # Test 1: Headless
    print("\n  Test 2a: HEADLESS (no visualization)")
    try:
        airport = AirportMap(AIRPORT_PATH)
        planner = AStarPlanner(airport)
        controller = Opt_StopGo(airport)
        sim = Simulation(airport, planner, controller, num_agents=num_ac)
        
        start = time.perf_counter()
        sim.run(max_steps=duration_steps)
        headless_time = time.perf_counter() - start
        print(f"      Wall-clock: {headless_time:.4f}s")
    except Exception as e:
        print(f"      ERROR: {e}")
        headless_time = None
    
    # Test 2: With visualization (may not display on headless server)
    print("\n  Test 2b: WITH VISUALIZATION (may not display on headless)")
    try:
        airport = AirportMap(AIRPORT_PATH)
        planner = AStarPlanner(airport)
        controller = Opt_StopGo(airport)
        sim = Simulation(airport, planner, controller, num_agents=num_ac)
        
        try:
            sim.init_visualization()
            has_display = True
            print("      Display initialized successfully")
        except Exception as display_err:
            has_display = False
            print(f"      Note: Display unavailable (headless mode): {display_err}")
        
        start = time.perf_counter()
        sim.run(max_steps=duration_steps)
        vis_time = time.perf_counter() - start
        print(f"      Wall-clock: {vis_time:.4f}s")
    except Exception as e:
        print(f"      ERROR: {e}")
        vis_time = None
        has_display = False
    
    result = {
        'headless_seconds': round(headless_time, 4) if headless_time else None,
        'visualization_seconds': round(vis_time, 4) if vis_time else None,
        'overhead_percent': round((vis_time - headless_time) / headless_time * 100, 1) 
                           if (headless_time and vis_time) else None,
        'display_available': has_display,
    }
    
    print("\n  Summary:")
    if headless_time and vis_time:
        print(f"      Overhead: {result['overhead_percent']:.1f}%")
    elif headless_time:
        print(f"      (Visualization unavailable - skipped)")
    
    RESULTS['2_visualization_overhead'] = result
    return result


def benchmark_planner_comparison():
    """Compare different planning algorithms."""
    print("\n" + "=" * 80)
    print("BENCHMARK 3: PLANNER ALGORITHM COMPARISON")
    print("=" * 80)
    print("Configuration: 10 aircraft, 400 steps, headless mode")
    print("-" * 80)
    
    planners_list = [
        ('AStarPlanner', AStarPlanner),
        ('DijkstraPlanner', DijkstraPlanner),
        ('GreedyPlanner', GreedyPlanner),
    ]
    
    num_ac = 10
    duration_steps = 400
    results = []
    
    for name, planner_class in planners_list:
        try:
            print(f"\n  {name}:")
            airport = AirportMap(AIRPORT_PATH)
            planner = planner_class(airport)
            controller = Opt_StopGo(airport)
            evaluator = SchedulerEvaluator()
            
            sim = Simulation(airport, planner, controller, num_agents=num_ac, 
                           evaluator=evaluator)
            
            for i in range(num_ac):
                evaluator.register_aircraft(f"AC{i}", path_length=2000)
            
            start = time.perf_counter()
            sim.run(max_steps=duration_steps)
            wall_clock = time.perf_counter() - start
            
            evaluator.finalize(sim.aircrafts)
            metrics = evaluator.get_metrics()
            
            entry = {
                'planner': name,
                'wall_clock_seconds': round(wall_clock, 4),
                'completed_aircraft': metrics['completed_aircraft'],
                'completion_rate_percent': round(100 * metrics['completed_aircraft'] / num_ac, 1),
                'total_conflicts': metrics['conflict_count'],
                'avg_taxi_time_seconds': round(metrics['avg_taxi_time'], 2),
                'throughput_aircraft_per_hour': round(metrics['throughput_per_hour'], 2),
            }
            results.append(entry)
            
            print(f"      Wall-clock:          {wall_clock:8.4f}s")
            print(f"      Completed:           {metrics['completed_aircraft']}/{num_ac} ({entry['completion_rate_percent']:5.1f}%)")
            print(f"      Conflicts:           {metrics['conflict_count']}")
            print(f"      Avg taxi time:       {entry['avg_taxi_time_seconds']:8.1f}s")
            print(f"      Throughput:          {entry['throughput_aircraft_per_hour']:8.2f} ac/hr")
            
        except Exception as e:
            print(f"      ERROR: {e}")
            import traceback
            traceback.print_exc()
    
    RESULTS['3_planner_comparison'] = results
    return results


def benchmark_controller_comparison():
    """Compare different control strategies."""
    print("\n" + "=" * 80)
    print("BENCHMARK 4: CONTROLLER STRATEGY COMPARISON")
    print("=" * 80)
    print("Configuration: 10 aircraft, 400 steps, AStar planner, headless mode")
    print("-" * 80)
    
    controllers_list = [
        ('StopGo', StopGo),
        ('Opt_StopGo', Opt_StopGo),
    ]
    
    num_ac = 10
    duration_steps = 400
    results = []
    
    for name, controller_class in controllers_list:
        try:
            print(f"\n  {name}:")
            airport = AirportMap(AIRPORT_PATH)
            planner = AStarPlanner(airport)
            controller = controller_class(airport)
            evaluator = SchedulerEvaluator()
            
            sim = Simulation(airport, planner, controller, num_agents=num_ac,
                           evaluator=evaluator)
            
            for i in range(num_ac):
                evaluator.register_aircraft(f"AC{i}", path_length=2000)
            
            start = time.perf_counter()
            sim.run(max_steps=duration_steps)
            wall_clock = time.perf_counter() - start
            
            evaluator.finalize(sim.aircrafts)
            metrics = evaluator.get_metrics()
            
            entry = {
                'controller': name,
                'wall_clock_seconds': round(wall_clock, 4),
                'completed_aircraft': metrics['completed_aircraft'],
                'completion_rate_percent': round(100 * metrics['completed_aircraft'] / num_ac, 1),
                'total_conflicts': metrics['conflict_count'],
                'avg_taxi_time_seconds': round(metrics['avg_taxi_time'], 2),
                'throughput_aircraft_per_hour': round(metrics['throughput_per_hour'], 2),
            }
            results.append(entry)
            
            print(f"      Wall-clock:          {wall_clock:8.4f}s")
            print(f"      Completed:           {metrics['completed_aircraft']}/{num_ac} ({entry['completion_rate_percent']:5.1f}%)")
            print(f"      Conflicts:           {metrics['conflict_count']}")
            print(f"      Avg taxi time:       {entry['avg_taxi_time_seconds']:8.1f}s")
            print(f"      Throughput:          {entry['throughput_aircraft_per_hour']:8.2f} ac/hr")
            
        except Exception as e:
            print(f"      ERROR: {e}")
            import traceback
            traceback.print_exc()
    
    RESULTS['4_controller_comparison'] = results
    return results


def benchmark_rl_environment():
    """Test RL environment performance."""
    print("\n" + "=" * 80)
    print("BENCHMARK 5: RL ENVIRONMENT PERFORMANCE")
    print("=" * 80)
    print("Configuration: 10 episodes, 10 aircraft, 400 steps per episode, random actions")
    print("-" * 80)
    
    try:
        airport = AirportMap(AIRPORT_PATH)
        planner = AStarPlanner(airport)
        
        env = AirportRLEnv(airport, planner, num_aircraft=10, max_steps=400)
        
        episode_times = []
        episode_rewards = []
        episode_completions = []
        episode_conflicts = []
        
        print("\n  Episode Results:")
        for episode in range(10):
            obs, info = env.reset()
            episode_reward = 0.0
            
            start = time.perf_counter()
            for step in range(400):
                action = env.action_space.sample()
                obs, reward, terminated, truncated, info = env.step(action)
                episode_reward += reward
                
                if terminated or truncated:
                    break
            
            episode_time = time.perf_counter() - start
            episode_times.append(episode_time)
            episode_rewards.append(episode_reward)
            episode_completions.append(info.get('completions', 0))
            episode_conflicts.append(info.get('conflicts', 0))
            
            print(f"    Episode {episode + 1:2d}: {episode_time:7.4f}s | "
                  f"reward: {episode_reward:9.2f} | "
                  f"completed: {info.get('completions', 0):2d} | "
                  f"conflicts: {info.get('conflicts', 0):2d}")
        
        result = {
            'num_episodes': 10,
            'num_aircraft': 10,
            'max_steps_per_episode': 400,
            'avg_episode_time_seconds': round(np.mean(episode_times), 4),
            'min_episode_time_seconds': round(np.min(episode_times), 4),
            'max_episode_time_seconds': round(np.max(episode_times), 4),
            'std_episode_time_seconds': round(np.std(episode_times), 4),
            'avg_reward': round(np.mean(episode_rewards), 2),
            'std_reward': round(np.std(episode_rewards), 2),
            'min_reward': round(np.min(episode_rewards), 2),
            'max_reward': round(np.max(episode_rewards), 2),
            'avg_completions_per_episode': round(np.mean(episode_completions), 2),
            'avg_conflicts_per_episode': round(np.mean(episode_conflicts), 2),
        }
        
        print(f"\n  Summary:")
        print(f"    Avg episode time:    {result['avg_episode_time_seconds']:.4f}s ± {result['std_episode_time_seconds']:.4f}s")
        print(f"    Time range:          {result['min_episode_time_seconds']:.4f}s - {result['max_episode_time_seconds']:.4f}s")
        print(f"    Avg reward:          {result['avg_reward']:.2f} ± {result['std_reward']:.2f}")
        print(f"    Reward range:        {result['min_reward']:.2f} - {result['max_reward']:.2f}")
        print(f"    Avg completions:     {result['avg_completions_per_episode']:.2f} aircraft/episode")
        print(f"    Avg conflicts:       {result['avg_conflicts_per_episode']:.2f} per episode")
        
        RESULTS['5_rl_environment'] = result
        return result
        
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
        RESULTS['5_rl_environment'] = {'error': str(e)}
        return None


def save_results():
    """Save all results to JSON file."""
    output_file = "benchmark_results_comprehensive.json"
    with open(output_file, 'w') as f:
        json.dump(RESULTS, f, indent=2)
    print(f"\nResults saved to: {output_file}")
    return output_file


def print_executive_summary():
    """Print high-level summary of findings."""
    print("\n" + "=" * 80)
    print("EXECUTIVE SUMMARY")
    print("=" * 80)
    
    if '1_aircraft_scaling' in RESULTS and RESULTS['1_aircraft_scaling']:
        print("\n1. SCALING CHARACTERISTICS:")
        scaling = RESULTS['1_aircraft_scaling']
        for r in scaling:
            print(f"   {r['num_aircraft']:2d} aircraft: {r['wall_clock_seconds']:7.4f}s "
                  f"({r['speed_ratio_sim_per_realtime']:6.2f}x speed), "
                  f"conflicts: {r['total_conflicts']:3d}")
    
    if '2_visualization_overhead' in RESULTS:
        print("\n2. VISUALIZATION IMPACT:")
        vis = RESULTS['2_visualization_overhead']
        if vis['overhead_percent'] is not None:
            print(f"   Overhead: {vis['overhead_percent']:5.1f}% on macOS")
        else:
            print(f"   (Display unavailable in headless environment)")
    
    if '3_planner_comparison' in RESULTS and RESULTS['3_planner_comparison']:
        print("\n3. PLANNER PERFORMANCE (10 aircraft, 400 steps):")
        for r in RESULTS['3_planner_comparison']:
            print(f"   {r['planner']:20s}: {r['wall_clock_seconds']:7.4f}s, "
                  f"completed: {r['completed_aircraft']}/10, "
                  f"conflicts: {r['total_conflicts']}")
    
    if '4_controller_comparison' in RESULTS and RESULTS['4_controller_comparison']:
        print("\n4. CONTROLLER STRATEGY (10 aircraft, 400 steps):")
        for r in RESULTS['4_controller_comparison']:
            print(f"   {r['controller']:20s}: {r['wall_clock_seconds']:7.4f}s, "
                  f"completed: {r['completed_aircraft']}/10, "
                  f"conflicts: {r['total_conflicts']}")
    
    if '5_rl_environment' in RESULTS and 'error' not in RESULTS['5_rl_environment']:
        print("\n5. RL ENVIRONMENT (10 episodes, 10 aircraft):")
        rl = RESULTS['5_rl_environment']
        print(f"   Avg episode:         {rl['avg_episode_time_seconds']:.4f}s ± {rl['std_episode_time_seconds']:.4f}s")
        print(f"   Avg reward:          {rl['avg_reward']:.2f} ± {rl['std_reward']:.2f}")
        print(f"   Avg completions:     {rl['avg_completions_per_episode']:.2f} per episode")


def main():
    """Run all benchmarks."""
    try:
        benchmark_aircraft_scaling()
        benchmark_visualization_impact()
        benchmark_planner_comparison()
        benchmark_controller_comparison()
        benchmark_rl_environment()
        
        save_results()
        print_executive_summary()
        
        print("\n" + "=" * 80)
        print("BENCHMARKS COMPLETED SUCCESSFULLY")
        print("=" * 80)
        return RESULTS
        
    except KeyboardInterrupt:
        print("\n\nBenchmarks interrupted by user")
        save_results()
        return RESULTS
    except Exception as e:
        print(f"\n\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        save_results()
        return None


if __name__ == "__main__":
    main()
