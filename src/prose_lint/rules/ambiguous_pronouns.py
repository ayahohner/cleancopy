"""ambiguous-pronouns: "it", "its", "they", "them", and "their" whose two most
likely antecedents are nearly tied.

The ranking is in ``coreference``: Lappin and Leass's salience weights, with
the filters and adjustments described there. A pronoun that is a verb's
subject keeps only the candidates the verb's literal sense takes, when any
does: in "the team read the rule, and it decided", only the team can decide.
A pronoun is flagged when the runner-up scores at least ``ratio`` of the
leader.
"""

from __future__ import annotations

from collections.abc import Iterator

from spacy.tokens import Doc, Token

from ..coreference import WINDOW, Candidate, candidates
from ..findings import Hit
from ..lexicon import Lexicon
from ..markdown import Segment
from ..verbs import VerbTable

NAME = "ambiguous-pronouns"
CONTEXT = WINDOW  # candidates come from this many preceding sentences


def check(doc: Doc, seg: Segment, ratio: float, lexicon: Lexicon, verbs: VerbTable) -> Iterator[Hit]:
    for tok in doc:
        ranked = _fitting(tok, candidates(tok, lexicon=lexicon), seg, lexicon, verbs)
        tied = [seg.restore(c.text) for c in ranked if c.score >= ratio * ranked[0].score]
        if len(tied) >= 2:
            message = f'"{tok.text}" could refer to {" or ".join(map(repr, tied))}; name the noun'
            yield Hit(tok, message, {"pronoun": tok.text, "candidates": [(seg.restore(c.text), c.score) for c in ranked[:4]]})


def _fitting(tok: Token, ranked: list[Candidate], seg: Segment, lexicon: Lexicon, verbs: VerbTable) -> list[Candidate]:
    req = verbs.match(tok.head) if ranked and tok.dep_ == "nsubj" else None
    if req is None:
        return ranked
    fit = [c for c in ranked if not any(req.fails(lexicon.classify(m, seg.placeholders).cls) for m in c.members)]
    return fit or ranked
