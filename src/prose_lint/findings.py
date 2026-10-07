from __future__ import annotations

from dataclasses import asdict, dataclass

SEVERITIES = ("info", "warning", "error")


@dataclass
class Finding:
    path: str
    line: int
    rule: str
    severity: str
    message: str
    excerpt: str
    data: dict

    def as_dict(self) -> dict:
        return asdict(self)
