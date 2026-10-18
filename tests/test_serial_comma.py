import pytest

RULE = "serial-comma"


@pytest.mark.parametrize("text", [
    "The table holds records, functions and choices.",
    "Attend a class, a retreat or a festival.",
    "A version carries its `id`, `snapshot`, `version` and `time`.",
])
def test_flags_lists_without_a_serial_comma(lint, text):
    [finding] = lint(text, RULE)
    assert finding.word in ("and", "or")


@pytest.mark.parametrize("text", [
    "The table holds records, functions, and choices.",
    "Meanwhile, universities slowed down and grew more expensive.",
    "They are wrong, and some of them decline and die believing that they are worthless.",
    "Families, biological or chosen, meet needs that no club can meet.",
    "Forbid “do not send,” “do not delete,” or “ask before spending.”",
    "Records and functions are values.",
])
def test_allows_serial_commas_pairs_and_nested_coordinations(lint, text):
    assert lint(text, RULE) == []


def test_allow_entry_skips_the_sentence(lint):
    text = "Bernard Suits wrote The Grasshopper: Games, Life and Utopia."
    assert lint(text, RULE)
    assert lint(text, RULE, rule={"allow": ["Games, Life and Utopia"]}) == []
