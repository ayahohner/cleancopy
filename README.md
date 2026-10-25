# cleancopy

Deterministic checks for English prose, aimed at the habits of
LLM-written text.

cleancopy parses every sentence of a Markdown file into a dependency tree
(which word modifies which) and checks the tree against rules, the way a code
linter checks a syntax tree. The same text always gets the same findings, and
each finding names the rule, the words, and a rewrite.

```console
$ cleancopy post.md
post.md:3: warning [literal-verbs] "draw line" takes a person, an organization, or an AI agent as its subject, but "theorem" is a text; literal options: separate, state the boundary between
    The theorem draws the line between safe and unsafe writes.
post.md:5: warning [ambiguous-pronouns] "it" could refer to 'rule' or 'team'; name the noun
    When the team got the rule, it was late.
post.md:7: warning [constructions] "X, not Y" is a contrast by negation: say what it is, and give a live misreading its own sentence with the reason
    It's a protocol, not a library.
post.md:9: warning [serial-comma] add a comma before "and", which ends a list of 3 items
    We support records, functions and choices.
post.md:11: warning [phrasal-verbs] "draw attention from" reads as 'draw attention away from' or 'attract attention from'; write the one you mean
    The scandal drew attention from the budget.
```

## Why

<!-- cleancopy-disable constructions -->
Language models write fluent prose with recurring tells: figurative verbs
given to things that cannot act, pronouns with two plausible antecedents, and
stock constructions such as "It's not X, it's Y". Each new model produces
fewer of them, and the ones that remain are harder to spot by eye. cleancopy
finds them mechanically, so a writer, an editor, or an agent revising a draft
can fix them before review, and you decide how your text reads.

## Rules

<!-- cleancopy-disable -->
| Rule | Flags | Passes |
|---|---|---|
| `literal-verbs` | "The theorem draws the line", "A function tolerates delays", "Money buys access" | "An AI agent tolerates delays", "The study suggests that", "The server confirms the move" |
| `ambiguous-pronouns` | "When the team got the rule, it was late." | "When the team got the rule, it decided to wait." (a rule cannot decide) |
| `serial-comma` | "records, functions and choices" | "records, functions, and choices" |
| `phrasal-verbs` | "drew attention from the budget" (away from it, or attracted from it?) | "drew attention away from the budget" |
| `constructions` | "It's a protocol, not a library", "This isn't about speed. It's about trust.", "Knowing the order tells you where to start" | "It is not only fast but also cheap." |

**literal-verbs.** Each verb's literal sense takes a kind of subject: people,
organizations, and AI agents decide, want, and buy; evidence shows and
suggests; a text says and asks; an institution such as a market or a custom
requires and permits. Nouns are classed by the project lexicon, then the
built-in one, then [WordNet](https://wordnet.princeton.edu/). A pronoun subject
takes the class of the noun it refers to, and "billions of people" takes the
class of "people". Words that name both people and mechanisms, such as
"resolver", are never flagged.

**ambiguous-pronouns.** "it", "its", "they", "them", and "their" are flagged
when the two likeliest antecedents score nearly the same. Candidates are
ranked by grammatical role and recency (Lappin and Leass, 1994). Before
ranking, cleancopy excludes the candidates that grammar forbids: "it" does not name a person, "the cost of applying it" does
not refer to the cost, "make it easier to" refers to nothing, and the verb
must fit (only an agent can decide). A chain of pronouns is judged once.

**serial-comma.** A list of three or more items needs a comma before its last
"and" or "or". Pairs inside a list and appositions are not lists.

<!-- cleancopy-disable phrasal-verbs -->
**phrasal-verbs.** A phrasal verb with two live readings is flagged with each
reading as a rewrite. The table holds 28 entries, such as "turn on", "put
off", and "make up".

**constructions.** Sentence shapes, matched in the tree, so different wordings
of one construction are caught together:

<!-- cleancopy-disable -->
- `comma-not`: "X, not Y"
- `not-but`: "not X but Y", though not "not only X but also Y"
- `not-then-is`: a denial corrected by the next clause with the same verb, as
  in "It isn't X. It's Y." or "This doesn't mean X. It means Y."
- `gerund-tells-you`: "Knowing X tells you Y"

You can ban your own constructions with spaCy
[DependencyMatcher](https://spacy.io/api/dependencymatcher) patterns (see
[Every option](#every-option)).

## Install

cleancopy needs Python 3.12 and [uv](https://docs.astral.sh/uv/). Run
cleancopy without installing:

```sh
uvx --from git+https://github.com/ayahohner/cleancopy@v0.4.1 cleancopy post.md
```

or install the command:

```sh
uv tool install git+https://github.com/ayahohner/cleancopy@v0.4.1
```

The first run downloads the spaCy transformer model (about 450 MB) and
WordNet. Parsing takes a few seconds per file, and parses are cached, so
unchanged files are not parsed again.

## Use

```text
cleancopy [paths...] [--config PATH] [--rule NAME]... [--format text|json]
          [--fail-on info|warning|error] [--no-cache]
```

- A folder stands for every Markdown file under it.
- With no paths, cleancopy lints the files that the config's `include`
  globs match.
- `--rule` runs only the named rule; repeat it for several.
- `--format json` prints a list of findings with `path`, `line`, `rule`,
  `severity`, `message`, `excerpt`, `word`, and rule-specific `data`.
- The exit status is 1 when any finding is at or above `--fail-on`
  (default `warning`), so cleancopy can gate CI or a pre-commit hook.

To turn rules off for the next paragraph, list, or table, put a comment
before it. With no rule named, every rule is off.

```markdown
<!-- cleancopy-disable literal-verbs constructions -->
The market decides, not the committee.
```

## Configure

cleancopy reads the nearest `cleancopy.toml`, searching upward from the
working directory. Every key is optional. A typical file:

```toml
include = ["src/content/posts/*.md"]

[lexicon]
agent = ["AI agent", "model"]          # can decide, want, and buy
mechanism = ["compiler", "runtime"]    # performs operations; cannot decide
mixed = ["resolver"]                   # a person or a function; never flagged

[rules.constructions]
allow = ["comma-not"]                  # permit "X, not Y"
```

### Lexicon classes

<!-- cleancopy-disable -->
| Class | Examples | Its literal verbs include |
|---|---|---|
| `agent` | person, team, AI agent | every verb |
| `physical` | server, phone | move, sit, grant |
| `display` | screen, chart, map | move, show, say |
| `mechanism` | compiler, module | set, assign, confirm |
| `text` | rule, message, post | say, ask, show, assume, dictate |
| `evidence` | study, result, "watching X" | show that, suggest, confirm |
| `idea` | goal, plan, principle | assume, guide |
| `institution` | market, money, custom | dictate, grant, treat as |
| `abstract` | record, theorem | none of the above |
| `mixed` | resolver | never flagged |

The built-in lists are in
[`src/cleancopy/data/lexicon.toml`](src/cleancopy/data/lexicon.toml), and a
project entry overrides them.

### Every option

```toml
[rules.literal-verbs]
severity = "warning"            # "info", "warning", "error", or "off"; every rule takes it
allow = ["compiler reject"]     # "subject verb"; the subject may be "@class" or "*"

[rules.ambiguous-pronouns]
ratio = 0.95                    # flag when the runner-up scores this share of the leader

[rules.serial-comma]
allow = ["Games, Life and Utopia"]  # skip any sentence containing the phrase

[rules.phrasal-verbs]
allow = ["make up"]             # "verb particle prep"

[rules.constructions]
allow = ["comma-not"]           # comma-not, not-but, not-then-is, gerund-tells-you

[[construction]]                # ban a construction; the first node is the flagged word
name = "at-the-end-of-the-day"
message = "say what finally matters"
pattern = [
  { RIGHT_ID = "end", RIGHT_ATTRS = { LOWER = "end" } },
  { LEFT_ID = "end", REL_OP = ">", RIGHT_ID = "of", RIGHT_ATTRS = { LOWER = "of" } },
  { LEFT_ID = "of", REL_OP = ">", RIGHT_ID = "day", RIGHT_ATTRS = { LOWER = "day" } },
]

[verbs]                         # extends src/cleancopy/data/verbs.toml
verb.offer = { suggest = ["provide"] }

[[phrasal]]                     # extends src/cleancopy/data/phrasal.toml
verb = "roll"
particle = "back"
readings = ["undo", "reduce"]
```

Parses are cached in `$XDG_CACHE_HOME/cleancopy`, or `~/.cache/cleancopy`
when `XDG_CACHE_HOME` is unset, and never in your project. The cache is keyed
by the model and the text, so projects share it; delete the folder to clear
it.

## How it works

1. Markdown is split into headings, paragraphs, list items, and table cells.
   Code blocks are skipped, and code spans and inline math become placeholder
   words, so the parser gets grammatical sentences.
2. spaCy's `en_core_web_trf` model, a RoBERTa transformer, tags each word and
   builds a dependency tree for each sentence.
3. Each rule checks the tree. Noun classes come from the lexicons and WordNet;
   the verb, phrasal-verb, and construction tables are TOML files.

The parser is a neural model, so it sometimes misreads a sentence. Each rule is
written to miss a finding rather than raise a false one, and every rule has an
allow list for the rest.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) to set up, test, and add rules.

## License

MIT; see [LICENSE](LICENSE).
