from datetime import datetime, timezone
import json
from collections import deque

from src.utils.app_paths import user_data_dir


class AuditLog:
    def __init__(self):
        self.path = user_data_dir() / "security_events.jsonl"

    def record(self, event: str, **details) -> None:
        row = {
            "time": datetime.now(timezone.utc).isoformat(),
            "event": event,
            **details,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    def recent(self, limit: int = 30) -> list[dict]:
        if not self.path.exists():
            return []

        rows = deque(maxlen=limit)
        with self.path.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    try:
                        rows.append(json.loads(line))
                    except ValueError:
                        rows.append({'event': 'audit_warning', 'reason': 'Unreadable audit entry; log may be interrupted or modified.'})
        return list(rows)

    def documents(self) -> list[dict]:
        latest = {}
        if not self.path.exists():
            return []

        with self.path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                row = json.loads(line)
                if row.get("event") == "document":
                    latest[row["source"]] = row

        return sorted(
            (
                row for row in latest.values()
                if row.get("status") != "DELETED"
            ),
            key=lambda row: row["source"],
        )
