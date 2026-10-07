"""literal-verbs: a verb's subject must be the kind of thing the verb's
literal sense takes.

Flags "the theorem draws the line", "a function tolerates delays", and "a
choice pays for two-phase commit", and allows "an AI agent tolerates delays".
Senses that a field has made into technical terms, such as "a compiler
rejects", are silenced with allow entries of the form "subject verb", where
the subject may be a lexicon key, "@class", or "*".
"""

from __future__ import annotations

from spacy.tokens import Doc

from ..findings import Finding
from ..grammar import subject_of
from ..lexicon import ABSTRACT, PHYSICAL, Lexicon
from ..markdown import Segment
from ..verbs import ANIMATE, CONCRETE, VerbTable

NAME = "literal-verbs"

_LABEL = {ANIMATE: "a person, an organization, or an AI agent", CONCRETE: "a physical object or an agent"}
_FAILS = {ANIMATE: {ABSTRACT, PHYSICAL}, CONCRETE: {ABSTRACT}}


def _allowed(allow: list[tuple[str, str]], subject_key: str, subject_cls: str, phrase: str) -> bool:
    for subj, verb in allow:
        if verb not in (phrase, phrase.split()[0], "*"):
            continue
        if subj in ("*", subject_key, f"@{subject_cls}") or subject_key.endswith(" " + subj):
            return True
    return False


def check(doc: Doc, seg: Segment, path: str, lexicon: Lexicon, verbs: VerbTable, allow: list[tuple[str, str]], severity: str) -> list[Finding]:
    out = []
    for sent in doc.sents:
        for tok in sent:
            if tok.pos_ != "VERB":
                continue
            # A bare past participle is adjectival: "made known".
            if tok.tag_ == "VBN" and not any(k.dep_ in ("aux", "auxpass", "agent") for k in tok.children):
                continue
            req = verbs.match(tok)
            if not req:
                continue
            head = subject_of(tok)
            if head is None:
                continue
            subj = lexicon.classify(head, seg.placeholders)
            if subj.cls not in _FAILS[req.needs]:
                continue
            if _allowed(allow, subj.key, subj.cls, req.phrase):
                continue
            message = f'"{req.phrase}" takes {_LABEL[req.needs]} as its subject, but "{subj.text}" is {"an abstraction" if subj.cls == ABSTRACT else "a physical object"}'
            if req.suggest:
                message += f"; literal options: {', '.join(req.suggest)}"
            out.append(Finding(
                path=path,
                line=seg.line,
                rule=NAME,
                severity="info" if req.source.startswith("VerbNet") else severity,
                message=message,
                excerpt=seg.restore(sent.text),
                data={"verb": tok.text, "phrase": req.phrase, "subject": subj.text, "subject_class": subj.cls,
                      "class_source": subj.source, "requirement": req.needs, "requirement_source": req.source},
            ))
    return out
