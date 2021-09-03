from django import template

register = template.Library()


@register.simple_tag(name='drop_param', takes_context=True)
def drop_param_filter(context, param_key):
    req = context.request.GET.copy()
    if param_key in req:
        del req[param_key]
    return req.urlencode()


@register.simple_tag(name='add_param', takes_context=True)
def add_param_filter(context, param_key, param_value):
    req = context.request.GET.copy()
    req[param_key] = param_value
    if param_key == 'o' and 'page' in req:
        del req['page']
    return req.urlencode()
