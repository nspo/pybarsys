from django import forms
from django.contrib import admin
from django.contrib.auth.models import Group
from django.db import models
from barsys.models import Category, Product, User, Purchase, Invoice, StatsDisplay
from django.db.models import F, DecimalField
from django.db.models.functions import Trunc
from django.db.models import DateTimeField


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

    list_filter = ["category"]
    list_select_related = True

    no_edit_foreign_tables_in_form = ["category"]


admin.site.register(Product, ProductAdmin)


class PurchaseAdmin(NoEditForeignTablesInlineMixin, admin.ModelAdmin):
    list_display = ['user', 'quantity', 'product_name', 'product_amount', 'cost']
    search_fields = ["user__email", "user__display_name", "product_name"]
    readonly_fields = ["invoice", "created_date", "modified_date", "cost"]

    no_edit_foreign_tables_in_form = ["user"]


admin.site.register(Purchase, PurchaseAdmin)


class UserAdmin(NoEditForeignTablesInlineMixin, admin.ModelAdmin):
    list_display = ['display_name', 'email', 'is_active', 'is_admin', 'is_buyer', 'purchases_paid_by_other']
    search_fields = ["display_name", "email"]

    list_filter = (
        'created_date', 'is_active', 'is_admin', 'is_buyer',
    )

    readonly_fields = ["last_login", "created_date", "modified_date",]

    no_edit_foreign_tables_in_form = ["purchases_paid_by_other"]

    def save_model(self, request, obj, form, change):
        # Override this to set the password to the value in the field if it's
        # changed.
        if change:
            orig_obj = User.objects.get(pk=obj.pk)
            if obj.password != orig_obj.password:
                obj.set_password(obj.password)
        else:
            obj.set_password(obj.password)
        obj.save()


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
