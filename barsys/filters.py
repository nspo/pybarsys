from .models import *
import django_filters
from django.forms import DateTimeInput, SplitDateTimeWidget
from django.db.models import DateTimeField


class UserFilter(django_filters.FilterSet):
    display_name = django_filters.CharFilter(lookup_expr='icontains')
    email = django_filters.CharFilter(lookup_expr='icontains')
    purchases_paid_by_other = django_filters.BooleanFilter(method="filter_has_purchases_paid_by_other")
    created_date = django_filters.DateTimeFromToRangeFilter(help_text="Format YYYY-MM-DD HH:MM. Time is 00:00 by default.")

    class Meta:
        model = User
        fields = ['is_active', 'is_buyer', 'is_favorite', 'is_admin']

    def filter_has_purchases_paid_by_other(self, queryset, name, value):
        return queryset.filter(purchases_paid_by_other__isnull=not value)


class PurchaseFilter(django_filters.FilterSet):
    product_name = django_filters.CharFilter(lookup_expr='icontains')
    product_category = django_filters.CharFilter(lookup_expr='icontains')
    invoice = django_filters.BooleanFilter(method='filter_has_invoice')
    created_date = django_filters.DateTimeFromToRangeFilter(help_text="Format YYYY-MM-DD HH:MM. Time is 00:00 by default.")

    def filter_has_invoice(self, queryset, name, value):
        return queryset.filter(invoice__isnull=not value)

    class Meta:
        model = Purchase
        fields = []


class PaymentFilter(django_filters.FilterSet):
    comment = django_filters.CharFilter(lookup_expr='icontains')
    amount__gte = django_filters.NumberFilter(name='amount', lookup_expr='gte')
    amount__lte = django_filters.NumberFilter(name='amount', lookup_expr='lte')

    created_date = django_filters.DateTimeFromToRangeFilter(help_text="Format YYYY-MM-DD HH:MM. Time is 00:00 by default.")

    class Meta:
        model = Payment
        fields = ["user"]


class CategoryFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains')

    class Meta:
        model = Category
        fields = []


class ProductFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains')

    class Meta:
        model = Product
        fields = ["name", "category"]


class StatsDisplayFilter(django_filters.FilterSet):
    title = django_filters.CharFilter(lookup_expr='icontains')

    class Meta:
        model = StatsDisplay
        fields = ["sort_by_and_show"]