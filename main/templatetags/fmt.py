from django import template
from django.utils.safestring import mark_safe

from main.constants import FORMAT_PRICE_HUNDREDS, FORMAT_PRICE_THOUSANDS
from main.models import Game, Listing

register = template.Library()


@register.filter
def price(obj, show_currency: bool = True):
    """Format price."""
    if isinstance(obj, Game):
        in_stock = obj.shop_in_stock
        price = obj.shop_price
    elif isinstance(obj, Listing):
        in_stock = obj.in_stock
        price = obj.price
    else:
        raise NotImplementedError(f'Unknown object {type(obj)}')

    if not in_stock:
        return mark_safe('<span class="out-of-stock">Out of Stock</span>')

    if price >= FORMAT_PRICE_THOUSANDS:
        price = round(price / 100) * 100
    elif price >= FORMAT_PRICE_HUNDREDS:
        price = round(price / 50) * 50

    # Determine if the currency should be shown
    currency = 'R' if show_currency else ''

    return mark_safe(f'<span class="price">{currency}{price:.0f}</span>')


@register.filter
def discount(obj, show_currency: bool = True):
    """Format discount."""
    try:
        if isinstance(obj, Game):
            if obj.shop_price:
                saving = obj.shop_saving
                perc = saving / obj.shop_mean
            else:
                saving = 0
                perc = 0.0
        elif isinstance(obj, Listing) and obj.price and obj.game:
            saving = obj.game.shop_mean - obj.price
            perc = saving / obj.game.shop_mean
        elif isinstance(obj, Listing):
            return mark_safe('&mdash;')
        else:
            raise NotImplementedError(f'Unknown object {type(obj)}')
    except ZeroDivisionError:
        perc = 0.0
    perc *= 100

    if saving >= FORMAT_PRICE_THOUSANDS:
        saving = round(saving / 100) * 100
    elif saving >= FORMAT_PRICE_HUNDREDS:
        saving = round(saving / 50) * 50

    # Determine if the currency should be shown
    currency = 'R' if show_currency else ''

    return mark_safe(f'<span class="price">{currency}{saving:.0f} ({perc:.0f}%)</span>')
