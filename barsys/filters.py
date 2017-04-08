from .models import *
import django_filters
from django.forms import DateTimeInput, SplitDateTimeWidget
from django.db.models import DateTimeField


class UserFilter(django_filters.FilterSet):
    display_name = django_filters.CharFilter(lookup_expr='icontains')
    email = django_filters.CharFilter(lookup_expr='icontains')
    created_date = django_filters.DateTimeFromToRangeFilter(help_text="Format YYYY-MM-DD HH:MM. Time is optional.")

    class Meta:
        model = User
        fields = []
