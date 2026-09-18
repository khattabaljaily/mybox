from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import get_language, gettext_lazy as _


class Category(models.Model):
    name_ar = models.CharField(max_length=100, verbose_name=_('الاسم بالعربية'))
    name_en = models.CharField(max_length=100, verbose_name=_('الاسم بالإنجليزية'))
    icon = models.CharField(
        max_length=50, blank=True, default='bi-folder2', verbose_name=_('الأيقونة'),
        help_text='CSS icon class, e.g. bi-folder2'
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='categories',
        null=True, blank=True, verbose_name=_('المالك'),
        help_text=_('الحقل الفارغ يعني أنه تصنيف افتراضي متاح لجميع المستخدمين'),
    )

    class Meta:
        ordering = ['name_ar']
        verbose_name = _('تصنيف')
        verbose_name_plural = _('التصنيفات')

    @property
    def name(self):
        return self.name_ar if get_language() == 'ar' else self.name_en

    def __str__(self):
        return self.name


class Entity(models.Model):
    """A fixed, predefined scope (myself, family, a vehicle, a property...)
    that documents can be grouped under — chosen from a list, like Category,
    not typed in by the user."""

    name_ar = models.CharField(max_length=100, verbose_name=_('الاسم بالعربية'))
    name_en = models.CharField(max_length=100, verbose_name=_('الاسم بالإنجليزية'))
    icon = models.CharField(max_length=50, blank=True, default='bi-person', verbose_name=_('الأيقونة'))
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='entities',
        null=True, blank=True, verbose_name=_('المالك'),
        help_text=_('الحقل الفارغ يعني أنه كيان افتراضي متاح لجميع المستخدمين'),
    )

    class Meta:
        ordering = ['name_ar']
        verbose_name = _('كيان')
        verbose_name_plural = _('الكيانات')

    @property
    def name(self):
        return self.name_ar if get_language() == 'ar' else self.name_en

    def __str__(self):
        return self.name


class Document(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='documents',
        verbose_name=_('المالك'),
    )
    title = models.CharField(max_length=200, verbose_name=_('العنوان'))
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='documents', verbose_name=_('التصنيف'),
    )
    entity = models.ForeignKey(
        Entity, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='documents', verbose_name=_('الكيان المرتبط'),
    )
    file = models.FileField(upload_to='documents/%Y/%m/', verbose_name=_('الملف'))
    tags = models.CharField(max_length=300, blank=True, verbose_name=_('الوسوم'))
    notes = models.TextField(blank=True, verbose_name=_('ملاحظات'))

    issue_date = models.DateField(null=True, blank=True, verbose_name=_('تاريخ الإصدار'))
    expiry_date = models.DateField(null=True, blank=True, verbose_name=_('تاريخ الانتهاء'))

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('مستند')
        verbose_name_plural = _('المستندات')

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('documents:detail', args=[self.pk])

    @property
    def days_to_expiry(self):
        if not self.expiry_date:
            return None
        return (self.expiry_date - timezone.localdate()).days

    @property
    def is_expired(self):
        days = self.days_to_expiry
        return days is not None and days < 0

    @property
    def tag_list(self):
        # Split on both the ASCII comma and the Arabic one (،), since Arabic
        # keyboards commonly insert the latter.
        normalized = self.tags.replace('،', ',')
        return [t.strip() for t in normalized.split(',') if t.strip()]

    @property
    def file_name(self):
        return self.file.name.rsplit('/', 1)[-1] if self.file else ''
