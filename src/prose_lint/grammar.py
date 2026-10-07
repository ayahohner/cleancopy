"""Find the noun that fills a verb's subject role, through the constructions
that hide it: relative clauses, coordinated verbs, control verbs, passives,
and participles."""

from __future__ import annotations

from spacy.tokens import Token

RELATIVE = {"that", "which", "who", "whom", "whose"}
_PASSIVE = {"nsubjpass", "csubjpass", "auxpass", "expl"}


def subject_of(verb: Token, depth: int = 0) -> Token | None:
    """The token heading the phrase that performs ``verb``, or None.

    For a passive verb the performer is the object of "by"; a passive verb
    without "by" has no performer in the sentence.
    """
    deps = {k.dep_: k for k in reversed(list(verb.children))}  # first child per relation
    if "agent" in deps:
        return _object(deps["agent"])
    if deps.keys() & _PASSIVE or depth > 6:
        return None
    subj = deps.get("nsubj", deps.get("csubj"))
    if subj is None:
        return _inherited(verb, depth)
    return verb.head if _relative(subj, verb) else subj


def _object(preposition: Token) -> Token | None:
    return next((g for g in preposition.children if g.dep_ == "pobj"), None)


def _relative(subj: Token, verb: Token) -> bool:
    """ "that" in "a function that decides" stands for "function". """
    return subj.lower_ in RELATIVE and verb.dep_ == "relcl"


def _inherited(verb: Token, depth: int) -> Token | None:
    """The subject of a verb that has none of its own: "a function deciding",
    "decides and records", "tries to decide", "..., making X"."""
    gerund = verb.tag_ == "VBG"
    if verb.dep_ == "relcl" or (verb.dep_ == "acl" and gerund):
        return verb.head
    if verb.dep_ in ("conj", "xcomp") or (verb.dep_ == "advcl" and gerund):
        return subject_of(verb.head, depth + 1)
    return None
