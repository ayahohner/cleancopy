from __future__ import annotations

from dataclasses import asdict, dataclass

from spacy.tokens import Token

SEVERITIES = ("info", "warning", "error")


@dataclass
class Hit:
    """What a rule reports: the flagged word, a message, and data for tuning."""

    token: Token
    message: str
    data: dict
    severity: str | None = None  # overrides the rule's severity


@dataclass
class Finding:
    path: str
    line: int
    rule: str
    severity: str
    message: str
    excerpt: str
    context: str  # the preceding sentences the rule read, if any
    word: str
    occurrence: int  # 1 for the first instance of ``word`` in ``excerpt``
    data: dict

    def as_dict(self) -> dict:
        return asdict(self)
