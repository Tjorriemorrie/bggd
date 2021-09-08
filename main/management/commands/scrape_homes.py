import csv
import logging
import re
from typing import List

import requests
from bs4 import BeautifulSoup
from django.core.management import BaseCommand

from bgg.settings import BASE_DIR

logger = logging.getLogger(__name__)

BEDROOMS = 0
BATHROOMS = 0
GARAGES = 0
HOST = 'https://www.privateproperty.co.za'
FILE_MODEL = BASE_DIR / 'homes.csv'


class Command(BaseCommand):
    help = 'Scrape bgg player data'

    def handle(self, *args, **options):
        url = '/for-sale/gauteng/centurion/centurion-west/956?pt=5,2,10&si=196,1295,205,200,202&page='
        page = 0
        all_homes = []
        while True:
            page += 1
            homes = scrape_page(url, page)
            if not homes:
                break
            all_homes.extend(homes)

        with open(FILE_MODEL, 'w+') as fp:
            writer = csv.DictWriter(fp, fieldnames=list(all_homes[0].keys()))
            writer.writeheader()
            writer.writerows(all_homes)


def scrape_page(url: str, page: int) -> List[dict]:
    logger.info(f'Scraping {url}{page}')
    headers = {
        'User-agent': 'Mozilla/5.0 (Windows NT 6.2; Win64; x64; rv:66.0) Gecko/20100101 Firefox/66.0'
    }
    res = requests.get(f'{HOST}{url}{page}', headers=headers)
    res.raise_for_status()

    html = BeautifulSoup(res.content, 'html.parser')
    if 'There were no listings' in html.text:
        return []

    homes = []
    listings = html.find_all('a', class_='listingResult')
    for listing in listings:
        # url
        href = HOST + listing.get('href')

        # add image
        # img_tag = listing.find_all('img')[0]
        # img = img_tag.get('data-src')

        # title
        try:
            title = listing.find('div', class_='title').text
            title_bits = title.split()
            size = float(title_bits.pop(0))
            mul = title_bits.pop(0)
            if mul == 'ha':
                size *= 10000
            area = title_bits[2:]
        except ValueError:
            size = 1000
            area = ''

        # fix size
        if size < 100:
            size *= 10_000
        # if size > 10_000 * 80:
        #     size /= 10_000

        # address
        try:
            address = listing.find('div', class_='address').text.title()
        except AttributeError:
            address = ''

        # price
        price_text = listing.find('div', class_='priceDescription').text
        if price_text in ['Sold', 'Price on Application']:
            continue
        if price_text in ['On Auction', 'Bank Negotiable']:
            price = 999_999
        else:
            try:
                price = re.findall(r'(\d+)', price_text.replace(' ', ''))[0]
            except (IndexError, AttributeError):
                raise Exception(f'Price? {price_text}')

        try:
            bedrooms = listing.find('div', class_='bedroom').previous_sibling.previous_sibling.text
        except AttributeError:
            bedrooms = 0
        try:
            bathrooms = listing.find('div', class_='bathroom').previous_sibling.previous_sibling.text
        except AttributeError:
            bathrooms = 0
        try:
            cars = listing.find('div', class_='garage').previous_sibling.previous_sibling.text
        except AttributeError:
            cars = 0

        home = {
            'area': ' '.join(area),
            'address': address,
            'price': price,
            'bedrooms': float(bedrooms),
            'bathrooms': float(bathrooms),
            'cars': float(cars),
            'url' : href,
            'size': size,
        }
        homes.append(home)
        logger.info(f'Added home {home}')

    return homes
