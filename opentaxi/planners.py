"""Path planners for airport surface routing.

Provides several graph-search planners that operate on an :class:`AirportMap`
and respect runway / parking node constraints.

Available planners:
    * :class:`FloydWarshallPlanner` – precomputed all-pairs shortest paths.
    * :class:`DijkstraPlanner` – single-source Dijkstra.
    * :class:`GreedyPlanner` – greedy best-first search.
    * :class:`AStarPlanner` – A* with optional turn-penalty support.
"""

import numpy as np
import heapq
from collections import deque

from opentaxi.airport import AirportMap


# ======================================================================
# Floyd-Warshall
# ======================================================================

class FloydWarshallPlanner:
    """All-pairs shortest path planner using Floyd-Warshall."""

    def __init__(self, airport_map: AirportMap):
        self.map = airport_map
        self.node_runway, self.node_parking = airport_map.get_excluded_nodes()

        self.nodes = list(self.map.G.nodes())
        self.node_to_idx = {n: i for i, n in enumerate(self.nodes)}
        self.n = len(self.nodes)

        self._precompute()

    def _is_valid_edge(self, from_node, to_node):
        if int(from_node) in self.node_runway:
            return False
        if int(to_node) in self.node_parking:
            return False
        return True

    def _precompute(self):
        print(f"FloydWarshallPlanner: Precomputing {self.n} nodes...")
        INF = float('inf')
        self.dist = [[INF] * self.n for _ in range(self.n)]
        self.next_node = [[None] * self.n for _ in range(self.n)]

        for i in range(self.n):
            self.dist[i][i] = 0
            self.next_node[i][i] = i

        for u in self.nodes:
            u_idx = self.node_to_idx[u]
            for v in self.map.get_neighbors(u):
                if v not in self.node_to_idx:
                    continue
                if not self._is_valid_edge(u, v):
                    continue
                v_idx = self.node_to_idx[v]
                edge_len = self.map.get_edge_length(u, v)
                if edge_len < self.dist[u_idx][v_idx]:
                    self.dist[u_idx][v_idx] = edge_len
                    self.next_node[u_idx][v_idx] = v_idx

        for k in range(self.n):
            for i in range(self.n):
                for j in range(self.n):
                    if self.dist[i][k] + self.dist[k][j] < self.dist[i][j]:
                        self.dist[i][j] = self.dist[i][k] + self.dist[k][j]
                        self.next_node[i][j] = self.next_node[i][k]

        print("FloydWarshallPlanner: Precomputation complete.")

    def _reconstruct_path(self, start_idx, end_idx):
        u_idx = self.node_to_idx.get(str(start_idx))
        v_idx = self.node_to_idx.get(str(end_idx))
        if u_idx is None or v_idx is None:
            return None
        if self.next_node[u_idx][v_idx] is None:
            return None

        path_nodes = [self.nodes[u_idx]]
        current = u_idx
        while current != v_idx:
            current = self.next_node[current][v_idx]
            if current is None:
                return None
            path_nodes.append(self.nodes[current])
        return path_nodes

    def plan_shortest_path(self, start_idx, end_idx):
        """Return (path, path_nodes) or (None, None)."""
        start_idx = str(start_idx)
        end_idx = str(end_idx)

        if int(start_idx) in self.node_parking:
            parking_chain = self._get_parking_chain(start_idx)
            for park_node in parking_chain:
                path_nodes = self._reconstruct_path(park_node, end_idx)
                if path_nodes is not None:
                    prefix = self._get_chain_to_node(start_idx, park_node)
                    if prefix:
                        path_nodes = prefix[:-1] + path_nodes
                    break
            else:
                return None, None
        else:
            path_nodes = self._reconstruct_path(start_idx, end_idx)

        if path_nodes is None:
            return None, None
        path = self._build_trajectory(path_nodes)
        return path, path_nodes

    def _get_parking_chain(self, start_idx):
        chain = set()
        to_visit = [start_idx]
        while to_visit:
            curr = to_visit.pop()
            if curr in chain:
                continue
            chain.add(curr)
            for neighbor in self.map.get_neighbors(curr):
                if int(neighbor) in self.node_parking and neighbor not in chain:
                    to_visit.append(neighbor)
        return list(chain)

    def _get_chain_to_node(self, start, end):
        if start == end:
            return [start]
        queue = deque([(start, [start])])
        visited = {start}
        while queue:
            curr, path = queue.popleft()
            for neighbor in self.map.get_neighbors(curr):
                if neighbor == end:
                    return path + [neighbor]
                if (int(neighbor) in self.node_parking
                        and neighbor not in visited):
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))
        return None

    def _build_trajectory(self, path_nodes):
        if len(path_nodes) < 2:
            return None
        segments = []
        for i in range(len(path_nodes) - 1):
            u, v = path_nodes[i], path_nodes[i + 1]
            edge_idxs = self.map.way_idxs.get((u, v), [])
            if edge_idxs:
                segments.append(self.map.way_dict["path"][edge_idxs[0]])
        if not segments:
            return None
        return np.vstack(segments)

    def get_distance(self, start_idx, end_idx):
        """Return precomputed distance between two nodes."""
        u_idx = self.node_to_idx.get(str(start_idx))
        v_idx = self.node_to_idx.get(str(end_idx))
        if u_idx is None or v_idx is None:
            return float('inf')
        return self.dist[u_idx][v_idx]


# ======================================================================
# Greedy best-first search
# ======================================================================

class GreedyPlanner:
    """Greedy best-first search planner (heuristic only, no g-cost)."""

    def __init__(self, airport_map: AirportMap):
        self.map = airport_map
        self.node_runway, self.node_parking = airport_map.get_excluded_nodes()

    def _get_valid_neighbors(self, current, start_idx=None, end_idx=None):
        neighbors = []
        for neighbor in self.map.get_neighbors(current):
            if self._is_valid_edge(current, neighbor, start_idx, end_idx):
                neighbors.append(neighbor)
        return neighbors

    def _is_valid_edge(self, from_node, to_node, start_idx=None,
                       end_idx=None):
        from_int = int(from_node)
        to_int = int(to_node)
        if from_int in self.node_runway:
            if start_idx is None or from_int != int(start_idx):
                return False
        if to_int in self.node_parking:
            if end_idx is None or to_int != int(end_idx):
                if from_int not in self.node_parking:
                    return False
        return True

    def _heuristic_distance(self, node_idx, goal_idx):
        p1 = self.map.get_point(node_idx)
        p2 = self.map.get_point(goal_idx)
        return np.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)

    def plan_shortest_path(self, start_idx, end_idx):
        """Return (path, path_nodes) using greedy best-first search."""
        start_idx = str(start_idx)
        end_idx = str(end_idx)

        counter = 0
        h_start = self._heuristic_distance(start_idx, end_idx)
        open_set = [(h_start, counter, start_idx)]
        came_from = {}
        visited = set()

        while open_set:
            _, _, current = heapq.heappop(open_set)
            if current in visited:
                continue
            visited.add(current)

            if current == end_idx:
                path_nodes = [current]
                while current in came_from:
                    current = came_from[current]
                    path_nodes.append(current)
                path_nodes.reverse()
                path = self._build_trajectory(path_nodes)
                return path, path_nodes

            for neighbor in self._get_valid_neighbors(
                    current, start_idx, end_idx):
                if neighbor in visited:
                    continue
                if neighbor not in came_from:
                    came_from[neighbor] = current
                    h = self._heuristic_distance(neighbor, end_idx)
                    counter += 1
                    heapq.heappush(open_set, (h, counter, neighbor))

        return None, None

    def _build_trajectory(self, path_nodes):
        if len(path_nodes) < 2:
            return None
        segments = []
        for i in range(len(path_nodes) - 1):
            u, v = path_nodes[i], path_nodes[i + 1]
            edge_idxs = self.map.way_idxs.get((u, v), [])
            if edge_idxs:
                segments.append(self.map.way_dict["path"][edge_idxs[0]])
        if not segments:
            return None
        return np.vstack(segments)


# ======================================================================
# Dijkstra
# ======================================================================

class DijkstraPlanner:
    """Dijkstra shortest-path planner."""

    def __init__(self, airport_map: AirportMap):
        self.map = airport_map
        self.node_runway, self.node_parking = airport_map.get_excluded_nodes()

    def _get_valid_neighbors(self, current, start_idx=None, end_idx=None):
        neighbors = []
        for neighbor in self.map.get_neighbors(current):
            if self._is_valid_edge(current, neighbor, start_idx, end_idx):
                neighbors.append(neighbor)
        return neighbors

    def _is_valid_edge(self, from_node, to_node, start_idx=None,
                       end_idx=None):
        from_int = int(from_node)
        to_int = int(to_node)
        if from_int in self.node_runway:
            if start_idx is None or from_int != int(start_idx):
                return False
        if to_int in self.node_parking:
            if end_idx is None or to_int != int(end_idx):
                if from_int not in self.node_parking:
                    return False
        return True

    def plan_shortest_path(self, start_idx, end_idx):
        """Return (path, path_nodes) using Dijkstra's algorithm."""
        start_idx = str(start_idx)
        end_idx = str(end_idx)

        counter = 0
        open_set = [(0, counter, start_idx)]
        came_from = {}
        dist = {start_idx: 0}
        visited = set()

        while open_set:
            d, _, current = heapq.heappop(open_set)
            if current in visited:
                continue
            visited.add(current)

            if current == end_idx:
                path_nodes = [current]
                while current in came_from:
                    current = came_from[current]
                    path_nodes.append(current)
                path_nodes.reverse()
                path = self._build_trajectory(path_nodes)
                return path, path_nodes

            for neighbor in self._get_valid_neighbors(
                    current, start_idx, end_idx):
                if neighbor in visited:
                    continue
                edge_length = self.map.get_edge_length(current, neighbor)
                new_dist = dist[current] + edge_length
                if neighbor not in dist or new_dist < dist[neighbor]:
                    came_from[neighbor] = current
                    dist[neighbor] = new_dist
                    counter += 1
                    heapq.heappush(open_set, (new_dist, counter, neighbor))

        return None, None

    def _build_trajectory(self, path_nodes):
        if len(path_nodes) < 2:
            return None
        segments = []
        for i in range(len(path_nodes) - 1):
            u, v = path_nodes[i], path_nodes[i + 1]
            edge_idxs = self.map.way_idxs.get((u, v), [])
            if edge_idxs:
                segments.append(self.map.way_dict["path"][edge_idxs[0]])
        if not segments:
            return None
        return np.vstack(segments)


# ======================================================================
# A*
# ======================================================================

class AStarPlanner:
    """A* planner supporting shortest-path and minimum-turn planning."""

    def __init__(self, airport_map: AirportMap):
        self.map = airport_map
        self.turn_penalty_weight = 200  # turn cost in metres-equivalent
        self.node_runway, self.node_parking = airport_map.get_excluded_nodes()

    def _get_valid_neighbors(self, current, start_idx=None, end_idx=None):
        neighbors = []
        for neighbor in self.map.get_neighbors(current):
            if self._is_valid_edge(current, neighbor, start_idx, end_idx):
                neighbors.append(neighbor)
        return neighbors

    def _is_valid_edge(self, from_node, to_node, start_idx=None,
                       end_idx=None):
        """Check edge validity w.r.t. runway / parking constraints."""
        from_int = int(from_node)
        to_int = int(to_node)

        if from_int in self.node_runway:
            if start_idx is None or from_int != int(start_idx):
                return False
        if to_int in self.node_parking:
            if end_idx is None or to_int != int(end_idx):
                if from_int not in self.node_parking:
                    return False
        return True

    def _heuristic_distance(self, node_idx, goal_idx):
        p1 = self.map.get_point(node_idx)
        p2 = self.map.get_point(goal_idx)
        return np.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)

    def _normalize_angle(self, angle):
        while angle > np.pi:
            angle -= 2 * np.pi
        while angle < -np.pi:
            angle += 2 * np.pi
        return angle

    def _compute_turn_cost(self, prev_heading, next_heading):
        if prev_heading is None:
            return 0
        delta = abs(self._normalize_angle(next_heading - prev_heading))
        return (delta / np.pi) * self.turn_penalty_weight

    # ----- Shortest path (distance only) -----

    def plan_shortest_path(self, start_idx, end_idx):
        """A* shortest-path search.

        Returns:
            (path, path_nodes) or (None, None).
        """
        start_idx = str(start_idx)
        end_idx = str(end_idx)

        counter = 0
        open_set = [(0, counter, start_idx)]
        came_from = {}
        g_score = {start_idx: 0}

        while open_set:
            _, _, current = heapq.heappop(open_set)

            if current == end_idx:
                path_nodes = [current]
                while current in came_from:
                    current = came_from[current]
                    path_nodes.append(current)
                path_nodes.reverse()
                path = self._build_trajectory(path_nodes)
                return path, path_nodes

            for neighbor in self._get_valid_neighbors(
                    current, start_idx, end_idx):
                edge_length = self.map.get_edge_length(current, neighbor)
                tentative_g = g_score[current] + edge_length

                if neighbor not in g_score or tentative_g < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f = tentative_g + self._heuristic_distance(
                        neighbor, end_idx)
                    counter += 1
                    heapq.heappush(open_set, (f, counter, neighbor))

        return None, None

    # ----- Minimum-turn path (distance + heading change) -----

    def plan_minimum_turn_path(self, start_idx, end_idx):
        """A* search that penalises heading changes.

        Returns:
            (path, path_nodes) or (None, None).
        """
        start_idx = str(start_idx)
        end_idx = str(end_idx)

        counter = 0
        initial_heading = None
        open_set = [(0, counter, start_idx, initial_heading)]

        came_from = {}
        g_score = {(start_idx, initial_heading): 0}

        best_goal_state = None
        best_goal_cost = float('inf')

        while open_set:
            f, _, current, current_heading = heapq.heappop(open_set)

            if f > best_goal_cost:
                break

            if current == end_idx:
                cost = g_score[(current, current_heading)]
                if cost < best_goal_cost:
                    best_goal_cost = cost
                    best_goal_state = (current, current_heading)
                continue

            current_g = g_score.get(
                (current, current_heading), float('inf'))

            for neighbor in self._get_valid_neighbors(
                    current, start_idx, end_idx):
                edge_length = self.map.get_edge_length(current, neighbor)
                start_heading, end_heading = self.map.get_edge_heading(
                    current, neighbor)

                turn_cost = self._compute_turn_cost(
                    current_heading, start_heading)
                tentative_g = current_g + edge_length + turn_cost
                state = (neighbor, end_heading)

                if state not in g_score or tentative_g < g_score[state]:
                    came_from[state] = (current, current_heading)
                    g_score[state] = tentative_g
                    h = self._heuristic_distance(neighbor, end_idx)
                    counter += 1
                    heapq.heappush(
                        open_set, (tentative_g + h, counter,
                                   neighbor, end_heading))

        if best_goal_state is None:
            return None, None

        path_nodes = []
        state = best_goal_state
        while state in came_from:
            path_nodes.append(state[0])
            state = came_from[state]
        path_nodes.append(state[0])
        path_nodes.reverse()

        path = self._build_trajectory(path_nodes)
        return path, path_nodes

    def _build_trajectory(self, path_nodes):
        if len(path_nodes) < 2:
            return None
        segments = []
        for i in range(len(path_nodes) - 1):
            u, v = path_nodes[i], path_nodes[i + 1]
            edge_idxs = self.map.way_idxs.get((u, v), [])
            if edge_idxs:
                segments.append(self.map.way_dict["path"][edge_idxs[0]])
        if not segments:
            return None
        return np.vstack(segments)

    # ----- Path geometry helpers -----

    def compute_path_geometry(self, path):
        """Compute arc length, heading, and curvature arrays for a path.

        Returns:
            (s, heading, curvature) arrays.
        """
        n = len(path)
        ds = np.sqrt(np.sum(np.diff(path, axis=0)**2, axis=1))
        s = np.zeros(n)
        s[1:] = np.cumsum(ds)

        heading = np.zeros(n)
        for i in range(n - 1):
            heading[i] = np.arctan2(path[i + 1, 1] - path[i, 1],
                                    path[i + 1, 0] - path[i, 0])
        heading[-1] = heading[-2] if n > 1 else 0

        curvature = np.zeros(n)
        for i in range(n - 1):
            if ds[i] > 0.01:
                dh = heading[i + 1] - heading[i] if i < n - 2 else 0
                if dh > np.pi:
                    dh -= 2 * np.pi
                elif dh < -np.pi:
                    dh += 2 * np.pi
                curvature[i] = dh / ds[i]
        curvature[-1] = curvature[-2] if n > 1 else 0

        if n > 5:
            kernel = np.ones(5) / 5
            curvature = np.convolve(curvature, kernel, mode='same')

        return s, heading, curvature

    def plan_velocity_profile(self, s, curvature):
        """Generate a curvature-limited velocity profile.

        Returns:
            Target velocity array (km/h).
        """
        curvature_safe = np.maximum(np.abs(curvature), 1e-6)
        velocity = np.sqrt(1.5 / curvature_safe) * 3.6
        velocity = np.minimum(velocity, 30)
        return velocity

    def compute_path_stats(self, path, path_nodes):
        """Compute summary statistics for a planned path.

        Returns:
            dict with ``length``, ``num_turns``, ``total_turn_angle``.
        """
        if path is None:
            return None
        total_length = 0
        total_turn = 0
        num_turns = 0
        prev_heading = None

        for i in range(len(path_nodes) - 1):
            u, v = path_nodes[i], path_nodes[i + 1]
            total_length += self.map.get_edge_length(u, v)

            start_h, end_h = self.map.get_edge_heading(u, v)
            if prev_heading is not None:
                delta = abs(self._normalize_angle(start_h - prev_heading))
                total_turn += delta
                if delta > np.deg2rad(15):
                    num_turns += 1
            prev_heading = end_h

        return {
            'length': total_length,
            'num_turns': num_turns,
            'total_turn_angle': np.rad2deg(total_turn),
        }

    def detect_head_on_conflicts(self, trajectories):
        """Detect head-on conflicts between planned trajectories.

        Args:
            trajectories: List of trajectory dicts with ``path_nodes``.

        Returns:
            List of ``(aircraft_i, aircraft_j, conflicting_edge)`` tuples.
        """
        conflicts = []
        n = len(trajectories)
        edge_sets = []
        for traj in trajectories:
            if traj is None:
                edge_sets.append(set())
                continue
            edges = set()
            pn = traj['path_nodes']
            for i in range(len(pn) - 1):
                edges.add((pn[i], pn[i + 1]))
            edge_sets.append(edges)

        for i in range(n):
            for j in range(i + 1, n):
                for edge in edge_sets[i]:
                    if (edge[1], edge[0]) in edge_sets[j]:
                        conflicts.append((i, j, edge))
        return conflicts
