#!/usr/bin/env bash
set -euo pipefail

function main() {
  cd /home/django/bggd
  source env/bin/activate
  ./manage.py redo_prediction
}

main
