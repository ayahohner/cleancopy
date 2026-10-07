from __future__ import annotations

from functools import partial
from pathlib import Path

from spacy.tokens import Span

from .config import Config
from .findings import Finding, Hit
from .lexicon import Lexicon
from .markdown import Segment, segments
from .nlp import parse
from .rules import ambiguous_pronouns, literal_verbs
from .verbs import VerbTable

RULES = (literal_verbs.NAME, ambiguous_pronouns.NAME)


class Linter:
    def __init__(self, cfg: Config, cache_dir: Path | None = None, only: list[str] | None = None):
        self.cfg = cfg
        self.cache_dir = cache_dir
        self.context = {literal_verbs.NAME: literal_verbs.CONTEXT, ambiguous_pronouns.NAME: ambiguous_pronouns.CONTEXT}
        checks = {
            literal_verbs.NAME: lambda: partial(literal_verbs.check, lexicon=Lexicon(cfg.lexicon), verbs=VerbTable.load(cfg.verbs), allow=cfg.allow(literal_verbs.NAME)),
            ambiguous_pronouns.NAME: lambda: partial(ambiguous_pronouns.check, ratio=cfg.rule(ambiguous_pronouns.NAME).get("ratio", 0.95)),
        }
        enabled = [r for r in RULES if cfg.severity(r) != "off" and (only is None or r in only)]
        self.checks = {r: checks[r]() for r in enabled}

    def lint(self, source: str, path: str) -> list[Finding]:
        segs = segments(source)
        docs = parse([s.text for s in segs], self.cache_dir)
        return [
            self._finding(path, seg, rule, hit)
            for seg, doc in zip(segs, docs)
            for rule, check in self.checks.items()
            if seg.enables(rule)
            for hit in check(doc, seg)
        ]

    def _finding(self, path: str, seg: Segment, rule: str, hit: Hit) -> Finding:
        tok = hit.token
        sent = tok.sent
        occurrence = sum(t.lower_ == tok.lower_ for t in sent if t.i <= tok.i)
        context = _preceding(sent, self.context[rule])
        severity = hit.severity or self.cfg.severity(rule)
        return Finding(path, seg.line, rule, severity, hit.message, seg.restore(sent.text), seg.restore(context), tok.text, occurrence, hit.data)


def _preceding(sent: Span, n: int) -> str:
    """The text of the ``n`` sentences before ``sent`` in its paragraph."""
    sents = list(sent.doc.sents)
    i = next(j for j, s in enumerate(sents) if s.start == sent.start)
    return " ".join(s.text for s in sents[max(0, i - n) : i])
