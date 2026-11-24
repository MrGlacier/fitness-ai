"""CLI für Einzel- und Ordnerimporte mit schreibfreier Vorprüfung."""
import argparse
import json
from pathlib import Path
import sys

from dotenv import load_dotenv

from fitness.archive import ROOT, AnalystStore, read_plan


def main() -> int:
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description="Bestehende Trainingspläne lokal archivieren und validieren")
    parser.add_argument("source", type=Path, nargs="+", help="Dateien oder Verzeichnisse")
    parser.add_argument("--metadata", type=Path, help="Planmetadaten für CSV-/Markdown-/XLSX-Tabellen")
    parser.add_argument("--pattern", default="*.json", help="Dateimuster für Verzeichnisse (Standard: *.json)")
    parser.add_argument("--dry-run", action="store_true", help="Nur prüfen; weder Archiv noch Datenbank verändern")
    args = parser.parse_args()
    try:
        metadata = json.loads(args.metadata.read_text()) if args.metadata else None
        files = sorted({file.resolve() for source in args.source
                        for file in (source.glob(args.pattern) if source.is_dir() else [source])
                        if file.is_file()})
        missing = [source for source in args.source if not source.exists()]
        if missing:
            parser.error("Quellpfad nicht gefunden: " + ", ".join(map(str, missing)))
        if not files:
            parser.error("Keine passenden Trainingsplandateien gefunden.")
        if metadata and len(files) > 1:
            parser.error("--metadata nur für eine einzelne Datei verwenden, damit Plan-IDs nicht kollidieren.")
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Vorbereitung fehlgeschlagen: {exc}\n")
    store = None if args.dry_run else AnalystStore()
    failed = 0
    for source in files:
        try:
            plan = read_plan(source, metadata) if args.dry_run else store.import_plan(source, metadata)
        except (ValueError, OSError) as exc:
            failed += 1
            print(f"Import fehlgeschlagen ({source.name}): {exc}", file=sys.stderr)
            continue
        warnings = sum(s.uncertainty is not None for s in plan.sessions)
        print(f"{'Geprüft' if args.dry_run else 'Importiert'}: {source.name}\n"
              f"  ID: {plan.id} · {len({s.week for s in plan.sessions})} Wochen · "
              f"{len(plan.sessions)} Einheiten · {warnings} unsichere Zuordnungen")
    print(f"{'Prüfung' if args.dry_run else 'Import'}: {len(files)-failed} erfolgreich, {failed} fehlgeschlagen.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
