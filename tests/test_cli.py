import json

from cleancopy.cli import cache_dir, main

CONFIG = 'include = ["*.md"]\n[lexicon]\nabstract = ["theorem"]\n[rules.ambiguous-pronouns]\nseverity = "off"\n'


def write(tmp_path, monkeypatch, text):
    (tmp_path / "cleancopy.toml").write_text(CONFIG)
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


def test_folder_means_its_markdown_files(tmp_path, monkeypatch, capsys):
    write(tmp_path, monkeypatch, "A person decides.\n")
    (tmp_path / "docs" / "notes").mkdir(parents=True)
    (tmp_path / "docs" / "notes" / "draft.md").write_text("The theorem draws the line.\n")
    (tmp_path / "docs" / "data.txt").write_text("The theorem draws the line.\n")
    assert main(["--no-cache", "docs"]) == 1
    assert capsys.readouterr().out.startswith("docs/notes/draft.md:1:")


def test_cache_is_reused(tmp_path, monkeypatch, capsys):
    write(tmp_path, monkeypatch, "A person decides.\n")
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    assert main([]) == 0
    assert main([]) == 0
    assert list((tmp_path / "cache" / "cleancopy").glob("*.spacy"))
    assert not (tmp_path / ".cache").exists()


def test_cache_defaults_to_the_home_directory(monkeypatch, tmp_path):
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert cache_dir() == tmp_path / ".cache" / "cleancopy"


def test_no_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    try:
        main([])
    except SystemExit as e:
        assert "no files" in str(e)
