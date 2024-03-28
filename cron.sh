#!/usr/bin/env bash
set -euo pipefail

duration=$((60*60*8))

function main() {
  end=$((SECONDS+duration))

  cd /home/django/bggd
  source env/bin/activate

  python manage.py update_game_stats

  python manage.py scrape_games

  while [ $SECONDS -lt $end ];
  do
    python manage.py scrape_players
  done

  python manage.py train_models sim

  python manage.py scrape_shop mav timeless geekhome thd ttg gargoyle outdated
}

main
