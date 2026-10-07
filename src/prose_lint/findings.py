from __future__ import annotations

from dataclasses import asdict, dataclass

from spacy.tokens import Span

SEVERITIES = ("info", "warning", "error")


@dataclass
class Hit:
    """What a rule reports: the sentence, a message, and data for tuning."""

    sentence: Span
    message: str
    data: dict


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
