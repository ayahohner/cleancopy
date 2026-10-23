# prose-lint

A linter for Markdown prose. It parses each sentence with spaCy's transformer
model and checks four rules:

- **literal-verbs**: a verb's subject must be the kind of thing the verb's
  literal sense takes. "The theorem draws the line" and "a function tolerates
  delays" are flagged; "an AI agent tolerates delays" is not. A pronoun
  subject takes the class of the noun it clearly refers to.
- **ambiguous-pronouns**: "it", "its", "they", "them", and "their" are flagged
  when their two most likely antecedents score nearly the same salience.
- **serial-comma**: a list of three or more items needs a comma before its
  last "and" or "or".
- **phrasal-verbs**: a phrasal verb with two live readings, such as "drew
  attention from the budget" (diverted from it, or attracted from it), is
  flagged with each reading as a rewrite.

## Install

prose-lint needs Python 3.12 and [uv](https://docs.astral.sh/uv/). Run it
without installing:

```sh
uvx --from git+https://github.com/ayahohner/prose-lint@v0.2.0 prose-lint posts/*.md
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
interface = ["presentation"]    # can move and show; see src/prose_lint/data/lexicon.toml
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

[verbs]                         # added to the built-in table in src/prose_lint/data/verbs.toml
verb.offer = { suggest = ["provide"] }

[[phrasal]]                     # added to the built-in table in src/prose_lint/data/phrasal.toml
verb = "roll"
particle = "back"
readings = ["undo", "reduce"]
```

`<!-- prose-lint-disable literal-verbs -->` disables the named rules, or every
rule when none is named, for the next paragraph, list, or table.

Parses are cached in `.cache/prose-lint` next to the config file.

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
