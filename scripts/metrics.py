"""Code-quality gate: per-function CRAP and per-file Maintainability Index,
with the formulas of Inner Graph's scripts/metrics.ts.

    CRAP(f)  = CC(f)^2 * (1 - coverage(f))^3 + CC(f)
    MI(file) = 171 - 5.2 ln(V) - 0.23 CC - 16.2 ln(SLOC), over the file's
               per-function averages (the escomplex convention)

Fails when any function's CRAP exceeds 8 or any file's MI is 75 or below.

    uv run pytest --cov=prose_lint --cov-report=json:.coverage.json
    uv run python scripts/metrics.py .coverage.json
"""

from __future__ import annotations

import ast
import io
import json
import keyword
import math
import sys
import textwrap
import tokenize
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "src" / "prose_lint"
CRAP_LIMIT = 8
MI_LIMIT = 75

_DECISIONS = (ast.If, ast.IfExp, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler, ast.match_case, ast.comprehension)
_FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef)
_OPERANDS = {tokenize.NAME, tokenize.NUMBER, tokenize.STRING}
_SKIPPED = {tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT, tokenize.ENDMARKER}


@dataclass
class Function:
    file: str
    name: str
    line: int
    cc: int
    sloc: int
    volume: float
    coverage: float

    @property
    def crap(self) -> float:
        return self.cc**2 * (1 - self.coverage) ** 3 + self.cc


def cyclomatic(fn: ast.AST) -> int:
    """McCabe complexity, not descending into nested functions."""
    count, stack = 1, list(ast.iter_child_nodes(fn))
    while stack:
        node = stack.pop()
        if isinstance(node, _FUNCTIONS):
            continue
        count += isinstance(node, _DECISIONS) + len(getattr(node, "ifs", ())) + (len(node.values) - 1 if isinstance(node, ast.BoolOp) else 0)
        stack.extend(ast.iter_child_nodes(node))
    return count


def halstead_volume(text: str) -> float:
    operators: dict[str, int] = {}
    operands: dict[str, int] = {}
    for tok in tokenize.generate_tokens(io.StringIO(text).readline):
        if tok.type in _SKIPPED:
            continue
        operand = tok.type in _OPERANDS and not keyword.iskeyword(tok.string)
        bucket = operands if operand else operators
        bucket[tok.string] = bucket.get(tok.string, 0) + 1
    total = sum(operators.values()) + sum(operands.values())
    return total * math.log2(max(len(operators) + len(operands), 2))


def code_lines(fn: ast.FunctionDef, lines: list[str]) -> set[int]:
    """Line numbers of the function, without blanks, comments, or the docstring."""
    doc = fn.body[0] if isinstance(fn.body[0], ast.Expr) and isinstance(fn.body[0].value, ast.Constant) else None
    skip = set(range(doc.lineno, doc.end_lineno + 1)) if doc else set()
    span = range(fn.lineno, fn.end_lineno + 1)
    return {n for n in span if n not in skip and lines[n - 1].strip() and not lines[n - 1].strip().startswith("#")}


def maintainability(volume: float, cc: float, sloc: float) -> float:
    return 171 - 5.2 * math.log(max(volume, 1)) - 0.23 * cc - 16.2 * math.log(max(sloc, 1))


def analyse(path: Path, covered: dict) -> list[Function]:
    text = path.read_text()
    lines = text.splitlines()
    executed, missing = set(covered.get("executed_lines", [])), set(covered.get("missing_lines", []))
    out = []
    for fn in (n for n in ast.walk(ast.parse(text)) if isinstance(n, _FUNCTIONS)):
        body = "\n".join(lines[fn.lineno - 1 : fn.end_lineno])
        statements = code_lines(fn, lines) & (executed | missing)
        coverage = len(statements & executed) / len(statements) if statements else 1.0
        out.append(Function(str(path.relative_to(ROOT)), fn.name, fn.lineno, cyclomatic(fn), len(code_lines(fn, lines)), halstead_volume(textwrap.dedent(body)), coverage))
    return out


def file_mi(fns: list[Function]) -> float | None:
    if not fns:
        return None
    return maintainability(*(sum(getattr(f, k) for f in fns) / len(fns) for k in ("volume", "cc", "sloc")))


def main(coverage_json: str) -> int:
    files = json.loads(Path(coverage_json).read_text())["files"]
    by_file = {p: analyse(p, _coverage_for(files, p)) for p in sorted(SOURCE.rglob("*.py"))}
    functions = [f for fns in by_file.values() for f in fns]
    mis = {str(p.relative_to(ROOT)): file_mi(fns) for p, fns in by_file.items()}
    for f in sorted(functions, key=lambda f: -f.crap)[:10]:
        print(f"CRAP {f.crap:5.2f}  cc {f.cc:2}  cov {f.coverage:4.2f}  {f.file}:{f.line} {f.name}")
    for name, mi in sorted(((n, m) for n, m in mis.items() if m is not None), key=lambda x: x[1]):
        print(f"MI {mi:6.1f}  {name}")
    bad_crap = [f for f in functions if f.crap > CRAP_LIMIT]
    bad_mi = [n for n, m in mis.items() if m is not None and m <= MI_LIMIT]
    ok = not bad_crap and not bad_mi
    print(f"{'PASS' if ok else 'FAIL'}: every function CRAP <= {CRAP_LIMIT} ({len(bad_crap)} over), every file MI > {MI_LIMIT} ({len(bad_mi)} at or under)")
    return 0 if ok else 1


def _coverage_for(files: dict, path: Path) -> dict:
    return next((v for k, v in files.items() if path.as_posix().endswith(k.replace("\\", "/"))), {})


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else ".coverage.json"))
