import io
import zipfile

from django.db import transaction
from django.utils import timezone


@transaction.atomic
def renew_document(document, new_expiry_date, new_file=None):
    """Push a document's expiry forward and clear its past reminders so the
    same reminder days (30/15/7/1) fire again for the new expiry date."""
    document.expiry_date = new_expiry_date
    if new_file is not None:
        document.file = new_file
    document.save(update_fields=['expiry_date', 'file', 'updated_at'] if new_file else ['expiry_date', 'updated_at'])
    document.reminders.all().delete()
    return document


def build_archive(documents):
    """Zip the given documents' files (each under its own folder) for export/backup."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        for document in documents:
            if not document.file:
                continue
            folder = f'{document.pk}_{document.title}'.replace('/', '-')
            arcname = f'{folder}/{document.file.name.rsplit("/", 1)[-1]}'
            with document.file.open('rb') as fh:
                archive.writestr(arcname, fh.read())
    buffer.seek(0)
    return buffer


def expiring_within(queryset, days_ahead):
    today = timezone.localdate()
    horizon = today + timezone.timedelta(days=days_ahead)
    return queryset.filter(expiry_date__isnull=False, expiry_date__gte=today, expiry_date__lte=horizon)
