# CLAUDE.md

## Line Endings

- Always use **CRLF** line endings. This is a Windows project with `core.autocrlf=true`.
- `.gitattributes` enforces `eol=crlf`.

## Linting

- This project uses **ruff** via pre-commit hooks.
- Max line length is **100 characters** (E501). Keep all Python lines within this limit.
- Run `pre-commit run ruff --files <file>` to check before committing.

## Project

- Django project for tracking board game prices across South African shops.
- Templates are in `main/templates/main/`.
- Static files are in `main/static/main/`.
- Custom template filters are in `main/templatetags/fmt.py`.
