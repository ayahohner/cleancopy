"""prose-lint: check Markdown prose for verbs that do not fit their subjects
and for pronouns with more than one likely antecedent."""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

# torch, loaded by the transformer parser, warns about its own deprecations.
warnings.filterwarnings("ignore", category=FutureWarning, module="torch")

from . import config  # noqa: E402
from .findings import SEVERITIES, Finding  # noqa: E402
from .linter import RULES, Linter  # noqa: E402
from .nlp import ensure_wordnet  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    args = _arguments().parse_args(argv)
    cfg = config.load(args.config or config.find(Path.cwd()))
    paths = args.paths or cfg.files()
    if not paths:
        sys.exit("prose-lint: no files given and no include globs in the config")
    ensure_wordnet()
    cache = None if args.no_cache else cfg.root / ".cache" / "prose-lint"
    linter = Linter(cfg, cache, args.rule)
    findings = [f for path in paths for f in linter.lint(path.read_text(), _shown(path))]
    _report(findings, args.format)
    return _status(findings, args.fail_on)


def _status(findings: list[Finding], fail_on: str) -> int:
    return int(any(SEVERITIES.index(f.severity) >= SEVERITIES.index(fail_on) for f in findings))


def _arguments() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="prose-lint", description=__doc__)
    ap.add_argument("paths", nargs="*", type=Path, help="Markdown files; defaults to the config's include globs")
    ap.add_argument("--config", type=Path, help=f"path to {config.NAME}; found by searching upward by default")
    ap.add_argument("--rule", action="append", choices=RULES, help="run only this rule (repeatable)")
    ap.add_argument("--format", choices=("text", "json"), default="text")
    ap.add_argument("--fail-on", choices=SEVERITIES, default="warning", help="lowest severity that sets exit status 1")
    ap.add_argument("--no-cache", action="store_true")
    return ap


def _shown(path: Path) -> str:
    resolved = path.resolve()
    return str(resolved.relative_to(Path.cwd())) if resolved.is_relative_to(Path.cwd()) else str(path)


def _report(findings: list[Finding], fmt: str) -> None:
    if fmt == "json":
        print(json.dumps([f.as_dict() for f in findings], indent=2))
        return
    print("".join(f"{f.path}:{f.line}: {f.severity} [{f.rule}] {f.message}\n    {f.excerpt}\n" for f in findings), end="")
    counts = ", ".join(f"{sum(f.rule == r for f in findings)} {r}" for r in RULES)
    print(f"{len(findings)} findings ({counts})", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
