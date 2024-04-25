#!/usr/bin/env bash
set -eu

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

  python manage.py scrape_shop mav
  python manage.py scrape_shop timeless
  python manage.py scrape_shop geekhome
  python manage.py scrape_shop thd
  python manage.py scrape_shop ttg
  python manage.py scrape_shop gargoyle
  python manage.py scrape_shop swordandboard
  python manage.py scrape_shop levelup
  python manage.py scrape_shop outdated
}

main
