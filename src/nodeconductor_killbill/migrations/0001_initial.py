# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import nodeconductor.logging.loggers
import uuidfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('structure', '0026_add_error_message'),
    ]

    operations = [
        migrations.CreateModel(
            name='Invoice',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('uuid', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
                ('amount', models.DecimalField(max_digits=9, decimal_places=2)),
                ('date', models.DateField()),
                ('pdf', models.FileField(null=True, upload_to=b'invoices', blank=True)),
                ('usage_pdf', models.FileField(null=True, upload_to=b'invoices', blank=True)),
                ('backend_id', models.CharField(max_length=255, blank=True)),
                ('customer', models.ForeignKey(related_name='killbill_invoices', to='structure.Customer')),
            ],
            options={
                'abstract': False,
            },
            bases=(nodeconductor.logging.loggers.LoggableMixin, models.Model),
        ),
    ]
