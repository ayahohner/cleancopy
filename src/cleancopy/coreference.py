"""Rank the antecedents of "it", "its", "they", "them", and "their".

Candidates are ranked by the salience weights of Lappin and Leass, "An
Algorithm for Pronominal Anaphora Resolution" (Computational Linguistics,
1994): a noun phrase scores for being recent, a subject, an object, and a
phrase's head rather than a modifier inside another phrase, and the score
halves with each sentence boundary. Readers resolve a pronoun to the most
salient candidate, so a pronoun is clear when one candidate stands well above
the rest and ambiguous when the runner-up scores at least ``ratio`` of the
leader.

Grammar settles some pronouns outright and rules out some nouns before
ranking; see ``binding``. Number agreement filters the rest, and so do
appositions and parentheticals, which repeat a noun already counted;
predicates ("is a component", "treat it as a record", "mark the choice
`acts`"), which describe a referent rather than name one; and, for "it" and
"its", nouns for people.

Four adjustments to Lappin and Leass, each a structure that readers resolve
without weighing salience:

- A coordination ("bookings, registrations, and transfers") is one candidate
  for a plural pronoun, and a disjunction ("the material or system") is one
  candidate for a singular pronoun.
- A subject inside a subordinate clause scores as an oblique, so the main
  clause's subject leads, as centering theory predicts.
- A pronoun that continues a chain of pronouns with the same number and role
  is not judged again (see ``binding.chained``).
- A possessive resolves to the subject of its own clause when the subject
  agrees (see ``binding``).

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

from . import binding
from .binding import NOUNS, NUMBER, OBJ, SUBJ, VERBS, WINDOW, number
from .grammar import subject_of
from .lexicon import AGENT, Lexicon, only_person, person
from .markdown import PLACEHOLDER

__all__ = ["NUMBER", "WINDOW", "Candidate", "antecedent", "candidates"]

# Lappin and Leass (1994), table of salience factors.
RECENCY = 100
SUBJECT = 80
EXISTENTIAL = 70
OBJECT = 50
OBLIQUE = 40
HEAD = 80
NON_ADVERBIAL = 50
PARALLEL = 35

_OBLIQUES = {"dative", "pobj"}
_MODIFIERS = {"compound", "poss", "nmod"}
_SUBORDINATE = {"advcl", "ccomp", "relcl", "acl", "csubj", "xcomp", "pcomp"}
_IT = {"it", "its"}


@dataclass
class Candidate:
    token: Token  # the head noun, or a coordination's first conjunct
    text: str
    score: float

    @property
    def members(self) -> list[Token]:
        """The nouns the candidate names: one, or each conjunct of a coordination."""
        return [self.token, *self.token.conjuncts] if " and " in self.text or " or " in self.text else [self.token]


def candidates(tok: Token, inclusive: bool = False, lexicon: Lexicon | None = None) -> list[Candidate]:
    """The ranked antecedents of ``tok``, or none when ``tok`` is not a pronoun
    this module resolves or when grammar alone resolves it. With ``inclusive``,
    earlier pronouns and, for "they", singular persons count too. ``lexicon``
    overrides WordNet on which nouns name people, whom "it" cannot refer to."""
    if binding.settled(tok) or (not inclusive and binding.chained(tok)):
        return []
    start, end = binding.window_start(tok), tok.sent.end
    return _Pronoun(tok, _parenthesized(tok.doc), inclusive, lexicon).rank([s for s in tok.doc[start:end].sents])


def antecedent(tok: Token, ratio: float, lexicon: Lexicon | None = None) -> Candidate | None:
    """The noun a reader picks for ``tok``, or None when none is clear or the
    pronoun follows a demonstrative such as "this". An earlier pronoun counts
    as the noun it refers to, so "it" does not tie with its own antecedent."""
    referents: dict[str, tuple[float, Candidate | None]] = {}
    for c in candidates(tok, inclusive=True, lexicon=lexicon):  # highest score first
        noun = _referent(c, ratio, lexicon)
        referents.setdefault(noun.token.lemma_.lower() if noun else f"#{c.token.i}", (c.score, noun))
    ranked = list(referents.values())
    if not ranked or (len(ranked) > 1 and ranked[1][0] >= ratio * ranked[0][0]):
        return None
    return ranked[0][1]


def _referent(c: Candidate, ratio: float, lexicon: Lexicon | None) -> Candidate | None:
    """The noun candidate ``c`` stands for, or None for a demonstrative or an unclear pronoun."""
    if c.token.pos_ != "PRON":
        return c
    return antecedent(c.token, ratio, lexicon) if c.token.lower_ in NUMBER else None


def _person(tok: Token) -> bool:
    """A singular noun that singular "they" can refer to."""
    return number(tok) == "sg" and (tok.ent_type_ == "PERSON" or (tok.pos_ == "NOUN" and person(tok.lemma_.lower())))


def _parenthesized(doc) -> set[int]:
    inside, depth = set(), 0
    for t in doc:
        depth = max(0, depth + (t.text == "(") - (t.text == ")"))
        if depth:
            inside.add(t.i)
    return inside


class _Pronoun:
    def __init__(self, tok: Token, parens: set[int], inclusive: bool, lexicon: Lexicon | None):
        self.tok = tok
        self.inclusive = inclusive
        self.lexicon = lexicon
        self.number = NUMBER[tok.lower_]
        self.role = _role_name(tok.head if tok.dep_ == "poss" else tok)
        self.excluded = parens | binding.excluded(tok)

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
        """The candidate as the pronoun sees a coordination, or as written."""
        group = [t, *t.conjuncts]
        disjunction = _disjunction(group)
        if self.number == "sg" and not disjunction:
            return t.text if number(t) == "sg" else None
        if len(group) == 1:
            return t.text if self._plural(t) else None
        return _joined(group, disjunction) if t.dep_ != "conj" else None  # a conjunct counts with the first

    def _plural(self, t: Token) -> bool:
        """Whether "they" can refer to ``t``: a plural, or one person for singular they."""
        return number(t) == "pl" or (self.inclusive and _person(t))

    def _human(self, t: Token) -> bool:
        """A person, whom "it" cannot name: "colleague", not "compiler" or a noun the lexicon classes otherwise."""
        if t.ent_type_ == "PERSON":
            return True
        listed = self.lexicon.entry(t) if self.lexicon else None
        return listed in (None, AGENT) and t.pos_ == "NOUN" and only_person(t.lemma_.lower())

    def _eligible(self, t: Token) -> bool:
        noun = t.pos_ in NOUNS or bool(PLACEHOLDER.fullmatch(t.text)) or (self.inclusive and binding.referring(t))
        return noun and t.i < self.tok.i and t.i not in self.excluded and not self._ruled_out(t)

    def _ruled_out(self, t: Token) -> bool:
        """A modifier, an apposition, a predicate, a person for "it", or a phrase containing the pronoun."""
        if t.dep_ in ("compound", "appos") or _predicate(t):
            return True
        return (self.tok.lower_ in _IT and self._human(t)) or binding.contains(t, self.tok)


def _joined(group: list[Token], disjunction: bool) -> str:
    return (" or " if disjunction else " and ").join(x.text for x in group)


def _disjunction(group: list[Token]) -> bool:
    """ "the material or system" """
    return len(group) > 1 and any(k.dep_ == "cc" and k.lower_ == "or" for t in group for k in t.children)


def _predicate(t: Token) -> bool:
    """A noun that describes a referent: "is a component", "treat it as a record", "mark the choice `acts`"."""
    if t.dep_ == "oprd":
        return True
    if t.dep_ == "attr":
        return subject_of(t.head) is not None
    prep = t.head
    return t.dep_ == "pobj" and prep.lower_ == "as" and prep.head.pos_ in VERBS and not any(k.lower_ == "such" for k in prep.children)


def _role_name(tok: Token) -> str:
    return "subj" if tok.dep_ in SUBJ else "obj" if tok.dep_ in OBJ else "other"


_ROLE_WEIGHTS = dict.fromkeys(SUBJ, SUBJECT) | dict.fromkeys(OBJ, OBJECT) | dict.fromkeys(_OBLIQUES, OBLIQUE)


def _role_weight(r: Token) -> int:
    if r.dep_ in SUBJ and _subordinate(r):
        return OBLIQUE
    if r.dep_ == "attr" and any(k.dep_ == "expl" for k in r.head.children):
        return EXISTENTIAL
    return _ROLE_WEIGHTS.get(r.dep_, 0)


def _subordinate(tok: Token) -> bool:
    return any(a.dep_ in _SUBORDINATE for a in tok.ancestors if a.pos_ in VERBS)


def _salience(tok: Token, back: int, pronoun_role: str) -> float:
    r = _extended(tok)
    role = "other" if r.dep_ in SUBJ and _subordinate(r) else _role_name(r)
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
    head = 0 if r.dep_ in _MODIFIERS or attached_to in NOUNS else HEAD
    return head + (0 if attached_to in VERBS else NON_ADVERBIAL)
