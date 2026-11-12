from datetime import date, timedelta
from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from main.constants import SCRAPE_OK
from main.errors import NoRowsFoundError, TooManyRequestsError
from main.models import Day, Scrapelog, Shop
from main.selectors import get_last_scrape
from main.shops.helpers import check_first_page

SHOP = 'main.management.commands.shop'


def _boom():
    raise TooManyRequestsError()


def _scrape(scraper):
    """Run the shop command for one enabled shop whose scraper is the given callable."""
    with (
        patch(f'{SHOP}.time.sleep'),
        patch.dict(f'{SHOP}.shop_scrapers', {'Level Up': scraper}),
        patch.dict(f'{SHOP}.shop_enabled', {'Level Up': True}),
    ):
        call_command('shop', 'Level Up')


class CheckFirstPageTests(SimpleTestCase):
    def test_empty_first_page_raises(self):
        with self.assertRaisesMessage(NoRowsFoundError, 'https://x/all'):
            check_first_page('Level Up', 'https://x/all', 1, False)

    def test_empty_later_page_ends_the_shelf(self):
        check_first_page('Level Up', 'https://x/all', 2, False)

    def test_first_page_with_products_passes(self):
        check_first_page('Level Up', 'https://x/all', 1, {'https://x/a'})


class ShopCommandTests(TestCase):
    def test_failed_scrape_raises_and_logs_the_error(self):
        with self.assertRaisesMessage(CommandError, 'Level Up'):
            _scrape(_boom)
        assert Scrapelog.objects.get(target='shop Level Up').outcome == 'TooManyRequestsError'

    def test_finished_scrape_logs_ok(self):
        _scrape(lambda: None)
        assert Scrapelog.objects.get(target='shop Level Up').outcome == SCRAPE_OK


class LastScrapeTests(TestCase):
    def test_failed_scrape_is_not_the_last_scrape(self):
        shop = Shop.objects.create(name='Level Up', slug='level-up')
        now = timezone.now()
        ok = Scrapelog.objects.create(
            day=Day.objects.create(day=date(2026, 11, 11)),
            target='shop Level Up',
            scraped_at=now - timedelta(days=1),
            outcome=SCRAPE_OK,
            duration=1,
        )
        Scrapelog.objects.create(
            day=Day.objects.create(day=date(2026, 11, 12)),
            target='shop Level Up',
            scraped_at=now,
            outcome='TooManyRequestsError',
            duration=1,
        )
        assert get_last_scrape(shop) == ok


class CronTests(TestCase):
    def test_failed_shops_still_run_the_bgg_steps(self):
        ran = []

        def fake(name, *args):
            if name == 'shop':
                raise CommandError('Failed to scrape 1 of 13 shops: Level Up')
            ran.append(args[0])

        with (
            patch('main.management.commands.cron.time.sleep'),
            patch('main.management.commands.cron.call_command', side_effect=fake),
            self.assertRaisesMessage(CommandError, 'Level Up'),
        ):
            call_command('cron')
        assert ran == ['auto', 'new', 'out', 'clean']
