# Contributing

Thanks for your interest in improving AMReXAgent!

## Preferred workflow

Please open a pull request (PR) from a branch on your fork. PRs are the
preferred way to contribute changes and enable review.

## Docstrings

Use NumPy-style docstrings for functions, classes, and modules. We lint
docstring style with `ruff`, so please run it before submitting:

```bash
ruff check .
```

## Tests and examples

Tests are organized under `tests/`. Start with the test guide in
`tests/README.md` and run the smallest scope that covers your change:

```bash
pytest --unit
pytest --integration -m "not slow"
pytest --quality
```

Examples live under `demo/`. Add a short README for new scenarios so others can
replay the workflow quickly.
