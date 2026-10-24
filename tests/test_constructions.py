import pytest

from cleancopy.config import Config
from cleancopy.linter import Linter

RULE = "constructions"


@pytest.mark.parametrize(("text", "name"), [
    ("It's a protocol, not a library.", "comma-not"),
    ("The point is coordination, not control.", "comma-not"),
    ("The function returns a list, not a set.", "comma-not"),
    ("He chose to wait, not because he was tired but because he was unsure.", "comma-not"),
    ("It is not a library but a protocol.", "not-but"),
    ("The rule does not decide but records.", "not-but"),
    ("It isn't a library; it's a protocol.", "not-then-is"),
    ("This isn't about speed. It's about trust.", "not-then-is"),
    ("This doesn't mean the world is unreal. It means the world is not fundamental.", "not-then-is"),
    ("Knowing the order tells you where to start.", "gerund-tells-you"),
    ("Seeing the trace gives you the cause.", "gerund-tells-you"),
])
def test_banned_constructions(lint, text, name):
    assert [f.data["construction"] for f in lint(text, RULE)] == [name]


@pytest.mark.parametrize("text", [
    "Not only is it fast, but it is also cheap.",
    "It is not only fast but also cheap.",
    "We did not stop, but we slowed down.",
    "It does not decide, and it never will.",
    "He waited, not knowing why.",
    "The order tells you where to start.",
    "The rule does not decide. The team reads it later.",
    "Price is not value. It tracks scarcity.",
])
def test_plain_negation_and_concession_pass(lint, text):
    assert lint(text, RULE) == []


def test_allow_silences_a_construction(lint):
    assert lint("It's a protocol, not a library.", RULE, rule={"allow": ["comma-not"]}) == []


def test_projects_ban_their_own_constructions():
    pattern = [
        {"RIGHT_ID": "end", "RIGHT_ATTRS": {"LOWER": "end"}},
        {"LEFT_ID": "end", "REL_OP": ">", "RIGHT_ID": "of", "RIGHT_ATTRS": {"LOWER": "of"}},
        {"LEFT_ID": "of", "REL_OP": ">", "RIGHT_ID": "day", "RIGHT_ATTRS": {"LOWER": "day"}},
    ]
    entry = {"name": "end-of-the-day", "message": "say what finally matters", "pattern": pattern}
    linter = Linter(Config(constructions=[entry]), only=[RULE])
    [finding] = linter.lint("At the end of the day, the team ships.\n", "x.md")
    assert (finding.word, finding.message) == ("end", "say what finally matters")
