import locale

from bootstrap3.templatetags.bootstrap3 import bootstrap_icon
from django import template
from django.conf import settings
from django.utils import formats

register = template.Library()

@register.simple_tag
def bool_to_icon(value):
    if value:
        return bootstrap_icon('ok')
    else:
        return bootstrap_icon('remove')


def get_locale_str():
    """ Please tell me how to do this the right way """
    l = settings.LANGUAGE_CODE
    l_split = l.split('-')
    l = l_split[0].lower() + "_" + l_split[1].upper() + ".UTF-8"

    return l


@register.filter(name='currency')
def currency(value):
    if not value:
        value = 0

    locale.setlocale(locale.LC_ALL, get_locale_str())
    return locale.currency(value, grouping=True)


@register.filter
def keyvalue(dict, key):
    return dict.get(key, '')


@register.filter
def sdatetime(value):
    return formats.date_format(value, "SHORT_DATETIME_FORMAT")

@register.filter
def sdate(value):
    return formats.date_format(value, "SHORT_DATE_FORMAT")
