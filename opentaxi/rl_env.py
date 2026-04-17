"""Gymnasium RL environment for airport surface movement control.

Wraps the existing simulation as a plug-and-play RL environment without
modifying core simulation code.

State space (per aircraft, sorted by remaining path length each step):
    0. remaining distance (normalised by 2000 m)
    1. spatial distance to predecessor (normalised by 50 m, capped at 1)
    2. velocity (normalised by 30 km/h)
    3. is_arrived flag
    4. is_waiting flag (arrived but not yet departed)
    5. is_done flag

Action space:
    MultiBinary – one stop/go decision per aircraft slot.

Example::

    from opentaxi.rl_env import AirportRLEnv
    env = AirportRLEnv(airport_map, planner, num_aircraft=10)
    obs, info = env.reset()
    action = env.action_space.sample()
    obs, reward, done, truncated, info = env.step(action)
"""

import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import matplotlib
matplotlib.use('Agg')

import gymnasium as gym
from gymnasium import spaces
import numpy as np


class AirportRLEnv(gym.Env):
    """Plug-and-play RL wrapper for the airport surface simulation."""

    metadata = {"render_modes": ["human", "none"]}

    def __init__(self, airport_map, planner, num_aircraft=10,
                 max_aircraft=50, min_separation=50.0,
                 hard_stop_distance=20.0, max_steps=2000,
                 max_episodes=1500, render=False):
        super().__init__()

        self.airport_map = airport_map
        self.planner = planner
        self.num_aircraft = num_aircraft
        self.max_aircraft = max_aircraft
        self.min_separation = min_separation
        self.hard_stop_distance = hard_stop_distance
        self.max_steps = max_steps
        self.max_episodes = max_episodes
        self.render_enabled = render

        self.sim = None
        self.timestep = 0
        self.sorted_aircraft_ids = []

        self.obs_dim = 6
        self.observation_space = spaces.Box(
            low=0.0, high=1.0,
            shape=(max_aircraft * self.obs_dim,),
            dtype=np.float32)
        self.action_space = spaces.MultiBinary(max_aircraft)

        self.episode_count = 0
        self.episode_reward = 0.0
        self.episode_conflicts = 0
        self.episode_completions = 0
        self.episode_reward_record = []

        self.reward_progress_total = 0.0
        self.reward_conflict_total = 0.0

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.episode_count += 1
        if self.episode_count > self.max_episodes:
            self._save_episode_data()
            self.training_done = True

        self.close()

        from opentaxi.simulator import Simulation
        self.sim = Simulation(
            airport_map=self.airport_map, planner=self.planner,
            controller=None, num_agents=self.num_aircraft)

        if self.render_enabled:
            self.sim.init_visualization()

        self.timestep = 0
        self.episode_reward = 0.0
        self.episode_conflicts = 0
        self.episode_completions = 0
        self.reward_progress_total = 0.0
        self.reward_conflict_total = 0.0

        for ac in self.sim.aircrafts.values():
            ac._rl_rewarded = False

        self._update_sorted_order()
        return self._get_obs(), self._get_info()

    def step(self, action):
        prev_remaining = {}
        for ac_id, ac in self.sim.aircrafts.items():
            if not ac.done:
                prev_remaining[ac_id] = self._get_remaining_dist(ac)

        self._update_sorted_order()
        self._apply_actions(action)

        for ac in self.sim.aircrafts.values():
            if not ac.done and not getattr(ac, 'arrived', False):
                ac.step()
            ac.check_arrival(current_timestep=self.timestep,
                             time_step_duration=5.0)

        self.timestep += 1
        self._update_sorted_order()

        if self.render_enabled:
            self.sim.update_visualization()

        reward = self._calc_reward(prev_remaining)
        self.episode_reward += reward

        all_arrived = all(
            getattr(ac, 'arrived', False) or ac.done
            for ac in self.sim.aircrafts.values())
        terminated = all_arrived
        truncated = self.timestep >= self.max_steps

        if terminated or truncated:
            self.episode_reward_record.append(
                self.episode_reward / self.timestep)

        return self._get_obs(), reward, terminated, truncated, self._get_info()

    # ---- Helpers ----

    def _get_remaining_dist(self, ac):
        if ac.done or getattr(ac, 'arrived', False):
            return 0.0
        path_length = ac.path_s[-1] if len(ac.path_s) > 0 else 0
        return max(0, path_length - ac.curr_s)

    def _update_sorted_order(self):
        items = [(ac_id, self._get_remaining_dist(ac))
                 for ac_id, ac in self.sim.aircrafts.items()]
        items.sort(key=lambda x: x[1])
        self.sorted_aircraft_ids = [ac_id for ac_id, _ in items]

    def _apply_actions(self, action):
        for i, ac_id in enumerate(self.sorted_aircraft_ids):
            if i >= len(action):
                break
            ac = self.sim.aircrafts[ac_id]
            if ac.done or getattr(ac, 'arrived', False):
                continue

            force_stop = False
            if i > 0:
                pred_id = self.sorted_aircraft_ids[i - 1]
                pred_ac = self.sim.aircrafts[pred_id]
                if not pred_ac.done:
                    dist = np.sqrt((ac.x - pred_ac.x)**2
                                   + (ac.y - pred_ac.y)**2)
                    if dist < self.hard_stop_distance:
                        force_stop = True

            if force_stop or action[i] == 0:
                ac.yield_flag = True
                ac.immediate_stop = True
            else:
                ac.yield_flag = False
                ac.immediate_stop = False

    def _get_obs(self):
        obs = np.zeros(self.max_aircraft * self.obs_dim, dtype=np.float32)
        for i, ac_id in enumerate(self.sorted_aircraft_ids):
            if i >= self.max_aircraft:
                break
            ac = self.sim.aircrafts[ac_id]
            idx = i * self.obs_dim

            is_done = 1.0 if ac.done else 0.0
            is_arrived = 1.0 if getattr(ac, 'arrived', False) else 0.0
            is_waiting = 1.0 if (is_arrived and not ac.done) else 0.0

            if ac.done:
                obs[idx:idx + self.obs_dim] = [0, 1, 0, 1, 0, 1]
            else:
                remaining = self._get_remaining_dist(ac)
                remaining_norm = min(remaining / 2000.0, 1.0)

                if i == 0:
                    dist_pred_norm = 1.0
                else:
                    pred = self.sim.aircrafts[
                        self.sorted_aircraft_ids[i - 1]]
                    dist = np.sqrt((ac.x - pred.x)**2
                                   + (ac.y - pred.y)**2)
                    dist_pred_norm = min(dist / 50.0, 1.0)

                v_norm = (min(ac.curr_v / 30.0, 1.0)
                          if not is_arrived else 0.0)

                obs[idx:idx + self.obs_dim] = [
                    remaining_norm, dist_pred_norm, v_norm,
                    is_arrived, is_waiting, is_done]
        return obs

    def _calc_reward(self, prev_remaining):
        r_progress = 0.0
        r_conflict = 0.0
        max_dist_per_step = 35.0

        progress_list = []
        for ac_id in self.sorted_aircraft_ids:
            ac = self.sim.aircrafts[ac_id]
            if ac.done or getattr(ac, 'arrived', False):
                continue
            if ac_id in prev_remaining:
                delta = (prev_remaining[ac_id]
                         - self._get_remaining_dist(ac))
                progress_list.append(
                    delta / max_dist_per_step if delta > 0 else 0.0)

        if progress_list:
            r_progress = sum(progress_list) / len(progress_list)

        for ac in self.sim.aircrafts.values():
            if (getattr(ac, 'arrived', False)
                    and not getattr(ac, '_rl_rewarded', False)):
                ac._rl_rewarded = True
                self.episode_completions += 1

        for i, ac_id in enumerate(self.sorted_aircraft_ids):
            ac = self.sim.aircrafts[ac_id]
            if ac.done or getattr(ac, 'arrived', False) or i == 0:
                continue
            pred = self.sim.aircrafts[self.sorted_aircraft_ids[i - 1]]
            if pred.done:
                continue
            dist = np.sqrt((ac.x - pred.x)**2 + (ac.y - pred.y)**2)
            if dist < self.min_separation:
                r_conflict -= 2.0 * (1.0 - dist / self.min_separation)
                self.episode_conflicts += 1

        self.reward_progress_total += r_progress
        self.reward_conflict_total += r_conflict
        return r_progress + r_conflict

    def _get_info(self):
        active = sum(1 for ac in self.sim.aircrafts.values()
                     if not ac.done)
        waiting = sum(1 for ac in self.sim.aircrafts.values()
                      if getattr(ac, 'arrived', False) and not ac.done)
        done = sum(1 for ac in self.sim.aircrafts.values() if ac.done)
        return {
            "timestep": self.timestep,
            "active": active, "waiting": waiting, "done": done,
            "conflicts": self.episode_conflicts,
            "completions": self.episode_completions,
        }

    def _save_episode_data(self):
        try:
            import scipy.io as scio
            scio.savemat('airport.mat',
                         mdict={'reward': self.episode_reward_record})
        except ImportError:
            np.save('airport_rewards.npy', self.episode_reward_record)

    def close(self):
        if self.render_enabled and self.sim is not None:
            import matplotlib.pyplot as plt
            if hasattr(self.sim, 'fig') and self.sim.fig is not None:
                plt.close(self.sim.fig)


class RLController:
    """Drop-in controller that delegates decisions to a trained RL agent."""

    def __init__(self, airport_map, agent=None, min_separation=50.0):
        self.airport_map = airport_map
        self.agent = agent
        self.min_separation = min_separation

        x_min, x_max, y_min, y_max = airport_map.get_bounds()
        self.x_min, self.x_max = x_min, x_max
        self.y_min, self.y_max = y_min, y_max
        self.x_range = x_max - x_min
        self.y_range = y_max - y_min

    def update(self, aircrafts, timestep=None):
        if self.agent is None:
            for ac in aircrafts.values():
                if not ac.done and not getattr(ac, 'arrived', False):
                    ac.yield_flag = False
                    ac.immediate_stop = False
            return

        obs = self._build_observation(aircrafts)
        action, _ = self.agent.predict(obs, deterministic=True)

        for ac_id, ac in aircrafts.items():
            if ac.done or getattr(ac, 'arrived', False):
                continue
            if ac_id < len(action):
                if action[ac_id] == 0:
                    ac.yield_flag = True
                    ac.immediate_stop = True
                    ac.wait_at_s = ac.curr_s + 10
                else:
                    ac.yield_flag = False
                    ac.immediate_stop = False
                    ac.wait_at_s = None

    def _build_observation(self, aircrafts, max_aircraft=50):
        obs = np.zeros((max_aircraft, 8), dtype=np.float32)
        positions = [(k, v.x, v.y) for k, v in aircrafts.items()
                     if not v.done]

        for ac_id, ac in aircrafts.items():
            if ac_id >= max_aircraft:
                continue
            if ac.done:
                obs[ac_id] = [0, 0, 0, 1, 0, 1, 1, 1]
                continue

            x_n = (ac.x - self.x_min) / self.x_range * 2 - 1
            y_n = (ac.y - self.y_min) / self.y_range * 2 - 1
            v_n = ac.curr_v / 30.0

            pl = ac.path_s[-1] if len(ac.path_s) > 0 else 1
            progress = ac.curr_s / pl

            dd = np.sqrt((ac.x - ac.end[0])**2 + (ac.y - ac.end[1])**2)
            dd_n = min(dd / 2000.0, 1.0)

            min_d = float('inf')
            for oid, ox, oy in positions:
                if oid != ac_id:
                    d = np.sqrt((ac.x - ox)**2 + (ac.y - oy)**2)
                    min_d = min(min_d, d)
            dn = min(min_d / 200.0, 1.0) if min_d < float('inf') else 1.0

            arr = 1.0 if getattr(ac, 'arrived', False) else 0.0
            obs[ac_id] = [x_n, y_n, v_n, progress, dd_n, dn, arr, 0.0]

        return obs

    def get_statistics(self):
        return {}
