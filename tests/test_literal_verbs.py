import pytest

RULE = "literal-verbs"
LEXICON = {"abstract": ["function", "choice", "sequencer", "compiler", "seal"], "agent": ["AI agent"]}


@pytest.mark.parametrize("text", [
    "The CALM theorem draws the same line for queries.",
    "A deterministic function tolerates different delays.",
    "A choice pays for two-phase commit.",
    "The seals sit between strata.",
    "What existing languages give up is a guarantee.",
    "Every interactive program faces the same problem.",
    "A function that decides the order is a sequencer.",
    "The order is decided by a function.",
])
def test_flags_figurative_verbs(lint, text):
    assert len(lint(text, RULE, lexicon=LEXICON)) == 1


@pytest.mark.parametrize("text", [
    "An AI agent can tolerate different delays.",
    "A person decides which slot to book.",
    "The compiler rejects the program.",
    "In a loop, `c` stands for an address.",
    "The function determines the order.",
    "The order is decided.",
])
def test_allows_literal_verbs(lint, text):
    assert lint(text, RULE, lexicon=LEXICON) == []


def test_allow_entry(lint):
    text = "The sequencer refuses the record."
    assert len(lint(text, RULE, lexicon=LEXICON | {"abstract": ["sequencer"]})) == 0  # "refuse" is not in the table
    rule = {"allow": ["sequencer decide"]}
    assert lint("The sequencer decides the order.", RULE, lexicon=LEXICON, rule=rule) == []
    assert len(lint("The function decides the order.", RULE, lexicon=LEXICON, rule=rule)) == 1


def test_disable_comment(lint):
    text = "<!-- prose-lint-disable literal-verbs -->\nThe theorem draws the line.\n\nThe theorem draws the line.\n"
    found = lint(text, RULE, lexicon=LEXICON)
    assert [f.line for f in found] == [4]


@pytest.mark.parametrize("text", [
    "A function deciding the order is a sequencer.",
    "The runtime records the value, deciding the order.",
    "If the hold is refused, the record rests on a record that rollback recovery calls an orphan.",
])
def test_finds_subjects_through_participles_and_complements(lint, text):
    lexicon = LEXICON | {"abstract": [*LEXICON["abstract"], "runtime", "rollback recovery"]}
    assert len(lint(text, RULE, lexicon=lexicon)) == 1
