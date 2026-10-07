import pytest

RULE = "ambiguous-pronouns"


@pytest.mark.parametrize("text", [
    "Specify each choice without naming its resolver, and set separately which resolvers may supply it.",
    "A rule is a function over the binding table, and a table that violates it is refused before it takes effect.",
])
def test_flags_tied_candidates(lint, text):
    assert lint(text, RULE)


@pytest.mark.parametrize("text", [
    "It is possible to seal the scope early.",
    "A scope declaration may add coordination but not remove it.",
    "A warehouse can promise its own stock.",
    "Analytics evaluates goals and their inputs over the records.",
    "Bookings, registrations, and transfers are order-coupled: they wait for a sequencer.",
    "The sequencer admits each record into the scope or refuses it.",
    "A function reads the records. It returns a view.",
])
def test_allows_clear_pronouns(lint, text):
    assert lint(text, RULE) == []


def test_expletive_with_clause(lint):
    assert lint("The record and the view exist. It seems that the scope is sealed.", RULE) == []


def test_existential_candidate_scores(lint):
    found = lint("There is a record in the scope, and a view reads it.", RULE)
    assert all(f.data["pronoun"] == "it" for f in found)


def test_finding_carries_previous_sentence(lint):
    text = "The rule constrains the table. A table that violates it is refused before it takes effect."
    found = lint(text, RULE)
    assert found and all(f.context == "The rule constrains the table." for f in found)
