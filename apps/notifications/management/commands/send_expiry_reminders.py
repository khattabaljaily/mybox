from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.db import transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.documents.models import Document
from apps.notifications.models import Notification, ReminderLog

# Run daily (cron/systemd timer/Celery beat — whatever the deployment uses).
# Idempotent: ReminderLog.unique_together stops a threshold firing twice.


class Command(BaseCommand):
    help = "Notify document owners whose documents are approaching (or renewing) their EXPIRY_REMINDER_DAYS thresholds."

    def handle(self, *args, **options):
        today = timezone.localdate()
        sent = 0

        for days_before in settings.EXPIRY_REMINDER_DAYS:
            target_date = today + timezone.timedelta(days=days_before)
            documents = Document.objects.filter(expiry_date=target_date).select_related('owner')

            for document in documents:
                with transaction.atomic():
                    _log, created = ReminderLog.objects.get_or_create(
                        document=document, days_before=days_before,
                    )
                    if not created:
                        continue

                    message = _('مستند "%(title)s" ينتهي خلال %(days)s يوم. اضغط لرفع المستند الجديد.') % {
                        'title': document.title, 'days': days_before,
                    }
                    Notification.objects.create(
                        user=document.owner,
                        title=_('اقتراب انتهاء مستند — يلزم التجديد'),
                        message=message,
                        url=reverse('documents:renew', args=[document.pk]),
                    )
                    if document.owner.email:
                        renew_url = settings.SITE_URL + reverse('documents:renew', args=[document.pk])
                        send_mail(
                            subject=_('تنبيه: %(title)s ينتهي قريبًا') % {'title': document.title},
                            message=render_to_string('notifications/expiry_reminder_email.txt', {
                                'document': document, 'days_before': days_before, 'renew_url': renew_url,
                            }),
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            recipient_list=[document.owner.email],
                            fail_silently=True,
                        )
                    sent += 1

        self.stdout.write(self.style.SUCCESS(f'Sent {sent} expiry reminder(s).'))
