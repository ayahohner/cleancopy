"""What each verb's literal sense requires of its subject.

The table in ``data/verbs.toml``, extended by the project config, lists verbs
and phrases. Phrases such as "draw the line" and "pay for" are figures whose
single verb has a literal sense with any subject, so a phrase matches on its
particle, preposition, object, or complement. A phrase with ``needs = "any"``
exempts an idiom, such as "stand for", from its verb's entry.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from importlib import resources

from spacy.tokens import Token

ANIMATE = "animate"  # a person, an organization, or an AI agent
CONCRETE = "concrete"  # a physical object or an agent
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
            if p["verb"] == lemma and _phrase_matches(verb, p):
                return p, " ".join(p[k] for k in ("verb", *_SLOTS) if k in p)
        return self.verbs.get(lemma), lemma


def _phrase_matches(verb: Token, phrase: dict) -> bool:
    kids = list(verb.children)
    filled = all(_filled(kids, _SLOTS[slot], phrase[slot]) for slot in _SLOTS if slot in phrase)
    return filled and (not phrase.get("complement") or _filled(kids, _COMPLEMENTS, None))


def _filled(kids: list[Token], deps: tuple[str, ...], word: str | None) -> bool:
    """Whether a child fills the slot; ``word`` None accepts any child."""
    return any(k.dep_ in deps and word in (None, k.lemma_.lower()) for k in kids)
