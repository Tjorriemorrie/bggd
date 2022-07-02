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
    shopgames = shop.shopgames.all()
    for ix, shopgame in enumerate(shopgames):
        logger.info(f'Progress {ix}/{len(shopgames)}')
        if shopgame.mia:
            continue
        try:
            data = scrape_raru_game(shopgame.url)
        except AttributeError as exc:
            logger.exception(f'Could not scrape {shopgame.url}')
            continue
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
    elif availability in ['In Stock', 'Dispatched in 20 to 30 working days', 'Dispatched in 10 to 15 working days', 'Dispatched in 7 to 10 working days', 'Dispatched in 5 to 7 working days']:
        status = STOCK_IN
    else:
        raise NotImplementedError(f'Not sure what is: {availability}')
    price = html.find('dl', class_='price').find('dd').find('span').text.replace(',', '')
    return {
        'status': status,
        'price': int(price),
    }
