from django.db import migrations

# Fewer, more general categories — and nothing that names a specific
# sensitive item (e.g. "Bank Cards"), so the category list itself doesn't
# advertise what kind of sensitive documents a user keeps.
OLD_CATEGORIES = [
    'بطاقة الهوية', 'جواز السفر', 'رخصة القيادة', 'البطاقات البنكية',
    'وثائق السيارة', 'وثائق العقار', 'الاشتراكات', 'عقود',
]

NEW_CATEGORIES = [
    ('الهوية والسفر', 'Identity & Travel', 'bi-person-vcard'),
    ('العقود', 'Contracts', 'bi-file-earmark-text'),
    ('التأمين', 'Insurance', 'bi-shield-check'),
    ('الشهادات', 'Certificates', 'bi-mortarboard'),
    ('الاشتراكات والفواتير', 'Subscriptions & Bills', 'bi-arrow-repeat'),
    ('الممتلكات', 'Assets', 'bi-house-door'),
    ('أخرى', 'Other', 'bi-folder2'),
]


def generalize_categories(apps, schema_editor):
    Category = apps.get_model('documents', 'Category')
    Document = apps.get_model('documents', 'Document')

    other, _ = Category.objects.get_or_create(
        name_ar='أخرى', owner=None, defaults={'name_en': 'Other', 'icon': 'bi-folder2'},
    )
    Document.objects.filter(category__name_ar__in=OLD_CATEGORIES, category__owner=None).update(category=other)
    Category.objects.filter(name_ar__in=OLD_CATEGORIES, owner=None).delete()

    for name_ar, name_en, icon in NEW_CATEGORIES:
        Category.objects.update_or_create(
            name_ar=name_ar, owner=None, defaults={'name_en': name_en, 'icon': icon},
        )


def restore_old_categories(apps, schema_editor):
    Category = apps.get_model('documents', 'Category')
    Category.objects.filter(name_ar__in=[c[0] for c in NEW_CATEGORIES], owner=None).exclude(name_ar='أخرى').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0003_alter_category_owner'),
    ]

    operations = [
        migrations.RunPython(generalize_categories, restore_old_categories),
    ]
