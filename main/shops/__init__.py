import importlib
import logging
import os
from pathlib import Path

import django

django.setup()

logger = logging.getLogger(__name__)

# Define a dictionary to hold shop data
shop_names = []
shop_enabled = {}
shop_hosts = {}
shop_scrapers = {}
shop_via_home = set()
_scrape_first = set()

# Directory where the shop modules are located
shops_dir = Path(__file__).parent

# Iterate through the files in the shops directory
for filename in os.listdir(shops_dir):
    if filename.endswith('_shop.py'):
        module_name = filename[:-3]  # Remove the .py extension
        module = importlib.import_module(f'main.shops.{module_name}')

        # Append shop name to the list
        shop_names.append(module.shop_name)

        shop_enabled[module.shop_name] = getattr(module, 'enabled', True)
        if getattr(module, 'scrape_first', False):
            _scrape_first.add(module.shop_name)
        if getattr(module, 'via_home', False):
            shop_via_home.add(module.shop_name)

        # Append shop host to the list
        shop_hosts[module.shop_name] = module.shop_host

        # Store shop data in the dictionary
        shop_scrapers[module.shop_name] = module.scrape

# Shops that only answer at some hours go first, so `shop all` reaches them at the cron's
# start time. The sort is stable: every other shop keeps its listing order.
shop_names.sort(key=lambda name: name not in _scrape_first)

# Specify the exported names
__all__ = ['shop_names', 'shop_enabled', 'shop_hosts', 'shop_scrapers', 'shop_via_home']
