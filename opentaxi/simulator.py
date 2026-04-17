"""Real-time simulation engine with matplotlib visualisation.

The :class:`Simulation` class ties together the airport map, path planner,
conflict controller, aircraft agents, and an optional evaluator into a
step-by-step simulation loop with a live 2-D display.
"""

import matplotlib
matplotlib.use("Qt5Agg")  # Change to "Qt5Agg" for interactive display
import matplotlib.pyplot as plt
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
import numpy as np
import os

from opentaxi.aircraft import Aircraft


class Simulation:
    """Multi-aircraft airport surface simulation.

    Supports two modes:

    * **Simulation mode** (default) – aircraft are created with random
      start/end points and move along planned paths.
    * **Replay mode** – aircraft positions are driven by external
      observation data.
    """

    AIRCRAFT_COLOR = 'lightgreen'
    PATH_COLOR = 'darkgreen'
    RISK_COLORS = [
        'lightgreen',  # 0: safe (>= 60 m)
        'red',         # 1: warning (40–60 m)
        'purple',      # 2: danger (20–40 m)
        'black',       # 3: critical (< 20 m)
    ]

    def __init__(self, airport_map, planner, controller, num_agents=3,
                 replay_mode=False, hist_data=None, evaluator=None):
        self.airport_map = airport_map
        self.planner = planner
        self.controller = controller
        self.evaluator = evaluator
        self.num_agents = num_agents
        self.aircrafts = {}
        self.timestep = 0

        # Replay state
        self.replay_mode = replay_mode
        self.hist_data = hist_data
        self.current_time_idx = 0
        self.aircraft_missing_count = {}

        # Visualisation handles
        self.fig = None
        self.ax = None
        self.vis_objects = {}

        if not replay_mode:
            self._create_aircrafts()

    # ------------------------------------------------------------------
    # Aircraft creation
    # ------------------------------------------------------------------

    def _create_aircrafts(self):
        """Create aircraft for simulation mode."""
        used_starts = set()
        for i in range(self.num_agents):
            ac = Aircraft(i, self.airport_map, self.planner,
                          replay_mode=False, used_starts=used_starts)
            ac.load_icon(scale=0.8, color=self.AIRCRAFT_COLOR)
            self.aircrafts[i] = ac
            if self.evaluator is not None:
                path_length = (ac.path_s[-1]
                               if hasattr(ac, 'path_s')
                               and len(ac.path_s) > 0 else 0)
                self.evaluator.register_aircraft(i, path_length)
            if hasattr(ac, 'start_node'):
                used_starts.add(ac.start_node)

    def _create_aircraft_for_replay(self, ac_id):
        """Lazily create an aircraft when it first appears in replay."""
        if ac_id not in self.aircrafts:
            ac = Aircraft(ac_id, self.airport_map, self.planner,
                          replay_mode=True)
            ac.load_icon(scale=0.8, color=self.AIRCRAFT_COLOR)
            self.aircrafts[ac_id] = ac

            self.vis_objects[ac_id] = {
                "path_line": self.ax.plot(
                    [], [], color=self.PATH_COLOR, linewidth=1.5,
                    alpha=0.6, label=f"AC {ac_id}", zorder=6)[0],
                "start_sc": self.ax.scatter(
                    [], [], s=20, c=self.AIRCRAFT_COLOR, marker="o",
                    zorder=11, edgecolors="black"),
                "end_sc": self.ax.scatter(
                    [], [], s=20, c=self.AIRCRAFT_COLOR, marker="^",
                    zorder=11, edgecolors="black"),
                "ac_icon": None,
                "ac_color": self.AIRCRAFT_COLOR,
                "ac_text": self.ax.text(
                    0, 0, "", fontsize=6, ha="center", va="bottom",
                    zorder=13, color="black",
                    bbox=dict(boxstyle="round,pad=0.2", fc="white",
                              ec="none", alpha=0.7)),
                "hist_line": self.ax.plot(
                    [], [], color=self.PATH_COLOR, linewidth=3,
                    zorder=7)[0],
            }

    # ------------------------------------------------------------------
    # Visualisation
    # ------------------------------------------------------------------

    def init_visualization(self):
        """Set up the matplotlib figure and draw the static map."""
        plt.ion()
        self.fig, self.ax = plt.subplots(figsize=(12, 10))

        x_min, x_max, y_min, y_max = self.airport_map.get_bounds()
        x_pad = (x_max - x_min) * 0.05
        y_pad = (y_max - y_min) * 0.05
        self.ax.set_xlim(x_min - x_pad, x_max + x_pad)
        self.ax.set_ylim(y_min - y_pad, y_max + y_pad)
        self.ax.set_aspect("equal")

        self._draw_static_map()

        if not self.replay_mode:
            self._create_dynamic_objects()

        title = ("Multi-Agent Airport Surface Operations"
                 + (" (Replay)" if self.replay_mode else ""))
        self.ax.set_title(title)

    def _draw_static_map(self):
        """Render static taxiway / runway geometries."""
        wd = self.airport_map.way_dict
        for i in range(len(wd["aeroway"])):
            line = wd["path"][i]
            atype = wd["aeroway"][i]
            if atype == "runway":
                self.ax.plot(line[:, 0], line[:, 1],
                             color="black", linewidth=2, alpha=0.8,
                             zorder=5)
            elif atype == "taxiway":
                self.ax.plot(line[:, 0], line[:, 1],
                             color="gray", linewidth=1, alpha=0.7,
                             zorder=5)
            elif atype == "parking_position":
                self.ax.plot(line[:, 0], line[:, 1],
                             color=str(0.3), linewidth=1, alpha=0.7,
                             zorder=5)

    def _create_dynamic_objects(self):
        """Allocate matplotlib artists for each aircraft."""
        for i in range(self.num_agents):
            self.vis_objects[i] = {
                "path_line": self.ax.plot(
                    [], [], color=self.PATH_COLOR, linewidth=1.5,
                    alpha=0.6, label=f"AC {i}", zorder=6)[0],
                "start_sc": self.ax.scatter(
                    [], [], s=20, c=self.AIRCRAFT_COLOR, marker="o",
                    zorder=11, edgecolors="black"),
                "end_sc": self.ax.scatter(
                    [], [], s=20, c=self.AIRCRAFT_COLOR, marker="^",
                    zorder=11, edgecolors="black"),
                "ac_icon": None,
                "ac_color": self.AIRCRAFT_COLOR,
                "ac_text": self.ax.text(
                    0, 0, "", fontsize=6, ha="center", va="bottom",
                    zorder=13, color="black",
                    bbox=dict(boxstyle="round,pad=0.2", fc="white",
                              ec="none", alpha=0.7)),
                "hist_line": self.ax.plot(
                    [], [], color=self.PATH_COLOR, linewidth=3,
                    zorder=7)[0],
            }

    def update_visualization(self):
        """Redraw all dynamic elements for the current time step."""
        for ac_id, aircraft in self.aircrafts.items():
            vis = self.vis_objects[ac_id]
            state = aircraft.get_state()

            if state["done"]:
                if vis["ac_icon"] is not None:
                    vis["ac_icon"].remove()
                    vis["ac_icon"] = None
                if vis.get("ac_text") is not None:
                    vis["ac_text"].set_text("")
                vis["hist_line"].set_data([], [])
                if not self.replay_mode:
                    vis["path_line"].set_data([], [])
                    vis["start_sc"].set_offsets(np.empty((0, 2)))
                    vis["end_sc"].set_offsets(np.empty((0, 2)))
                continue

            risk = getattr(aircraft, 'risk_level', 0)
            risk_color = self.RISK_COLORS[risk]
            if risk_color != vis.get("ac_color", self.AIRCRAFT_COLOR):
                vis["ac_color"] = risk_color
                aircraft.load_icon(scale=0.8, color=risk_color)

            if not self.replay_mode:
                vis["path_line"].set_data(state["path"][:, 0],
                                          state["path"][:, 1])
                vis["start_sc"].set_offsets(
                    np.array([[state["start"][0], state["start"][1]]]))
                vis["end_sc"].set_offsets(
                    np.array([[state["end"][0], state["end"][1]]]))

            if vis["ac_icon"] is not None:
                vis["ac_icon"].remove()
                vis["ac_icon"] = None

            rotated = aircraft.get_rotated_icon()
            if rotated is not None:
                ib = OffsetImage(rotated, zoom=0.3)
                ab = AnnotationBbox(
                    ib, (state["x"], state["y"]),
                    frameon=False, zorder=12)
                vis["ac_icon"] = self.ax.add_artist(ab)
            else:
                vis["ac_icon"] = self.ax.scatter(
                    state["x"], state["y"], s=120,
                    c=vis["ac_color"], marker="s",
                    zorder=12, edgecolors="black", linewidths=2)

            if vis.get("ac_text") is not None:
                vis["ac_text"].set_text(str(ac_id))
                vis["ac_text"].set_position(
                    (state["x"], state["y"] + 10))

            if len(state["hist_path"]) > 0:
                hx = [p[0] for p in state["hist_path"]]
                hy = [p[1] for p in state["hist_path"]]
                vis["hist_line"].set_data(hx, hy)

        self.fig.canvas.draw()
        self.fig.canvas.flush_events()
        plt.pause(0.01)

    # ------------------------------------------------------------------
    # Simulation stepping
    # ------------------------------------------------------------------

    def step(self):
        """Advance one simulation time step."""
        if self.controller is not None:
            self.controller.update(self.aircrafts)

        for aircraft in self.aircrafts.values():
            if not aircraft.arrived:
                aircraft.step()
            aircraft.check_arrival(
                current_timestep=self.timestep, time_step_duration=5.0)

        if self.evaluator is not None:
            self.evaluator.update(self.aircrafts, self.timestep)

        self.timestep += 1

    def step_replay(self):
        """Advance one replay time step from historical data.

        Returns:
            True if data remains, False if replay is finished.
        """
        if self.current_time_idx >= len(self.hist_data):
            return False

        current_time_data = self.hist_data[self.current_time_idx]
        current_ids = set()

        for row in current_time_data:
            ac_id = int(row[0])
            timestamp = row[1]
            lat, lon, alt = row[2], row[3], row[4]

            current_ids.add(ac_id)
            self._create_aircraft_for_replay(ac_id)
            self.aircrafts[ac_id].set_state_from_data(
                lon, lat, alt, timestamp)
            self.aircrafts[ac_id].done = False
            self.aircraft_missing_count[ac_id] = 0

        # Mark aircraft as done after 3 consecutive missing frames
        for ac_id in list(self.aircrafts.keys()):
            if ac_id not in current_ids:
                self.aircraft_missing_count[ac_id] = (
                    self.aircraft_missing_count.get(ac_id, 0) + 1)
                if (self.aircraft_missing_count[ac_id] >= 3
                        and not self.aircrafts[ac_id].done):
                    self.aircrafts[ac_id].done = True

        self.current_time_idx += 1
        self.timestep += 1
        return True

    def check_all_done(self):
        """Return True when all aircraft have completed their routes."""
        if self.replay_mode:
            return self.current_time_idx >= len(self.hist_data)
        return all(ac.done for ac in self.aircrafts.values())

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self, max_steps=10000):
        """Run the full simulation loop with visualisation."""
        self.init_visualization()

        if self.replay_mode:
            print(f"Starting replay ({len(self.hist_data)} steps)...")
        else:
            print(f"Starting simulation with {self.num_agents} aircraft...")

        for _ in range(max_steps):
            if self.replay_mode:
                if not self.step_replay():
                    break
            else:
                self.step()

            self.update_visualization()

            if self.check_all_done():
                if not self.replay_mode and self.evaluator is not None:
                    self.evaluator.finalize(self.aircrafts)
                    self.evaluator.print_report()
                print(f"Completed at timestep {self.timestep}.")
                break

        print("Simulation complete. Closing in 3 seconds...")
        plt.pause(3)
        plt.ioff()
        plt.close(self.fig)

    # ------------------------------------------------------------------
    # Frame export
    # ------------------------------------------------------------------

    def save_frame(self, output_dir='./frames', fmt='svg'):
        """Save the current visualisation frame as an image file."""
        os.makedirs(output_dir, exist_ok=True)
        filename = f"{self.timestep:06d}.{fmt}"
        filepath = os.path.join(output_dir, filename)
        self.fig.savefig(filepath, format=fmt, dpi=150,
                         bbox_inches='tight', transparent=False,
                         facecolor='white', edgecolor='none')
