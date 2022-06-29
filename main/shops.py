import logging

from bs4 import BeautifulSoup

from main.constants import SHOP_RARU, STOCK_OUT, STOCK_IN
from main.models import Shop, Price, Day
from main.scraper import get

logger = logging.getLogger(__name__)


def scrape_raru():
    logger.info('Scraping Raru')
    day = Day.get_today()
    shop = Shop.objects.get(name=SHOP_RARU)
    for shopgame in shop.shopgames.all():
        if shopgame.mia:
            continue
        data = scrape_raru_game(shopgame.url)
        prev_price = shopgame.prices.last()
        if not prev_price or prev_price.price != data['price'] or prev_price.status != data['status']:
            new_price, _ = Price.objects.update_or_create(
                shopgame=shopgame,
                day=day,
                defaults={
                    'status': data['status'],
                    'price': data['price'],
                }
            )
            logger.info(f'New Price! {new_price}')
    logger.info('Finished scraping Raru')


def scrape_raru_game(url: str) -> dict:
    res = get(url)
    html = BeautifulSoup(res.text, 'html.parser')

    availability = html.find('div', class_='avail').text
    if availability in ['Out of Stock', 'Unreleased']:
        status = STOCK_OUT
    elif availability in ['In Stock', 'Dispatched in 7 to 10 working days']:
        status = STOCK_IN
    else:
        raise NotImplementedError()
    price = html.find('dl', class_='price').find('dd').find('span').text.replace(',', '')
    return {
        'status': status,
        'price': int(price),
    }
