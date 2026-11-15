"""Run a scenario headless and print the timeline. Mock only.

Usage:
  .venv/bin/python tools/headless_run.py [scenario_name]

S1: tracks only — no scoring, no planner, no approvals.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running as `python tools/headless_run.py` from repo root.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config
from engine.world import World


def run(scenario: str, max_seconds: float = 120.0) -> World:
    world = World()
    world.load_scenario(scenario)
    world.handle_command({"type": "start"})
    max_ticks = int(max_seconds / config.DT) + 1
    last_statuses: dict[str, str] = {}

    print(f"scenario={scenario} replay={world.replay}")
    for _ in range(max_ticks):
        world.step(config.DT)
        for track in world.tracks:
            prev = last_statuses.get(track.id)
            if prev != track.status:
                print(
                    f"t={world.t:6.1f}  track={track.id:3s}  "
                    f"{prev or 'spawn'} -> {track.status}  "
                    f"pos=({track.x:.1f},{track.y:.1f})  truth={track.truth}"
                )
                last_statuses[track.id] = track.status
        if world.phase == "ended":
            break

    print(f"phase={world.phase} t={world.t:.1f}")
    for track in world.tracks:
        print(
            f"  final {track.id}: status={track.status} "
            f"pos=({track.x:.1f},{track.y:.1f})"
        )
    for unit in world.units:
        print(f"  unit {unit.id}: state={unit.state} variant={unit.variant}")
    return world


def main() -> None:
    parser = argparse.ArgumentParser(description="Headless Triage scenario run")
    parser.add_argument(
        "scenario",
        nargs="?",
        default="juniper_night1",
        help="juniper_night1 | juniper_night2 | tower22",
    )
    parser.add_argument("--max-seconds", type=float, default=120.0)
    args = parser.parse_args()
    run(args.scenario, max_seconds=args.max_seconds)


if __name__ == "__main__":
    main()
