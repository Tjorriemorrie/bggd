from django import template

from django import template

from main.models import Game, ShopGame

register = template.Library()


@register.filter
def price(obj):
    if isinstance(obj, Game):
        shopgame = obj.best_shop()
    elif isinstance(obj, ShopGame):
        shopgame = obj
    else:
        raise NotImplementedError(f'Unknown object {type(obj)}')

    # if no best shopgame or shopgame cannot scrape latest price
    if not shopgame or not shopgame.current_price:
        url = shopgame.url if shopgame else ''
        return f'<a href="{url}" target="_blank" class="text-decoration-none text-muted">out of print</a>'

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
    deco = 'text-success' if shopgame.mean_saving > 0 else 'text-danger'
    return f'<a href="{shopgame.url}" target="_blank" class="text-decoration-none {deco}">{price_txt}</a>'
