"""serial-comma: a list of three or more items needs a comma before its last
"and" or "or", as in "records, functions, and choices".

The parse groups a list's items as conjuncts, so the rule sees only real
lists: "Meanwhile, universities slowed down and grew" has two conjuncts, and
"Families, biological or chosen" has an apposition, not a list. A list counts
only when it is flat, with every item after the first beginning right after a
comma, so a pair nested in a larger list ("they are wrong, and some decline
and die") is not flagged. A comma inside closing quotation marks counts, as in
"“send,” “delete,” or “spend”".

Titles and sentences that the parser misreads are silenced with allow entries:
phrases that skip any sentence containing them.
"""

from __future__ import annotations

from collections.abc import Iterator

from spacy.tokens import Doc, Token

from ..findings import Hit
from ..markdown import Segment

NAME = "serial-comma"

CONTEXT = 0  # preceding sentences a reader needs to judge a finding

_COORDINATORS = {"and", "or"}
_QUOTES = {'"', "'", "“", "”", "‘", "’"}


def check(doc: Doc, seg: Segment, allow: list[str]) -> Iterator[Hit]:
    for head in doc:
        items = _items(head)
        cc = _bare_coordinator(items) if len(items) >= 3 else None
        if cc is not None and not any(a in seg.restore(cc.sent.text) for a in allow):
            yield Hit(cc, f'add a comma before "{cc.text}", which ends a list of {len(items)} items', {"items": len(items)})


def _items(head: Token) -> list[Token]:
    """The conjuncts of the coordination that ``head`` begins, in order."""
    if head.dep_ == "conj":
        return []
    found, todo = [], [head]
    while todo:
        tok = todo.pop()
        found.append(tok)
        todo += [c for c in tok.children if c.dep_ == "conj"]
    return sorted(found, key=lambda t: t.i)


def _bare_coordinator(items: list[Token]) -> Token | None:
    """The coordinator before a flat list's last item when no comma precedes it."""
    starts = [_start(t) for t in items[1:]]
    if any(_previous(s).text != "," for s in starts[:-1]):
        return None
    cc = _previous(starts[-1])
    return cc if cc.lower_ in _COORDINATORS and _previous(cc).text != "," else None


def _start(item: Token) -> Token:
    """The first word of an item, past any quotation mark or coordinator."""
    return next((t for t in item.subtree if not (t.is_punct or t.dep_ == "cc")), item)


def _previous(tok: Token) -> Token:
    """The token before ``tok``, past closing quotation marks."""
    i = tok.i - 1
    while i > 0 and tok.doc[i].text in _QUOTES:
        i -= 1
    return tok.doc[max(i, 0)]
