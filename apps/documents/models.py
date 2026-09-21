import os
import secrets

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import get_language, gettext_lazy as _

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}


def _file_kind(file):
    """'image', 'pdf', or 'other' — used to decide whether a file can be
    previewed inline (in a modal) or should just be offered as a download."""
    if not file:
        return 'other'
    ext = os.path.splitext(file.name)[1].lower()
    if ext == '.pdf':
        return 'pdf'
    if ext in IMAGE_EXTENSIONS:
        return 'image'
    return 'other'


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


class ActiveDocumentManager(models.Manager):
    """Default manager: hides documents that are in the trash."""

    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


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

    reminder_days = models.CharField(
        max_length=60, blank=True, verbose_name=_('أيام التنبيه'),
        help_text=_('أيام قبل الانتهاء مفصولة بفواصل. الحقل الفارغ يعني استخدام الإعداد الافتراضي.'),
    )
    snoozed_until = models.DateField(null=True, blank=True, editable=False)

    deleted_at = models.DateTimeField(null=True, blank=True, editable=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # `objects` must stay first: it's the default manager, so every existing
    # Document.objects / related-manager query skips trashed documents.
    objects = ActiveDocumentManager()
    all_objects = models.Manager()

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

    @property
    def file_kind(self):
        return _file_kind(self.file)

    @property
    def reminder_days_list(self):
        """The custom reminder days set on this document, largest first (empty = use defaults)."""
        days = {int(d) for d in self.reminder_days.split(',') if d.strip().isdigit()}
        return sorted(days, reverse=True)

    @property
    def reminder_thresholds(self):
        return self.reminder_days_list or list(settings.EXPIRY_REMINDER_DAYS)

    @property
    def is_trashed(self):
        return self.deleted_at is not None


class DocumentVersion(models.Model):
    """A snapshot of what a document looked like before it was renewed or had its
    file replaced. The file moves here from the document (it isn't copied), and a
    renewal without a new file records just the expiry date that was in effect."""

    REASON_RENEWED = 'renewed'
    REASON_REPLACED = 'replaced'
    REASON_RESTORED = 'restored'
    REASON_CHOICES = [
        (REASON_RENEWED, _('تجديد')),
        (REASON_REPLACED, _('استبدال الملف')),
        (REASON_RESTORED, _('استرجاع نسخة قديمة')),
    ]

    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name='versions', verbose_name=_('المستند'),
    )
    file = models.FileField(upload_to='documents/%Y/%m/', blank=True, verbose_name=_('الملف'))
    expiry_date = models.DateField(null=True, blank=True, verbose_name=_('تاريخ الانتهاء'))
    reason = models.CharField(max_length=10, choices=REASON_CHOICES, verbose_name=_('السبب'))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        verbose_name = _('نسخة سابقة')
        verbose_name_plural = _('النسخ السابقة')

    def __str__(self):
        return f'{self.document} ({self.get_reason_display()})'

    @property
    def file_name(self):
        return self.file.name.rsplit('/', 1)[-1] if self.file else ''

    @property
    def file_kind(self):
        return _file_kind(self.file)


class DocumentShare(models.Model):
    """A time-limited link that lets anyone who has it view/download one document
    without an account. Creating a new one for a document replaces any existing
    link (see views.document_share_create) — there's only ever one active link."""

    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name='shares', verbose_name=_('المستند'),
    )
    token = models.CharField(max_length=43, unique=True, editable=False, verbose_name=_('الرمز'))
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(verbose_name=_('تاريخ الانتهاء'))

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('رابط مشاركة')
        verbose_name_plural = _('روابط المشاركة')

    def __str__(self):
        return f'{self.document} -> {self.token}'

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(24)
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    def get_absolute_url(self):
        return reverse('documents:shared', args=[self.token])
