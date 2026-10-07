import pytest

from prose_lint.config import Config
from prose_lint.linter import Linter
from prose_lint.nlp import ensure_wordnet

ensure_wordnet()


@pytest.fixture
def lint():
    def run(text: str, name: str, **cfg):
        c = Config(lexicon=cfg.get("lexicon", {}), rules={name: cfg.get("rule", {})})
        return Linter(c, only={name}).lint(text, "test.md")

    return run
