from django import forms
from django.contrib import admin
from django.contrib.auth.models import Group

from barsys.models import Category, Product, User, Purchase, Invoice, StatsDisplay


class NoEditForeignTablesInlineMixin(object):
    """ Don't show links to add/edit/delete foreign key element besides ForeignKey selection in forms """
    no_edit_foreign_tables_in_form = []

    def get_form(self, request, obj=None, **kwargs):
        """
        Don't allow adding/changing/deleting users inline
        """
        form = super(NoEditForeignTablesInlineMixin, self).get_form(request, obj, **kwargs)
        for key in self.no_edit_foreign_tables_in_form:
            form.base_fields[key].widget.can_add_related = False
            form.base_fields[key].widget.can_change_related = False
            form.base_fields[key].widget.can_delete_related = False
        return form


class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "get_number_products"]
    readonly_fields = ["get_number_products"]

admin.site.register(Category, CategoryAdmin)


class ProductAdmin(NoEditForeignTablesInlineMixin, admin.ModelAdmin):
    search_fields = ["name", "category__name", "amount"]
    list_display = ["name", "category", "amount", "price"]

    no_edit_foreign_tables_in_form = ["category"]

admin.site.register(Product, ProductAdmin)


class PurchaseAdmin(NoEditForeignTablesInlineMixin, admin.ModelAdmin):
    list_display = ['user', 'quantity', 'product_name', 'product_amount', ]
    search_fields = ["user__email", "user__display_name", "product_name"]
    readonly_fields = ["invoice", "created_date", "modified_date",]

    no_edit_foreign_tables_in_form = ["user"]

admin.site.register(Purchase, PurchaseAdmin)

class UserAdmin(NoEditForeignTablesInlineMixin, admin.ModelAdmin):
    list_display = ['display_name', 'email', 'is_active', 'is_admin', 'is_buyer', 'purchases_paid_by']
    search_fields = ["display_name", "email"]

    list_filter = (
        'created_date', 'is_active', 'is_admin', 'is_buyer',
    )

    readonly_fields = ["last_login", "created_date", "modified_date",]
    no_edit_foreign_tables_in_form = ["purchases_paid_by"]

admin.site.register(User, UserAdmin)

admin.site.register(Invoice)

class StatsDisplayAdmin(NoEditForeignTablesInlineMixin, admin.ModelAdmin):
    list_display = ["title", "example_row", "filter_category", "filter_product", "sort_by_and_show",
                    "show_by_default"]
    readonly_fields = ["example_row"]

    no_edit_foreign_tables_in_form = ["filter_category", "filter_product"]

admin.site.register(StatsDisplay, StatsDisplayAdmin)

if admin.site.is_registered(Group):
    admin.site.unregister(Group)