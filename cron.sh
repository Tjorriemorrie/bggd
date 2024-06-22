#!/usr/bin/env bash
set -eu

duration=$((60*60*8))

function main() {
  end=$((SECONDS+duration))

  cd /home/django/bggd
  source .venv/bin/activate

  python manage.py scrapehotness
  python manage.py scrape_games

  python manage.py update_game_stats
  python manage.py train_models sim


  while [ $SECONDS -lt $end ];
  do
    python manage.py scrape_players
  done

  python manage.py scrape_shop bgbsa thd mav timeless geekhome
  python manage.py scrape_shop ttg gargoyle swordandboard levelup amazon
  python manage.py scrape_shop outdated

}

main
