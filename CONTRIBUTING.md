# Contributing to proseclean

## Set up

proseclean needs Python 3.12 and [uv](https://docs.astral.sh/uv/). From a
clone, install the dependencies, including the test tools:

```sh
uv sync
```

The first test run downloads the spaCy transformer model (about 450 MB) and
WordNet.

## Test

```sh
uv run pytest
```

Every change keeps two quality thresholds: no function has a CRAP score above
8, and every file has a maintainability index above 75. Check both with a
coverage report:

```sh
uv run pytest --cov=proseclean --cov-report=json:.coverage.json
uv run python scripts/metrics.py .coverage.json
```

The metrics script prints each score, ends with PASS or FAIL, and exits with
status 1 on a failure.

## Add to the tables

Most new checks are data, and most need no code:

- A verb or phrase for `literal-verbs` goes in
  [`src/proseclean/data/verbs.toml`](src/proseclean/data/verbs.toml). The
  comment at the top of the file lists the subject classes.
- A noun class for `literal-verbs` goes in
  [`src/proseclean/data/lexicon.toml`](src/proseclean/data/lexicon.toml).
- A phrasal verb goes in
  [`src/proseclean/data/phrasal.toml`](src/proseclean/data/phrasal.toml), with
  one unambiguous rewrite per reading.
- A built-in construction goes in
  [`src/proseclean/rules/constructions.py`](src/proseclean/rules/constructions.py)
  as a function from a token to a boolean, listed in `_TESTS`, with its
  message in `MESSAGES`.

Add a test for each entry: one sentence that the entry flags, and a similar
sentence that the entry passes. Each rule has a test file in `tests/` with
examples to copy.

## Write the docs

The README and this file pass proseclean with no findings. Check them before
you commit:

```sh
uv run proseclean README.md CONTRIBUTING.md
```

## Release

A version lives in `pyproject.toml` and `npm/package.json`; set both, commit,
and push a tag:

```sh
git tag v0.5.0
git push origin v0.5.0
```

The tag runs [`.github/workflows/publish.yml`](.github/workflows/publish.yml):

1. `pypi` checks that the tag matches both versions, runs the tests, builds
   the wheel and source archive, and publishes the two files to PyPI. When
   PyPI already has the version, the job skips the upload, so a rerun can
   reach npm.
2. `npm` stages `@innerlattice/proseclean` from [`npm/`](npm). The package
   is a launcher that runs `uvx proseclean@VERSION` with its own version, so
   the launcher always runs the PyPI release of the same version.

PyPI and npm accept the workflow through trusted publishing, so no token is
stored. PyPI trusts `ayahohner/proseclean`'s `publish.yml` in the GitHub
environment `pypi`. npm trusts the same workflow to stage only:

```sh
npm trust github @innerlattice/proseclean --file publish.yml --repo ayahohner/proseclean --allow-stage-publish
```

A staged npm package goes live once a maintainer approves it with 2FA. The
Staged Packages tab on npmjs.com has an Approve button, and the command line
has:

```sh
npm stage list @innerlattice/proseclean
npm stage approve <stage-id>
```

The spaCy model is not in the package. proseclean downloads the pinned
version on first use and checks its hash (`MODEL_VERSION`, `MODEL_URL`, and
`MODEL_SHA256` in [`src/proseclean/nlp.py`](src/proseclean/nlp.py)). A new
model can parse differently and change the findings, so it changes only in a
release: update all three.

## License

Contributions are licensed under the [MIT License](LICENSE), the same as the
rest of proseclean.
