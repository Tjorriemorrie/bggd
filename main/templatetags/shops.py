from django import template
from django.utils.safestring import mark_safe

from main.constants import FORMAT_PRICE_HUNDREDS, FORMAT_PRICE_THOUSANDS
from main.models import Game, ShopGame

register = template.Library()


@register.filter
def price(obj):  # noqa PLR0912
    """Format price."""
    if isinstance(obj, Game):
        shopgame = obj.best_shop()
    elif isinstance(obj, ShopGame):
        shopgame = obj
    elif hasattr(obj, 'game'):
        shopgame = obj.game.best_shop()
    else:
        raise NotImplementedError(f'Unknown object {type(obj)}')

    # if no best shopgame
    # or shopgame cannot scrape the latest price
    # Note best shop only returns available, thus mia shops are None here
    if not shopgame or not shopgame.current_price:
        return mark_safe('<span class="text-muted">not in retail</span>')  # noqa S308

    if shopgame.current_price >= FORMAT_PRICE_THOUSANDS:
        price = round(shopgame.current_price / 100) * 100
    elif shopgame.current_price >= FORMAT_PRICE_HUNDREDS:
        price = round(shopgame.current_price / 50) * 50
    else:
        price = shopgame.current_price
    if not shopgame.current_available:  # noqa SIM108
        price_txt = f'<del>{price:,.0f}</del>'
    else:
        price_txt = f'{price:,.0f}'

    if not shopgame.game.shop_mean:
        deco = 'text-warning'
    elif shopgame.current_price < shopgame.game.shop_mean:
        deco = 'text-success'
    else:
        deco = 'text-danger'

    if shopgame.url:
        return mark_safe(  # noqa S308
            f'<a href="{shopgame.url}" target="_blank" class="text-decoration-none '
            f'{deco}">{price_txt}</a>'
        )
    else:
        return mark_safe(f'<span {deco}>{price_txt}</span>')  # noqa S308
