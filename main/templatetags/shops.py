from django import template

from django import template
from django.utils.safestring import mark_safe

from main.models import Game, ShopGame, Rec

register = template.Library()


@register.filter
def price(obj):
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
        return mark_safe(f'<span class="text-muted">out of print</span>')

    if shopgame.current_price >= 1_000:
        price = round(shopgame.current_price / 100) * 100
    elif shopgame.current_price >= 100:
        price = round(shopgame.current_price / 50) * 50
    else:
        price = shopgame.current_price
    if not shopgame.current_available:
        price_txt = f'<del>{price:,.0f}</del>'
    else:
        price_txt = f'{price:,.0f}'
    is_bargain = shopgame.current_price <= shopgame.game.shop_price and shopgame.game.shop_saving > 0
    deco = 'text-success' if is_bargain else 'text-danger'
    return mark_safe(f'<a href="{shopgame.url}" target="_blank" class="text-decoration-none {deco}">{price_txt}</a>')
