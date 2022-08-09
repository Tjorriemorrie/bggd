#!/usr/bin/env bash
set -euo pipefail

duration=$((60*60*7))

function main() {
  end=$((SECONDS+duration))

  cd /home/django/bggd
  source env/bin/activate

  ./manage.py scrape_shop raru mav timeless frontpage

  while [ $SECONDS -lt $end ];
  do
    for cmd in 'scrape_games' 'scrape_players'
    do
      ./manage.py $cmd
    done
  done

  ./manage.py update_game_stats

  ./manage.py train_models mec
}

main
