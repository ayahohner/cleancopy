import pytest

RULE = "phrasal-verbs"


@pytest.mark.parametrize("text, phrase", [
    ("The scandal drew attention from the budget.", "draw from"),
    ("The essay takes away from the argument.", "take away from"),
    ("The result turns on the order.", "turn on"),
    ("They passed on the offer.", "pass on"),
    ("The claim stands up to scrutiny.", "stand up to"),
])
def test_flags_ambiguous_phrasal_verbs(lint, text, phrase):
    [finding] = lint(text, RULE)
    assert finding.data["phrase"] == phrase


@pytest.mark.parametrize("text", [
    "The scandal drew attention away from the budget.",
    "The scandal drew attention to the budget.",
    "The switch turns on the light.",
    "Readers take away a lesson from the essay.",
])
def test_allows_settled_readings(lint, text):
    assert lint(text, RULE) == []


def test_message_names_each_reading(lint):
    [finding] = lint("The scandal drew attention from the budget.", RULE)
    assert finding.data["readings"] == ["draw attention away from", "attract attention from"]
    assert finding.severity == "warning"


def test_broad_phrases_are_info(lint):
    [finding] = lint("Records make up the log.", RULE)
    assert finding.severity == "info"


def test_allow_entry(lint):
    assert lint("Records make up the log.", RULE, rule={"allow": ["make up"]}) == []


def test_project_entries_extend_the_table():
    from cleancopy.config import Config
    from cleancopy.linter import Linter

    entry = {"verb": "roll", "particle": "back", "readings": ["undo", "reduce"]}
    cfg = Config(phrasal=[entry])
    assert Linter(cfg, only={RULE}).lint("The team rolled back the price.", "test.md")


def test_a_preposition_before_the_verb_does_not_complete_it(lint):
    assert lint("From the start, the scandal drew attention.", RULE) == []
