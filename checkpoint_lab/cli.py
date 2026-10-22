"""Compare checkpoint intervals using a local JSON scenario."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

from .simulator import compare_intervals


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", type=Path)
    parser.add_argument("--json", action="store_true", help="emit ranked results as JSON")
    args = parser.parse_args(argv)
    try:
        config = json.loads(args.scenario.read_text(encoding="utf-8"))
        if not isinstance(config, dict):
            raise ValueError("scenario must be a JSON object")
        results = compare_intervals(**config)
    except (OSError, ValueError, TypeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps([dict(asdict(r), efficiency=r.efficiency) for r in results], indent=2))
    else:
        print("interval_s  total_s   lost_s   checkpoint_s  recovery_s  efficiency")
        for r in results:
            print(f"{r.interval_seconds:10.1f}  {r.total_seconds:7.1f}  {r.lost_work_seconds:7.1f}"
                  f"  {r.checkpoint_seconds:12.1f}  {r.recovery_seconds:10.1f}  {r.efficiency:10.2%}")
        print("Ranked on this synthetic trace only; evaluate on held-out traces before choosing a policy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
