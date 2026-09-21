import shutil
import tempfile
from datetime import timedelta
from io import StringIO

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import User
from apps.documents import services
from apps.documents.models import Document

from .models import Notification, ReminderLog

MEDIA_ROOT = tempfile.mkdtemp(prefix='mybox-tests-')


@override_settings(MEDIA_ROOT=MEDIA_ROOT, EXPIRY_REMINDER_DAYS=[30, 15, 7, 1])
class SendExpiryRemindersTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.user = User.objects.create_user('alice', 'alice@example.com', 'pw-12345-xyz')
        self.today = timezone.localdate()

    def doc(self, days_left, **kwargs):
        return Document.objects.create(
            owner=self.user, title=f'Doc {days_left}', expiry_date=self.today + timedelta(days=days_left),
            file=SimpleUploadedFile('d.pdf', b'%PDF-1.4'), **kwargs,
        )

    def run_command(self):
        call_command('send_expiry_reminders', stdout=StringIO())

    def test_default_thresholds_fire_once(self):
        self.doc(7)
        self.doc(8)  # not a threshold day
        self.run_command()
        self.run_command()  # idempotent
        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_custom_days_replace_the_defaults_for_that_document(self):
        on_custom = self.doc(60, reminder_days='60,3')
        on_default = self.doc(7, reminder_days='60,3')  # 7 is a default day, but this doc opted out of it
        self.run_command()
        self.assertEqual(Notification.objects.count(), 1)
        self.assertTrue(ReminderLog.objects.filter(document=on_custom, days_before=60).exists())
        self.assertFalse(ReminderLog.objects.filter(document=on_default).exists())

    def test_trashed_documents_are_not_reminded(self):
        services.trash_document(self.doc(7))
        self.run_command()
        self.assertEqual(Notification.objects.count(), 0)

    def test_snooze_fires_once_when_due_and_then_clears(self):
        doc = self.doc(20)
        Document.objects.filter(pk=doc.pk).update(snoozed_until=self.today)
        self.run_command()
        self.assertEqual(Notification.objects.count(), 1)
        self.assertIn('20', Notification.objects.get().message)
        doc.refresh_from_db()
        self.assertIsNone(doc.snoozed_until)
        self.run_command()
        self.assertEqual(Notification.objects.count(), 1)

    def test_snooze_not_yet_due_does_nothing(self):
        doc = self.doc(20)
        Document.objects.filter(pk=doc.pk).update(snoozed_until=self.today + timedelta(days=2))
        self.run_command()
        self.assertEqual(Notification.objects.count(), 0)

    def test_missed_snooze_day_is_caught_up(self):
        doc = self.doc(20)
        Document.objects.filter(pk=doc.pk).update(snoozed_until=self.today - timedelta(days=2))
        self.run_command()
        self.assertEqual(Notification.objects.count(), 1)

    def test_snooze_on_an_expired_document_says_so(self):
        doc = self.doc(-3)
        Document.objects.filter(pk=doc.pk).update(snoozed_until=self.today)
        self.run_command()
        self.assertIn('انتهت صلاحيته', Notification.objects.get().message)
        self.assertEqual(len(mail.outbox), 1)


class PurgeTrashCommandTests(TestCase):
    def test_runs_and_reports(self):
        out = StringIO()
        call_command('purge_trash', stdout=out)
        self.assertIn('Purged 0', out.getvalue())
