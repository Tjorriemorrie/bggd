#!/usr/bin/env bash
set -eu

function main() {
  cd /home/django/bggd
  source env/bin/activate
  python manage.py redo_prediction
}

main
