"""Command line: python3 -m harness.generate_instance --seed 42 [options]"""
import argparse
import json
import sys
from pathlib import Path

from .config import ConfigError, InstanceConfig
from .dataset import DatasetError, load_places
from .instance import build_instance

DEFAULT_DATASET = Path(__file__).resolve().parent.parent / "data" / "MY.txt"


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python3 -m harness.generate_instance",
                                 description="Generate a seeded problem instance file.")
    ap.add_argument("--seed", type=int, help="required; drives selection and slot assignment")
    ap.add_argument("--customers", type=int, default=10)
    ap.add_argument("--departure", type=int, default=360, help="departure minute since midnight")
    ap.add_argument("--period", type=int, default=480, help="period in minutes")
    ap.add_argument("--speed", type=float, default=40.0, help="km/h")
    ap.add_argument("--dataset", default=str(DEFAULT_DATASET))
    ap.add_argument("--out", help="output file (default instances/<instanceId>.json)")
    args = ap.parse_args(argv)
    try:
        config = InstanceConfig(seed=args.seed, num_customers=args.customers,
                                departure_minute=args.departure, period_minutes=args.period,
                                speed_kmh=args.speed)
        instance = build_instance(load_places(args.dataset), config)
    except (ConfigError, DatasetError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    out = Path(args.out) if args.out else Path("instances") / f"{config.instance_id}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(instance, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
