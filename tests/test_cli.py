import json

from prose_lint.cli import main

CONFIG = 'include = ["*.md"]\n[lexicon]\nabstract = ["theorem"]\n[rules.ambiguous-pronouns]\nseverity = "off"\n'


def write(tmp_path, monkeypatch, text):
    (tmp_path / "prose-lint.toml").write_text(CONFIG)
    (tmp_path / "post.md").write_text(text)
    monkeypatch.chdir(tmp_path)


def test_text_report_and_exit_status(tmp_path, monkeypatch, capsys):
    write(tmp_path, monkeypatch, "The theorem draws the line.\n")
    assert main([]) == 1
    out, err = capsys.readouterr()
    assert out.startswith("post.md:1: warning [literal-verbs]")
    assert "1 findings" in err


def test_json_report_and_fail_on(tmp_path, monkeypatch, capsys):
    write(tmp_path, monkeypatch, "The theorem draws the line.\n")
    assert main(["--format", "json", "--fail-on", "error", "--no-cache", "post.md"]) == 0
    [finding] = json.loads(capsys.readouterr().out)
    assert finding["data"]["phrase"] == "draw line"


def test_cache_is_reused(tmp_path, monkeypatch, capsys):
    write(tmp_path, monkeypatch, "A person decides.\n")
    assert main([]) == 0
    assert main([]) == 0
    assert list((tmp_path / ".cache" / "prose-lint").glob("*.spacy"))


def test_no_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    try:
        main([])
    except SystemExit as e:
        assert "no files" in str(e)
