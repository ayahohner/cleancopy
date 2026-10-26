import hashlib
import zipfile

import pytest

from cleancopy.nlp import MODEL, MODEL_VERSION, model_path

DATA = f"{MODEL}/{MODEL}-{MODEL_VERSION}/config.cfg"


def wheel(tmp_path):
    path = tmp_path / "model.whl"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(DATA, "[nlp]\n")
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def test_model_is_downloaded_once(tmp_path):
    path, sha256 = wheel(tmp_path)
    found = model_path(tmp_path / "models", path.as_uri(), sha256)
    assert (found / "config.cfg").read_text() == "[nlp]\n"
    path.unlink()
    assert model_path(tmp_path / "models", path.as_uri(), sha256) == found


def test_download_with_the_wrong_hash_is_not_kept(tmp_path):
    path, _ = wheel(tmp_path)
    with pytest.raises(SystemExit, match="expected hash"):
        model_path(tmp_path / "models", path.as_uri(), "0" * 64)
    assert list((tmp_path / "models").iterdir()) == []
