#!/usr/bin/env bash
set -eu

function main() {
  cd /home/django/bggd
  source .venv/bin/activate
  python manage.py redo_prediction
}

main
