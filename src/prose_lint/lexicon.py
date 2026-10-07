"""Classify the noun phrase that fills a verb's subject.

Classes, from most to least capable:

- ``agent``: can judge, intend, prefer, or tolerate: people, organizations,
  and AI agents or models.
- ``physical``: a concrete object, such as a phone or a server.
- ``abstract``: an abstraction, such as a function, a record, a theorem, or a
  code identifier.
- ``mixed``: a term that covers both agents and non-agents, such as
  "resolver", which can be a person or a function; never flagged.
- ``unknown``: pronouns, unrecognized names, and words not in WordNet; never
  flagged.

The project lexicon is consulted first, then named-entity labels, then
WordNet. WordNet is used conservatively for animacy: a word with a person
sense, such as "server" or "host", is never flagged unless the lexicon says
otherwise. Between physical and abstract, the first (most frequent) sense
decides, so "goal" is abstract although one sense is a goalpost.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from nltk.corpus import wordnet as wn
from spacy.tokens import Token

from .markdown import PLACEHOLDER

AGENT = "agent"
PHYSICAL = "physical"
ABSTRACT = "abstract"
MIXED = "mixed"
UNKNOWN = "unknown"

PRONOUNS = {"it", "its", "they", "them", "their", "this", "that", "these", "those", "which", "who", "what"}
PERSONAL = {"i", "we", "you", "he", "she", "one", "someone", "anyone", "everyone", "nobody", "somebody"}

_ANIMATE_ROOTS = {"person.n.01", "organism.n.01", "social_group.n.01", "people.n.01"}
_PHYSICAL_ROOT = "physical_entity.n.01"
_ENTITIES = dict.fromkeys(("PERSON", "ORG", "NORP"), AGENT) | dict.fromkeys(("PRODUCT", "LAW", "WORK_OF_ART", "LANGUAGE"), ABSTRACT)


@dataclass(frozen=True)
class Subject:
    text: str  # the phrase as written
    key: str  # the lexicon key that matched, or the head lemma
    cls: str
    source: str  # "lexicon", "entity", "wordnet", "placeholder", or "grammar"


@lru_cache(maxsize=None)
def wordnet_class(lemma: str) -> str:
    synsets = wn.synsets(lemma.replace(" ", "_"), pos=wn.NOUN)
    if not synsets:
        return UNKNOWN
    animate = [s for s in synsets if _roots(s) & _ANIMATE_ROOTS]
    if animate:
        return AGENT if animate[0] is synsets[0] else MIXED
    return PHYSICAL if _PHYSICAL_ROOT in _roots(synsets[0]) else ABSTRACT


def _roots(synset) -> set[str]:
    return {h.name() for path in synset.hypernym_paths() for h in path}


class Lexicon:
    def __init__(self, entries: dict[str, list[str]]):
        self.table = {w.lower(): cls for cls, words in entries.items() for w in words}

    def classify(self, head: Token, placeholders: dict[str, str]) -> Subject:
        if PLACEHOLDER.fullmatch(head.text):
            original = placeholders.get(head.text, head.text)
            return Subject(original, original, ABSTRACT, "placeholder")
        found = _pronoun(head) or self._lookup(head) or _entity(head) or _form(head)
        lemma = head.lemma_.lower()
        key, cls, source = found or (lemma, wordnet_class(lemma), "wordnet")
        return Subject(" ".join(t.text for t in _phrase(head)), key, cls, source)

    def _lookup(self, head: Token) -> tuple[str, str, str] | None:
        key = next((k for k in _keys(head) if k in self.table), None)
        return (key, self.table[key], "lexicon") if key else None


def _pronoun(head: Token) -> tuple[str, str, str] | None:
    if head.lower_ in PERSONAL:
        return head.lower_, AGENT, "grammar"
    if head.lower_ in PRONOUNS or head.pos_ == "PRON":
        return head.lower_, UNKNOWN, "grammar"
    return None


def _entity(head: Token) -> tuple[str, str, str] | None:
    cls = _ENTITIES.get(head.ent_type_)
    return (head.lower_, cls, "entity") if cls else None


def _form(head: Token) -> tuple[str, str, str] | None:
    """A gerund or clause subject names an activity; a proper noun is unclassified."""
    if head.tag_ == "VBG" or head.dep_ == "csubj":
        return head.lemma_.lower(), ABSTRACT, "grammar"
    if head.pos_ == "PROPN":
        return head.lower_, UNKNOWN, "grammar"
    return None


def _phrase(head: Token) -> list[Token]:
    return [t for t in head.lefts if t.dep_ in ("compound", "amod", "poss", "nmod")] + [head]


def _keys(head: Token) -> list[str]:
    """Lexicon keys to try, longest first: "AI agent", then "agent"."""
    mods = [t.lower_ for t in head.lefts if t.dep_ in ("compound", "amod")]
    heads = dict.fromkeys((head.lower_, head.lemma_.lower()))
    return [" ".join([*mods[i:], h]) for i in range(len(mods) + 1) for h in heads]
