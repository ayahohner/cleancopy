"""Rank the antecedents of "it", "its", "they", "them", and "their".

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

One more filter: an argument of a relative clause cannot refer to the noun
the clause modifies ("goals they care about" are not caring).

``antecedent``, which picks one noun for another rule to check, widens the
candidates in two ways that make it decline more often. It ranks earlier
pronouns, so that "it" in "this matters because it tells you" follows
"this", and "it" after "it" follows the chain to a noun. And it lets "they"
refer to one person (singular they), so that "a person ... they" is not
resolved to a plural noun nearby.
"""

from __future__ import annotations

from dataclasses import dataclass

from spacy.tokens import Span, Token

from .grammar import RELATIVE, subject_of
from .lexicon import person
from .markdown import PLACEHOLDER

WINDOW = 1  # candidates come from this many preceding sentences

NUMBER = {"it": "sg", "its": "sg", "they": "pl", "them": "pl", "their": "pl"}
_DEMONSTRATIVE = {"this": "sg", "that": "sg", "these": "pl", "those": "pl"}
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
    token: Token  # the head noun, or a coordination's first conjunct
    text: str
    score: float

    @property
    def members(self) -> list[Token]:
        """The nouns the candidate names: one, or each conjunct of a coordination."""
        return [self.token, *self.token.conjuncts] if " and " in self.text else [self.token]


def candidates(tok: Token, inclusive: bool = False) -> list[Candidate]:
    """The ranked antecedents of ``tok``, or none when ``tok`` is not a pronoun
    this module resolves or when grammar alone resolves it. With ``inclusive``,
    earlier pronouns and, for "they", singular persons count too."""
    if _resolved(tok):
        return []
    sents = list(tok.doc.sents)
    i = next(j for j, s in enumerate(sents) if s.start <= tok.i < s.end)
    return _Pronoun(tok, _parenthesized(tok.doc), inclusive).rank(sents[max(0, i - WINDOW) : i + 1])


def antecedent(tok: Token, ratio: float) -> Candidate | None:
    """The noun a reader picks for ``tok``, or None when none is clear or the
    pronoun follows a demonstrative such as "this". An earlier pronoun counts
    as the noun it refers to, so "it" does not tie with its own antecedent."""
    referents: dict[str, tuple[float, Candidate | None]] = {}
    for c in candidates(tok, inclusive=True):  # highest score first
        noun = _referent(c, ratio)
        referents.setdefault(noun.token.lemma_.lower() if noun else f"#{c.token.i}", (c.score, noun))
    ranked = list(referents.values())
    if not ranked or (len(ranked) > 1 and ranked[1][0] >= ratio * ranked[0][0]):
        return None
    return ranked[0][1]


def _referent(c: Candidate, ratio: float) -> Candidate | None:
    """The noun candidate ``c`` stands for, or None for a demonstrative or an unclear pronoun."""
    if c.token.pos_ != "PRON":
        return c
    return antecedent(c.token, ratio) if c.token.lower_ in NUMBER else None


def _resolved(tok: Token) -> bool:
    """Not a pronoun this module ranks, or one that grammar alone resolves."""
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
    if tok.pos_ == "PRON":
        return NUMBER.get(tok.lower_) or _DEMONSTRATIVE.get(tok.lower_)
    return "sg" if PLACEHOLDER.fullmatch(tok.text) else _TAG_NUMBER.get(tok.tag_)


def _person(tok: Token) -> bool:
    """A singular noun that singular "they" can refer to."""
    return _number(tok) == "sg" and (tok.ent_type_ == "PERSON" or (tok.pos_ == "NOUN" and person(tok.lemma_.lower())))


def _parenthesized(doc) -> set[int]:
    inside, depth = set(), 0
    for t in doc:
        depth = max(0, depth + (t.text == "(") - (t.text == ")"))
        if depth:
            inside.add(t.i)
    return inside


class _Pronoun:
    def __init__(self, tok: Token, parens: set[int], inclusive: bool):
        self.tok = tok
        self.inclusive = inclusive
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
        return Candidate(t, text, _salience(t, back, self.role)) if text else None

    def _text(self, t: Token) -> str | None:
        """The candidate as a plural pronoun sees a coordination, or as written."""
        if self.number == "sg":
            return t.text if _number(t) == "sg" else None
        if t.dep_ == "conj":
            return None  # counted with the first conjunct
        group = list(t.conjuncts)
        if group:
            return " and ".join(x.text for x in [t, *group])
        return t.text if self._plural(t) else None

    def _plural(self, t: Token) -> bool:
        """Whether "they" can refer to ``t``: a plural, or one person for singular they."""
        return _number(t) == "pl" or (self.inclusive and _person(t))

    def _eligible(self, t: Token) -> bool:
        noun = t.pos_ in _NOUNS or bool(PLACEHOLDER.fullmatch(t.text)) or (self.inclusive and _referring(t))
        return noun and t.i < self.tok.i and t.i not in self.excluded and t.dep_ not in ("compound", "appos") and not _contains(t, self.tok)


def _referring(t: Token) -> bool:
    """A pronoun that can stand before another: "it", "they", or "this", not "that" in "a function that"."""
    if t.pos_ != "PRON" or _number(t) is None:
        return False
    return not (t.lower_ in RELATIVE and t.head.dep_ == "relcl")


def _binding_excluded(tok: Token) -> set[int]:
    """The pronoun's own phrase, the subject of the verb it is an object of,
    and the noun modified by the relative clause it is an argument of."""
    own = {t.i for t in tok.head.subtree} if tok.dep_ == "poss" else set()
    relative = {tok.head.head.i} if tok.dep_ in _SUBJ | _OBJ and tok.head.dep_ == "relcl" else set()
    return own | relative | _coargument_subject(tok)


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
