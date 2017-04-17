# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2017-04-17 18:54
from __future__ import unicode_literals

from decimal import Decimal
import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('barsys', '0032_productchangeaction_price'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='is_active',
            field=models.BooleanField(default=True, help_text='Whether this product is shown on the purchasing page'),
        ),
        migrations.AlterField(
            model_name='productchangeaction',
            name='price',
            field=models.DecimalField(blank=True, decimal_places=2, help_text='If set, will change the price of all products to this.', max_digits=5, null=True, validators=[django.core.validators.MinValueValidator(Decimal('0'))]),
        ),
    ]
