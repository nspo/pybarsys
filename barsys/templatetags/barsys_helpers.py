from bootstrap3.templatetags.bootstrap3 import bootstrap_icon
from django.utils.translation import to_locale, get_language
from constance import config
from django.conf import settings

from django import template
import locale

register = template.Library()

@register.simple_tag
def bool_to_icon(value):
    if value:
        return bootstrap_icon('ok')
    else:
        return bootstrap_icon('remove')


@register.filter(name='currency')
def currency(value):
    """ Please tell me how to do this the right way """
    if not value:
        value = 0

    l = settings.LANGUAGE_CODE
    l_split = l.split('-')
    l = l_split[0].lower() + "_" + l_split[1].upper() + ".UTF-8"

    locale.setlocale(locale.LC_ALL, l)
    return locale.currency(value, grouping=True)


@register.filter
def keyvalue(dict, key):
    return dict.get(key, '')