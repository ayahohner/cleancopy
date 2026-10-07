"""Classify the noun phrase that fills a verb's subject.

Classes, from most to least capable:

- ``agent``: can judge, intend, prefer, or tolerate: people, organizations,
  and AI agents or models.
- ``physical``: a concrete object, such as a phone or a server.
- ``abstract``: an abstraction, such as a function, a record, a theorem, or a
  code identifier.
- ``mixed``: a term that covers both agents and non-agents, such as
  "resolver", which can be a person or a function; never flagged.
- ``unknown``: not classified; never flagged.

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
PRONOUN = "pronoun"

PRONOUNS = {"it", "its", "they", "them", "their", "this", "that", "these", "those", "which", "who", "what"}
PERSONAL = {"i", "we", "you", "he", "she", "one", "someone", "anyone", "everyone", "nobody", "somebody"}

_ANIMATE_ROOTS = {"person.n.01", "organism.n.01", "social_group.n.01", "people.n.01"}
_PHYSICAL_ROOT = "physical_entity.n.01"


@dataclass(frozen=True)
class Subject:
    text: str  # the phrase as written
    key: str  # the lexicon key that matched, or the head lemma
    cls: str
    source: str  # "lexicon", "entity", "wordnet", "placeholder", "grammar"


@lru_cache(maxsize=None)
def wordnet_class(lemma: str) -> str:
    synsets = wn.synsets(lemma.replace(" ", "_"), pos=wn.NOUN)
    if not synsets:
        return UNKNOWN
    for s in synsets:
        if _roots(s) & _ANIMATE_ROOTS:
            return MIXED if len(synsets) > 1 and s is not synsets[0] else AGENT
    return PHYSICAL if _PHYSICAL_ROOT in _roots(synsets[0]) else ABSTRACT


def _roots(synset) -> set[str]:
    return {h.name() for path in synset.hypernym_paths() for h in path}


class Lexicon:
    def __init__(self, entries: dict[str, list[str]]):
        self.table: dict[str, str] = {}
        for cls, words in entries.items():
            for w in words:
                self.table[w.lower()] = cls

    def classify(self, head: Token, segment_placeholders: dict[str, tuple[str, str]]) -> Subject:
        text = " ".join(t.text for t in _phrase(head))
        lower = head.lower_
        if PLACEHOLDER.fullmatch(head.text):
            kind, original = segment_placeholders.get(head.text, ("code", head.text))
            return Subject(original, original, ABSTRACT, "placeholder")
        if lower in PERSONAL:
            return Subject(text, lower, AGENT, "grammar")
        if lower in PRONOUNS or head.pos_ == "PRON":
            return Subject(text, lower, PRONOUN, "grammar")
        # Longest lexicon match among the head's compound modifiers.
        for key in _keys(head):
            if key in self.table:
                return Subject(text, key, self.table[key], "lexicon")
        if head.ent_type_ in ("PERSON", "ORG", "NORP"):
            return Subject(text, lower, AGENT, "entity")
        if head.ent_type_ in ("PRODUCT", "LAW", "WORK_OF_ART", "LANGUAGE"):
            return Subject(text, lower, ABSTRACT, "entity")
        if head.tag_ == "VBG" or head.dep_ == "csubj":
            return Subject(text, head.lemma_.lower(), ABSTRACT, "grammar")
        if head.pos_ == "PROPN":
            return Subject(text, lower, UNKNOWN, "grammar")
        lemma = head.lemma_.lower()
        return Subject(text, lemma, wordnet_class(lemma), "wordnet")


def _phrase(head: Token) -> list[Token]:
    left = [t for t in head.lefts if t.dep_ in ("compound", "amod", "poss", "nmod")]
    return left + [head]


def _keys(head: Token) -> list[str]:
    compounds = [t for t in head.lefts if t.dep_ in ("compound", "amod")]
    keys = []
    for i in range(len(compounds)):
        words = [t.lower_ for t in compounds[i:]] + [head.lower_]
        lemmas = [t.lower_ for t in compounds[i:]] + [head.lemma_.lower()]
        keys += [" ".join(words), " ".join(lemmas)]
    keys += [head.lower_, head.lemma_.lower()]
    return keys
