# -*- coding: utf-8 -*-
# Generated by Django 1.11.2 on 2017-07-14 16:25
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion
import perma_payments.models
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='SubscriptionAgreement',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('registrar', models.IntegerField()),
                ('status', models.CharField(choices=[('Pending', 'Pending'), ('Rejected', 'Rejected'), ('Cancelled', 'Cancelled'), ('Completed', 'Completed'), ('Current', 'Current'), ('Hold', 'Hold'), ('Superseded', 'Superseded')], max_length=20)),
                ('status_updated', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='SubscriptionRequest',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reference_number', models.CharField(default=perma_payments.models.generate_reference_number, help_text="Unqiue ID for this subscription. Subsequent charges, automatically made byCyberSource onthe recurring schedule, will all be associated with this reference number. Called 'Merchant Reference Number' in CyberSource Business Center.", max_length=32)),
                ('transaction_uuid', models.UUIDField(default=uuid.uuid4, help_text="A unique ID for this 'transaction'. Intended to protect against duplicate transactions.")),
                ('request_datetime', models.DateTimeField(auto_now_add=True)),
                ('amount', models.DecimalField(decimal_places=2, help_text='Amount to be charged immediately', max_digits=19)),
                ('recurring_amount', models.DecimalField(decimal_places=2, help_text='Amount to be charged repeatedly, beginning on recurring_start_date', max_digits=19)),
                ('recurring_frequency', models.CharField(choices=[('weekly', 'weekly'), ('bi-weekly', 'bi-weekly'), ('quad-weekly', 'quad-weekly'), ('monthly', 'monthly'), ('semi-monthly', 'semi-monthly'), ('quarterly', 'quarterly'), ('semi-annually', 'semi-annually'), ('annually', 'annually')], max_length=20)),
                ('currency', models.CharField(default='USD', max_length=3)),
                ('locale', models.CharField(default='en-us', max_length=5)),
                ('payment_method', models.CharField(default='card', max_length=30)),
                ('transaction_type', models.CharField(default='sale,create_payment_token', max_length=30)),
                ('subscription_agreement', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='subscription_agreement', to='perma_payments.SubscriptionAgreement')),
            ],
        ),
    ]