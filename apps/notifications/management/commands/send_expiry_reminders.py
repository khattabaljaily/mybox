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
# Idempotent: ReminderLog.unique_together stops a threshold firing twice, and a
# snooze is cleared as soon as it fires.


class Command(BaseCommand):
    help = (
        "Notify document owners whose documents are at one of their reminder thresholds "
        "(the document's own reminder days, else EXPIRY_REMINDER_DAYS) or whose snooze is due."
    )

    def handle(self, *args, **options):
        today = timezone.localdate()
        sent = 0

        # Threshold reminders. A document's own reminder days can be larger than the
        # default ones, so look ahead as far as the largest threshold in use.
        max_days = max([*settings.EXPIRY_REMINDER_DAYS, 90])
        upcoming = Document.objects.filter(
            expiry_date__gte=today, expiry_date__lte=today + timezone.timedelta(days=max_days),
        ).select_related('owner')
        for document in upcoming:
            days_left = (document.expiry_date - today).days
            if days_left not in document.reminder_thresholds:
                continue
            with transaction.atomic():
                _log, created = ReminderLog.objects.get_or_create(document=document, days_before=days_left)
                if not created:
                    continue
                self._notify(document, days_left)
                sent += 1

        # Snoozed reminders. `<= today` (not `==`) so a missed cron day doesn't lose them.
        for document in Document.objects.filter(snoozed_until__lte=today).select_related('owner'):
            with transaction.atomic():
                document.snoozed_until = None
                document.save(update_fields=['snoozed_until'])
                self._notify(document, (document.expiry_date - today).days if document.expiry_date else None)
                sent += 1

        self.stdout.write(self.style.SUCCESS(f'Sent {sent} expiry reminder(s).'))

    def _notify(self, document, days_left):
        if days_left is None:
            message = _('مستند "%(title)s" يحتاج إلى مراجعة. اضغط لرفع المستند الجديد.') % {'title': document.title}
        elif days_left < 0:
            message = _('مستند "%(title)s" انتهت صلاحيته. اضغط لرفع المستند الجديد.') % {'title': document.title}
        else:
            message = _('مستند "%(title)s" ينتهي خلال %(days)s يوم. اضغط لرفع المستند الجديد.') % {
                'title': document.title, 'days': days_left,
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
                subject=(
                    _('تنبيه: %(title)s ينتهي قريبًا') if days_left is not None and days_left >= 0
                    else _('تنبيه: مستند %(title)s يحتاج إلى تجديد')
                ) % {'title': document.title},
                message=render_to_string('notifications/expiry_reminder_email.txt', {
                    'document': document, 'days_before': days_left, 'renew_url': renew_url,
                }),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[document.owner.email],
                fail_silently=True,
            )
