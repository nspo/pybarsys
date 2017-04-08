from bootstrap3.templatetags.bootstrap3 import bootstrap_icon

from django import template
register = template.Library()

@register.simple_tag
def bool_to_icon(value):
    if value:
        return bootstrap_icon('ok')
    else:
        return bootstrap_icon('remove')