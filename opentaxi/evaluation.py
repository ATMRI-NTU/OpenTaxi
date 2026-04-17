"""Evaluation metrics for path planning and simulation performance.

* :class:`PlannerEvaluator` – analyses individual path quality (length,
  turns, smoothness, edge utilisation).
* :class:`SchedulerEvaluator` – tracks runtime simulation metrics
  (conflicts, taxi times, throughput).
"""

import numpy as np
from collections import defaultdict


# ======================================================================
# Planner Evaluator
# ======================================================================

class PlannerEvaluator:
    """Evaluate path-planning quality metrics."""

    def __init__(self, airport_map, planner=None, turn_threshold=15.0):
        """
        Args:
            airport_map: :class:`AirportMap` instance.
            planner: Planner instance (required for batch evaluation).
            turn_threshold: Minimum angle (degrees) counted as a turn.
        """
        self.airport_map = airport_map
        self.planner = planner
        self.turn_threshold = turn_threshold

        self.total_edge_length = sum(airport_map.way_dict["length"])
        self.total_edge_count = len(airport_map.way_dict["length"])

    # ---- Single path ----

    def evaluate(self, aircraft):
        """Return a dict of quality metrics for one aircraft path."""
        metrics = {
            'ac_id': getattr(aircraft, 'id', -1),
            'start_idx': getattr(aircraft, 'start_idx', None),
            'end_idx': getattr(aircraft, 'end_idx', None),
            'path_length': 0.0,
            'num_turns': 0,
            'turn_angles': [],
            'total_turn_angle': 0.0,
            'avg_turn_angle': 0.0,
            'max_turn_angle': 0.0,
            'num_edges': 0,
            'edge_length_used': 0.0,
            'edge_occupancy_rate': 0.0,
            'path_smoothness': 0.0,
            'avg_edge_length': 0.0,
        }
        if aircraft.path is None or len(aircraft.path) < 2:
            return metrics

        metrics['path_length'] = self._compute_path_length(aircraft)

        turn_info = self._analyze_turns(aircraft)
        metrics.update({k: turn_info[k] for k in turn_info})

        edge_info = self._analyze_edges(aircraft)
        metrics.update({k: edge_info[k] for k in edge_info})

        metrics['path_smoothness'] = self._compute_smoothness(aircraft)
        return metrics

    def evaluate_path(self, path, path_nodes,
                      start_idx=None, end_idx=None):
        """Evaluate a path directly (without an Aircraft object)."""
        class _Holder:
            pass
        h = _Holder()
        h.id = -1
        h.path = path
        h.path_nodes = path_nodes
        h.start_idx = start_idx
        h.end_idx = end_idx
        h.path_s = np.zeros(len(path))
        if len(path) > 1:
            ds = np.sqrt(np.sum(np.diff(path, axis=0)**2, axis=1))
            h.path_s[1:] = np.cumsum(ds)
        return self.evaluate(h)

    # ---- Batch ----

    def evaluate_all(self, aircrafts):
        """Evaluate all aircraft paths and return a list of dicts."""
        return [self.evaluate(ac) for ac in aircrafts.values()]

    def evaluate_all_gates_to_runway(self, runway_node_idx=None,
                                     visualize_failed=False):
        """Plan and evaluate paths from every gate to a runway node."""
        if self.planner is None:
            raise ValueError("Planner not set.")

        valid_starts = self.airport_map.get_valid_parking_startpoints()
        valid_ends = self.airport_map.get_valid_runway_endpoints()
        if not valid_starts or not valid_ends:
            print("Error: No valid start/end points found")
            return []

        if runway_node_idx is None:
            runway_node_idx = valid_ends[0]

        print(f"Target runway: {runway_node_idx}, "
              f"Gates: {len(valid_starts)}")

        # Build taxiway edge length lookup
        taxiway_edges = {}
        for i in range(len(self.airport_map.way_dict["aeroway"])):
            if self.airport_map.way_dict["aeroway"][i] == "taxiway":
                u = str(self.airport_map.way_dict["start_idx"][i])
                v = str(self.airport_map.way_dict["end_idx"][i])
                taxiway_edges[tuple(sorted([u, v]))] = (
                    self.airport_map.way_dict["length"][i])

        total_taxiway_length = sum(taxiway_edges.values()) / 2

        results = []
        successful = failed = 0
        used_edges = set()
        total_path_length = 0.0

        for sid in valid_starts:
            start_idx = str(sid)
            end_idx = str(runway_node_idx)
            try:
                path, path_nodes = self.planner.plan_minimum_turn_path(
                    start_idx, end_idx)
                if path is not None and len(path) > 0:
                    metrics = self.evaluate_path(
                        path, path_nodes, start_idx, end_idx)
                    results.append(metrics)
                    successful += 1
                    for i in range(len(path_nodes) - 1):
                        ek = tuple(sorted(
                            [str(path_nodes[i]), str(path_nodes[i + 1])]))
                        if ek in taxiway_edges:
                            used_edges.add(ek)
                            total_path_length += taxiway_edges[ek]
                else:
                    failed += 1
            except Exception:
                failed += 1

        used_len = sum(taxiway_edges[e] for e in used_edges)
        util = used_len / total_path_length if total_path_length > 0 else 0
        coverage = (used_len / total_taxiway_length
                    if total_taxiway_length > 0 else 0)

        print(f"Results: {successful} ok, {failed} failed | "
              f"Utilisation {util:.2%} | Coverage {coverage:.2%}")
        return results

    # ---- Metric helpers ----

    def _compute_path_length(self, aircraft):
        if hasattr(aircraft, 'path_s') and len(aircraft.path_s) > 0:
            return aircraft.path_s[-1]
        ds = np.sqrt(np.sum(np.diff(aircraft.path, axis=0)**2, axis=1))
        return np.sum(ds)

    def _analyze_turns(self, aircraft):
        result = {
            'num_turns': 0, 'turn_angles': [], 'total_turn_angle': 0.0,
            'avg_turn_angle': 0.0, 'max_turn_angle': 0.0,
        }
        if (not hasattr(aircraft, 'path_nodes')
                or len(aircraft.path_nodes) < 3):
            return result

        pn = aircraft.path_nodes
        angles = []
        for i in range(len(pn) - 2):
            _, h_ab = self.airport_map.get_edge_heading(pn[i], pn[i + 1])
            h_bc, _ = self.airport_map.get_edge_heading(pn[i + 1], pn[i + 2])
            ta = abs(np.degrees(self._normalize_angle(h_bc - h_ab)))
            if ta >= self.turn_threshold:
                angles.append(ta)

        result['turn_angles'] = angles
        result['num_turns'] = len(angles)
        result['total_turn_angle'] = sum(angles)
        result['avg_turn_angle'] = np.mean(angles) if angles else 0.0
        result['max_turn_angle'] = max(angles) if angles else 0.0
        return result

    def _analyze_edges(self, aircraft):
        result = {
            'num_edges': 0, 'edge_length_used': 0.0,
            'edge_occupancy_rate': 0.0, 'avg_edge_length': 0.0,
        }
        if (not hasattr(aircraft, 'path_nodes')
                or len(aircraft.path_nodes) < 2):
            return result

        lengths = []
        for i in range(len(aircraft.path_nodes) - 1):
            u, v = aircraft.path_nodes[i], aircraft.path_nodes[i + 1]
            el = self.airport_map.get_edge_length(u, v)
            if el < float('inf'):
                lengths.append(el)

        result['num_edges'] = len(lengths)
        result['edge_length_used'] = sum(lengths)
        result['edge_occupancy_rate'] = (
            result['edge_length_used'] / self.total_edge_length
            if self.total_edge_length > 0 else 0.0)
        result['avg_edge_length'] = np.mean(lengths) if lengths else 0.0
        return result

    def _compute_smoothness(self, aircraft):
        path = aircraft.path
        if len(path) < 3:
            return 0.0
        dx = np.diff(path[:, 0])
        dy = np.diff(path[:, 1])
        headings = np.arctan2(dy, dx)
        dh = np.diff(headings)
        dh = np.arctan2(np.sin(dh), np.cos(dh))
        return np.std(np.abs(dh))

    def _normalize_angle(self, angle):
        while angle > np.pi:
            angle -= 2 * np.pi
        while angle < -np.pi:
            angle += 2 * np.pi
        return angle

    # ---- Reporting ----

    def print_metrics(self, metrics):
        print(f"\nPath {metrics.get('start_idx', '?')} -> "
              f"{metrics.get('end_idx', '?')}")
        print(f"  Length:       {metrics['path_length']:.1f} m")
        print(f"  Edges:        {metrics['num_edges']}")
        print(f"  Turns:        {metrics['num_turns']}")
        print(f"  Total angle:  {metrics['total_turn_angle']:.1f} deg")
        print(f"  Smoothness:   {metrics['path_smoothness']:.4f}")

    def print_summary(self, results):
        if not results:
            return
        lengths = [m['path_length'] for m in results]
        turns = [m['num_turns'] for m in results]
        print(f"\nSummary ({len(results)} paths): "
              f"length {np.mean(lengths):.0f} +/- {np.std(lengths):.0f} m, "
              f"turns {np.mean(turns):.1f}")

    def save_to_csv(self, results, filename='path_evaluation.csv'):
        import csv
        with open(filename, 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['start_idx', 'end_idx', 'path_length', 'num_edges',
                         'num_turns', 'total_turn_angle', 'path_smoothness'])
            for m in results:
                w.writerow([m.get('start_idx', ''), m.get('end_idx', ''),
                            f"{m['path_length']:.2f}", m['num_edges'],
                            m['num_turns'], f"{m['total_turn_angle']:.2f}",
                            f"{m['path_smoothness']:.6f}"])
        print(f"Results saved to {filename}")

    def get_edge_usage_stats(self, aircrafts):
        edge_usage = {}
        for ac in aircrafts.values():
            if not hasattr(ac, 'path_nodes') or len(ac.path_nodes) < 2:
                continue
            for i in range(len(ac.path_nodes) - 1):
                edge = (ac.path_nodes[i], ac.path_nodes[i + 1])
                edge_usage[edge] = edge_usage.get(edge, 0) + 1
        counts = list(edge_usage.values())
        return {
            'total_unique_edges': len(edge_usage),
            'total_traversals': sum(counts),
            'max_usage': max(counts) if counts else 0,
            'avg_usage': np.mean(counts) if counts else 0,
            'shared_edges': sum(1 for c in counts if c > 1),
        }


# ======================================================================
# Scheduler Evaluator
# ======================================================================

class SchedulerEvaluator:
    """Runtime performance evaluator for multi-aircraft simulation."""

    def __init__(self, conflict_threshold=50.0, time_step_duration=5.0,
                 start_ignore_distance=100.0):
        """
        Args:
            conflict_threshold: Conflict distance in metres.
            time_step_duration: Duration of each time step in seconds.
            start_ignore_distance: Ignore conflicts within this many
                metres of the start position.
        """
        self.conflict_threshold = conflict_threshold
        self.time_step_duration = time_step_duration
        self.start_ignore_distance = start_ignore_distance
        self.reset()

    def reset(self):
        self.metrics = {
            'conflict_count': 0,
            'conflict_pairs': set(),
            'conflict_history': [],
            'aircraft_stats': {},
            'completed_count': 0,
            'total_taxi_time': 0.0,
        }
        self.timestep = 0

    def register_aircraft(self, ac_id, path_length=0.0):
        """Register an aircraft and initialise its statistics."""
        self.metrics['aircraft_stats'][ac_id] = {
            'start_time': None,
            'first_move_detected': False,
            'initial_s': 0.0,
            'end_time': None,
            'taxi_time': None,
            'distance': path_length,
            'completed': False,
        }

    def update(self, aircrafts, timestep):
        """Called every simulation step to update all metrics."""
        self.timestep = timestep
        self._check_movement_start(aircrafts)
        self._detect_conflicts(aircrafts)
        self._check_completions(aircrafts)

    # ---- Internal ----

    def _check_movement_start(self, aircrafts):
        for ac_id, ac in aircrafts.items():
            stats = self.metrics['aircraft_stats'].get(ac_id)
            if stats is None or stats['first_move_detected']:
                continue
            curr_s = getattr(ac, 'curr_s', 0)
            curr_v = getattr(ac, 'curr_v', 0)
            if stats['initial_s'] == 0.0 and curr_s > 0:
                stats['initial_s'] = curr_s
            if curr_s > stats['initial_s'] + 1.0 or curr_v > 0.5:
                stats['first_move_detected'] = True
                stats['start_time'] = self.timestep * self.time_step_duration

    def _detect_conflicts(self, aircrafts):
        active = [(k, v) for k, v in aircrafts.items() if not v.done]
        for i, (id1, ac1) in enumerate(active):
            for id2, ac2 in active[i + 1:]:
                s1 = getattr(ac1, 'curr_s', 0)
                s2 = getattr(ac2, 'curr_s', 0)
                if (s1 < self.start_ignore_distance
                        and s2 < self.start_ignore_distance):
                    continue
                dist = np.sqrt((ac1.x - ac2.x)**2 + (ac1.y - ac2.y)**2)
                if dist < self.conflict_threshold:
                    pair = frozenset([id1, id2])
                    if pair not in self.metrics['conflict_pairs']:
                        self.metrics['conflict_pairs'].add(pair)
                        self.metrics['conflict_count'] += 1
                        self.metrics['conflict_history'].append({
                            'timestep': self.timestep,
                            'time': self.timestep * self.time_step_duration,
                            'aircraft_1': id1,
                            'aircraft_2': id2,
                            'distance': dist,
                        })

    def _check_completions(self, aircrafts):
        for ac_id, ac in aircrafts.items():
            stats = self.metrics['aircraft_stats'].get(ac_id)
            if stats is None:
                continue
            if ac.done and not stats['completed']:
                self.record_completion(ac_id)

    def record_completion(self, ac_id):
        stats = self.metrics['aircraft_stats'].get(ac_id)
        if stats is None or stats['completed']:
            return
        stats['end_time'] = self.timestep * self.time_step_duration
        if stats['start_time'] is None:
            stats['start_time'] = 0
        stats['taxi_time'] = stats['end_time'] - stats['start_time']
        stats['completed'] = True
        self.metrics['completed_count'] += 1
        self.metrics['total_taxi_time'] += stats['taxi_time']

    def finalize(self, aircrafts=None):
        """Call at end of simulation to ensure all completions recorded."""
        if aircrafts is None:
            return
        for ac_id, ac in aircrafts.items():
            stats = self.metrics['aircraft_stats'].get(ac_id)
            if stats is None:
                continue
            if ac.done and not stats['completed']:
                self.record_completion(ac_id)

    # ---- Reporting ----

    def get_metrics(self):
        """Return a summary dict of all metrics."""
        completed = [s for s in self.metrics['aircraft_stats'].values()
                     if s.get('completed')]
        avg_taxi = (self.metrics['total_taxi_time'] / len(completed)
                    if completed else 0)
        sim_time = self.timestep * self.time_step_duration
        throughput = (self.metrics['completed_count'] / (sim_time / 3600)
                      if sim_time > 0 else 0)
        return {
            'conflict_count': self.metrics['conflict_count'],
            'conflict_threshold': self.conflict_threshold,
            'conflict_history': self.metrics['conflict_history'],
            'total_aircraft': len(self.metrics['aircraft_stats']),
            'completed_aircraft': self.metrics['completed_count'],
            'aircraft_stats': self.metrics['aircraft_stats'],
            'total_taxi_time': self.metrics['total_taxi_time'],
            'avg_taxi_time': avg_taxi,
            'simulation_time': sim_time,
            'throughput_per_hour': throughput,
        }

    def print_report(self):
        """Print a formatted performance report."""
        m = self.get_metrics()
        print("\n" + "=" * 60)
        print("         SIMULATION PERFORMANCE REPORT")
        print("=" * 60)
        print(f"  Simulation Time:    {m['simulation_time']:.1f}s "
              f"({m['simulation_time']/60:.1f} min)")
        print(f"  Total Aircraft:     {m['total_aircraft']}")
        print(f"  Completed:          {m['completed_aircraft']}")
        print(f"  Conflicts:          {m['conflict_count']} "
              f"(threshold {m['conflict_threshold']}m)")
        print(f"  Avg Taxi Time:      {m['avg_taxi_time']:.1f}s")
        print(f"  Throughput:         "
              f"{m['throughput_per_hour']:.2f} ac/hr")
        print("=" * 60)
        return m

    def export_to_csv(self, filepath):
        """Export metrics to a CSV file."""
        import csv
        m = self.get_metrics()
        with open(filepath, 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['Metric', 'Value'])
            w.writerow(['Conflict Count', m['conflict_count']])
            w.writerow(['Total Aircraft', m['total_aircraft']])
            w.writerow(['Completed', m['completed_aircraft']])
            w.writerow(['Total Taxi Time (s)', m['total_taxi_time']])
            w.writerow(['Avg Taxi Time (s)', m['avg_taxi_time']])
            w.writerow(['Throughput (ac/hr)', m['throughput_per_hour']])
            w.writerow([])
            w.writerow(['AC_ID', 'Completed', 'Taxi_Time', 'Distance'])
            for ac_id, s in sorted(m['aircraft_stats'].items()):
                w.writerow([ac_id, s.get('completed'),
                            s.get('taxi_time', ''), s.get('distance', 0)])
        print(f"Exported to {filepath}")

    def export_to_json(self, filepath):
        """Export metrics to a JSON file."""
        import json
        m = self.get_metrics()
        with open(filepath, 'w') as f:
            json.dump(m, f, indent=2, default=str)
        print(f"Exported to {filepath}")
