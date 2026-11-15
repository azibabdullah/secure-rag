# Contributing to SecureRAG

Thanks for your interest. SecureRAG is a final year project, so the core design is fixed, but bug reports, documentation fixes and test cases are welcome.

## Reporting problems

- **Bugs and ideas:** open an [issue](https://github.com/azibabdullah/secure-rag/issues/new/choose) using the matching template.
- **Security vulnerabilities:** do **not** open a public issue. Follow [SECURITY.md](SECURITY.md).

## Development setup

Follow [Run from source](README.md#-run-from-source) in the README, then check that the tests pass:

```powershell
python -m pytest
```

## Making a change

1. Create a branch from `main`, named by type: `feature/<short-name>`, `fix/<short-name>` or `docs/<short-name>`.
2. Keep each pull request focused on one change.
3. Write commit messages in the [Conventional Commits](https://www.conventionalcommits.org) style, for example `fix(ingestion): keep page numbers for DOCX tables`.
4. Add or update tests for behaviour changes, and run `python -m pytest` before pushing.
5. Open a pull request against `main` and fill in the template.

## Ground rules

- Do not modify the frozen model folders or evaluation sets.
- Never commit model weights, datasets, `.env` files or personal documents.
- Classifier decisions must fail closed: an error is never treated as SAFE.
