import logging
import zoneinfo

from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from django.templatetags.static import static
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin

from main.models import Game, PageView, VisitorLog
from main.selectors import get_client_ip, get_today

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
                context['og_img'] = request.build_absolute_uri(static('main/img/favicon.png'))
                context['og_url'] = request.build_absolute_uri()

        return response


class PageViewMiddleware:
    """Middleware to record unique page views for a GameDetailView."""

    def __init__(self, get_response):
        """Init."""
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        """Call middleware."""
        response = self.get_response(request)

        # Proceed only for the 'game-detail' path
        if request.resolver_match and request.resolver_match.url_name.startswith('game-detail'):
            self.record_page_view(request)

        return response

    def record_page_view(self, request: HttpRequest):
        """Record a unique PageView entry based on IP, day, and game."""
        # Get client IP address
        ip_address = get_client_ip(request)

        # Get the day object (today's date)
        day = get_today()

        # Extract the game ID from the path
        game_id = request.resolver_match.kwargs.get('pk')
        if not game_id:
            return
        game = get_object_or_404(Game, pk=game_id)

        # Check for existence and create if necessary
        PageView.objects.get_or_create(
            day=day, game=game, ip=ip_address, defaults={'viewed_at': timezone.now()}
        )


class VisitorLoggingMiddleware:
    def __init__(self, get_response):
        """Get response."""
        self.get_response = get_response

    def __call__(self, request):
        """Log visit."""
        response = self.get_response(request)

        if request.method == 'GET' and not request.path.startswith('/admin/'):
            ip = self.get_client_ip(request)
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            referrer = request.META.get('HTTP_REFERER', '')
            path = request.get_full_path()

            VisitorLog.objects.create(
                ip_address=ip,
                user_agent=user_agent,
                referrer=referrer,
                path=path,
                timestamp=timezone.now(),
            )

        return response

    def get_client_ip(self, request):
        """Get IP."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR', '')
