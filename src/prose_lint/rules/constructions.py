"""constructions: banned sentence constructions, found in the parse rather
than in the words, so "It's a protocol, not a library" and "This isn't about
speed. It's about trust." are one construction.

Built in:

- ``comma-not``: "X, not Y" ("coordination, not control"; "a list, not a set").
- ``not-but``: "not X but Y" ("not a library but a protocol"), but not "not
  only X but also Y", which adds rather than corrects.
- ``not-then-is``: a negated clause corrected by the next one, with the same
  subject and verb: "It isn't a library; it's a protocol", "This doesn't mean
  X. It means Y." A clause joined by "and" or "but" is a concession or a
  list, not a correction.
- ``gerund-tells-you``: "Knowing the order tells you where to start", "Seeing
  the trace gives you the cause".

A project bans more constructions with spaCy ``DependencyMatcher`` patterns
(https://spacy.io/api/dependencymatcher) and silences built-ins by name.
"""

from __future__ import annotations

from collections.abc import Iterator

from spacy.matcher import DependencyMatcher
from spacy.tokens import Doc, Span, Token

from ..findings import Hit
from ..markdown import Segment

NAME = "constructions"

CONTEXT = 0

_CONTRAST = "contrast by negation: say what it is, and give a live misreading its own sentence with the reason"
MESSAGES = {
    "comma-not": f'"X, not Y" is a {_CONTRAST}',
    "not-but": f'"not X but Y" is a {_CONTRAST}',
    "not-then-is": f'"It isn\'t X. It\'s Y." is a {_CONTRAST}',
    "gerund-tells-you": '"Knowing X tells you Y": say what X implies, as in "X implies Y" or "if X, then Y"',
}
_BREAKS = {",", ";", "—", "–", "(", ":"}
_NOUNLIKE = {"NOUN", "PROPN", "PRON", "ADJ", "ADV", "ADP", "NUM", "DET"}
_REASONS = {"because", "since", "as"}
_ADDITIVE = {"only", "just", "merely", "simply", "even"}
_TELL = {"tell", "give", "show", "teach"}
_ADDRESSEES = {"you", "us"}
_JOINS = {"and", "but", "or", "yet", "so"}
_RESUMING = {"it", "this", "they", "that"}


def check(doc: Doc, seg: Segment, allow: list[str], patterns: list[dict]) -> Iterator[Hit]:
    found = [*_builtins(doc), *_matched(doc, patterns)]
    for name, tok, message in found:
        if name not in allow:
            yield Hit(tok, message, {"construction": name})


def _builtins(doc: Doc) -> Iterator[tuple[str, Token, str]]:
    for tok in doc:
        for name, test in _TESTS.items():
            if test(tok):
                yield name, tok, MESSAGES[name]


def _comma_not(tok: Token) -> bool:
    """ "coordination, not control"; "chose to wait, not because he was tired" """
    if not _negator(tok) or tok.i == 0 or _doc_text(tok, -1) not in _BREAKS:
        return False
    head = tok.head
    return head.pos_ in _NOUNLIKE or any(k.dep_ == "mark" and k.lower_ in _REASONS for k in head.children)


def _not_but(tok: Token) -> bool:
    """ "not a library but a protocol"; "does not decide but records" """
    if not _negator(tok) or tok.dep_ == "preconj" or _additive(tok):
        return False
    return _joined(tok.head, {"but"}) and any(k.dep_ == "conj" and not _has_subject(k) for k in tok.head.children)


def _not_then_is(tok: Token) -> bool:
    """ "It isn't a library; it's a protocol." """
    if tok.dep_ != "neg" or tok.head.pos_ not in ("VERB", "AUX"):
        return False
    verb = tok.head
    subj = _subject(verb)
    after = _next_clause(verb)
    return subj is not None and after is not None and after.lemma_ == verb.lemma_ and _corrects(subj, after)


def _gerund_tells_you(tok: Token) -> bool:
    """ "Knowing the order tells you where to start." """
    if tok.lemma_.lower() not in _TELL or tok.pos_ != "VERB":
        return False
    gerund = any(k.dep_ in ("csubj", "nsubj") and k.tag_ == "VBG" for k in tok.children)
    return gerund and any(k.dep_ in ("dobj", "dative") and k.lower_ in _ADDRESSEES for k in tok.children)


_TESTS = {"comma-not": _comma_not, "not-but": _not_but, "not-then-is": _not_then_is, "gerund-tells-you": _gerund_tells_you}


def _doc_text(tok: Token, offset: int) -> str:
    return tok.doc[tok.i + offset].text


def _negator(tok: Token) -> bool:
    return tok.lower_ == "not" and tok.dep_ in ("neg", "preconj")


def _additive(tok: Token) -> bool:
    return tok.i + 1 < len(tok.doc) and _doc_text(tok, 1).lower() in _ADDITIVE


def _joined(head: Token, words: set[str]) -> bool:
    return any(k.dep_ == "cc" and k.lower_ in words for k in head.children)


def _has_subject(verb: Token) -> bool:
    return any(k.dep_ in ("nsubj", "nsubjpass", "expl") for k in verb.children)


def _subject(verb: Token) -> Token | None:
    return next((k for k in verb.children if k.dep_ in ("nsubj", "nsubjpass", "expl")), None)


def _next_clause(verb: Token) -> Token | None:
    """The clause right after ``verb``'s, when nothing joins them but punctuation."""
    if verb.dep_ == "ccomp" and verb.head.i > verb.i:  # "It isn't X; it's Y" parses the first as the second's complement
        return verb.head
    later = _later_clause(verb)
    if later is not None:
        return None if _joined(verb, _JOINS) else later
    return _following_root(verb.sent) if verb == verb.sent.root else None


def _later_clause(verb: Token) -> Token | None:
    return next((k for k in verb.children if k.dep_ in ("conj", "parataxis") and k.i > verb.i), None)


def _following_root(sent: Span) -> Token | None:
    doc = sent.doc
    return doc[sent.end].sent.root if sent.end < len(doc) else None


def _corrects(subj: Token, verb: Token) -> bool:
    """ ``verb`` is a positive clause whose subject is ``subj`` again or a pronoun for it. """
    other = _subject(verb)
    if other is None or any(k.dep_ == "neg" for k in verb.children):
        return False
    return other.lower_ == subj.lower_ or (other.pos_ == "PRON" and other.lower_ in _RESUMING)


_MATCHERS: dict[int, tuple[list[dict], DependencyMatcher]] = {}


def _matched(doc: Doc, patterns: list[dict]) -> Iterator[tuple[str, Token, str]]:
    if not patterns:
        return
    matcher = _matcher(doc, patterns)
    for key, ids in matcher(doc):
        name = doc.vocab.strings[key]
        entry = next(p for p in patterns if p["name"] == name)
        yield name, doc[ids[0]], entry.get("message", f'"{name}" is a banned construction')


def _matcher(doc: Doc, patterns: list[dict]) -> DependencyMatcher:
    cached = _MATCHERS.get(id(doc.vocab))
    if cached is None or cached[0] is not patterns:
        matcher = DependencyMatcher(doc.vocab)
        for p in patterns:
            matcher.add(p["name"], [p["pattern"]])
        cached = _MATCHERS[id(doc.vocab)] = (patterns, matcher)
    return cached[1]
