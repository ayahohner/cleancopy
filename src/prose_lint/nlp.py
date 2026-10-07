"""Load the parser and NLTK data, and cache parses.

The transformer parser takes seconds per post, so each file's parse is cached
under a key made from the model's name and version and the file's segments.
Editing one paragraph re-parses the file; leaving the file unchanged reuses
the cache.
"""

from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path

import nltk
import spacy
from spacy.language import Language
from spacy.tokens import Doc, DocBin

MODEL = "en_core_web_trf"
_NLTK = {"corpora/wordnet": "wordnet", "corpora/omw-1.4": "omw-1.4", "corpora/verbnet3": "verbnet3"}


def ensure_nltk_data() -> None:
    for path, package in _NLTK.items():
        try:
            nltk.data.find(path)
        except LookupError:
            nltk.download(package, quiet=True)


@lru_cache(maxsize=1)
def pipeline() -> Language:
    return spacy.load(MODEL)


def _key(nlp_meta: dict, texts: list[str]) -> str:
    h = hashlib.sha256()
    h.update(f"{nlp_meta['name']}-{nlp_meta['version']}-{spacy.__version__}".encode())
    for t in texts:
        h.update(b"\0" + t.encode())
    return h.hexdigest()[:32]


def parse(texts: list[str], cache_dir: Path | None) -> list[Doc]:
    nlp = pipeline()
    path = None
    if cache_dir is not None:
        path = cache_dir / f"{_key(nlp.meta, texts)}.spacy"
        if path.exists():
            return list(DocBin().from_disk(path).get_docs(nlp.vocab))
    docs = list(nlp.pipe(texts, batch_size=32))
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        DocBin(store_user_data=False, docs=docs).to_disk(path)
    return docs
