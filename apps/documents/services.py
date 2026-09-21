import io
import zipfile
from datetime import timedelta

from django.conf import settings
from django.core.files.storage import default_storage
from django.db import transaction
from django.utils import timezone

from .models import Document, DocumentVersion

SNOOZE_DAY_CHOICES = (1, 3, 7)


def archive_version(document, reason, file_name=None, expiry_date=None):
    """Record the document's current state (or the given pre-change state) as a version.

    Pass `file_name`/`expiry_date` when the document row has already been
    modified in memory and the values to keep are the ones from before.
    """
    return DocumentVersion.objects.create(
        document=document,
        file=file_name if file_name is not None else '',
        expiry_date=expiry_date,
        reason=reason,
    )


@transaction.atomic
def renew_document(document, new_expiry_date, new_file=None):
    """Push a document's expiry forward and clear its past reminders so the
    same reminder days (30/15/7/1) fire again for the new expiry date. The
    previous expiry (and file, when replaced) is kept in the version history."""
    archive_version(
        document, DocumentVersion.REASON_RENEWED,
        file_name=document.file.name if new_file is not None and document.file else '',
        expiry_date=document.expiry_date,
    )
    document.expiry_date = new_expiry_date
    document.snoozed_until = None
    update_fields = ['expiry_date', 'snoozed_until', 'updated_at']
    if new_file is not None:
        document.file = new_file
        update_fields.append('file')
    document.save(update_fields=update_fields)
    document.reminders.all().delete()
    return document


def archive_replaced_file(document, old_file_name, old_expiry_date):
    """Call after an edit that may have swapped the file: if it did, keep the old one."""
    if old_file_name and document.file.name != old_file_name:
        archive_version(
            document, DocumentVersion.REASON_REPLACED,
            file_name=old_file_name, expiry_date=old_expiry_date,
        )


@transaction.atomic
def restore_version(document, version):
    """Make an old version's file the current one (the current file becomes a version)."""
    if not version.file:
        raise ValueError('This version has no file to restore.')
    archive_version(
        document, DocumentVersion.REASON_RESTORED,
        file_name=document.file.name, expiry_date=document.expiry_date,
    )
    document.file = version.file.name
    document.save(update_fields=['file', 'updated_at'])
    version.delete()
    return document


def snooze_document(document, days):
    """Postpone the reminder: notify again in `days` days (never later than the expiry itself)."""
    until = timezone.localdate() + timedelta(days=days)
    if document.expiry_date and document.expiry_date >= timezone.localdate():
        until = min(until, document.expiry_date)
    document.snoozed_until = until
    document.save(update_fields=['snoozed_until', 'updated_at'])
    return until


@transaction.atomic
def trash_document(document):
    document.deleted_at = timezone.now()
    document.save(update_fields=['deleted_at', 'updated_at'])
    document.shares.all().delete()  # a trashed document must not stay reachable by link
    return document


def restore_document(document):
    document.deleted_at = None
    document.save(update_fields=['deleted_at', 'updated_at'])
    return document


def purge_document(document):
    """Delete the row and every file it owns (current file + all versions). Irreversible."""
    file_names = [v.file.name for v in document.versions.all() if v.file]
    if document.file:
        file_names.append(document.file.name)
    document.delete()
    for name in file_names:
        default_storage.delete(name)


def purge_expired_trash(now=None):
    cutoff = (now or timezone.now()) - timedelta(days=settings.TRASH_RETENTION_DAYS)
    expired = list(Document.all_objects.filter(deleted_at__isnull=False, deleted_at__lt=cutoff))
    for document in expired:
        purge_document(document)
    return len(expired)


def trash_days_left(document):
    """Whole days until a trashed document is purged for good."""
    purge_at = document.deleted_at + timedelta(days=settings.TRASH_RETENTION_DAYS)
    return max(0, (purge_at - timezone.now()).days)


def build_archive(documents):
    """Zip the given documents' files (each under its own folder) for export/backup,
    including previous file versions under a `versions/` subfolder."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        for document in documents.prefetch_related('versions'):
            folder = f'{document.pk}_{document.title}'.replace('/', '-')
            if document.file:
                arcname = f'{folder}/{document.file.name.rsplit("/", 1)[-1]}'
                with document.file.open('rb') as fh:
                    archive.writestr(arcname, fh.read())
            for version in document.versions.all():
                if not version.file:
                    continue
                stamp = timezone.localtime(version.created_at).strftime('%Y%m%d-%H%M%S')
                arcname = f'{folder}/versions/{stamp}_{version.file_name}'
                with version.file.open('rb') as fh:
                    archive.writestr(arcname, fh.read())
    buffer.seek(0)
    return buffer


def expiring_within(queryset, days_ahead):
    today = timezone.localdate()
    horizon = today + timezone.timedelta(days=days_ahead)
    return queryset.filter(expiry_date__isnull=False, expiry_date__gte=today, expiry_date__lte=horizon)
