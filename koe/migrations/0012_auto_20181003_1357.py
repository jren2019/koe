# Generated by Django 2.0.4 on 2018-10-03 13:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('koe', '0011_task_started'),
    ]

    operations = [
        migrations.AlterField(
            model_name='datamatrix',
            name='name',
            field=models.CharField(max_length=255),
        ),
    ]