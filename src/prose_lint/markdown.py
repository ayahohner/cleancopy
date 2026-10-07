"""Extract prose from Markdown as segments that keep their source line.

Code spans and inline math are replaced by placeholder words so that the
parser sees a grammatical sentence; each placeholder remembers the text it
replaced, so findings can quote the original.

``<!-- prose-lint-disable literal-verbs -->`` disables the named rules, or
all rules when none is named, for the next block: a paragraph, list, or table.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from markdown_it import MarkdownIt
from markdown_it.token import Token
from mdit_py_plugins.dollarmath import dollarmath_plugin
from mdit_py_plugins.front_matter import front_matter_plugin

# A placeholder must be one token that the parser tags as a proper noun.
PLACEHOLDER = re.compile(r"\bZq[a-z]+\b")
DISABLE = re.compile(r"<!--\s*prose-lint-disable\b([^>]*?)-->")
_FIELD = re.compile(r"(?:title|description):\s*(.*)")
_INLINE_CODE = {"code_inline": "`{}`", "math_inline": "${}$"}

_parser = MarkdownIt("commonmark").enable("table").use(front_matter_plugin).use(dollarmath_plugin)


@dataclass
class Segment:
    text: str
    line: int
    placeholders: dict[str, str] = field(default_factory=dict)  # placeholder -> original text
    disabled: set[str] = field(default_factory=set)

    def restore(self, text: str) -> str:
        return PLACEHOLDER.sub(lambda m: self.placeholders.get(m.group(0), m.group(0)), text)

    def enables(self, rule: str) -> bool:
        return not self.disabled & {"*", rule}


class _Disabled:
    """Rules named by a disable comment, applied to the next top-level block."""

    def __init__(self) -> None:
        self.pending: set[str] = set()
        self.active: set[str] = set()
        self.depth = 0

    def note(self, html: str) -> None:
        m = DISABLE.search(html)
        if m:
            self.pending = set(m.group(1).split()) or {"*"}

    def enter(self, token: Token) -> None:
        if token.nesting == 1 and self.depth == 0:
            self.active, self.pending = self.pending, set()
        self.depth += token.nesting


def segments(source: str) -> list[Segment]:
    out: list[Segment] = []
    disabled = _Disabled()
    for token in _parser.parse(source):
        if token.type == "front_matter":
            out += _front_matter(token.content)
        elif token.type == "html_block":
            disabled.note(token.content)
        else:
            disabled.enter(token)
            out += _inline(token, disabled.active)
    return out


def _front_matter(content: str) -> list[Segment]:
    # Line 1 is the opening "---".
    matches = ((i + 2, _FIELD.match(raw)) for i, raw in enumerate(content.splitlines()))
    return [Segment(m.group(1).strip().strip("\"'"), line) for line, m in matches if m]


def _inline(token: Token, disabled: set[str]) -> list[Segment]:
    if token.type != "inline" or not token.map:
        return []
    seg = Segment("", token.map[0] + 1, disabled=set(disabled))
    seg.text = "".join(_text(child, seg) for child in token.children or []).strip()
    return [seg] if seg.text else []


def _text(child: Token, seg: Segment) -> str:
    if child.type == "text":
        return child.content
    if child.type in ("softbreak", "hardbreak"):
        return " "
    if child.type in _INLINE_CODE:
        word = _placeholder(len(seg.placeholders))
        seg.placeholders[word] = _INLINE_CODE[child.type].format(child.content)
        return word
    return ""  # images and link markup


def _placeholder(n: int) -> str:
    """Zqa, Zqb, ..., Zqz, Zqaa, ..."""
    letters = ""
    n += 1
    while n:
        n, r = divmod(n - 1, 26)
        letters = chr(97 + r) + letters
    return "Zq" + letters
