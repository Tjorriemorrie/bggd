from datetime import datetime, timedelta

from django import template
from django.utils import timezone
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
def last_price(obj, show_currency: bool = True):
    """Format price, but for out of stock items, so it looks up last active price."""
    if not isinstance(obj, Listing):
        raise NotImplementedError(f'last_price only supports Listing objects, got {type(obj)}')

    last_active_price = obj.prices.filter(in_stock=True).last()
    if not last_active_price:
        return mark_safe('<span>Unknown</span>')

    price = last_active_price.price

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
            if obj.shop_price is None:
                saving = 0
                perc = 0.0
            else:
                saving = obj.shop_saving
                perc = saving / obj.shop_mean
        elif isinstance(obj, Listing) and obj.price and obj.game and obj.game.shop_mean:
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


@register.filter
def days_ago(value):
    """Calculate how many days ago a given date or datetime was, considering the user's timezone."""
    if not isinstance(value, datetime | timedelta):
        return ''

    value = timezone.localtime(value)
    now = timezone.localtime(timezone.now())
    # date_str = value.strftime('%H:%M')

    # today
    if value.date() == now.date():
        return 'Today'
        # return f'Today ({date_str})'

    value_midnight = value.replace(hour=0, minute=0, second=0)
    now_midnight = now.replace(hour=23, minute=59, second=59)
    delta = now_midnight - value_midnight

    # yesterday
    if delta.days <= 1:
        return 'Yesterday'
        # return f'Yesterday ({date_str})'

    # x days ago
    # day = value.day  # Get the day without leading zero
    # month = value.strftime('%b')  # Get the abbreviated month
    # date_str = f'{day} {month}'  # Combine day and month
    return f'{delta.days} days ago'
    # return f'{delta.days} days ago ({date_str})'
