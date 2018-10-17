# Generated by Django 2.0.4 on 2018-10-15 03:35

from django.db import migrations, models


def consolidate_individual(apps, schema_editor):
    """
    Merge individuals with the same name in to one. Prefer individuals that have species != None.
    If individual name is '_', they come from an earlier import script. Set their name to the species name plus suffix
    """
    db_alias = schema_editor.connection.alias
    indi_model = apps.get_model('koe', 'Individual')
    af_model = apps.get_model('koe', 'AudioFile')

    vl = indi_model.objects.using(db_alias).all().values_list('id', 'name', 'species')
    name2vals = {}
    for id, name, species in vl:
        if name not in name2vals:
            name2vals[name] = [(id, species)]
        else:
            name2vals[name].append((id, species))
    name2vals = {name: vals for name, vals in name2vals.items() if len(vals) > 1}

    if '_' in name2vals:
        suffixes = {}
        vals = name2vals['_']
        for id, species in vals:
            if species not in suffixes:
                suffix = 0
            else:
                suffix = suffixes[species] + 1
            suffixes[species] = suffix
            indi = indi_model.objects.get(id=id)
            if indi.species:
                new_name = '{}-{}_{}'.format(indi.species.genus, indi.species.species, suffix)
            else:
                new_name = 'Unknown-species_{}'.format(suffix)
            indi.name = new_name
            indi.save()

    del name2vals['_']

    name2chosen = {}
    for name, vals in name2vals.items():
        chosen = None
        for id, species in vals:
            if species is not None:
                chosen = id
                break
        if chosen is None:
            chosen = vals[0][0]
        name2chosen[name] = chosen

    replace = {chosen: [] for chosen in name2chosen.values()}
    for name, vals in name2vals.items():
        chosen = name2chosen[name]
        for id, species in vals:
            if id != chosen:
                replace[chosen].append(id)

    for chosen, replaced in replace.items():
        af_model.objects.using(db_alias).filter(id__in=replaced).update(individual_id=chosen)
        indi_model.objects.using(db_alias).filter(id__in=replaced).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('koe', '0012_auto_20181003_1357'),
    ]

    operations = [
        migrations.RunPython(consolidate_individual, reverse_code=migrations.RunPython.noop),
        migrations.AlterField(
            model_name='individual',
            name='name',
            field=models.CharField(max_length=255, unique=True),
        ),
        migrations.AlterUniqueTogether(
            name='individual',
            unique_together=set(),
        ),
    ]
