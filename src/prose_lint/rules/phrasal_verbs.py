"""phrasal-verbs: a phrasal verb with two or more live readings, such as "the
scandal drew attention from the budget", which reads as "drew attention away
from the budget" or "attracted attention from the budget".

The table in ``data/phrasal.toml``, extended by the project config's
``[[phrasal]]`` entries, lists each phrase with its readings. A phrase matches
on the verb's lemma and the words attached to the verb; ``unless`` words, such
as "away", settle the reading. Phrases a project uses in one sense are
silenced with allow entries, such as "make up".
"""

from __future__ import annotations

import tomllib
from collections.abc import Iterator
from importlib import resources

from spacy.tokens import Doc, Token

from ..findings import Hit
from ..markdown import Segment

NAME = "phrasal-verbs"

CONTEXT = 0  # preceding sentences a reader needs to judge a finding

_PARTICLES = ("prt", "advmod", "prep")
_PREPOSITIONS = ("prep", "prt")
_OBJECTS = ("dobj", "obj")


def load(extra: list[dict] | None = None) -> list[dict]:
    data = tomllib.loads(resources.files("prose_lint.data").joinpath("phrasal.toml").read_text())
    return data.get("phrasal", []) + (extra or [])


def check(doc: Doc, seg: Segment, table: list[dict], allow: list[str]) -> Iterator[Hit]:
    for tok in doc:
        found = _match(tok, table) if tok.pos_ == "VERB" else None
        if found and _key(found[0]) not in allow:
            entry, obj = found
            readings = [r.format(object=obj or "") for r in entry["readings"]]
            message = f'"{_phrase(entry, obj)}" reads as {" or ".join(map(repr, readings))}; write the one you mean'
            yield Hit(tok, message, {"phrase": _key(entry), "readings": readings}, entry.get("severity"))


def _match(verb: Token, table: list[dict]) -> tuple[dict, str | None] | None:
    lemma = verb.lemma_.lower()
    kids = list(verb.children)
    obj = _object(kids)
    for entry in table:
        if entry["verb"] == lemma and _fits(entry, kids, obj):
            return entry, obj
    return None


def _fits(entry: dict, kids: list[Token], obj: str | None) -> bool:
    lemmas = {k.lemma_.lower() for k in kids}
    if lemmas & set(entry.get("unless", ())) or not _transitivity(entry, obj):
        return False
    slots = [(entry.get("particle"), _PARTICLES), (entry.get("prep"), _PREPOSITIONS)]
    return _wanted(entry.get("object"), obj) and all(_attached(kids, word, deps) for word, deps in slots if word)


def _transitivity(entry: dict, obj: str | None) -> bool:
    wanted = entry.get("transitive")
    return wanted is None or wanted == (obj is not None)


def _wanted(allowed: str | list[str] | None, obj: str | None) -> bool:
    if allowed is None:
        return True
    return obj in ([allowed] if isinstance(allowed, str) else allowed)


def _object(kids: list[Token]) -> str | None:
    return next((k.lemma_.lower() for k in kids if k.dep_ in _OBJECTS), None)


def _attached(kids: list[Token], word: str, deps: tuple[str, ...]) -> bool:
    return any(k.lower_ == word and k.dep_ in deps for k in kids)


def _key(entry: dict) -> str:
    return " ".join(w for w in (entry["verb"], entry.get("particle"), entry.get("prep")) if w)


def _phrase(entry: dict, obj: str | None) -> str:
    words = (entry["verb"], obj if entry.get("object") else None, entry.get("particle"), entry.get("prep"))
    return " ".join(w for w in words if w)
