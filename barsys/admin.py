from django import forms
from django.contrib import admin
from django.contrib.auth.models import Group

from barsys.models import Category, Product, User, Purchase, Invoice, StatsDisplay

class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "get_number_products"]
    readonly_fields = ["get_number_products"]

admin.site.register(Category, CategoryAdmin)

class ProductAdmin(admin.ModelAdmin):
    search_fields = ["name", "category__name", "amount"]
    list_display = ["name", "category", "amount", "price"]

admin.site.register(Product, ProductAdmin)

class PurchaseAdmin(admin.ModelAdmin):
    list_display = ['user', 'quantity', 'product_name', 'product_amount', ]
    search_fields = ["user__email", "user__display_name", "product_name"]
    readonly_fields = ["invoice", "created_date", "modified_date",]

admin.site.register(Purchase, PurchaseAdmin)

class UserAdmin(admin.ModelAdmin):
    list_display = ['display_name', 'email', 'is_active', 'is_admin', 'is_buyer', 'purchases_paid_by']
    search_fields = ["display_name", "email"]

    readonly_fields = ["last_login", "created_date", "modified_date",]

admin.site.register(User, UserAdmin)

admin.site.register(Invoice)

class StatsDisplayAdmin(admin.ModelAdmin):
    list_display = ["title", "example_row", "filter_category", "filter_product", "sort_by_and_show",
                    "show_by_default"]
    readonly_fields = ["example_row"]

admin.site.register(StatsDisplay, StatsDisplayAdmin)

if admin.site.is_registered(Group):
    admin.site.unregister(Group)