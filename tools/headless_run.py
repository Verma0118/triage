"""Run a scenario headless and print the timeline. Mock only.

Usage:
  .venv/bin/python tools/headless_run.py [scenario_name] [--approve-delay N]

S3: scripted operator approves every proposed line N seconds after it appears.
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
from bridge import MockUnit
from engine.world import World


def run(
    scenario: str,
    max_seconds: float = 120.0,
    approve_delay: float | None = 2.0,
) -> World:
    world = World()
    world.load_scenario(scenario)
    mock = MockUnit()
    world.apply_u1_snapshot(mock.read())
    world.handle_command({"type": "start"})
    max_ticks = int(max_seconds / config.DT) + 1
    last_statuses: dict[str, str] = {}
    first_seen: dict[str, float] = {}
    n_events = 0

    print(f"scenario={scenario} replay={world.replay} approve_delay={approve_delay}")
    for _ in range(max_ticks):
        world.apply_u1_snapshot(mock.read())
        world.step(config.DT)

        if approve_delay is not None and not world.replay:
            for line in world.plan:
                if line.approved:
                    continue
                if line.id not in first_seen:
                    first_seen[line.id] = world.t
                if world.t - first_seen[line.id] + 1e-12 >= approve_delay:
                    effects = world.handle_command(
                        {"type": "approve", "line_ids": [line.id]}
                    )
                    for eff in effects:
                        if eff and eff[0] == "motor_test":
                            mock.motor_test()

        for track in world.tracks:
            prev = last_statuses.get(track.id)
            if prev != track.status:
                print(
                    f"t={world.t:6.1f}  track={track.id:3s}  "
                    f"{prev or 'spawn'} -> {track.status}  "
                    f"pos=({track.x:.1f},{track.y:.1f})  "
                    f"label={track.label} score={track.threat_score}"
                )
                last_statuses[track.id] = track.status

        while n_events < len(world.events):
            e = world.events[n_events]
            print(f"t={e.t:6.1f}  EVENT {e.kind:12s}  {e.msg}")
            n_events += 1

        if world.phase == "ended":
            break

    print(f"phase={world.phase} t={world.t:.1f}")
    for track in world.tracks:
        print(
            f"  final {track.id}: status={track.status} label={track.label} "
            f"pos=({track.x:.1f},{track.y:.1f})"
        )
    for unit in world.units:
        print(
            f"  unit {unit.id}: state={unit.state} variant={unit.variant} "
            f"pos=({unit.x:.1f},{unit.y:.1f})"
        )
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
    parser.add_argument(
        "--approve-delay",
        type=float,
        default=2.0,
        help="Seconds after a plan line appears before auto-approve. Negative disables.",
    )
    args = parser.parse_args()
    delay = None if args.approve_delay < 0 else args.approve_delay
    run(args.scenario, max_seconds=args.max_seconds, approve_delay=delay)


if __name__ == "__main__":
    main()
