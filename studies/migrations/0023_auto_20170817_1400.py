# -*- coding: utf-8 -*-
# Generated by Django 1.11.2 on 2017-08-17 14:00
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('studies', '0022_feedback'),
    ]

    operations = [
        migrations.AlterField(
            model_name='feedback',
            name='response',
            field=models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, related_name='feedback', to='studies.Response'),
        ),
    ]