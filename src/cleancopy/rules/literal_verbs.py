"""literal-verbs: a verb's subject must be the kind of thing the verb's
literal sense takes.

Flags "the theorem draws the line", "a function tolerates delays", and "a
choice pays for two-phase commit", and allows "an AI agent tolerates delays".
Senses that a field has made into technical terms are silenced with allow
entries of the form "subject verb", where the subject may be a lexicon key,
"@class", or "*".

A pronoun subject ("it", "they") takes the class of its antecedent when one
candidate clearly leads the salience ranking in ``coreference``; a tied
pronoun is left to the ambiguous-pronouns rule. A coordination fails only
when every conjunct fails.
"""

from __future__ import annotations

from collections.abc import Iterator

from spacy.tokens import Doc, Token

from ..coreference import NUMBER, WINDOW, antecedent
from ..findings import Hit
from ..grammar import subject_of
from ..lexicon import Lexicon, Subject
from ..markdown import Segment
from ..verbs import NOUNS, Requirement, VerbTable

NAME = "literal-verbs"

CONTEXT = 0  # preceding sentences a reader needs to judge a finding

def check(doc: Doc, seg: Segment, lexicon: Lexicon, verbs: VerbTable, allow: list[tuple[str, str]], ratio: float) -> Iterator[Hit]:
    for tok in doc:
        req = _requirement(tok, verbs)
        head = subject_of(tok) if req else None
        if head is None:
            continue
        subjects, pronoun = _subjects(head, seg, lexicon, ratio)
        if all(req.fails(s.cls) and not _allowed(allow, s, req.phrase) for s in subjects):
            subj = subjects[0]
            data = {"phrase": req.phrase, "subject": subj.text, "class": subj.cls, "class_source": subj.source, "pronoun": pronoun}
            yield Hit(tok, _message(req, subj, pronoun), data, req.severity, WINDOW if pronoun else None)


def _subjects(head: Token, seg: Segment, lexicon: Lexicon, ratio: float) -> tuple[list[Subject], str | None]:
    """The classified subject, or the nouns a pronoun subject clearly refers to."""
    found = antecedent(head, ratio, lexicon) if head.lower_ in NUMBER else None
    if found is None:
        return [lexicon.classify(head, seg.placeholders)], None
    return [lexicon.classify(m, seg.placeholders) for m in found.members], head.text


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


def _message(req: Requirement, subj: Subject, pronoun: str | None) -> str:
    named = f'"{pronoun}", meaning "{subj.text}",' if pronoun else f'"{subj.text}"'
    message = f'"{req.phrase}" takes {req.described()} as its subject, but {named} is {NOUNS[subj.cls]}'
    return message + (f"; literal options: {', '.join(req.suggest)}" if req.suggest else "")
