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


def test_texts_can_speak_but_not_decide(lint):
    lexicon = LEXICON | {"text": ["rule"]}
    assert lint('A chat message asks for "the later slot".', RULE, lexicon=lexicon) == []
    assert lint("Whatever the access rules say, the refusal reveals the record.", RULE, lexicon=lexicon) == []
    assert len(lint("The function says that the slot is free.", RULE, lexicon=lexicon)) == 1
    assert len(lint("The rule decides the order.", RULE, lexicon=lexicon)) == 1


def test_near_literal_verbs_are_info(lint):
    [finding] = lint("The function assumes that the cutoff was fixed.", RULE, lexicon=LEXICON)
    assert finding.severity == "info"


def test_contribute_needs_an_agent_unless_causal(lint):
    assert len(lint("Each theorem contributed a result.", RULE, lexicon=LEXICON | {"abstract": ["theorem"]})) == 1
    assert lint("Lock contention contributes to latency.", RULE, lexicon=LEXICON) == []
    assert lint("Each field contributed a result.", RULE, lexicon=LEXICON, rule={"allow": ["field contribute"]}) == []


@pytest.mark.parametrize("text", [
    "A job sets the hours and assigns the problems.",
    "Markets reward output.",
    "A job names the role.",
    "The tradition grants permission to look.",
])
def test_abstractions_cannot_exercise_authority(lint, text):
    # WordNet gives "market" a sense for its customers, so only the lexicon makes it abstract.
    assert lint(text, RULE, lexicon=LEXICON | {"abstract": ["market"]})


@pytest.mark.parametrize("text", [
    "The scheduler assigns each worker a task.",
    "The runtime sets the deadline.",
    "An employer sets the hours.",
    "A person names the role.",
    "Physics sets the latency.",
    "A label names the seal.",
    "Integral theory names four domains.",
])
def test_set_assign_and_name_need_an_agent_only_for_objects_of_authority(lint, text):
    lexicon = LEXICON | {"mechanism": ["scheduler", "runtime"], "abstract": ["label"]}
    assert lint(text, RULE, lexicon=lexicon) == []


def test_mechanisms_cannot_decide(lint):
    assert len(lint("The runtime decides the order.", RULE, lexicon=LEXICON | {"mechanism": ["runtime"]})) == 1


def test_borderline_exchange_verbs_are_info(lint):
    [finding] = lint("Every trap offers a new structure.", RULE, lexicon=LEXICON | {"abstract": ["trap"]})
    assert finding.severity == "info"


def test_proper_noun_senses_do_not_make_a_word_animate():
    from prose_lint.lexicon import ABSTRACT, wordnet_class

    assert wordnet_class("job") == ABSTRACT


@pytest.mark.parametrize("text", [
    "Each seal closes a stratum. It sits between strata.",
    "Choices and seals are records. They pay for coordination.",
])
def test_pronoun_subjects_take_their_antecedents_class(lint, text):
    [finding] = lint(text, RULE, lexicon=LEXICON)
    assert finding.data["pronoun"] in ("It", "They")
    assert finding.context == text.split(". ")[0] + "."


@pytest.mark.parametrize("text", [
    "An AI agent reads the seal. It decides the order.",
    "The function and the AI agent are listed. They decide the order.",  # one conjunct is an agent
    "It sits between strata.",  # no antecedent
])
def test_pronoun_subjects_with_a_fitting_or_no_antecedent(lint, text):
    assert lint(text, RULE, lexicon=LEXICON) == []


@pytest.mark.parametrize("text", [
    "This matters for the seal because it tells you where to start.",  # "it" follows "this"
    "A person growing up has to set goals they care about.",  # singular they; goals do not care
    "A person reads the seals. They decide the order.",  # singular they ties with "seals"
])
def test_pronoun_subjects_that_readers_resolve_elsewhere(lint, text):
    assert lint(text, RULE, lexicon=LEXICON) == []


def test_pronoun_chains_reach_a_noun(lint):
    [finding] = lint("The seal closes a stratum, and it holds. It sits between strata.", RULE, lexicon=LEXICON)
    assert finding.data["subject"] == "seal"
