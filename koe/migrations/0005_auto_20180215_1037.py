# Generated by Django 2.0.1 on 2018-02-14 21:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('koe', '0004_segment_mean_ff'),
    ]

    operations = [
        migrations.AddField(
            model_name='segment',
            name='max_ff',
            field=models.FloatField(null=True),
        ),
        migrations.AddField(
            model_name='segment',
            name='min_ff',
            field=models.FloatField(null=True),
        ),
    ]
