# CLAUDE.md

## Line Endings

- `.gitattributes` enforces `eol=crlf` for most files, but **shell scripts (`*.sh`) must use LF**.
- Never change shell scripts to CRLF — they run on Linux and will break.

## Linting

- This project uses **ruff** via pre-commit hooks.
- Max line length is **100 characters** (E501). Keep all Python lines within this limit.
- All public functions must have a **docstring** (D103). Add a one-line docstring to every `def` that isn't prefixed with `_`.
- Run `pre-commit run ruff --files <file>` to check before committing.

## Project

- Django project for tracking board game prices across South African shops.
- Templates are in `main/templates/main/`.
- Static files are in `main/static/main/`.
- Custom template filters are in `main/templatetags/fmt.py`.
