# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2017-04-07 20:41
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('barsys', '0019_auto_20170407_0243'),
    ]

    operations = [
        migrations.CreateModel(
            name='PurchaseSummary',
            fields=[
            ],
            options={
                'verbose_name_plural': 'Purchases Summary',
                'indexes': [],
                'verbose_name': 'Purchase Summary',
                'proxy': True,
            },
            bases=('barsys.purchase',),
        ),
    ]
