import logging
import zoneinfo

from django.templatetags.static import static
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class TimezoneMiddleware:
    def __init__(self, get_response):
        """Get response to set timezone."""
        self.get_response = get_response

    def __call__(self, request):
        """Middleware called."""
        # Get django_timezone from the cookie
        tzname = request.COOKIES.get('django_timezone')
        if tzname:
            timezone.activate(zoneinfo.ZoneInfo(tzname))
        else:
            logger.info(f'Timezone deactivated: {tzname}')
            timezone.deactivate()

        response = self.get_response(request)
        return response


class OpenGraphMiddleware(MiddlewareMixin):
    def process_template_response(self, request, response):
        """Add Open Graph metadata to the context."""
        if not hasattr(response, 'context_data'):
            return response

        context = response.context_data
        url = request.build_absolute_uri()
        view_name = getattr(getattr(request, 'resolver_match', None), 'view_name', '')

        if view_name in ('game-detail', 'game-detail-slug'):
            game = context.get('game')
            desc = game.pitch or game.description
            context.update(
                {
                    'og_title': f'{game.name} ({game.year}) - Board Game Prices',
                    'og_desc': desc[:200]
                    if desc
                    else f'Compare prices for {game.name} across South African board game shops.',
                    'og_img': game.img or request.build_absolute_uri(static('main/favicon.svg')),
                    'og_url': url,
                    'og_type': 'product',
                }
            )

        elif view_name in ('listing-detail', 'listing-detail-slug'):
            listing = context.get('listing')
            if listing.in_stock and listing.price:
                price_str = f'R{listing.price:.0f}'
                desc = f'{listing.name} available at {listing.shop.name} for {price_str}.'
            else:
                desc = f'{listing.name} at {listing.shop.name} — currently out of stock.'
            context.update(
                {
                    'og_title': f'{listing.name} — {listing.shop.name}',
                    'og_desc': desc,
                    'og_img': listing.img or request.build_absolute_uri(static('main/favicon.svg')),
                    'og_url': url,
                    'og_type': 'product',
                }
            )

        elif view_name in ('shop-detail', 'shop-detail-slug'):
            shop = context.get('shop')
            context.update(
                {
                    'og_title': f'{shop.name} — Board Game Shop',
                    'og_desc': f'Browse board game listings from {shop.name} on BGG Data.',
                    'og_img': request.build_absolute_uri(static('main/favicon.svg')),
                    'og_url': url,
                }
            )

        elif view_name == 'game-list':
            context.update(
                {
                    'og_title': 'Board Games — BGG Data',
                    'og_desc': (
                        'Browse and compare prices for board games' ' across South African shops.'
                    ),
                    'og_img': request.build_absolute_uri(static('main/favicon.svg')),
                    'og_url': url,
                }
            )

        elif view_name == 'listing-list':
            context.update(
                {
                    'og_title': 'All Listings — BGG Data',
                    'og_desc': (
                        'Browse board game listings from South African shops.'
                        ' Compare prices and find the best deals.'
                    ),
                    'og_img': request.build_absolute_uri(static('main/favicon.svg')),
                    'og_url': url,
                }
            )

        elif view_name == 'shop-list':
            context.update(
                {
                    'og_title': 'Shops — BGG Data',
                    'og_desc': 'South African board game shops tracked by BGG Data.',
                    'og_img': request.build_absolute_uri(static('main/favicon.svg')),
                    'og_url': url,
                }
            )

        elif view_name == 'home':
            context.update(
                {
                    'og_title': 'BGG Data — Board Game Price Tracker',
                    'og_desc': (
                        'Find the best deals on board games from South African'
                        ' shops. Compare prices, track savings, and discover'
                        ' new games.'
                    ),
                    'og_img': request.build_absolute_uri(static('main/favicon.svg')),
                    'og_url': url,
                }
            )

        else:
            # Category list pages and any other views
            category_names = {
                'card-list': 'Card Games',
                'tabletop-list': 'Tabletop Games',
                'rpg-list': 'RPG',
                'accessories-list': 'Accessories',
                'other-list': 'Other',
            }
            name = category_names.get(view_name, 'Board Games')
            context.update(
                {
                    'og_title': f'{name} — BGG Data',
                    'og_desc': (
                        f'Browse {name.lower()} listings from' ' South African board game shops.'
                    ),
                    'og_img': request.build_absolute_uri(static('main/favicon.svg')),
                    'og_url': url,
                }
            )

        return response
