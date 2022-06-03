from django import template

from django import template

from main.models import Game

register = template.Library()


@register.simple_tag(name='shop_mean', takes_context=False)
def mean_filter(game: Game):
    perc = int((1 - game.ps_mean) * 100)
    mean = int(game.ps_data['aggregations']['price']['mean'])
    return f'{ perc }% below avg R{ mean }'


@register.simple_tag(name='shop_range', takes_context=False)
def range_filter(game: Game):
    perc = int(game.ps_range * 100)
    min_ = int(game.ps_data['aggregations']['price']['min'])
    return f'{ perc }% above min R{ min_ }'
