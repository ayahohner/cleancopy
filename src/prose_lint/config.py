"""Project configuration, read from the nearest ``prose-lint.toml``.

```toml
include = ["src/content/posts/*.md"]

[lexicon]                       # what kind of thing each noun names
agent = ["AI agent", "model"]
physical = ["server", "phone"]
abstract = ["sequencer", "record"]
mixed = ["resolver"]            # never flagged

[rules.literal-verbs]
severity = "warning"            # "info", "warning", "error", or "off"
allow = ["compiler reject"]     # "subject verb"; subject may be "@class" or "*"
verbnet = false                 # also report VerbNet-restricted verbs, at info

[rules.ambiguous-pronouns]
severity = "warning"
ratio = 0.85                    # flag when the runner-up has this share of the leader's salience

[verbs]                         # added to the built-in verb table
verb.offer = { suggest = ["provide"] }
ignore.verbs = ["serve"]
```
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

NAME = "prose-lint.toml"


@dataclass
class Config:
    root: Path
    include: list[str] = field(default_factory=list)
    lexicon: dict[str, list[str]] = field(default_factory=dict)
    rules: dict[str, dict] = field(default_factory=dict)
    verbs: dict = field(default_factory=dict)

    def rule(self, name: str) -> dict:
        return self.rules.get(name, {})

    def severity(self, name: str) -> str:
        return self.rule(name).get("severity", "warning")

    def allow(self, name: str) -> list[tuple[str, str]]:
        pairs = []
        for entry in self.rule(name).get("allow", []):
            subject, _, verb = entry.strip().rpartition(" ")
            pairs.append((subject.lower() or "*", verb.lower()))
        return pairs


def find(start: Path) -> Path | None:
    for d in [start, *start.parents]:
        if (d / NAME).is_file():
            return d / NAME
    return None


def load(path: Path | None) -> Config:
    if path is None:
        return Config(root=Path.cwd())
    data = tomllib.loads(path.read_text())
    return Config(
        root=path.parent,
        include=data.get("include", []),
        lexicon=data.get("lexicon", {}),
        rules=data.get("rules", {}),
        verbs=data.get("verbs", {}),
    )
