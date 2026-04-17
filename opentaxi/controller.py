"""Conflict detection and resolution controllers for multi-aircraft taxi.

Two controllers are provided:

* :class:`StopGo` – prediction-based FCFS conflict resolution.
* :class:`Opt_StopGo` – separation controller that maximises concurrent
  movement while maintaining a minimum separation distance.
"""

import numpy as np


class StopGo:
    """Prediction-based First-Come-First-Served conflict resolver.

    Algorithm:
        1. Predict each aircraft's reachable arc-length range over a
           time horizon.
        2. Check whether predicted path segments intersect spatially.
        3. The aircraft farther from the conflict point yields at the
           next graph node.
    """

    def __init__(self, airport_map, predict_horizon=20.0,
                 collision_buffer=50.0):
        """
        Args:
            airport_map: :class:`AirportMap` instance.
            predict_horizon: Look-ahead time in seconds.
            collision_buffer: Minimum separation distance in metres.
        """
        self.airport_map = airport_map
        self.predict_horizon = predict_horizon
        self.collision_buffer = collision_buffer

    def update(self, aircrafts):
        """Run one arbitration cycle over all aircraft."""
        active = {ac_id: ac for ac_id, ac in aircrafts.items()
                  if not ac.done}
        if len(active) < 2:
            for ac in active.values():
                self._clear_yield(ac)
            return

        # Predict future segments
        states = [self._get_arbitration_state(ac) for ac in active.values()]
        predictions = self._predict_segments(states)
        predicted_conflicts = self._detect_conflicts(predictions)

        yielders = {}

        for i, j, conflict_info in predicted_conflicts:
            pred_i = predictions[i]
            pred_j = predictions[j]
            dist_i = conflict_info['dist_i']
            dist_j = conflict_info['dist_j']

            # FCFS: closer aircraft has priority
            if dist_i <= dist_j:
                yielder_pred = pred_j
                priority_id = pred_i['ac_id']
            else:
                yielder_pred = pred_i
                priority_id = pred_j['ac_id']

            yielder_id = yielder_pred['ac_id']
            wait_node, wait_s = self._find_next_node(
                yielder_pred['curr_s'], yielder_pred['path_nodes'])

            if yielder_id not in yielders:
                yielders[yielder_id] = (wait_node, wait_s, priority_id)

        for ac_id, ac in active.items():
            if ac_id in yielders:
                wait_node, wait_s, conflict_with = yielders[ac_id]
                if not ac.yield_flag or ac.wait_at_s != wait_s:
                    self._set_yield(ac, True, wait_node, wait_s,
                                    conflict_with)
            else:
                self._clear_yield(ac)

    # ---- Aircraft interface ----

    def _get_arbitration_state(self, aircraft):
        return {
            'ac_id': aircraft.id,
            'x': (aircraft.path[:, 0]
                  if aircraft.path is not None and len(aircraft.path) > 0
                  else np.array([aircraft.x])),
            'y': (aircraft.path[:, 1]
                  if aircraft.path is not None and len(aircraft.path) > 0
                  else np.array([aircraft.y])),
            'path_s': (aircraft.path_s if len(aircraft.path_s) > 0
                       else np.array([0.0])),
            'curr_s': aircraft.curr_s,
            'path_nodes': getattr(aircraft, 'path_nodes', []),
            'min_pred_v': aircraft.min_pred_v,
            'max_pred_v': aircraft.max_pred_v,
            'done': aircraft.done,
        }

    def _set_yield(self, aircraft, yield_flag, wait_at_node=None,
                   wait_at_s=None, conflict_with=None):
        aircraft.yield_flag = yield_flag
        aircraft.wait_at_node = wait_at_node
        aircraft.wait_at_s = wait_at_s
        aircraft.conflict_with = conflict_with

    def _clear_yield(self, aircraft):
        aircraft.yield_flag = False
        aircraft.wait_at_node = None
        aircraft.wait_at_s = None
        aircraft.conflict_with = None

    # ---- Prediction ----

    def _predict_segments(self, states):
        predictions = []
        for state in states:
            curr_s = state['curr_s']
            path_s = state['path_s']
            path_length = path_s[-1] if len(path_s) > 0 else 0

            v_min = state['min_pred_v'] / 3.6
            v_max = state['max_pred_v'] / 3.6

            s_min = min(curr_s + v_min * self.predict_horizon, path_length)
            s_max = min(curr_s + v_max * self.predict_horizon, path_length)

            path_x = state['x']
            path_y = state['y']

            if len(path_x) > 0 and len(path_s) > 0:
                mask = (path_s >= curr_s) & (path_s <= s_max)
                segment = np.column_stack([path_x[mask], path_y[mask]])
                segment_path_s = path_s[mask]
            else:
                segment = np.array([])
                segment_path_s = np.array([])

            completion = curr_s / path_length if path_length > 0 else 0.0

            predictions.append({
                'ac_id': state['ac_id'],
                'curr_s': curr_s,
                's_min': s_min,
                's_max': s_max,
                'segment': segment,
                'path_s': segment_path_s,
                'path_nodes': state['path_nodes'],
                'completion': completion,
            })
        return predictions

    # ---- Conflict detection ----

    def _detect_conflicts(self, predictions):
        conflicts = []
        n = len(predictions)
        for i in range(n):
            for j in range(i + 1, n):
                info = self._find_conflict_point(
                    predictions[i], predictions[j])
                if info is not None:
                    conflicts.append((i, j, info))
        return conflicts

    def _find_conflict_point(self, pred_i, pred_j):
        seg1 = pred_i['segment']
        seg2 = pred_j['segment']
        path_s1 = pred_i.get('path_s', np.array([]))
        path_s2 = pred_j.get('path_s', np.array([]))

        if len(seg1) == 0 or len(seg2) == 0:
            return None

        step1 = max(1, len(seg1) // 50)
        step2 = max(1, len(seg2) // 50)

        min_dist = float('inf')
        conflict_point = None
        s_at_i = s_at_j = None

        for idx1 in range(0, len(seg1), step1):
            p1 = seg1[idx1]
            for idx2 in range(0, len(seg2), step2):
                p2 = seg2[idx2]
                dist = np.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)
                if dist < self.collision_buffer and dist < min_dist:
                    min_dist = dist
                    conflict_point = ((p1[0] + p2[0]) / 2,
                                      (p1[1] + p2[1]) / 2)
                    s_at_i = (path_s1[idx1] if idx1 < len(path_s1)
                              else pred_i['curr_s'])
                    s_at_j = (path_s2[idx2] if idx2 < len(path_s2)
                              else pred_j['curr_s'])

        if conflict_point is None:
            return None

        return {
            'conflict_point': conflict_point,
            'dist_i': max(0, s_at_i - pred_i['curr_s']),
            'dist_j': max(0, s_at_j - pred_j['curr_s']),
            'min_separation': min_dist,
        }

    # ---- Resolution helpers ----

    def _find_next_node(self, curr_s, path_nodes):
        """Find the next graph node ahead of *curr_s* along the path."""
        if not path_nodes or len(path_nodes) < 2:
            return None, None
        s_cum = 0.0
        for i in range(len(path_nodes) - 1):
            u, v = path_nodes[i], path_nodes[i + 1]
            edge_len = self.airport_map.get_edge_length(u, v)
            if s_cum + edge_len > curr_s + 0.1:
                return path_nodes[i], s_cum + edge_len
            s_cum += edge_len
        return None, None


# ======================================================================


class Opt_StopGo:
    """Separation controller that maximises concurrent movement.

    Rules:
        1. Priority = closer to destination.
        2. Aircraft may move as long as they stay farther than
           ``min_separation`` from any higher-priority aircraft.
        3. A maximum of ``max_concurrent`` aircraft may move at once.
    """

    def __init__(self, airport_map, predict_horizon=20.0,
                 min_separation=150.0, max_concurrent=5):
        self.airport_map = airport_map
        self.predict_horizon = predict_horizon
        self.min_separation = min_separation
        self.max_concurrent = max_concurrent

    def update(self, aircrafts, timestep=None):
        """Run one control cycle."""
        active = {ac_id: ac for ac_id, ac in aircrafts.items()
                  if not ac.done}
        if len(active) <= 1:
            for ac in active.values():
                if not getattr(ac, 'arrived', False):
                    self._clear_yield(ac)
            return

        arrived = {k: v for k, v in active.items()
                   if getattr(v, 'arrived', False)}
        moving = {k: v for k, v in active.items()
                  if not getattr(v, 'arrived', False)}
        if not moving:
            return

        priority = self._calculate_priority(moving)
        sorted_ids = sorted(moving, key=lambda x: priority[x], reverse=True)

        can_move = set()
        must_stop = {}

        for ac_id in sorted_ids:
            ac = moving[ac_id]

            if len(can_move) + len(arrived) >= self.max_concurrent:
                must_stop[ac_id] = "concurrent limit"
                continue

            blocked_by = None
            my_p = priority[ac_id]

            # Check against arrived aircraft
            for arr_id, arr_ac in arrived.items():
                dist = np.sqrt((ac.x - arr_ac.x)**2
                               + (ac.y - arr_ac.y)**2)
                if dist < self.min_separation:
                    blocked_by = arr_id
                    must_stop[ac_id] = (
                        f"too close to waiting AC {arr_id} ({dist:.1f}m)")
                    break
            if blocked_by is not None:
                continue

            # Check against higher-priority moving aircraft
            for oid, oac in moving.items():
                if oid == ac_id:
                    continue
                if priority[oid] <= my_p:
                    continue
                dist = np.sqrt((ac.x - oac.x)**2 + (ac.y - oac.y)**2)
                if dist < self.min_separation:
                    blocked_by = oid
                    must_stop[ac_id] = (
                        f"too close to AC {oid} ({dist:.1f}m)")
                    break
                if oid in can_move:
                    mfd = self._get_min_future_distance(ac, oac)
                    if mfd < self.min_separation:
                        sd = self._get_safe_travel_distance(ac, oac)
                        if sd < 5.0:
                            blocked_by = oid
                            must_stop[ac_id] = (
                                f"will conflict with AC {oid}")
                            break
            if blocked_by is None:
                can_move.add(ac_id)

        # Apply commands
        for ac_id, ac in moving.items():
            if ac_id in must_stop:
                self._set_yield(ac, must_stop[ac_id])
            else:
                wait_s = self._get_wait_point(
                    ac, moving, can_move, priority, arrived)
                if wait_s is not None:
                    self._set_wait_at(ac, wait_s)
                else:
                    self._clear_yield(ac)

    # ---- Priority ----

    def _calculate_priority(self, active):
        priority = {}
        for ac_id, ac in active.items():
            path_length = (ac.path_s[-1]
                           if hasattr(ac, 'path_s') and len(ac.path_s) > 0
                           else 0)
            remaining = path_length - ac.curr_s
            priority[ac_id] = (10000 - remaining
                               + (1000 - ac_id) * 0.0001)
        return priority

    # ---- Prediction helpers ----

    def _get_min_future_distance(self, ac1, ac2):
        seg1 = self._get_future_path(ac1)
        seg2 = self._get_future_path(ac2)
        if len(seg1) == 0 or len(seg2) == 0:
            return float('inf')

        min_dist = float('inf')
        step1 = max(1, len(seg1) // 10)
        step2 = max(1, len(seg2) // 10)
        for i in range(0, len(seg1), step1):
            for j in range(0, len(seg2), step2):
                dist = np.sqrt((seg1[i, 0] - seg2[j, 0])**2
                               + (seg1[i, 1] - seg2[j, 1])**2)
                min_dist = min(min_dist, dist)
        return min_dist

    def _get_safe_travel_distance(self, ac, higher_ac):
        if ac.path is None or len(ac.path) == 0:
            return 0.0
        curr_s = ac.curr_s
        path_s = ac.path_s

        for s in np.arange(curr_s, min(curr_s + 200, path_s[-1]), 5.0):
            idx = np.searchsorted(path_s, s)
            if idx >= len(ac.path):
                break
            pos = ac.path[idx]
            time_to_s = ((s - curr_s) / (ac.max_pred_v / 3.6)
                         if ac.max_pred_v > 0 else 0)
            higher_s = (higher_ac.curr_s
                        + time_to_s * (higher_ac.max_pred_v / 3.6))

            if higher_s < higher_ac.path_s[-1]:
                hi = np.searchsorted(higher_ac.path_s, higher_s)
                if hi < len(higher_ac.path):
                    hp = higher_ac.path[hi]
                    dist = np.sqrt((pos[0] - hp[0])**2
                                   + (pos[1] - hp[1])**2)
                    if dist < self.min_separation:
                        return s - curr_s - self.min_separation
        return 200.0

    def _get_future_path(self, ac):
        if ac.path is None or len(ac.path) == 0:
            return np.array([])
        path_s = ac.path_s
        path_length = path_s[-1] if len(path_s) > 0 else 0
        v = ac.max_pred_v / 3.6
        s_max = min(ac.curr_s + v * self.predict_horizon, path_length)
        mask = (path_s >= ac.curr_s) & (path_s <= s_max)
        return ac.path[mask]

    def _get_wait_point(self, ac, moving, can_move, priority, arrived):
        if ac.path is None or len(ac.path) == 0:
            return None
        my_p = priority.get(ac.id, 0)
        curr_s = ac.curr_s
        path_s = ac.path_s
        path_end = path_s[-1] if len(path_s) > 0 else 0

        closest_dist = float('inf')
        closest_pos = None

        for arr_ac in arrived.values():
            dist = np.sqrt((ac.x - arr_ac.x)**2 + (ac.y - arr_ac.y)**2)
            if dist < closest_dist:
                closest_dist = dist
                closest_pos = (arr_ac.x, arr_ac.y)

        for oid, oac in moving.items():
            if oid == ac.id or priority.get(oid, 0) <= my_p:
                continue
            dist = np.sqrt((ac.x - oac.x)**2 + (ac.y - oac.y)**2)
            if dist < closest_dist:
                closest_dist = dist
                closest_pos = (oac.x, oac.y)

        if closest_pos is not None and closest_dist < self.min_separation * 3:
            for s in np.arange(curr_s, min(curr_s + 200, path_end), 5.0):
                idx = np.searchsorted(path_s, s)
                if idx >= len(ac.path):
                    break
                pos = ac.path[idx]
                d = np.sqrt((pos[0] - closest_pos[0])**2
                            + (pos[1] - closest_pos[1])**2)
                if d < self.min_separation:
                    wait_s = s - 10
                    if wait_s > curr_s:
                        return wait_s
                    break
        return None

    # ---- Yield helpers ----

    def _set_yield(self, aircraft, reason):
        aircraft.yield_flag = True
        aircraft.wait_at_s = aircraft.curr_s + 50.0
        aircraft.immediate_stop = True

    def _set_wait_at(self, aircraft, wait_s):
        aircraft.yield_flag = True
        aircraft.wait_at_s = wait_s
        aircraft.immediate_stop = False

    def _clear_yield(self, aircraft):
        aircraft.yield_flag = False
        aircraft.wait_at_s = None
        aircraft.immediate_stop = False

    def get_statistics(self):
        return {}
