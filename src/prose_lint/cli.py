"""prose-lint: check Markdown prose for verbs that do not fit their subjects
and for pronouns with more than one candidate antecedent."""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

# torch, loaded by the transformer parser, warns about its own deprecations.
warnings.filterwarnings("ignore", category=FutureWarning, module="torch")

from . import config as config_mod
from .findings import SEVERITIES, Finding
from .lexicon import Lexicon
from .markdown import segments
from .nlp import ensure_nltk_data, parse
from .rules import ambiguous_pronouns, literal_verbs
from .verbs import VerbTable

RULES = (literal_verbs.NAME, ambiguous_pronouns.NAME)


def lint_text(source: str, path: str, cfg: config_mod.Config, cache_dir: Path | None, only: set[str] | None = None, verbnet: bool = False) -> list[Finding]:
    segs = segments(source)
    docs = parse([s.text for s in segs], cache_dir)
    lexicon = Lexicon(cfg.lexicon)
    verbs = VerbTable.load(cfg.verbs, verbnet=verbnet or cfg.rule(literal_verbs.NAME).get("verbnet", False))
    enabled = {r for r in RULES if cfg.severity(r) != "off" and (only is None or r in only)}
    out: list[Finding] = []
    for seg, doc in zip(segs, docs):
        on = enabled - seg.disabled if "*" not in seg.disabled else set()
        if literal_verbs.NAME in on:
            out += literal_verbs.check(doc, seg, path, lexicon, verbs, cfg.allow(literal_verbs.NAME), cfg.severity(literal_verbs.NAME))
        if ambiguous_pronouns.NAME in on:
            rule = cfg.rule(ambiguous_pronouns.NAME)
            out += ambiguous_pronouns.check(doc, seg, path, cfg.severity(ambiguous_pronouns.NAME), rule.get("ratio", 0.85))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="prose-lint", description=__doc__)
    ap.add_argument("paths", nargs="*", type=Path, help="Markdown files; defaults to the config's include globs")
    ap.add_argument("--config", type=Path, help=f"path to {config_mod.NAME}; found by searching upward by default")
    ap.add_argument("--rule", action="append", choices=RULES, help="run only this rule (repeatable)")
    ap.add_argument("--format", choices=("text", "json"), default="text")
    ap.add_argument("--fail-on", choices=SEVERITIES, default="warning", help="lowest severity that sets exit status 1")
    ap.add_argument("--verbnet", action="store_true", help="also report, at info, verbs that VerbNet restricts to animate subjects")
    ap.add_argument("--no-cache", action="store_true")
    args = ap.parse_args(argv)

    cfg = config_mod.load(args.config or config_mod.find(Path.cwd()))
    paths = args.paths or sorted({p for g in cfg.include for p in cfg.root.glob(g)})
    if not paths:
        ap.error("no files given and no include globs in the config")
    cache_dir = None if args.no_cache else cfg.root / ".cache" / "prose-lint"
    ensure_nltk_data()

    findings: list[Finding] = []
    for p in paths:
        try:
            shown = str(p.resolve().relative_to(Path.cwd()))
        except ValueError:
            shown = str(p)
        findings += lint_text(p.read_text(), shown, cfg, cache_dir, set(args.rule) if args.rule else None, args.verbnet)

    if args.format == "json":
        json.dump([f.as_dict() for f in findings], sys.stdout, indent=2)
        print()
    else:
        for f in findings:
            print(f"{f.path}:{f.line}: {f.severity} [{f.rule}] {f.message}")
            print(f"    {f.excerpt}")
        counts = {r: sum(1 for f in findings if f.rule == r) for r in RULES}
        print(f"{len(findings)} findings ({', '.join(f'{n} {r}' for r, n in counts.items())})", file=sys.stderr)

    threshold = SEVERITIES.index(args.fail_on)
    return 1 if any(SEVERITIES.index(f.severity) >= threshold for f in findings if f.severity in SEVERITIES) else 0


if __name__ == "__main__":
    sys.exit(main())
