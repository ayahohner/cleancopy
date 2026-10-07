"""What each verb requires of its subject.

Two sources, consulted in order:

1. A table of verbs and phrases (``data/verbs.toml`` plus the project's
   config). Phrases such as "draw the line" and "pay for" are figures whose
   single verb has a literal sense with any subject, so only the table can
   catch them.
2. Optionally, VerbNet 3, which records selectional restrictions on thematic roles. For
   each class a verb belongs to, the subject of every frame is found and its
   restriction read. A verb requires an animate subject only if the subject
   of every frame in every class does, so a verb with any literal sense that
   takes an inanimate subject is never flagged from VerbNet alone.

   VerbNet's restrictions describe a role's typical filler rather than the
   verb's literal limit: "depend", "arrive", and "determine" are restricted
   to animate subjects. Measured on three long posts, about one VerbNet
   finding in seven was a figure, so VerbNet findings are a discovery aid,
   reported at "info" for curating the table, and are off by default.

A phrase with ``needs = "any"`` exempts a lexicalized idiom, such as "stand
for", from the entry for its verb.
"""

from __future__ import annotations

import tomllib
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from functools import lru_cache
from importlib import resources

from nltk.corpus.reader import VerbnetCorpusReader
from nltk.data import find
from spacy.tokens import Token

ANIMATE = "animate"  # person, organization, or AI agent
ANY = "any"  # an exemption
CONCRETE = "concrete"  # a physical object or an agent

_ANIMATE_TYPES = {"animate", "organization", "human"}
_CONCRETE_TYPES = _ANIMATE_TYPES | {"concrete", "solid", "body_part", "elongated", "pointy", "machine", "vehicle", "animal", "plant", "garment"}


@dataclass(frozen=True)
class Requirement:
    needs: str  # ANIMATE or CONCRETE
    source: str  # "table" or a VerbNet class id
    phrase: str  # the verb or phrase as it matched
    suggest: tuple[str, ...] = ()


@dataclass
class VerbTable:
    verbs: dict[str, dict] = field(default_factory=dict)
    phrases: list[dict] = field(default_factory=list)
    ignore: set[str] = field(default_factory=set)
    verbnet: bool = False

    @classmethod
    def load(cls, extra: dict | None = None, verbnet: bool = False) -> "VerbTable":
        data = tomllib.loads(resources.files("prose_lint.data").joinpath("verbs.toml").read_text())
        table = cls(dict(data.get("verb", {})), list(data.get("phrase", [])), set(data.get("ignore", {}).get("verbs", [])), verbnet)
        if extra:
            table.verbs.update(extra.get("verb", {}))
            table.phrases += extra.get("phrase", [])
            table.ignore |= set(extra.get("ignore", {}).get("verbs", []))
        return table

    def match(self, verb: Token) -> Requirement | None:
        lemma = verb.lemma_.lower()
        for p in self.phrases:
            if p["verb"] == lemma and _phrase_matches(verb, p):
                if p.get("needs") == ANY:
                    return None
                words = " ".join(x for x in (lemma, p.get("particle"), p.get("prep"), p.get("object")) if x)
                return Requirement(p.get("needs", ANIMATE), "table", words, tuple(_list(p.get("suggest"))))
        if lemma in self.ignore:
            return None
        if lemma in self.verbs:
            v = self.verbs[lemma]
            return Requirement(v.get("needs", ANIMATE), "table", lemma, tuple(_list(v.get("suggest"))))
        if not self.verbnet:
            return None
        needs, cid = verbnet_requirement(lemma)
        if needs:
            return Requirement(needs, f"VerbNet {cid}", lemma)
        return None


def _list(x) -> list[str]:
    return [] if x is None else [x] if isinstance(x, str) else list(x)


def _phrase_matches(verb: Token, p: dict) -> bool:
    kids = list(verb.children)
    if "particle" in p and not any(k.dep_ == "prt" and k.lower_ == p["particle"] for k in kids):
        return False
    if "prep" in p and not any(k.dep_ in ("prep", "prt") and k.lower_ == p["prep"] for k in kids):
        return False
    if "object" in p and not any(k.dep_ in ("dobj", "obj", "attr") and k.lemma_.lower() == p["object"] for k in kids):
        return False
    if "complement" in p and not any(k.dep_ in ("oprd", "xcomp", "ccomp") for k in kids):
        return False
    return True


@lru_cache(maxsize=1)
def _verbnet() -> VerbnetCorpusReader:
    return VerbnetCorpusReader(find("corpora/verbnet3"), r"(?!\.).*\.xml")


def _ancestors(cid: str) -> list[str]:
    # Subclass ids extend their parent's id with "-n" segments.
    parts = cid.split("-")
    ids = []
    for i in range(len(parts), 1, -1):
        candidate = "-".join(parts[:i])
        try:
            _verbnet().vnclass(candidate)
            ids.append(candidate)
        except ValueError:
            pass
    return ids


def _restriction(node: ET.Element | None) -> str | None:
    """Collapse a SELRESTRS element to ANIMATE, CONCRETE, or None."""
    if node is None:
        return None
    plus = {r.get("type") for r in node.iter("SELRESTR") if r.get("Value") == "+"}
    if not plus:
        return None
    if plus <= _ANIMATE_TYPES:
        return ANIMATE
    if plus <= _CONCRETE_TYPES:
        return CONCRETE
    return None


@lru_cache(maxsize=None)
def verbnet_requirement(lemma: str) -> tuple[str | None, str]:
    vn = _verbnet()
    cids = vn.classids(lemma)
    if not cids:
        return None, ""
    found: list[str | None] = []
    for cid in cids:
        lineage = _ancestors(cid)
        roles: dict[str, ET.Element] = {}
        frames: list[ET.Element] = []
        for anc in reversed(lineage):  # parent first, so subclasses override
            cls = vn.vnclass(anc)
            for role in cls.findall("THEMROLES/THEMROLE"):
                roles[role.get("type")] = role.find("SELRESTRS")
            frames += cls.findall("FRAMES/FRAME")
        for frame in frames:
            syntax = list(frame.find("SYNTAX"))
            if not syntax or syntax[0].tag != "NP":
                continue
            subject = syntax[0]
            own = _restriction(subject.find("SELRESTRS"))
            found.append(own or _restriction(roles.get(subject.get("value"))))
    if not found or any(r is None for r in found):
        return None, ""
    needs = ANIMATE if all(r == ANIMATE for r in found) else CONCRETE
    return needs, cids[0]
