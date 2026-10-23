"""ambiguous-pronouns: "it", "its", "they", "them", and "their" whose two most
likely antecedents are nearly tied.

The ranking is in ``coreference``: Lappin and Leass's salience weights, with
the filters and adjustments described there. A pronoun is flagged when the
runner-up scores at least ``ratio`` of the leader.
"""

from __future__ import annotations

from collections.abc import Iterator

from spacy.tokens import Doc

from ..coreference import WINDOW, candidates
from ..findings import Hit
from ..markdown import Segment

NAME = "ambiguous-pronouns"
CONTEXT = WINDOW  # candidates come from this many preceding sentences


def check(doc: Doc, seg: Segment, ratio: float) -> Iterator[Hit]:
    for tok in doc:
        ranked = candidates(tok)
        tied = [seg.restore(c.text) for c in ranked if c.score >= ratio * ranked[0].score]
        if len(tied) >= 2:
            message = f'"{tok.text}" could refer to {" or ".join(map(repr, tied))}; name the noun'
            yield Hit(tok, message, {"pronoun": tok.text, "candidates": [(seg.restore(c.text), c.score) for c in ranked[:4]]})
