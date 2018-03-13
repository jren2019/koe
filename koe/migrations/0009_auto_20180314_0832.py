# Generated by Django 2.0.1 on 2018-03-13 19:32

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('koe', '0008_audiofile_database'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='databaseassignment',
            options={'ordering': ('user', 'database', 'permission')},
        ),
        migrations.AlterField(
            model_name='database',
            name='name',
            field=models.CharField(max_length=255, unique=True),
        ),
        migrations.AlterUniqueTogether(
            name='databaseassignment',
            unique_together={('user', 'database', 'permission')},
        ),
    ]
