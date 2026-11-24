"""Private, portable plan archive and transactional local analyst persistence."""
from contextlib import contextmanager
import csv
import hashlib
from io import StringIO
import json
import os
import shutil
import sqlite3
from tempfile import NamedTemporaryFile
from zipfile import ZipFile
from xml.etree import ElementTree
from pathlib import Path

from fitness.analyst_models import PlanAssignment, Race, TrainingPlan

ROOT = Path(__file__).resolve().parent.parent


class AnalystStore:
    def __init__(self, root: Path | None = None):
        self.root = root or Path(os.getenv("FITNESS_DATA_DIR", str(ROOT / "training_plans")))
        self.originals = self.root / "originals"
        self.structured = self.root / "structured"
        self.originals.mkdir(parents=True, exist_ok=True)
        self.structured.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS records(kind TEXT, id TEXT, body TEXT,
                    PRIMARY KEY(kind,id));
                CREATE TABLE IF NOT EXISTS preparation_history(race_id TEXT, day TEXT, body TEXT,
                    PRIMARY KEY(race_id,day));
            ''')

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.root / "analyst.sqlite3", timeout=10)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def put(self, kind: str, key: str, body: dict) -> None:
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO records VALUES(?,?,?)",
                       (kind, key, json.dumps(body, ensure_ascii=False)))

    def records(self, kind: str) -> list[dict]:
        with self.connect() as db:
            return [json.loads(r[0]) for r in db.execute(
                "SELECT body FROM records WHERE kind=? ORDER BY id", (kind,))]

    def plans(self) -> list[TrainingPlan]:
        # Portable JSON files are the source of truth; edits are validated on read.
        return [TrainingPlan.model_validate_json(p.read_text())
                for p in sorted(self.structured.glob("*.json"))]

    def save_plan(self, plan: TrainingPlan) -> None:
        target = self.structured / f"{plan.id}.json"
        with NamedTemporaryFile(mode="w", dir=self.structured, suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(plan.model_dump_json(indent=2))
        try:
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)

    def import_plan(self, source: Path, metadata: dict | None = None) -> TrainingPlan:
        """Import explicit tables only. Unstructured documents require reviewed JSON."""
        source = source.resolve()
        suffix = source.suffix.lower()
        if suffix not in {".json", ".csv", ".md", ".pdf", ".xlsx", ".xls"}:
            raise ValueError("Unsupported plan format")
        digest = hashlib.sha256(source.read_bytes()).hexdigest()[:16]
        original = self.originals / f"{digest}{suffix}"
        if not original.exists():
            shutil.copyfile(source, original)
        plan = read_plan(source, metadata)
        self.save_plan(plan)
        return plan

    def save_race(self, race: Race) -> Race:
        import uuid
        if not race.id:
            race = race.model_copy(update={"id": uuid.uuid4().hex})
        self.put("race", race.id, race.model_dump(mode="json"))
        return race

    def save_assignment(self, assignment: PlanAssignment) -> None:
        if assignment.end_date < assignment.start_date:
            raise ValueError("Das Gültigkeitsende liegt vor dem Planstart.")
        if assignment.start_date.weekday() != 0:
            raise ValueError("Der Start der Planwoche 1 muss ein Montag sein.")
        if assignment.plan_id not in {p.id for p in self.plans()}:
            raise ValueError("Der gewählte Trainingsplan ist nicht im Archiv vorhanden.")
        from datetime import datetime, timezone
        body = dict(assignment.model_dump(mode="json"), updated_at=datetime.now(timezone.utc).isoformat())
        self.put("assignment", assignment.start_date.isoformat(), body)

    def preparation_history(self, race_id: str) -> list[dict]:
        with self.connect() as db:
            return [dict(day=r[0], **json.loads(r[1])) for r in db.execute(
                "SELECT day,body FROM preparation_history WHERE race_id=? ORDER BY day", (race_id,))]


def read_xlsx_table(source: Path) -> list[dict]:
    """Read explicit scalar cells in sheet1, without guessing formulas or merged layouts."""
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with ZipFile(source) as workbook:
        strings = []
        if "xl/sharedStrings.xml" in workbook.namelist():
            strings = ["".join(s.itertext()) for s in ElementTree.fromstring(
                workbook.read("xl/sharedStrings.xml")).findall("m:si", ns)]
        root = ElementTree.fromstring(workbook.read("xl/worksheets/sheet1.xml"))
        if root.find("m:mergeCells", ns) is not None:
            raise ValueError("Merged Excel layouts require a reviewed CSV export")
        rows = []
        for row in root.findall("m:sheetData/m:row", ns):
            cells = {}
            for cell in row.findall("m:c", ns):
                if cell.find("m:f", ns) is not None:
                    raise ValueError("Excel formulas require a reviewed values-only CSV export")
                column = "".join(c for c in cell.attrib.get("r", "") if c.isalpha())
                value = cell.findtext("m:v", default="", namespaces=ns)
                kind = cell.attrib.get("t")
                if kind == "s":
                    value = strings[int(value)]
                elif kind == "inlineStr":
                    value = "".join(cell.find("m:is", ns).itertext())
                if value != "":
                    cells[column] = value
            if cells:
                rows.append(cells)
        if len(rows) < 2:
            raise ValueError("Excel sheet1 requires a header and session rows")
        headers = rows[0]
        if not {"week", "day", "title", "sport"} <= set(headers.values()):
            raise ValueError("Excel sheet1 must use explicit session schema headers")
        if any(set(row) - set(headers) for row in rows[1:]):
            raise ValueError("Excel data without column headers")
        return [{headers[column]: value for column, value in row.items()} for row in rows[1:]]


def read_plan(source: Path, metadata: dict | None = None) -> TrainingPlan:
    """Liest ein unterstütztes Format ohne Archiv- oder Datenbankänderung."""
    suffix = source.suffix.lower()
    if suffix == ".json":
        data = json.loads(source.read_text(encoding="utf-8-sig"))
        if isinstance(data, dict) and ("userTrainingPlan" in data or ("weeks" in data and "title" in data)):
            from fitness.lorang_import import import_lorang
            return import_lorang(data)
        if isinstance(data, dict) and "weeks" in data and "sessions" not in data:
            raise ValueError("Konvertierter Intervals-Plan: Bitte die ursprüngliche Lorang-JSON-Datei importieren.")
    elif suffix == ".xlsx":
        rows = read_xlsx_table(source)
        data = dict(metadata or {})
        data["sessions"] = rows
    elif suffix in {".csv", ".md"}:
        text = source.read_text(encoding="utf-8-sig")
        if suffix == ".csv":
            rows = list(csv.DictReader(StringIO(text)))
        else:
            lines = [line.strip().strip("|") for line in text.splitlines() if line.strip().startswith("|")]
            if len(lines) < 3:
                raise ValueError("Markdown requires an explicit session table")
            rows = list(csv.DictReader([lines[0], *lines[2:]], delimiter="|"))
            rows = [{k.strip(): v.strip() for k, v in row.items()} for row in rows]
        data = dict(metadata or {})
        data["sessions"] = [{k: v for k, v in row.items() if v not in ("", None)} for row in rows]
    else:
        raise ValueError("Original archived. Export a reviewed CSV/JSON table for import; PDF/legacy XLS interpretation is not automatic.")
    return TrainingPlan.model_validate(data)
