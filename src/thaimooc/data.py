"""Validated course records and an idempotent SQLite store."""
from dataclasses import asdict, dataclass
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import re
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / "data/processed/courses.sqlite3"


@dataclass
class Course:
    course_id: str
    title: str
    description: str
    url: str
    collected_at: str
    learning_outcomes: str = ""
    category: str | None = None
    institution: str | None = None
    level: str | None = None
    duration_hours: float | None = None
    prerequisites: str | None = None
    provenance: str = "http"

    def __post_init__(self):
        for field in ("course_id", "title", "description", "collected_at"):
            if not isinstance(getattr(self, field), str) or not getattr(self, field).strip():
                raise ValueError(f"Missing {field}")
        if not re.fullmatch(r"[A-Za-z0-9_-]+", self.course_id):
            raise ValueError("Invalid course_id")
        for field in ("learning_outcomes", "provenance"):
            if not isinstance(getattr(self, field), str):
                raise ValueError(f"{field} must be a string")
        for field in ("category", "institution", "level", "prerequisites"):
            if getattr(self, field) is not None and not isinstance(getattr(self, field), str):
                raise ValueError(f"{field} must be a string or null")
        if not isinstance(self.url, str):
            raise ValueError("url must be a string")
        parts = urlsplit(self.url)
        if parts.scheme != "https" or parts.hostname not in {"thaimooc.ac.th", "www.thaimooc.ac.th", "thaimooc.org", "www.thaimooc.org"}:
            raise ValueError("Expected an official HTTPS Thai MOOC course URL")
        if parts.username or parts.password or parts.port not in (None, 443) or parts.query or parts.fragment:
            raise ValueError("Expected a canonical course URL without credentials, query or fragment")
        if parts.path.rstrip("/") != f"/courses/{self.course_id}":
            raise ValueError("Course ID must match URL")
        if self.duration_hours is not None:
            import math
            if isinstance(self.duration_hours, bool) or not isinstance(self.duration_hours, (int, float)) or not math.isfinite(self.duration_hours) or self.duration_hours <= 0:
                raise ValueError("duration_hours must be positive or null")

    def search_text(self):
        return " ".join([self.title, self.title, self.description, self.learning_outcomes])


def load_jsonl(path):
    records = []
    for number, line in enumerate(Path(path).read_text(encoding="utf-8-sig").splitlines(), 1):
        if line.strip():
            try:
                records.append(Course(**json.loads(line)))
            except (TypeError, ValueError) as error:
                raise ValueError(f"{path}:{number}: {error}") from error
    if not records:
        raise ValueError("No course records found")
    return records


def save_courses(courses, db=DEFAULT_DB):
    db = Path(db)
    db.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(db)) as connection, connection:
        connection.execute("CREATE TABLE IF NOT EXISTS courses (course_id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
        connection.executemany(
            "INSERT INTO courses VALUES (?, ?) ON CONFLICT(course_id) DO UPDATE SET payload=excluded.payload",
            [(c.course_id, json.dumps(asdict(c), ensure_ascii=False)) for c in courses],
        )


def read_courses(db=DEFAULT_DB):
    if not Path(db).exists():
        raise ValueError("Course database missing. Run import first.")
    with closing(sqlite3.connect(db)) as connection:
        return [Course(**json.loads(row[0])) for row in connection.execute("SELECT payload FROM courses ORDER BY course_id")]


def quality_report(courses):
    fields = ["category", "institution", "level", "duration_hours", "learning_outcomes", "prerequisites"]
    ids = [c.course_id for c in courses]
    return {"records": len(courses), "unique_ids": len(set(ids)), "duplicate_ids": len(ids)-len(set(ids)),
            "missing": {f: sum(getattr(c, f) in (None, "") for c in courses) for f in fields}}
