# Generated by Django 2.0.4 on 2018-06-15 14:09

from django.db import migrations, models
import django.db.models.deletion
import root.models


class Migration(migrations.Migration):

    dependencies = [
        ('koe', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Feature',
            fields=[
                ('id', models.AutoField(auto_created=True, editable=False, max_length=255, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255, unique=True)),
                ('is_fixed_length', models.BooleanField()),
                ('is_one_dimensional', models.BooleanField()),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, root.models.AutoSetterGetterMixin),
        ),
        migrations.CreateModel(
            name='SegmentFeature',
            fields=[
                ('id', models.AutoField(auto_created=True, editable=False, max_length=255, primary_key=True, serialize=False)),
                ('feature', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='koe.Feature')),
                ('segment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='koe.Segment')),
            ],
            bases=(models.Model, root.models.AutoSetterGetterMixin),
        ),
        migrations.AlterUniqueTogether(
            name='segmentfeature',
            unique_together={('segment', 'feature')},
        ),
    ]
