import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

DEFAULT_ENTITIES = [
    ('شخصي', 'Personal', 'bi-person'),
    ('أسرة', 'Family', 'bi-people'),
    ('مركبة', 'Vehicle', 'bi-car-front'),
    ('عقار', 'Property', 'bi-house-door'),
    ('عمل', 'Work', 'bi-briefcase'),
    ('أخرى', 'Other', 'bi-folder2'),
]


def seed_entities(apps, schema_editor):
    Entity = apps.get_model('documents', 'Entity')
    for name_ar, name_en, icon in DEFAULT_ENTITIES:
        Entity.objects.get_or_create(
            name_ar=name_ar, owner=None,
            defaults={'name_en': name_en, 'icon': icon},
        )


def remove_entities(apps, schema_editor):
    Entity = apps.get_model('documents', 'Entity')
    Entity.objects.filter(owner__isnull=True, name_ar__in=[e[0] for e in DEFAULT_ENTITIES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0004_generalize_default_categories'),
    ]

    operations = [
        migrations.RemoveField(model_name='entity', name='name'),
        migrations.AddField(
            model_name='entity', name='name_ar',
            field=models.CharField(default='', max_length=100, verbose_name='الاسم بالعربية'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='entity', name='name_en',
            field=models.CharField(default='', max_length=100, verbose_name='الاسم بالإنجليزية'),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='entity', name='owner',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                related_name='entities', to=settings.AUTH_USER_MODEL,
                verbose_name='المالك',
                help_text='الحقل الفارغ يعني أنه كيان افتراضي متاح لجميع المستخدمين',
            ),
        ),
        migrations.AlterModelOptions(
            name='entity',
            options={'ordering': ['name_ar'], 'verbose_name': 'كيان', 'verbose_name_plural': 'الكيانات'},
        ),
        migrations.RunPython(seed_entities, remove_entities),
    ]
