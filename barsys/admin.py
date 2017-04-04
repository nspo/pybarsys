from django import forms
from django.contrib import admin
from django.contrib.auth.models import Group

from barsys.models import Category, Product

admin.site.register(Category)
admin.site.register(Product)

#admin.site.unregister(Group)

# Register your models here.
