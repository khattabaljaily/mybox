from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Notification(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications',
        verbose_name=_('المستخدم'),
    )
    title = models.CharField(max_length=200, verbose_name=_('العنوان'))
    message = models.CharField(max_length=300, verbose_name=_('الرسالة'))
    url = models.CharField(max_length=300, blank=True, verbose_name=_('الرابط'))
    is_read = models.BooleanField(default=False, verbose_name=_('مقروءة'))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('إشعار')
        verbose_name_plural = _('الإشعارات')

    def __str__(self):
        return self.title


class ReminderLog(models.Model):
    """Tracks which expiry-reminder thresholds already fired for a document,
    so send_expiry_reminders never notifies the same threshold twice in one cycle."""

    document = models.ForeignKey(
        'documents.Document', on_delete=models.CASCADE, related_name='reminders',
        verbose_name=_('المستند'),
    )
    days_before = models.PositiveSmallIntegerField(verbose_name=_('عدد أيام التنبيه'))
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['document', 'days_before']
        verbose_name = _('سجل تنبيه')
        verbose_name_plural = _('سجلات التنبيهات')
