"""Find the noun that fills a verb's subject role, through the constructions
that hide it: relative clauses, coordinated verbs, control verbs, passives,
and participles."""

from __future__ import annotations

from spacy.tokens import Token

RELATIVE = {"that", "which", "who", "whom", "whose"}


def subject_of(verb: Token, depth: int = 0) -> Token | None:
    """The token heading the phrase that performs ``verb``, or None.

    For a passive verb the performer is the object of "by"; a passive verb
    without "by" has no performer in the sentence, so None is returned.
    """
    if depth > 6:
        return None
    kids = list(verb.children)
    for k in kids:
        if k.dep_ == "agent":  # passive "by X"
            objs = [g for g in k.children if g.dep_ == "pobj"]
            return objs[0] if objs else None
    if any(k.dep_ in ("nsubjpass", "csubjpass", "auxpass") for k in kids):
        return None
    for k in kids:
        if k.dep_ in ("nsubj", "csubj", "expl"):
            if k.dep_ == "expl":
                return None
            if k.lower_ in RELATIVE and verb.dep_ == "relcl":
                return verb.head
            return k
    if verb.dep_ == "relcl":
        return verb.head
    if verb.dep_ == "acl" and verb.tag_ == "VBG":  # "a function deciding ..."
        return verb.head
    if verb.dep_ in ("conj", "xcomp") and verb.head.i != verb.i:
        return subject_of(verb.head, depth + 1)
    if verb.dep_ == "advcl" and verb.tag_ == "VBG":  # "..., making X" shares the main subject
        return subject_of(verb.head, depth + 1)
    return None


def is_negated(verb: Token) -> bool:
    return any(k.dep_ == "neg" for k in verb.children)
