from django.conf import settings
from django.core.management.base import BaseCommand

from apps.documents import services

# Run daily alongside send_expiry_reminders.


class Command(BaseCommand):
    help = "Permanently delete documents (and their files) that have been in the trash longer than TRASH_RETENTION_DAYS."

    def handle(self, *args, **options):
        purged = services.purge_expired_trash()
        self.stdout.write(self.style.SUCCESS(
            f'Purged {purged} document(s) trashed more than {settings.TRASH_RETENTION_DAYS} days ago.'
        ))
