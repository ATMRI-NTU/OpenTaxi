#!/usr/bin/env python3
"""Example: train an RL controller for airport surface movement.

Requires ``stable-baselines3`` and ``gymnasium``:
    pip install stable-baselines3 gymnasium

Usage:
    python train_rl.py train  --map ./opentaxi/airport_map/changi.graphml
    python train_rl.py demo   --map ./opentaxi/airport_map/changi.graphml
"""

import os
import argparse
import numpy as np
from datetime import datetime

try:
    from stable_baselines3 import PPO, A2C
    from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv
    from stable_baselines3.common.callbacks import (
        EvalCallback, CheckpointCallback, CallbackList)
    from stable_baselines3.common.monitor import Monitor
    SB3_AVAILABLE = True
except ImportError:
    SB3_AVAILABLE = False


def make_env(airport_map, planner, num_aircraft, rank, seed=0):
    def _init():
        from opentaxi.rl_env import AirportRLEnv
        env = AirportRLEnv(
            airport_map=airport_map, planner=planner,
            num_aircraft=num_aircraft, max_aircraft=50,
            min_separation=50.0, max_steps=2000, render=False)
        env = Monitor(env)
        env.reset(seed=seed + rank)
        return env
    return _init


def train(args):
    if not SB3_AVAILABLE:
        print("Error: stable-baselines3 is required. "
              "Install with: pip install stable-baselines3")
        return

    from opentaxi.airport import AirportMap
    from opentaxi.planners import AStarPlanner

    airport_map = AirportMap(args.map_path)
    planner = AStarPlanner(airport_map)

    if args.num_envs > 1:
        env = SubprocVecEnv([
            make_env(airport_map, planner, args.num_aircraft, i, args.seed)
            for i in range(args.num_envs)])
    else:
        env = DummyVecEnv([
            make_env(airport_map, planner, args.num_aircraft, 0, args.seed)])

    eval_env = DummyVecEnv([
        make_env(airport_map, planner, args.num_aircraft, 0, args.seed + 100)])

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir = os.path.join(args.output_dir, f"run_{timestamp}")
    os.makedirs(log_dir, exist_ok=True)

    policy_kwargs = dict(net_arch=[256, 256, 128])

    if args.algorithm == "PPO":
        model = PPO("MlpPolicy", env,
                     learning_rate=args.learning_rate,
                     n_steps=1024, batch_size=128, n_epochs=10,
                     gamma=0.99, gae_lambda=0.95, clip_range=0.2,
                     ent_coef=0.01, policy_kwargs=policy_kwargs,
                     verbose=1, tensorboard_log=log_dir)
    elif args.algorithm == "A2C":
        model = A2C("MlpPolicy", env,
                     learning_rate=args.learning_rate,
                     n_steps=5, gamma=0.99, gae_lambda=0.95,
                     ent_coef=0.01, policy_kwargs=policy_kwargs,
                     verbose=1, tensorboard_log=log_dir)
    else:
        raise ValueError(f"Unknown algorithm: {args.algorithm}")

    callbacks = CallbackList([
        CheckpointCallback(save_freq=10000, save_path=log_dir,
                           name_prefix="airport_rl"),
        EvalCallback(eval_env, best_model_save_path=log_dir,
                     log_path=log_dir, eval_freq=5000,
                     n_eval_episodes=5, deterministic=True),
    ])

    print(f"Training {args.algorithm} for {args.total_timesteps} steps...")
    model.learn(total_timesteps=args.total_timesteps,
                callback=callbacks, progress_bar=True)
    model.save(os.path.join(log_dir, "final_model"))
    print(f"Saved to {log_dir}")
    env.close()
    eval_env.close()


def demo(args):
    from opentaxi.airport import AirportMap
    from opentaxi.planners import AStarPlanner
    from opentaxi.simulator import Simulation
    from opentaxi.rl_env import RLController

    airport_map = AirportMap(args.map_path)
    planner = AStarPlanner(airport_map)

    agent = None
    if args.model_path and SB3_AVAILABLE:
        agent = PPO.load(args.model_path)
        print(f"Loaded agent from {args.model_path}")

    controller = RLController(airport_map, agent=agent)
    sim = Simulation(airport_map, planner, controller,
                     num_agents=args.num_aircraft)
    sim.run(max_steps=args.max_steps)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Train / demo RL airport controller")
    sub = parser.add_subparsers(dest="command")

    tp = sub.add_parser("train")
    tp.add_argument("--map_path", required=True)
    tp.add_argument("--algorithm", default="PPO", choices=["PPO", "A2C"])
    tp.add_argument("--num_aircraft", type=int, default=10)
    tp.add_argument("--num_envs", type=int, default=4)
    tp.add_argument("--total_timesteps", type=int, default=1_000_000)
    tp.add_argument("--learning_rate", type=float, default=3e-4)
    tp.add_argument("--seed", type=int, default=42)
    tp.add_argument("--output_dir", default="./rl_models")

    dp = sub.add_parser("demo")
    dp.add_argument("--map_path", required=True)
    dp.add_argument("--model_path", default=None)
    dp.add_argument("--num_aircraft", type=int, default=10)
    dp.add_argument("--max_steps", type=int, default=5000)

    args = parser.parse_args()
    if args.command == "train":
        train(args)
    elif args.command == "demo":
        demo(args)
    else:
        parser.print_help()
