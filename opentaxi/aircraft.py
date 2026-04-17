"""Aircraft state model for airport surface simulation.

Each Aircraft instance tracks a single vehicle moving along a planned
taxiway path from a parking position to a runway threshold.
"""

import random
import numpy as np
import re
import io

from opentaxi.tools import find_waypoint_in_curve, lonlat_to_utm, polyline_length


class Aircraft:
    """Manage the kinematic state of a single aircraft on the surface."""

    def __init__(self, ac_id, airport_map, planner, seed=None,
                 replay_mode=False, used_starts=None):
        self.id = ac_id
        self.airport_map = airport_map
        self.planner = planner
        self.replay_mode = replay_mode
        self.start_node = None

        if not replay_mode:
            self.init_path(seed, used_starts=used_starts)
            self.path_s = polyline_length(self.path)
        else:
            self.start = (0, 0)
            self.end = (0, 0)
            self.path = np.array([[0, 0]])
            self.path_s = []

        # Kinematic state
        self.x = self.start[0]
        self.y = self.start[1]
        self.yaw = 0
        self.curr_v = 0         # current velocity (km/h)
        self.targ_v = 30.0      # target velocity (km/h)
        self.min_pred_v = 0.0   # minimum prediction velocity (km/h)
        self.max_pred_v = 30.0  # maximum prediction velocity (km/h)
        self.curr_s = 0.0       # current arc-length position (m)
        self.max_acc = 0.2      # maximum acceleration (m/s^2)
        self.max_dec = 0.5      # maximum deceleration (m/s^2)
        self.hist_path = []     # historical trajectory [(x,y), ...]
        self.risk_level = 0     # 0-3

        # Yield / conflict state
        self.yield_flag = False
        self.wait_at_node = None
        self.wait_at_s = None
        self.conflict_with = None

        # Completion state
        self.done = False
        self.arrived = False
        self.arrival_time = None
        self.departure_wait = 90.0  # post-arrival hold time (seconds)

        self.icon_path = "../opentaxi/airport_map/ac_logo.svg"
        self.icon = None

    # ------------------------------------------------------------------
    # Path initialisation
    # ------------------------------------------------------------------

    def init_path(self, seed, max_attempts=50, used_starts=None):
        """Initialise path with random valid start/end points.

        Args:
            seed: Random seed.
            max_attempts: Maximum random attempts to find a valid path.
            used_starts: Set of already-used start node IDs.
        """
        if seed is None:
            seed = random.randint(0, 1000) + self.id * 100
        rnd = random.Random(seed)

        valid_starts = self.airport_map.get_valid_parking_startpoints()
        valid_ends = self.airport_map.get_valid_runway_endpoints()

        if not valid_starts or not valid_ends:
            raise ValueError(
                f"Aircraft {self.id}: No valid start/end points in map")

        if used_starts is not None:
            available = [s for s in valid_starts
                         if str(s) not in used_starts]
            if not available:
                print(f"[Warning] Aircraft {self.id}: "
                      "All starts used, allowing reuse")
                available = valid_starts
        else:
            available = valid_starts

        for _ in range(max_attempts):
            try:
                start_idx = str(rnd.choice(available))
                # end_idx = str(rnd.choice(valid_ends))
                end_idx = str(377)

                path, path_nodes = self.planner.plan_shortest_path(
                    start_idx, end_idx)

                if path is not None and len(path) > 0:
                    self.start = self.airport_map.get_point(start_idx)
                    self.end = self.airport_map.get_point(end_idx)
                    self.path = path
                    self.path_nodes = path_nodes
                    self.start_idx = start_idx
                    self.end_idx = end_idx
                    self.start_node = start_idx
                    self.path_s = polyline_length(self.path)
                    return
            except Exception:
                pass

        raise RuntimeError(
            f"Aircraft {self.id}: Could not find valid path after "
            f"{max_attempts} attempts. "
            f"Valid starts: {len(valid_starts)}, "
            f"Valid ends: {len(valid_ends)}")

    def init_path_with_endpoints(self, start_idx, end_idx):
        """Initialise path with specific start and end nodes.

        Returns:
            True if a valid path was found, False otherwise.
        """
        try:
            path, path_nodes = self.planner.plan_shortest_path(
                start_idx, end_idx)

            if path is not None and len(path) > 0:
                self.start = self.airport_map.get_point(start_idx)
                self.end = self.airport_map.get_point(end_idx)
                self.path = path
                self.path_nodes = path_nodes
                self.start_idx = start_idx
                self.end_idx = end_idx

                self.x = self.start[0]
                self.y = self.start[1]
                self.curr_s = 0
                self.hist_path = []
                self.done = False
                self.path_s = polyline_length(self.path)
                return True
            else:
                print(f"Aircraft {self.id}: "
                      f"No path found from {start_idx} to {end_idx}")
                return False
        except Exception as e:
            print(f"Aircraft {self.id}: Error planning path - {e}")
            return False

    # ------------------------------------------------------------------
    # Icon rendering
    # ------------------------------------------------------------------

    def load_icon(self, scale=1.0, color=None):
        """Load and optionally recolour the aircraft SVG icon.

        Requires ``cairosvg`` and ``Pillow``.
        """
        if self.icon_path is None:
            self.icon = None
            return
        try:
            import cairosvg
            from PIL import Image

            with open(self.icon_path, 'r') as f:
                svg = f.read()

            if color is not None:
                if 'fill=' in svg or 'fill:' in svg:
                    svg = re.sub(r'fill="[^"]*"',
                                 f'fill="{color}"', svg)
                    svg = re.sub(r'fill:[^;}"]*',
                                 f'fill:{color}', svg)
                else:
                    for tag in ('path', 'polygon', 'rect',
                                'circle', 'ellipse'):
                        svg = re.sub(
                            rf'<{tag} ',
                            f'<{tag} fill="{color}" '
                            f'stroke="black" stroke-width="1" ',
                            svg)

            png_data = cairosvg.svg2png(
                bytestring=svg.encode('utf-8'), scale=scale)
            image = Image.open(io.BytesIO(png_data))
            self.icon = np.array(image)
            self.color = color
        except Exception as e:
            print(f"Warning: Could not load aircraft icon: {e}")
            self.icon = None

    def get_rotated_icon(self):
        """Return the icon rotated to the current heading."""
        if self.icon is None:
            return None
        from PIL import Image
        angle_deg = np.degrees(self.yaw)
        pil_img = Image.fromarray(self.icon)
        rotated = pil_img.rotate(-angle_deg, expand=True,
                                 resample=Image.BICUBIC)
        return np.array(rotated)

    # ------------------------------------------------------------------
    # Kinematics
    # ------------------------------------------------------------------

    def calculate_heading(self, prev_x, prev_y, curr_x, curr_y):
        """Compute heading angle in radians (0 = north, clockwise)."""
        dx = curr_x - prev_x
        dy = curr_y - prev_y
        if abs(dx) < 1e-6 and abs(dy) < 1e-6:
            return self.yaw
        return np.arctan2(dx, dy)

    def step(self, dura=5):
        """Advance aircraft state by *dura* seconds."""
        if self.done:
            return
        prev_x, prev_y = self.x, self.y

        next_dis, next_v = self.motion_update(dura)
        self.curr_s += next_dis

        next_loc = find_waypoint_in_curve(
            self.curr_s, self.path_s, self.path)
        self.curr_v = next_v
        self.x = next_loc[0]
        self.y = next_loc[1]
        self.yaw = self.calculate_heading(prev_x, prev_y, self.x, self.y)
        self.hist_path.append((self.x, self.y))

    def check_arrival(self, min_dist=0.5, current_timestep=0,
                      time_step_duration=5.0):
        """Check whether the aircraft has reached its destination.

        After arriving the aircraft holds for ``departure_wait`` seconds
        before being marked as *done*.

        Returns:
            True if the aircraft is done (departed).
        """
        if self.done:
            return True

        curr_pos = np.array((self.x, self.y))
        target_pos = np.array((self.end[0], self.end[1]))
        dist = np.linalg.norm(curr_pos - target_pos)

        if not self.arrived and (dist - min_dist) < 1e-3:
            self.arrived = True
            self.arrival_time = current_timestep
            self.curr_v = 0

        if self.arrived:
            wait_time = ((current_timestep - self.arrival_time)
                         * time_step_duration)
            if wait_time >= self.departure_wait:
                self.done = True

        return self.done

    def motion_update(self, dura):
        """Compute displacement and new velocity for the next time step.

        Uses a simple kinematic model with acceleration / deceleration
        limits.

        Returns:
            (distance, velocity) in metres and km/h.
        """
        self.targ_v = self.update_target_velocity()

        if abs(self.curr_v - self.targ_v) < 5:
            next_dis = (self.curr_v / 3.6) * dura
            next_v = self.curr_v
        else:
            if self.curr_v < self.targ_v:
                next_dis = ((self.curr_v / 3.6) * dura
                            + 0.5 * self.max_acc * dura**2)
                next_v = ((self.curr_v / 3.6)
                          + self.max_acc * dura) * 3.6
            else:
                next_dis = ((self.curr_v / 3.6) * dura
                            - 0.5 * self.max_dec * dura**2)
                next_v = ((self.curr_v / 3.6)
                          - self.max_dec * dura) * 3.6

        next_v = max(0, next_v)
        return next_dis, next_v

    def update_target_velocity(self):
        """Determine effective target velocity considering yield state."""
        if getattr(self, 'immediate_stop', False):
            return 0.0

        if not self.yield_flag or self.wait_at_s is None:
            return 25.0

        dist_to_wait = self.wait_at_s - self.curr_s

        if dist_to_wait <= 5:
            return 25.0
        if dist_to_wait <= 20.0:
            return 0.0
        if dist_to_wait < 50.0:
            return self.min_pred_v
        return 25.0

    # ------------------------------------------------------------------
    # Replay helpers
    # ------------------------------------------------------------------

    def set_state_from_data(self, lon, lat, alt, timestamp):
        """Set aircraft position from lon/lat observation data."""
        points_utm = lonlat_to_utm(
            self.airport_map.transformer, [(lon, lat)])
        prev_x, prev_y = self.x, self.y
        self.x = points_utm[0][0]
        self.y = points_utm[0][1]

        if len(self.hist_path) > 0:
            self.yaw = self.calculate_heading(
                prev_x, prev_y, self.x, self.y)
        self.hist_path.append((self.x, self.y))

    # ------------------------------------------------------------------
    # State snapshot
    # ------------------------------------------------------------------

    def get_state(self):
        """Return a dict snapshot of the current aircraft state."""
        return {
            "id": self.id,
            "start": self.start,
            "end": self.end,
            "max_acc": self.max_acc,
            "max_dec": self.max_dec,
            "x": self.x,
            "y": self.y,
            "curr_v": self.curr_v,
            "targ_v": self.targ_v,
            "curr_s": self.curr_s,
            "min_pred_v": self.min_pred_v,
            "max_pred_v": self.max_pred_v,
            "path": self.path,
            "path_nodes": getattr(self, 'path_nodes', []),
            "hist_path": self.hist_path,
            "risk_level": self.risk_level,
            "yield_flag": self.yield_flag,
            "wait_at_node": self.wait_at_node,
            "conflict_with": self.conflict_with,
            "done": self.done,
        }
