# prose-lint

A linter for Markdown prose. It parses each sentence with spaCy's transformer
model and checks five rules:

- **literal-verbs**: a verb's subject must be the kind of thing the verb's
  literal sense takes. "The theorem draws the line" and "a function tolerates
  delays" are flagged; "an AI agent tolerates delays" is not. A pronoun
  subject takes the class of the noun it clearly refers to.
- **ambiguous-pronouns**: "it", "its", "they", "them", and "their" are flagged
  when their two most likely antecedents score nearly the same salience.
  Grammar rules out nouns first: "it" never names a person, "the cost of
  applying it" is not the cost, "make it easier to" refers to nothing, and a
  chain of pronouns is judged once.
- **serial-comma**: a list of three or more items needs a comma before its
  last "and" or "or".
- **phrasal-verbs**: a phrasal verb with two live readings, such as "drew
  attention from the budget" (diverted from it, or attracted from it), is
  flagged with each reading as a rewrite.
- **constructions**: banned sentence constructions, matched in the parse
  rather than the words. Built in: contrast by negation ("It's a protocol,
  not a library", "not X but Y", "It isn't X. It's Y.") and "Knowing X tells
  you Y". A project adds its own as spaCy
  [DependencyMatcher](https://spacy.io/api/dependencymatcher) patterns.

## Install

prose-lint needs Python 3.12 and [uv](https://docs.astral.sh/uv/). Run it
without installing:

```sh
uvx --from git+https://github.com/ayahohner/prose-lint@v0.3.0 prose-lint posts/*.md
```

The first run downloads the spaCy model (about 450 MB) and WordNet.

## Configure

prose-lint reads the nearest `prose-lint.toml`, searching upward from the
working directory. With no paths on the command line, it lints the files that
`include` matches.

```toml
include = ["src/content/posts/*.md"]

[lexicon]                       # what kind of thing each noun names
agent = ["AI agent", "model"]
physical = ["server", "phone"]
display = ["presentation"]      # can move and show; see src/prose_lint/data/lexicon.toml
evidence = ["benchmark"]        # can show, suggest, or confirm that
idea = ["plan"]                 # can guide and assume
institution = ["market"]        # can require and permit, not want or buy
mechanism = ["compiler", "runtime"]  # performs operations, cannot decide
abstract = ["record", "theorem"]
text = ["rule", "message"]      # can ask or say, not decide
mixed = ["resolver"]            # never flagged

[rules.literal-verbs]
severity = "warning"            # "info", "warning", "error", or "off"
allow = ["compiler reject"]     # "subject verb"; subject may be "@class" or "*"

[rules.ambiguous-pronouns]
ratio = 0.95                    # flag when the runner-up has this share of the leader's salience

[rules.serial-comma]
allow = ["Games, Life and Utopia"]  # skips any sentence containing the phrase

[rules.phrasal-verbs]
allow = ["make up"]             # "verb particle prep"

[rules.constructions]
allow = ["comma-not"]           # built-ins to permit: comma-not, not-but, not-then-is, gerund-tells-you

[[construction]]                # a DependencyMatcher pattern to ban; the first node is the flagged word
name = "at-the-end-of-the-day"
message = "say what finally matters"
pattern = [
  { RIGHT_ID = "end", RIGHT_ATTRS = { LOWER = "end" } },
  { LEFT_ID = "end", REL_OP = ">", RIGHT_ID = "of", RIGHT_ATTRS = { LOWER = "of" } },
  { LEFT_ID = "of", REL_OP = ">", RIGHT_ID = "day", RIGHT_ATTRS = { LOWER = "day" } },
]

[verbs]                         # added to the built-in table in src/prose_lint/data/verbs.toml
verb.offer = { suggest = ["provide"] }

[[phrasal]]                     # added to the built-in table in src/prose_lint/data/phrasal.toml
verb = "roll"
particle = "back"
readings = ["undo", "reduce"]
```

`<!-- prose-lint-disable literal-verbs -->` disables the named rules, or every
rule when none is named, for the next paragraph, list, or table.

Parses are cached in `$XDG_CACHE_HOME/prose-lint`, or `~/.cache/prose-lint`
when `XDG_CACHE_HOME` is unset, never in the project. The cache is keyed by
the model and the text, so projects share it; delete the folder to clear it.

## Options

```text
prose-lint [paths...] [--config PATH] [--rule NAME]... [--format text|json]
           [--fail-on info|warning|error] [--no-cache]
```

## Develop

```sh
uv run pytest
uv run pytest --cov=prose_lint --cov-report=json:.coverage.json
uv run python scripts/metrics.py .coverage.json
```

The metrics script fails when any function's CRAP score exceeds 8 or any
file's maintainability index is 75 or below.
