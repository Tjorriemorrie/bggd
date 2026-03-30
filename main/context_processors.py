from django.conf import settings


def developer(request):
    """Expose the DEVELOPER setting to all templates."""
    return {'DEVELOPER': settings.DEVELOPER}
