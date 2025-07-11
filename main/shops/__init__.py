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

        # Append shop host to the list
        shop_hosts[module.shop_name] = module.shop_host

        # Store shop data in the dictionary
        shop_scrapers[module.shop_name] = module.scrape

# Specify the exported names
__all__ = ['shop_names', 'shop_enabled', 'shop_hosts', 'shop_scrapers']
