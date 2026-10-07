"""Extract prose from Markdown as segments that keep their source line.

Code spans and inline math are replaced by placeholder words so that the
parser sees a grammatical sentence; each placeholder remembers the text it
replaced, so findings can quote the original.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from markdown_it import MarkdownIt
from mdit_py_plugins.dollarmath import dollarmath_plugin
from mdit_py_plugins.front_matter import front_matter_plugin

# A placeholder must be one token that the parser tags as a proper noun.
PLACEHOLDER = re.compile(r"\bZq[a-z]+\b")


@dataclass
class Segment:
    text: str
    line: int
    # placeholder word -> (kind, original text); kind is "code" or "math"
    placeholders: dict[str, tuple[str, str]] = field(default_factory=dict)
    # rules disabled for this segment by a preceding "<!-- prose-lint-disable rule ... -->"
    disabled: set[str] = field(default_factory=set)

    def restore(self, text: str) -> str:
        return PLACEHOLDER.sub(lambda m: self.placeholders.get(m.group(0), ("", m.group(0)))[1], text)


def _placeholder(n: int) -> str:
    letters = ""
    n += 1
    while n:
        n, r = divmod(n - 1, 26)
        letters = chr(97 + r) + letters
    return "Zq" + letters


# "<!-- prose-lint-disable literal-verbs -->" disables the named rules (or all
# rules, with no names) for the next block: a paragraph, list item, or table.
DISABLE = re.compile(r"<!--\s*prose-lint-disable\b([^>]*?)-->")

_parser = MarkdownIt("commonmark").enable("table").use(front_matter_plugin).use(dollarmath_plugin)


def segments(source: str) -> list[Segment]:
    out: list[Segment] = []
    pending: set[str] | None = None  # rules to disable in the next block
    active: set[str] = set()
    depth = 0
    for token in _parser.parse(source):
        if token.type in ("html_block", "html_inline"):
            m = DISABLE.search(token.content)
            if m:
                pending = set(m.group(1).split()) or {"*"}
            continue
        if token.nesting == 1:
            if depth == 0:
                active, pending = (pending or set()), None
            depth += 1
        elif token.nesting == -1:
            depth -= 1
        if token.type == "front_matter":
            for offset, raw in enumerate(token.content.splitlines()):
                m = re.match(r"(title|description):\s*(.*)", raw)
                if m:
                    value = m.group(2).strip().strip('"').strip("'")
                    out.append(Segment(value, offset + 2))
        elif token.type == "inline" and token.map:
            seg = Segment("", token.map[0] + 1, disabled=set(active))
            parts: list[str] = []
            for child in token.children or []:
                if child.type == "image":
                    continue
                if child.type == "text":
                    parts.append(child.content)
                elif child.type in ("code_inline", "math_inline"):
                    word = _placeholder(len(seg.placeholders))
                    kind = "code" if child.type == "code_inline" else "math"
                    original = f"`{child.content}`" if kind == "code" else f"${child.content}$"
                    seg.placeholders[word] = (kind, original)
                    parts.append(word)
                elif child.type in ("softbreak", "hardbreak"):
                    parts.append(" ")
            seg.text = "".join(parts).strip()
            if seg.text:
                out.append(seg)
    return out
