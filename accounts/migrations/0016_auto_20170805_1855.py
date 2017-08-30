# -*- coding: utf-8 -*-
# Generated by Django 1.11.2 on 2017-08-05 18:55
from __future__ import unicode_literals

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0015_auto_20170805_1827'),
    ]

    operations = [
        migrations.AlterField(
            model_name='demographicdata',
            name='child_birthdays',
            field=django.contrib.postgres.fields.ArrayField(base_field=models.DateField(), blank=True, size=None, verbose_name="children's birthdays"),
        ),
    ]
