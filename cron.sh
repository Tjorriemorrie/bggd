#!/usr/bin/env bash
set -eu

duration=$((60*60*8))

function main() {
  end=$((SECONDS+duration))

  cd /home/django/bggd
  source .venv/bin/activate

  # Check if the current day is Sunday or if the date is before the 6th of the month
  day_of_week=$(date +'%u')  # Get the day of the week (1-7, 1 being Monday)
  day_of_month=$(date +'%d') # Get the day of the month

  if [ "$day_of_week" -eq 7 ] || [ "$day_of_month" -lt 6 ]; then
    python manage.py update_game_stats
  fi

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
  python manage.py scrape_shop amazon
  python manage.py scrape_shop outdated
}

main
