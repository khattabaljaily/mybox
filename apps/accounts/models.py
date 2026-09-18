import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    phone = models.CharField(max_length=20, blank=True, verbose_name=_('رقم الهاتف'))

    class Meta:
        verbose_name = _('مستخدم')
        verbose_name_plural = _('المستخدمون')

    def __str__(self):
        return self.get_full_name() or self.username


class LoginOTP(models.Model):
    """A one-time code emailed at login time, as a second factor on top of the password."""

    VALIDITY_MINUTES = 10

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='login_otps',
        verbose_name=_('المستخدم'),
    )
    code = models.CharField(max_length=6, verbose_name=_('الرمز'))
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False, verbose_name=_('تم استخدامه'))

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('رمز تحقق الدخول')
        verbose_name_plural = _('رموز تحقق الدخول')

    def __str__(self):
        return f'{self.user} - {self.code}'

    @property
    def is_expired(self):
        return timezone.now() > self.created_at + timedelta(minutes=self.VALIDITY_MINUTES)

    @staticmethod
    def generate_code():
        return ''.join(secrets.choice('0123456789') for _ in range(6))
