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


def test_relative_clause_arguments_skip_the_modified_noun(lint):
    assert lint("Every record carries the version it was made under.", RULE) == []


@pytest.mark.parametrize("text", [
    # expletive object and comparative
    "The record and the view are stored. Feeling calmer can make it easier to identify the next step.",
    "When a business writes a policy around the software, changing the software becomes harder than it needs to be.",
    # quotation
    "The suite passed and the autonomy grew. “It looked good in a chat” is not a quality gate.",
    # i-within-i through a gerund, and not through a coordination
    "The idea may be old, but the marginal cost of applying it changes.",
    "Jobs to Be Done helps investigate the desired result and the circumstances behind it.",
    # coarguments and control
    "Admitting a desire does not require reorganizing your life around it.",
    "An agent can be capable at generating a plausible action and still be unqualified to execute it.",
    # copula predicate, through a participle
    "The values are choices, and the records are records of values supplied at them.",
    # predicates are not referents
    "Before responding to a limit, identify what kind of limit it is.",
    # "it" does not name a person
    "A junior colleague may have a useful suggestion but expect that raising it will make them seem difficult.",
    # distributive "each" and disjunction
    "Polynomial functors give this composition an algebraic form, in which an interface is a set of positions, each with the set of replies it accepts.",
    "The same physical material or system can perform computations, with observers drawing results from it.",
    # possessives: pronoun subject, object beside it, participle
    "Every engineering field invents a vocabulary faster than it preserves its lineage.",
    "Before selecting a framework, separate the system into its constituent parts.",
    "A tortoise is drawing its limbs into its shell.",
])
def test_grammar_settles_pronouns(lint, text):
    assert lint(text, RULE) == []


def test_project_lexicon_lets_it_name_a_mechanism(lint):
    text = "The dispatcher reads the view and the choice. It records the value."
    assert lint(text, RULE, lexicon={"mechanism": ["dispatcher"]}) == []


def test_relative_clause_blocks_the_copula_condition(lint):
    assert lint("Arrangements are indexes shared by every operator that reads them.", RULE) == []


def test_a_chain_of_pronouns_is_judged_once(lint):
    text = "You must commit to your categories to make decisions and build systems. But you must hold them humbly enough to revise them."
    assert len(lint(text, RULE)) == 1
