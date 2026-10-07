import pytest

from prose_lint import config
from prose_lint.cli import lint_text
from prose_lint.nlp import ensure_nltk_data

ensure_nltk_data()


@pytest.fixture
def lint():
    def run(text: str, name: str, **cfg):
        c = config.Config(root=None, lexicon=cfg.get("lexicon", {}), rules={name: cfg.get("rule", {})})
        return [f for f in lint_text(text, "test.md", c, cache_dir=None, only={name})]
    return run
