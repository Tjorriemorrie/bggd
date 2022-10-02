#!/usr/bin/env bash
set -euo pipefail

duration=$((60*60*8))

function main() {
  end=$((SECONDS+duration))

  cd /home/django/bggd
  source env/bin/activate

  ./manage.py update_game_stats

  ./manage.py scrape_games

  while [ $SECONDS -lt $end ];
  #do
  #  for cmd in 'scrape_games' 'scrape_players'
  #  do
  #    ./manage.py $cmd
  #  done
    ./manage.py scrape_players
  done

  ./manage.py train_models sim

  ./manage.py scrape_shop raru mav timeless geekhome frontpage
}

main
