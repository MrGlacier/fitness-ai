"""CLI: python -m fitness.import_plan PATH [--metadata metadata.json]."""
import argparse
import json
from pathlib import Path

from fitness.archive import AnalystStore


def main() -> int:
    parser = argparse.ArgumentParser(description="Archive and validate an existing training plan")
    parser.add_argument("source", type=Path)
    parser.add_argument("--metadata", type=Path, help="Plan metadata for CSV/Markdown session tables")
    args = parser.parse_args()
    try:
        metadata = json.loads(args.metadata.read_text()) if args.metadata else None
        plan = AnalystStore().import_plan(args.source, metadata)
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Import failed: {exc}\n")
    print(f"Imported {plan.id}: {len(plan.sessions)} sessions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
