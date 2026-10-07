"""ambiguous-pronouns: "it", "its", "they", "them", and "their" whose two most
likely antecedents are nearly tied.

Candidates are ranked by the salience weights of Lappin and Leass, "An
Algorithm for Pronominal Anaphora Resolution" (Computational Linguistics,
1994): a noun phrase scores for being recent, a subject, an object, and a
phrase's head rather than a modifier inside another phrase, and the score
halves with each sentence boundary. Readers resolve a pronoun to the most
salient candidate, so a pronoun is clear when one candidate stands well above
the rest and ambiguous when the runner-up scores at least ``ratio`` of the
leader.

Filters before ranking: number agreement; the expletive "it" ("it is possible
to"); nouns whose phrase contains the pronoun without an intervening clause
("its" in "its value" cannot be the value); appositions and parentheticals,
which repeat a noun already counted; and, for a pronoun that is an object of a
verb or of a preposition attached to the verb, the verb's subject, which
English expresses with "itself" instead.

Four adjustments to Lappin and Leass, each a structure that readers resolve
without weighing salience:

- A coordination ("bookings, registrations, and transfers") is one candidate
  for a plural pronoun.
- "X and its Y" resolves to X, and "add X but not remove it" to X.
- A possessive resolves to the subject of its own clause when the subject
  agrees: "a warehouse can promise its own stock".
- A subject inside a subordinate clause scores as an oblique, so the main
  clause's subject leads, as centering theory predicts.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from spacy.tokens import Doc, Span, Token

from ..findings import Hit
from ..grammar import subject_of
from ..markdown import PLACEHOLDER, Segment

NAME = "ambiguous-pronouns"
CONTEXT = 1  # candidates come from this many preceding sentences

NUMBER = {"it": "sg", "its": "sg", "they": "pl", "them": "pl", "their": "pl"}
_TAG_NUMBER = {"NN": "sg", "NNP": "sg", "NNS": "pl", "NNPS": "pl"}
_EXPLETIVE_HEADS = {"be", "seem", "appear", "take", "make", "follow", "turn", "matter", "help"}
_EXTRAPOSED = {"to", "that", "whether", "if"}

# Lappin and Leass (1994), table of salience factors.
RECENCY = 100
SUBJECT = 80
EXISTENTIAL = 70
OBJECT = 50
OBLIQUE = 40
HEAD = 80
NON_ADVERBIAL = 50
PARALLEL = 35

_SUBJ = {"nsubj", "nsubjpass", "csubj"}
_OBJ = {"dobj", "obj"}
_OBLIQUES = {"dative", "pobj", "oprd"}
_MODIFIERS = {"compound", "poss", "nmod"}
_SUBORDINATE = {"advcl", "ccomp", "relcl", "acl", "csubj", "xcomp", "pcomp"}
_NOUNS = {"NOUN", "PROPN"}
_VERBS = {"VERB", "AUX"}


@dataclass
class Candidate:
    text: str
    score: float


def check(doc: Doc, seg: Segment, ratio: float) -> Iterator[Hit]:
    parens = _parenthesized(doc)
    sents = list(doc.sents)
    for i, sent in enumerate(sents):
        for tok in sent:
            if _resolved(tok):
                continue
            ranked = _Pronoun(tok, parens).rank(sents[max(0, i - CONTEXT) : i + 1])
            tied = [seg.restore(c.text) for c in ranked if c.score >= ratio * ranked[0].score]
            if len(tied) >= 2:
                message = f'"{tok.text}" could refer to {" or ".join(map(repr, tied))}; name the noun'
                yield Hit(tok, message, {"pronoun": tok.text, "candidates": [(seg.restore(c.text), c.score) for c in ranked[:4]]})


def _resolved(tok: Token) -> bool:
    """Not a pronoun this rule checks, or one that grammar alone resolves."""
    if tok.lower_ not in NUMBER:
        return True
    return _expletive(tok) or _after_conjunct(tok) or _shared_object(tok) or _local_subject_agrees(tok)


def _expletive(tok: Token) -> bool:
    """ "it" in "it is possible to seal early" """
    if tok.dep_ == "expl":
        return True
    return tok.lower_ == "it" and tok.dep_ in _SUBJ and tok.head.lemma_ in _EXPLETIVE_HEADS and _extraposed(tok)


def _extraposed(tok: Token) -> bool:
    head = tok.head
    clause = any(k.dep_ in ("ccomp", "xcomp", "csubj") for k in head.children)
    return clause or any(t.lower_ in _EXTRAPOSED and t.i > tok.i for t in head.subtree)


def _after_conjunct(tok: Token) -> bool:
    """ "X and its Y" """
    owner = tok.head
    return tok.dep_ == "poss" and owner.dep_ == "conj" and any(k.dep_ == "cc" for k in owner.head.children)


def _shared_object(tok: Token) -> bool:
    """ "add X but not remove it" """
    verb = tok.head
    if tok.dep_ not in _OBJ or verb.dep_ != "conj":
        return False
    obj = next((k for k in verb.head.children if k.dep_ in _OBJ), None)
    return obj is not None and _number(obj) == NUMBER[tok.lower_]


def _local_subject_agrees(tok: Token) -> bool:
    """ "a warehouse can promise its own stock" """
    verb = next((a for a in tok.ancestors if a.pos_ in _VERBS), None) if tok.dep_ == "poss" else None
    subj = subject_of(verb) if verb is not None else None
    if subj is None or subj.pos_ not in _NOUNS:
        return False
    return not subj.left_edge.i <= tok.i <= subj.right_edge.i and _number(subj) == NUMBER[tok.lower_]


def _number(tok: Token) -> str | None:
    return "sg" if PLACEHOLDER.fullmatch(tok.text) else _TAG_NUMBER.get(tok.tag_)


def _parenthesized(doc: Doc) -> set[int]:
    inside, depth = set(), 0
    for t in doc:
        depth = max(0, depth + (t.text == "(") - (t.text == ")"))
        if depth:
            inside.add(t.i)
    return inside


class _Pronoun:
    def __init__(self, tok: Token, parens: set[int]):
        self.tok = tok
        self.number = NUMBER[tok.lower_]
        self.role = _role_name(tok.head if tok.dep_ == "poss" else tok)
        self.excluded = parens | _binding_excluded(tok)

    def rank(self, window: list[Span]) -> list[Candidate]:
        best: dict[str, Candidate] = {}
        for back, sent in enumerate(reversed(window)):
            for t in sent:
                c = self._candidate(t, back)
                key = t.lemma_.lower()
                if c and (key not in best or c.score > best[key].score):
                    best[key] = c
        return sorted(best.values(), key=lambda c: -c.score)

    def _candidate(self, t: Token, back: int) -> Candidate | None:
        text = self._text(t) if self._eligible(t) else None
        return Candidate(text, _salience(t, back, self.role)) if text else None

    def _text(self, t: Token) -> str | None:
        """The candidate as a plural pronoun sees a coordination, or as written."""
        if self.number == "sg":
            return t.text if _number(t) == "sg" else None
        if t.dep_ == "conj":
            return None  # counted with the first conjunct
        group = list(t.conjuncts)
        return " and ".join(x.text for x in [t, *group]) if group else t.text if _number(t) == "pl" else None

    def _eligible(self, t: Token) -> bool:
        noun = t.pos_ in _NOUNS or bool(PLACEHOLDER.fullmatch(t.text))
        return noun and t.i < self.tok.i and t.i not in self.excluded and t.dep_ not in ("compound", "appos") and not _contains(t, self.tok)


def _binding_excluded(tok: Token) -> set[int]:
    """The pronoun's own phrase, and the subject of the verb it is an object of."""
    own = {t.i for t in tok.head.subtree} if tok.dep_ == "poss" else set()
    return own | _coargument_subject(tok)


def _coargument_subject(tok: Token) -> set[int]:
    verb = {**dict.fromkeys(_OBJ, tok.head), "pobj": tok.head.head}.get(tok.dep_)
    subj = subject_of(verb) if verb is not None else None
    if subj is None or subj.pos_ not in _NOUNS:
        return set()
    return {subj.i} | {t.i for t in subj.conjuncts}


def _contains(t: Token, tok: Token) -> bool:
    """Whether ``tok`` lies in the phrase headed by ``t`` with no clause between."""
    for a in tok.ancestors:
        if a.i == t.i or a.pos_ in _VERBS:
            return a.i == t.i
    return False


def _role_name(tok: Token) -> str:
    return "subj" if tok.dep_ in _SUBJ else "obj" if tok.dep_ in _OBJ else "other"


_ROLE_WEIGHTS = dict.fromkeys(_SUBJ, SUBJECT) | dict.fromkeys(_OBJ, OBJECT) | dict.fromkeys(_OBLIQUES, OBLIQUE)


def _role_weight(r: Token) -> int:
    if r.dep_ in _SUBJ and _subordinate(r):
        return OBLIQUE
    if r.dep_ == "attr" and any(k.dep_ == "expl" for k in r.head.children):
        return EXISTENTIAL
    return _ROLE_WEIGHTS.get(r.dep_, 0)


def _subordinate(tok: Token) -> bool:
    return any(a.dep_ in _SUBORDINATE for a in tok.ancestors if a.pos_ in _VERBS)


def _salience(tok: Token, back: int, pronoun_role: str) -> float:
    r = _extended(tok)
    role = "other" if r.dep_ in _SUBJ and _subordinate(r) else _role_name(r)
    parallel = PARALLEL if role == pronoun_role != "other" else 0
    return (RECENCY + _role_weight(r) + _placement_weight(r) + parallel) / 2**back


def _extended(tok: Token) -> Token:
    """A conjunct or apposition takes the role of the phrase it extends."""
    while tok.dep_ in ("conj", "appos"):
        tok = tok.head
    return tok


def _placement_weight(r: Token) -> int:
    """Head-noun and non-adverbial emphasis."""
    attached_to = r.head.head.pos_ if r.dep_ == "pobj" else None
    head = 0 if r.dep_ in _MODIFIERS or attached_to in _NOUNS else HEAD
    return head + (0 if attached_to in _VERBS else NON_ADVERBIAL)
