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
8, and every function and file has a maintainability index above 75.
[neroli](https://www.npmjs.com/package/@innerlattice/neroli) checks both with
the policy in `neroli.toml`, after running the tests with coverage:

```sh
npx @innerlattice/neroli@0.1.0 gate src --run-coverage
```

proseclean checks its own docs, the Markdown that `proseclean.toml` includes:

```sh
uv run proseclean
```

[`.github/workflows/check.yml`](.github/workflows/check.yml) runs the tests,
the gate, and the docs check on every push to `main` and every pull request.

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

A release takes its version from its tag, and no file holds the version. To
release the current commit on `main`, push a tag, or create a release with
that tag on GitHub, whose release notes list the commits since the last tag:

```sh
git tag v0.6.0
git push origin v0.6.0
```

[hatch-vcs](https://github.com/ofek/hatch-vcs) reads the version from git, so
a build between tags gets a development version such as `0.6.1.dev2+g1a2b3c4`.
The version in `npm/package.json` stays `0.0.0`.

The tag runs [`.github/workflows/publish.yml`](.github/workflows/publish.yml):

1. `pypi` runs the tests, builds the wheel and source archive, checks that
   the wheel took its version from the tag, and publishes the two files to
   PyPI. When
   PyPI already has the version, the job skips the upload, so a rerun can
   reach npm.
2. `npm` sets the version in [`npm/package.json`](npm/package.json) from the
   tag and stages `@innerlattice/proseclean`. The package
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
