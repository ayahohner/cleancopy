"""Grammar that settles or narrows what a pronoun refers to, before salience.

A pronoun is settled, and never ranked, when grammar alone decides it:

- the expletive "it": "it is possible to seal early", "make it easier to
  identify", and "harder than it needs to be";
- a pronoun inside quoted speech, which refers within the quotation;
- "X and its Y" (X), "add X but not remove it" (X), and a possessive whose
  own clause has an agreeing subject, a direct object it sits beside
  ("split the system into its parts"), or a participle's noun ("metabolites,
  noted for their aromas");
- a pronoun under distributive "each": "each in its own way";
- a pronoun that continues a chain: an earlier pronoun of the same number and
  role in the window ("hold them ... revise them"). Centering theory predicts
  that a chain keeps its referent, so only the chain's first pronoun is
  judged.

Nouns a pronoun cannot refer to, the binding conditions of Chomsky's Lectures
on Government and Binding (1981) as they apply to plain pronouns:

- its own phrase: "its" in "its value" is not the value;
- a phrase that contains it, through prepositions and gerunds but not
  through a clause or a coordination: "the cost of applying it" is not the
  cost (the i-within-i condition);
- the subject and the other objects of its own verb, which English expresses
  with "itself": "reorganizing your life around it" is not the life;
- the implicit subject of an infinitive or a gerund: "unqualified to execute
  it" and "before acting on it" do not refer to the one executing or acting;
- the subject of a copula whose predicate contains it, through prepositions
  and participles but not through a relative clause;
- the noun modified by the relative clause it is an argument of: "goals they
  care about" are not caring.
"""

from __future__ import annotations

from spacy.tokens import Token

from .grammar import RELATIVE, subject_of
from .markdown import PLACEHOLDER

WINDOW = 1  # candidates come from this many preceding sentences

NUMBER = {"it": "sg", "its": "sg", "they": "pl", "them": "pl", "their": "pl"}
_DEMONSTRATIVE = {"this": "sg", "these": "pl"}
_TAG_NUMBER = {"NN": "sg", "NNP": "sg", "NNS": "pl", "NNPS": "pl"}
_EXPLETIVE_HEADS = {"be", "seem", "appear", "take", "make", "follow", "turn", "matter", "help"}
_SMALL_CLAUSE_HEADS = {"make", "find", "consider", "keep", "leave", "render", "think", "deem"}
_EXTRAPOSED = {"to", "that", "whether", "if"}

SUBJ = {"nsubj", "nsubjpass", "csubj"}
OBJ = {"dobj", "obj"}
NOUNS = {"NOUN", "PROPN"}
VERBS = {"VERB", "AUX"}
_ARGUMENTS = OBJ | {"dative"}


def number(tok: Token) -> str | None:
    if tok.pos_ == "PRON":
        return NUMBER.get(tok.lower_) or _DEMONSTRATIVE.get(tok.lower_)
    return "sg" if PLACEHOLDER.fullmatch(tok.text) else _TAG_NUMBER.get(tok.tag_)


def role(tok: Token) -> str:
    if tok.dep_ == "poss":
        return "poss"
    return "subj" if tok.dep_ in SUBJ else "obj" if tok.dep_ in _ARGUMENTS | {"pobj"} else "other"


def window_start(tok: Token) -> int:
    """The first token of the earliest sentence a pronoun's antecedent can come from."""
    sents = list(tok.doc.sents)
    i = next(j for j, s in enumerate(sents) if s.start <= tok.i < s.end)
    return sents[max(0, i - WINDOW)].start


def settled(tok: Token) -> bool:
    """Not a pronoun this module ranks, or one that grammar alone resolves."""
    if tok.lower_ not in NUMBER:
        return True
    return any(f(tok) for f in (expletive, _quoted, _after_conjunct, _shared_object, _local_owner, _distributive))


def chained(tok: Token) -> bool:
    """ "hold them humbly enough to revise them" """
    r = role(tok)
    return any(_referring(t) and number(t) == NUMBER[tok.lower_] and role(t) == r and not expletive(t) for t in tok.doc[window_start(tok) : tok.i])


def expletive(tok: Token) -> bool:
    """ "it is possible to seal early", "make it easier to identify", "harder than it needs to be" """
    if tok.dep_ == "expl":
        return True
    if tok.lower_ != "it":
        return False
    extraposed = tok.dep_ in SUBJ and tok.head.lemma_ in _EXPLETIVE_HEADS and _extraposed(tok)
    return extraposed or _small_clause(tok) or _comparative(tok)


def _extraposed(tok: Token) -> bool:
    head = tok.head
    clause = any(k.dep_ in ("ccomp", "xcomp", "csubj") for k in head.children)
    return clause or any(t.lower_ in _EXTRAPOSED and t.i > tok.i for t in head.subtree)


def _small_clause(tok: Token) -> bool:
    """ "make it easier to identify", parsed with "it" as the subject of "easier" or as the object of "make" """
    adj = _predicate_adjective(tok)
    if adj is None:
        return False
    verb = adj.head if adj == tok.head else tok.head
    return verb.lemma_ in _SMALL_CLAUSE_HEADS and any(_infinitive(k) or k.dep_ == "ccomp" for k in adj.children)


def _predicate_adjective(tok: Token) -> Token | None:
    if tok.head.pos_ == "ADJ":
        return tok.head
    return next((k for k in tok.head.children if k.pos_ == "ADJ" and k.i > tok.i), None)


def _infinitive(tok: Token) -> bool:
    return tok.pos_ in VERBS and any(k.dep_ == "aux" and k.lower_ == "to" for k in tok.children)


def _comparative(tok: Token) -> bool:
    return tok.dep_ in SUBJ and any(k.dep_ == "mark" and k.lower_ == "than" for k in tok.head.children)


def _quoted(tok: Token) -> bool:
    depth = 0
    for t in tok.doc[tok.sent.start : tok.i]:
        depth = depth + 1 if t.text == "“" else depth - 1 if t.text == "”" else 1 - depth if t.text == '"' else depth
    return depth > 0


def _after_conjunct(tok: Token) -> bool:
    """ "X and its Y" """
    owner = tok.head
    return tok.dep_ == "poss" and owner.dep_ == "conj" and any(k.dep_ == "cc" for k in owner.head.children)


def _shared_object(tok: Token) -> bool:
    """ "add X but not remove it" """
    verb = tok.head
    if tok.dep_ not in OBJ or verb.dep_ != "conj":
        return False
    obj = next((k for k in verb.head.children if k.dep_ in OBJ), None)
    return obj is not None and number(obj) == NUMBER[tok.lower_]


def _local_owner(tok: Token) -> bool:
    """ "a warehouse can promise its own stock", "split the system into its parts", "metabolites, noted for their aromas" """
    verb = next((a for a in tok.ancestors if a.pos_ in VERBS), None) if tok.dep_ == "poss" else None
    if verb is None:
        return False
    return any(o is not None and _agrees_outside(o, tok) for o in _owners(tok, verb))


def _owners(tok: Token, verb: Token) -> list[Token | None]:
    """The clause's subject, the direct object beside the possessive's phrase, and a participle's noun."""
    beside = tok.head.dep_ == "pobj" and tok.head.head.head == verb
    return [subject_of(verb), _direct_object(verb) if beside else None, verb.head if verb.dep_ == "acl" else None]


def _direct_object(verb: Token) -> Token | None:
    return next((k for k in verb.children if k.dep_ in OBJ), None)


def _agrees_outside(owner: Token, tok: Token) -> bool:
    if owner.pos_ not in NOUNS and not (owner.lower_ in NUMBER and owner.i < tok.i):
        return False
    return not contains(owner, tok) and number(owner) == NUMBER[tok.lower_]


def _distributive(tok: Token) -> bool:
    """ "each in its own way", "each with the replies it accepts" """
    return any(a.lower_ == "each" for a in tok.ancestors)


def _referring(t: Token) -> bool:
    """A pronoun that can stand before another: "it", "they", or "this", not "that" in "a function that"."""
    if t.pos_ != "PRON" or number(t) is None:
        return False
    return not (t.lower_ in RELATIVE and t.head.dep_ == "relcl")


def excluded(tok: Token) -> set[int]:
    """The nouns, by index, that the pronoun cannot refer to, beyond the
    phrases that contain it (see ``contains``)."""
    own = {t.i for t in tok.head.subtree} if tok.dep_ == "poss" else set()
    relative = {tok.head.head.i} if tok.dep_ in SUBJ | OBJ and tok.head.dep_ == "relcl" else set()
    return own | relative | _coarguments(tok) | _predicated(tok)


def _coarguments(tok: Token) -> set[int]:
    verb = _governor(tok)
    if verb is None:
        return set()
    subj = subject_of(_controller(verb))
    others = [k for k in verb.children if k.dep_ in _ARGUMENTS and k != tok] if tok.dep_ != "poss" else []
    return _with_conjuncts([subj, *others])


def _governor(tok: Token) -> Token | None:
    """The verb whose object or oblique the pronoun is."""
    if tok.dep_ in _ARGUMENTS:
        return tok.head
    return tok.head.head if tok.dep_ == "pobj" and tok.head.head.pos_ in VERBS else None


def _controller(verb: Token) -> Token:
    """The verb whose subject performs ``verb``: "unqualified to execute it", "before acting on it"."""
    if verb.dep_ == "xcomp" and verb.head.pos_ == "ADJ":
        return verb.head.head
    if verb.dep_ == "pcomp" and verb.head.head.pos_ in VERBS:
        return verb.head.head
    return verb


def _predicated(tok: Token) -> set[int]:
    """ "$r_a$ and $r_b$ are records of values supplied at them" """
    if tok.dep_ == "poss":
        return set()
    for a in tok.ancestors:
        if a.dep_ == "attr":
            return _with_conjuncts([subject_of(a.head)])
        if a.pos_ in VERBS and a.dep_ not in ("pcomp", "acl"):
            break
    return set()


def _with_conjuncts(nouns: list[Token | None]) -> set[int]:
    return {t.i for n in nouns if n is not None and n.pos_ in NOUNS for t in (n, *n.conjuncts)}


def contains(t: Token, tok: Token) -> bool:
    """Whether ``tok`` lies in the phrase headed by ``t``: through
    prepositions and their gerunds, but not through another clause or from one
    conjunct into the next."""
    child = tok
    for a in tok.ancestors:
        if child.dep_ == "conj":
            return False
        if a.i == t.i:
            return True
        if a.pos_ in VERBS and a.dep_ != "pcomp":
            return False
        child = a
    return False
