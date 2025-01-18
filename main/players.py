import logging

from bs4 import BeautifulSoup

from main.games import get
from main.models import Saffa

logger = logging.getLogger(__name__)

HOST = 'https://boardgamegeek.com'
URL_SAFFAS = '{host}/users/page/{page}?country=South%20Africa&state&city'


def scrape_saffas():
    """Scrape saffas from bgg."""
    logger.info('Scraping saffas...')
    page = 0
    while True:
        page += 1
        url = URL_SAFFAS.format(host=HOST, page=page)
        res = get(url)

        soup = BeautifulSoup(res.content, 'html.parser')
        table = soup.find('table', class_='forum_table')
        tds = table.find_all('td')
        logger.info(f'{len(tds)} saffas found on page {page}')
        if not tds:
            break
        for td in tds:
            username_cell = td.find('div', class_='username')
            if not username_cell:
                continue
            username_txt = username_cell.get_text(strip=True)
            username = username_txt.lstrip('(').rstrip(')')
            href = HOST + username_cell.find('a')['href']
            name = username_cell.find_previous_sibling('div').get_text(strip=True)

            saffa, created = Saffa.objects.get_or_create(
                link=href,
                defaults={
                    'name': name,
                    'username': username,
                },
            )

            if created:
                logger.info(f'Created {saffa}')
