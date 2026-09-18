from django.db import migrations

DEFAULT_CATEGORIES = [
    ('بطاقة الهوية', 'National ID', 'bi-person-vcard'),
    ('جواز السفر', 'Passport', 'bi-airplane'),
    ('رخصة القيادة', 'Driving License', 'bi-car-front'),
    ('عقود', 'Contracts', 'bi-file-earmark-text'),
    ('التأمين', 'Insurance', 'bi-shield-check'),
    ('الشهادات', 'Certificates', 'bi-mortarboard'),
    ('البطاقات البنكية', 'Bank Cards', 'bi-credit-card'),
    ('الاشتراكات', 'Subscriptions', 'bi-arrow-repeat'),
    ('وثائق السيارة', 'Vehicle Documents', 'bi-car-front-fill'),
    ('وثائق العقار', 'Property Documents', 'bi-house-door'),
    ('أخرى', 'Other', 'bi-folder2'),
]


def seed_categories(apps, schema_editor):
    Category = apps.get_model('documents', 'Category')
    for name_ar, name_en, icon in DEFAULT_CATEGORIES:
        Category.objects.get_or_create(
            name_ar=name_ar, owner=None,
            defaults={'name_en': name_en, 'icon': icon},
        )


def remove_categories(apps, schema_editor):
    Category = apps.get_model('documents', 'Category')
    Category.objects.filter(owner__isnull=True, name_ar__in=[c[0] for c in DEFAULT_CATEGORIES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_categories, remove_categories),
    ]
