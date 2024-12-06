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
        if hasattr(response, 'context_data'):
            context = response.context_data

            # Check if the view is GameDetailView by matching its view name
            if (
                hasattr(request, 'resolver_match')
                and request.resolver_match.view_name == 'game-detail-slug'
            ):
                game = context.get('game')
                context['og_title'] = game.name  # Use game name for title
                context['og_desc'] = game.pitch  # Use game pitch for description
                context['og_img'] = game.img  # Use game image for og:image
                context['og_url'] = request.build_absolute_uri()  # Use current URL for og:url
            else:
                context['og_title'] = 'BoardGame Price Tracker'
                context['og_desc'] = 'Find the best deals on board games from local shops.'
                context['og_img'] = static('main/img/favicon.png')
                context['og_url'] = request.build_absolute_uri()

        return response
