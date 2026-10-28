"""Classify the noun phrase that fills a verb's subject.

Classes, from most to least capable:

- ``agent``: can judge, intend, prefer, or tolerate: people, organizations,
  and AI agents or models.
- ``physical``: a concrete object, such as a phone or a server.
- ``display``: something that presents an image to the eye, such as a
  screen, a window, a chart, a figure, or a map, which can move or show as a
  physical object can. The built-in lexicon in ``data/lexicon.toml`` assigns
  this class; ``interface`` is an older name for it.
- ``mechanism``: software that performs operations, such as a compiler or a
  runtime, which can set, assign, or deliver but not decide. Only the project
  lexicon assigns this class.
- ``text``: something that carries words, such as a message, a request, or a
  rule, which can ask or say but not decide.
- ``evidence``: something that supports a claim, such as a study, a result,
  an example, or an act or fact named by a gerund or a clause ("watching a
  community", "that it halts"), which can show or suggest that something is
  so. The built-in lexicon lists the nouns.
- ``idea``: cognitive content, such as a goal, a plan, a principle, or a
  model, which can assume or imply but not decide. WordNet's
  ``content.n.05`` assigns this class.
- ``institution``: a practice that exists because people keep acting as if it
  does, such as a market, money, or a custom (John Searle's "institutional
  facts"), which can require or permit but not want, buy, or reward. The
  built-in lexicon assigns this class; courts and governments are
  organizations, so agents.
- ``abstract``: an abstraction, such as a function, a record, a theorem, or a
  code identifier.
- ``mixed``: a term that covers both agents and non-agents, such as
  "resolver", which can be a person or a function; never flagged.
- ``unknown``: pronouns, unrecognized names, and words not in WordNet; never
  flagged.

The project lexicon, over the built-in one, is consulted first, then
named-entity labels, then WordNet. WordNet is used conservatively for animacy: a word with a person
sense, such as "server" or "host", is never flagged unless the lexicon says
otherwise. A proper-noun sense does not count, so "job" is not a person
because of the biblical Job. Among physical, text, and abstract, the first (most frequent) sense
decides, so "goal" is abstract although one sense is a goalpost.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources

from nltk.corpus import wordnet as wn
from spacy.tokens import Token

from .markdown import PLACEHOLDER

AGENT = "agent"
PHYSICAL = "physical"
DISPLAY = "display"
MECHANISM = "mechanism"
TEXT = "text"
EVIDENCE = "evidence"
IDEA = "idea"
INSTITUTION = "institution"
ABSTRACT = "abstract"
MIXED = "mixed"
UNKNOWN = "unknown"

PRONOUNS = {"it", "its", "they", "them", "their", "this", "that", "these", "those", "which", "who", "what", "none", "each", "either", "neither", "both", "all"}
# "Billions of people", "most of the records": the class is the "of" phrase's.
_QUANTITIES = {
    "billion", "million", "thousand", "hundred", "dozen", "number", "majority", "minority", "most", "many",
    "some", "few", "lot", "half", "percent", "share", "rest", "none", "each", "all", "both", "either", "neither",
}
PERSONAL = {"i", "we", "you", "he", "she", "one", "someone", "anyone", "everyone", "nobody", "somebody"}

_ANIMATE_ROOTS = {"person.n.01", "organism.n.01", "social_group.n.01", "people.n.01"}
_PHYSICAL_ROOT = "physical_entity.n.01"
_TEXT_ROOT = "communication.n.02"
_IDEA_ROOT = "content.n.05"
_ALIASES = {"interface": DISPLAY}
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
    synsets = _common_senses(synsets, lemma)
    animate = [s for s in synsets if _roots(s) & _ANIMATE_ROOTS]
    if animate:
        return AGENT if animate[0] is synsets[0] else MIXED
    return _inanimate_class(_roots(synsets[0]))


@lru_cache(maxsize=None)
def person(lemma: str) -> bool:
    """Whether the noun's most frequent common sense names a person, not a group."""
    synsets = _common_senses(wn.synsets(lemma.replace(" ", "_"), pos=wn.NOUN), lemma)
    return bool(synsets) and "person.n.01" in _roots(synsets[0])


@lru_cache(maxsize=None)
def only_person(lemma: str) -> bool:
    """Whether every common sense of the noun names a person, as for "colleague"
    but not "compiler", which is also a program."""
    synsets = _common_senses(wn.synsets(lemma.replace(" ", "_"), pos=wn.NOUN), lemma)
    return bool(synsets) and all("person.n.01" in _roots(s) for s in synsets)


def _common_senses(synsets: list, lemma: str) -> list:
    """The senses that do not name one individual, or all of them if none remain."""
    return [s for s in synsets if not _proper(s, lemma)] or synsets


def _proper(synset, lemma: str) -> bool:
    """Whether the sense names one individual, such as Job in "job"."""
    names = [n for n in synset.lemma_names() if n.lower() == lemma.replace(" ", "_")]
    return bool(names) and all(n[0].isupper() for n in names)


def _inanimate_class(roots: set[str]) -> str:
    if _PHYSICAL_ROOT in roots:
        return PHYSICAL
    if _TEXT_ROOT in roots:
        return TEXT
    return IDEA if _IDEA_ROOT in roots else ABSTRACT


def _roots(synset) -> set[str]:
    return {h.name() for path in synset.hypernym_paths() for h in path}


class Lexicon:
    def __init__(self, entries: dict[str, list[str]]):
        builtin = tomllib.loads(resources.files("proseclean.data").joinpath("lexicon.toml").read_text())
        self.table = {w.lower(): _ALIASES.get(cls, cls) for table in (builtin, entries) for cls, words in table.items() for w in words}

    def classify(self, head: Token, placeholders: dict[str, str]) -> Subject:
        head = _counted(head) or head
        if PLACEHOLDER.fullmatch(head.text):
            original = placeholders.get(head.text, head.text)
            return Subject(original, original, ABSTRACT, "placeholder")
        key, cls, source = self._find(head)
        return Subject(" ".join(t.text for t in _phrase(head)), key, cls, source)

    def _find(self, head: Token) -> tuple[str, str, str]:
        found = _pronoun(head) or self._lookup(head) or _entity(head) or _form(head)
        lemma = head.lemma_.lower()
        return found or (lemma, wordnet_class(lemma), "wordnet")

    def entry(self, head: Token) -> str | None:
        """The class the lexicon gives the noun, or None when it has no entry."""
        found = self._lookup(head)
        return found[1] if found else None

    def _lookup(self, head: Token) -> tuple[str, str, str] | None:
        key = next((k for k in _keys(head) if k in self.table), None)
        return (key, self.table[key], "lexicon") if key else None


def _counted(head: Token) -> Token | None:
    """ "people" in "billions of people" """
    if head.lemma_.lower() not in _QUANTITIES and head.pos_ != "NUM":
        return None
    return next((k for o in _of(head) for k in o.children if k.dep_ == "pobj"), None)


def _of(head: Token) -> list[Token]:
    return [k for k in head.children if k.dep_ == "prep" and k.lower_ == "of"]


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
    """A gerund or clause subject names an act or a fact, which is evidence; a
    proper noun is unclassified."""
    if head.tag_ == "VBG" or head.dep_ == "csubj":
        return head.lemma_.lower(), EVIDENCE, "grammar"
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
