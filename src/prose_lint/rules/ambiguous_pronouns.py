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

- A coordination ("bookings, registrations, and transfers") is one plural
  candidate, not several.
- "X and its Y" resolves to X, and "add X but not remove it" to X.
- A possessive resolves to the subject of its own clause when the subject
  agrees: "a warehouse can promise its own stock".
- A subject inside a subordinate clause scores as an oblique, so the main
  clause's subject leads, as centering theory predicts.
"""

from __future__ import annotations

from dataclasses import dataclass

from spacy.tokens import Doc, Span, Token

from ..findings import Finding
from ..grammar import subject_of
from ..markdown import PLACEHOLDER, Segment

NAME = "ambiguous-pronouns"

SINGULAR = {"it", "its"}
PLURAL = {"they", "them", "their"}
_EXPLETIVE_HEADS = {"be", "seem", "appear", "take", "make", "follow", "turn", "matter", "help"}

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
_SUBORDINATE = {"advcl", "ccomp", "relcl", "acl", "csubj", "xcomp", "pcomp"}
_OBJ = {"dobj", "obj"}


@dataclass
class Candidate:
    token: Token
    text: str
    score: float


def _expletive(tok: Token) -> bool:
    if tok.dep_ == "expl":
        return True
    if tok.lower_ != "it" or tok.dep_ not in _SUBJ:
        return False
    head = tok.head
    if head.lemma_ not in _EXPLETIVE_HEADS:
        return False
    return any(k.dep_ in ("ccomp", "xcomp", "csubj") for k in head.children) or any(
        t.lower_ in ("to", "that", "whether", "if") and t.i > tok.i for t in head.subtree
    )


def _number(tok: Token) -> str | None:
    if PLACEHOLDER.fullmatch(tok.text):
        return "sg"
    if tok.tag_ in ("NN", "NNP"):
        return "sg"
    if tok.tag_ in ("NNS", "NNPS"):
        return "pl"
    return None


def _role(tok: Token) -> Token:
    """A conjunct or apposition takes the role of the phrase it extends."""
    while tok.dep_ in ("conj", "appos") and tok.head.i != tok.i:
        tok = tok.head
    return tok


def _subordinate(tok: Token) -> bool:
    return any(a.dep_ in _SUBORDINATE for a in tok.ancestors if a.pos_ in ("VERB", "AUX"))


def _salience(tok: Token, sentences_back: int, pronoun_role: str) -> float:
    r = _role(tok)
    s = RECENCY
    if r.dep_ in _SUBJ and _subordinate(r):
        s += OBLIQUE
        role = "other"
    elif r.dep_ in _SUBJ:
        s += SUBJECT
        role = "subj"
    elif r.dep_ == "attr" and any(k.dep_ == "expl" for k in r.head.children):
        s += EXISTENTIAL
        role = "other"
    elif r.dep_ in _OBJ:
        s += OBJECT
        role = "obj"
    elif r.dep_ in ("dative", "pobj", "oprd"):
        s += OBLIQUE
        role = "other"
    else:
        role = "other"
    in_np = r.dep_ in ("compound", "poss", "nmod") or (r.dep_ == "pobj" and r.head.head.pos_ in ("NOUN", "PROPN"))
    if not in_np:
        s += HEAD
    adverbial = r.dep_ == "pobj" and r.head.head.pos_ in ("VERB", "AUX")
    if not adverbial:
        s += NON_ADVERBIAL
    if role == pronoun_role and role != "other":
        s += PARALLEL
    return s / (2 ** sentences_back)


def _pronoun_role(tok: Token) -> str:
    if tok.dep_ == "poss":
        return _pronoun_role(tok.head)
    if tok.dep_ in _SUBJ:
        return "subj"
    if tok.dep_ in _OBJ:
        return "obj"
    return "other"


def _shared_object(tok: Token) -> Token | None:
    """For "add X but not remove it", return X."""
    verb = tok.head
    if tok.dep_ not in _OBJ or verb.dep_ != "conj":
        return None
    objs = [k for k in verb.head.children if k.dep_ in _OBJ]
    return objs[0] if objs and _number(objs[0]) == _number_of(tok) else None


def _number_of(pronoun: Token) -> str:
    return "sg" if pronoun.lower_ in SINGULAR else "pl"


def _contains(t: Token, tok: Token) -> bool:
    """Whether ``tok`` lies in the phrase headed by ``t`` with no clause between."""
    for a in tok.ancestors:
        if a.i == t.i:
            return True
        if a.pos_ in ("VERB", "AUX"):
            return False
    return False


def _parenthetical(t: Token) -> bool:
    sent = t.sent
    before = [x.text for x in sent if x.i < t.i]
    return before.count("(") > before.count(")")


def _local_subject(tok: Token) -> Token | None:
    """The subject of the clause containing a possessive pronoun."""
    a = tok
    while a.head.i != a.i and a.pos_ not in ("VERB", "AUX"):
        a = a.head
    if a.pos_ not in ("VERB", "AUX"):
        return None
    subj = subject_of(a)
    if subj is None or tok in subj.subtree or subj.pos_ not in ("NOUN", "PROPN"):
        return None
    return subj


def _coordinated_with(tok: Token) -> Token | None:
    """For "X and its Y", return X."""
    if tok.dep_ != "poss":
        return None
    owner = tok.head
    if owner.dep_ == "conj" and any(k.dep_ == "cc" for k in owner.head.children):
        return owner.head
    return None

def candidates(tok: Token, window: list[Span]) -> list[Candidate]:
    want = "sg" if tok.lower_ in SINGULAR else "pl"
    own = {t.i for t in tok.head.subtree} if tok.dep_ == "poss" else set()
    if tok.dep_ in _OBJ or tok.dep_ == "pobj":
        subj = subject_of(tok.head if tok.dep_ in _OBJ else tok.head.head)
        if subj is not None and subj.pos_ in ("NOUN", "PROPN"):
            own |= {t.i for t in subj.conjuncts} | {subj.i}
    pronoun_role = _pronoun_role(tok)
    best: dict[str, Candidate] = {}
    for back, sent in enumerate(reversed(window)):
        for t in sent:
            if t.i >= tok.i or t.i in own:
                continue
            if t.pos_ not in ("NOUN", "PROPN") and not PLACEHOLDER.fullmatch(t.text):
                continue
            if t.dep_ in ("compound", "appos") or _contains(t, tok) or _parenthetical(t):
                continue
            group = list(t.conjuncts)
            if group and t.dep_ == "conj":
                continue  # counted with the first conjunct
            number = "pl" if group and t.tag_ not in ("VBG",) and any(k.dep_ == "cc" for k in [t, *group] for k in k.children) else _number(t)
            if number != want:
                continue
            key = t.lemma_.lower()
            score = _salience(t, back, pronoun_role)
            if key not in best or score > best[key].score:
                text = " and ".join(x.text for x in [t, *group]) if number == "pl" and group and _number(t) == "sg" else t.text
                best[key] = Candidate(t, text, score)
    return sorted(best.values(), key=lambda c: -c.score)

def check(doc: Doc, seg: Segment, path: str, severity: str, ratio: float = 0.85) -> list[Finding]:
    out = []
    sents = list(doc.sents)
    for i, sent in enumerate(sents):
        for tok in sent:
            if tok.lower_ not in SINGULAR | PLURAL or _expletive(tok):
                continue
            if _coordinated_with(tok) is not None or _shared_object(tok) is not None:
                continue
            if tok.dep_ == "poss":
                subj = _local_subject(tok)
                if subj is not None and _number(subj) == ("sg" if tok.lower_ in SINGULAR else "pl"):
                    continue
            ranked = candidates(tok, sents[max(0, i - 1): i + 1])
            if len(ranked) < 2 or ranked[1].score < ratio * ranked[0].score:
                continue
            tied = [c for c in ranked if c.score >= ratio * ranked[0].score]
            names = [seg.restore(c.text) for c in tied]
            out.append(Finding(
                path=path, line=seg.line, rule=NAME, severity=severity,
                message=f'"{tok.text}" could refer to {" or ".join(repr(n) for n in names)}; name the noun',
                excerpt=seg.restore(sent.text),
                data={"pronoun": tok.text, "candidates": [(seg.restore(c.text), c.score) for c in ranked[:4]]},
            ))
    return out
