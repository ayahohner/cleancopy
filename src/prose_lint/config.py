"""Project configuration, read from the nearest ``prose-lint.toml``.

```toml
include = ["src/content/posts/*.md"]

[lexicon]                       # what kind of thing each noun names
agent = ["AI agent", "model"]
physical = ["server", "phone"]
abstract = ["sequencer", "record"]
text = ["rule", "message"]        # can ask or say, not decide
mixed = ["resolver"]            # never flagged

[rules.literal-verbs]
severity = "warning"            # "info", "warning", "error", or "off"
allow = ["compiler reject"]     # "subject verb"; subject may be "@class" or "*"

[rules.ambiguous-pronouns]
ratio = 0.95                    # flag when the runner-up has this share of the leader's salience

[verbs]                         # added to the built-in verb table
verb.offer = { suggest = ["provide"] }
```
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

NAME = "prose-lint.toml"


@dataclass
class Config:
    root: Path = field(default_factory=Path.cwd)
    include: list[str] = field(default_factory=list)
    lexicon: dict[str, list[str]] = field(default_factory=dict)
    rules: dict[str, dict] = field(default_factory=dict)
    verbs: dict = field(default_factory=dict)

    def rule(self, name: str) -> dict:
        return self.rules.get(name, {})

    def severity(self, name: str) -> str:
        return self.rule(name).get("severity", "warning")

    def files(self) -> list[Path]:
        return sorted({p for pattern in self.include for p in self.root.glob(pattern)})

    def allow(self, name: str) -> list[tuple[str, str]]:
        """Allow entries as (subject, verb); a bare verb allows every subject."""
        pairs = (entry.strip().lower().rpartition(" ") for entry in self.rule(name).get("allow", []))
        return [(subject or "*", verb) for subject, _, verb in pairs]


def find(start: Path) -> Path | None:
    return next((d / NAME for d in [start, *start.parents] if (d / NAME).is_file()), None)


def load(path: Path | None) -> Config:
    if path is None:
        return Config()
    data = tomllib.loads(path.read_text())
    return Config(path.parent, data.get("include", []), data.get("lexicon", {}), data.get("rules", {}), data.get("verbs", {}))
