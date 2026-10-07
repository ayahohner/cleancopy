"""literal-verbs: a verb's subject must be the kind of thing the verb's
literal sense takes.

Flags "the theorem draws the line", "a function tolerates delays", and "a
choice pays for two-phase commit", and allows "an AI agent tolerates delays".
Senses that a field has made into technical terms are silenced with allow
entries of the form "subject verb", where the subject may be a lexicon key,
"@class", or "*".
"""

from __future__ import annotations

from collections.abc import Iterator

from spacy.tokens import Doc, Token

from ..findings import Hit
from ..grammar import subject_of
from ..lexicon import ABSTRACT, PHYSICAL, Lexicon, Subject
from ..markdown import Segment
from ..verbs import ANIMATE, CONCRETE, Requirement, VerbTable

NAME = "literal-verbs"

_TAKES = {ANIMATE: "a person, an organization, or an AI agent", CONCRETE: "a physical object or an agent"}
_IS = {ABSTRACT: "an abstraction", PHYSICAL: "a physical object"}
_FAILS = {ANIMATE: {ABSTRACT, PHYSICAL}, CONCRETE: {ABSTRACT}}


def check(doc: Doc, seg: Segment, lexicon: Lexicon, verbs: VerbTable, allow: list[tuple[str, str]]) -> Iterator[Hit]:
    for tok in doc:
        req = _requirement(tok, verbs)
        head = subject_of(tok) if req else None
        if head is None:
            continue
        subj = lexicon.classify(head, seg.placeholders)
        if subj.cls in _FAILS[req.needs] and not _allowed(allow, subj, req.phrase):
            yield Hit(tok.sent, _message(req, subj), {"phrase": req.phrase, "subject": subj.text, "class": subj.cls, "class_source": subj.source})


def _requirement(tok: Token, verbs: VerbTable) -> Requirement | None:
    if tok.pos_ != "VERB":
        return None
    # A bare past participle is adjectival: "made known".
    if tok.tag_ == "VBN" and not any(k.dep_ in ("aux", "auxpass", "agent") for k in tok.children):
        return None
    return verbs.match(tok)


def _allowed(allow: list[tuple[str, str]], subj: Subject, phrase: str) -> bool:
    verbs = {phrase, phrase.split()[0], "*"}
    subjects = {"*", subj.key, f"@{subj.cls}", subj.key.rsplit(" ", 1)[-1]}
    return any(v in verbs and s in subjects for s, v in allow)


def _message(req: Requirement, subj: Subject) -> str:
    message = f'"{req.phrase}" takes {_TAKES[req.needs]} as its subject, but "{subj.text}" is {_IS[subj.cls]}'
    return message + (f"; literal options: {', '.join(req.suggest)}" if req.suggest else "")
