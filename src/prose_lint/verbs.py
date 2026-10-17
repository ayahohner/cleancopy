"""What each verb's literal sense requires of its subject.

The table in ``data/verbs.toml``, extended by the project config, lists verbs
and phrases. Phrases such as "draw the line" and "pay for" are figures whose
single verb has a literal sense with any subject, so a phrase matches on its
particle, preposition, object, or complement; a slot may list several words,
as "set" does with the objects of authority ("set the hours"). A phrase with ``needs = "any"``
exempts an idiom, such as "stand for", from its verb's entry.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from importlib import resources

from spacy.tokens import Token

ANIMATE = "animate"  # a person, an organization, or an AI agent
CONCRETE = "concrete"  # a physical object, a mechanism, or an agent
SPEAKER = "speaker"  # an agent, or a text that carries words
ANY = "any"  # an exemption

_SLOTS = {"particle": ("prt",), "prep": ("prep", "prt"), "object": ("dobj", "obj", "attr")}
_COMPLEMENTS = ("oprd", "xcomp", "ccomp")


@dataclass(frozen=True)
class Requirement:
    needs: str  # ANIMATE or CONCRETE
    phrase: str  # the verb or phrase as it matched
    suggest: tuple[str, ...] = ()
    severity: str | None = None  # overrides the rule's severity


@dataclass
class VerbTable:
    verbs: dict[str, dict]
    phrases: list[dict]

    @classmethod
    def load(cls, extra: dict | None = None) -> VerbTable:
        data = tomllib.loads(resources.files("prose_lint.data").joinpath("verbs.toml").read_text())
        extra = extra or {}
        return cls({**data.get("verb", {}), **extra.get("verb", {})}, data.get("phrase", []) + extra.get("phrase", []))

    def match(self, verb: Token) -> Requirement | None:
        entry, words = self._lookup(verb)
        if entry is None or entry.get("needs") == ANY:
            return None
        return Requirement(entry.get("needs", ANIMATE), words, tuple(entry.get("suggest", ())), entry.get("severity"))

    def _lookup(self, verb: Token) -> tuple[dict | None, str]:
        lemma = verb.lemma_.lower()
        for p in self.phrases:
            words = _phrase_words(verb, p) if p["verb"] == lemma else None
            if words:
                return p, words
        return self.verbs.get(lemma), lemma


def _phrase_words(verb: Token, phrase: dict) -> str | None:
    """The phrase as it matched, or None when a slot is empty."""
    kids = list(verb.children)
    words = [phrase["verb"], *_slot_words(kids, phrase)]
    if phrase.get("complement"):
        words.append(_filler(kids, _COMPLEMENTS, None) and "")
    return None if None in words else " ".join(w for w in words if w)


def _slot_words(kids: list[Token], phrase: dict) -> list[str | None]:
    return [_filler(kids, deps, phrase[slot]) for slot, deps in _SLOTS.items() if slot in phrase]


def _filler(kids: list[Token], deps: tuple[str, ...], allowed: str | list[str] | None) -> str | None:
    """The lemma of the child that fills the slot; ``allowed`` None accepts any child."""
    allowed = [allowed] if isinstance(allowed, str) else allowed
    lemmas = (k.lemma_.lower() for k in kids if k.dep_ in deps)
    return next((w for w in lemmas if allowed is None or w in allowed), None)
