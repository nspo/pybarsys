# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2017-04-17 17:44
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('barsys', '0029_auto_20170417_1943'),
    ]

    operations = [
        migrations.AlterField(
            model_name='productchangeaction',
            name='title',
            field=models.CharField(max_length=30, unique=True),
        ),
    ]
