#!/usr/bin/env bash
set -euo pipefail

duration=$((60*60*8))

function main() {
  end=$((SECONDS+duration))

  cd /home/django/bggd
  source env/bin/activate

  while [ $SECONDS -lt $end ];
  do
    for cmd in 'scrape_games' 'scrape_players' 'update_days'
    do
      ./manage.py $cmd
    done
  done

  ./manage.py update_hotness
  ./manage.py model_train
}

main
