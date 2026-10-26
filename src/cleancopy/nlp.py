"""Load the parser and WordNet, and cache parses.

The transformer parser takes seconds per post, so each file's parse is cached
under a key made from the model's name and version and the file's segments.
Editing one paragraph re-parses the file; leaving the file unchanged reuses
the cache.

PyPI does not accept a dependency on a URL, and spaCy publishes its models
only as wheels on GitHub, so an installed cleancopy downloads the model into
the user cache on first use. A development install has it as a package.
"""

from __future__ import annotations

import hashlib
import os
import sys
import tempfile
import urllib.request
import zipfile
from functools import lru_cache
from pathlib import Path

import nltk
import spacy
from spacy.language import Language
from spacy.tokens import Doc, DocBin

MODEL = "en_core_web_trf"
MODEL_VERSION = "3.8.0"
MODEL_URL = (
    "https://github.com/explosion/spacy-models/releases/download/"
    f"{MODEL}-{MODEL_VERSION}/{MODEL}-{MODEL_VERSION}-py3-none-any.whl"
)
MODEL_SHA256 = "272a31e9d8530d1e075351d30a462d7e80e31da23574f1b274e200f3fff35bf5"


def cache_dir() -> Path:
    """$XDG_CACHE_HOME/cleancopy, or ~/.cache/cleancopy. Parses are keyed by
    content, so every project can share one cache."""
    return Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "cleancopy"


def ensure_wordnet() -> None:
    try:
        nltk.data.find("corpora/wordnet")
    except LookupError:
        nltk.download("wordnet", quiet=True)


@lru_cache(maxsize=1)
def pipeline() -> Language:
    try:
        return spacy.load(MODEL)
    except OSError:  # not installed as a package
        return spacy.load(model_path(cache_dir() / "models"))


def model_path(root: Path, url: str = MODEL_URL, sha256: str = MODEL_SHA256) -> Path:
    """The model's data folder under ``root``, downloaded and unpacked on first use."""
    unpacked = root / f"{MODEL}-{MODEL_VERSION}"
    if not unpacked.exists():
        print(f"cleancopy: downloading {MODEL} {MODEL_VERSION} (about 450 MB) once", file=sys.stderr)
        _unpack(url, sha256, unpacked)
    return unpacked / MODEL / f"{MODEL}-{MODEL_VERSION}"


def _unpack(url: str, sha256: str, dest: Path) -> None:
    """Download the wheel, check its hash, and move the unpacked files into place
    only when complete, so an interrupted download is never used."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=dest.parent) as tmp:
        wheel = Path(tmp) / "model.whl"
        digest = hashlib.sha256()
        with urllib.request.urlopen(url) as response, wheel.open("wb") as out:
            while chunk := response.read(1 << 20):
                digest.update(chunk)
                out.write(chunk)
        if digest.hexdigest() != sha256:
            sys.exit(f"cleancopy: the download of {url} does not match its expected hash")
        with zipfile.ZipFile(wheel) as z:
            z.extractall(Path(tmp) / "unpacked")
        (Path(tmp) / "unpacked").rename(dest)


def _key(meta: dict, texts: list[str]) -> str:
    h = hashlib.sha256(f"{meta['name']}-{meta['version']}-{spacy.__version__}".encode())
    for t in texts:
        h.update(b"\0" + t.encode())
    return h.hexdigest()[:32]


def parse(texts: list[str], cache_dir: Path | None) -> list[Doc]:
    nlp = pipeline()
    path = cache_dir / f"{_key(nlp.meta, texts)}.spacy" if cache_dir else None
    if path and path.exists():
        return list(DocBin().from_disk(path).get_docs(nlp.vocab))
    docs = list(nlp.pipe(texts, batch_size=32))
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        DocBin(store_user_data=False, docs=docs).to_disk(path)
    return docs
