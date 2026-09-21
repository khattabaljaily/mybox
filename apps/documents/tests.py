import json
import shutil
import tempfile
from datetime import timedelta
from types import SimpleNamespace
from unittest import mock

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User

from . import extraction, services
from .forms import DocumentForm
from .models import Category, Document, DocumentShare, DocumentVersion

MEDIA_ROOT = tempfile.mkdtemp(prefix='mybox-tests-')


def _pdf(name='doc.pdf', body=b'%PDF-1.4 test'):
    return SimpleUploadedFile(name, body, content_type='application/pdf')


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class DocumentTestCase(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.user = User.objects.create_user('alice', 'alice@example.com', 'pw-12345-xyz')
        self.other = User.objects.create_user('bob', 'bob@example.com', 'pw-12345-xyz')
        self.client.force_login(self.user)
        self.doc = Document.objects.create(
            owner=self.user, title='Passport', file=_pdf('passport.pdf'),
            expiry_date=timezone.localdate() + timedelta(days=100),
        )


class TrashTests(DocumentTestCase):
    def test_delete_moves_to_trash_instead_of_removing(self):
        self.client.post(reverse('documents:delete', args=[self.doc.pk]))
        self.assertFalse(Document.objects.filter(pk=self.doc.pk).exists())
        trashed = Document.all_objects.get(pk=self.doc.pk)
        self.assertTrue(trashed.is_trashed)
        self.assertTrue(trashed.file.storage.exists(trashed.file.name))

    def test_trashed_document_is_hidden_and_unreachable(self):
        services.trash_document(self.doc)
        self.assertEqual(self.client.get(reverse('documents:detail', args=[self.doc.pk])).status_code, 404)
        self.assertNotContains(self.client.get(reverse('documents:list')), 'Passport')
        self.assertContains(self.client.get(reverse('documents:trash')), 'Passport')

    def test_trashing_revokes_share_link(self):
        share = DocumentShare.objects.create(document=self.doc, expires_at=timezone.now() + timedelta(days=1))
        services.trash_document(self.doc)
        self.assertEqual(self.client.get(share.get_absolute_url()).status_code, 404)

    def test_shared_view_refuses_trashed_document_even_if_link_survived(self):
        share = DocumentShare.objects.create(document=self.doc, expires_at=timezone.now() + timedelta(days=1))
        Document.all_objects.filter(pk=self.doc.pk).update(deleted_at=timezone.now())
        self.assertEqual(self.client.get(share.get_absolute_url()).status_code, 410)

    def test_restore(self):
        services.trash_document(self.doc)
        self.client.post(reverse('documents:restore', args=[self.doc.pk]))
        self.assertTrue(Document.objects.filter(pk=self.doc.pk).exists())

    def test_cannot_restore_or_purge_someone_elses_document(self):
        services.trash_document(self.doc)
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(reverse('documents:restore', args=[self.doc.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse('documents:purge', args=[self.doc.pk])).status_code, 404)
        self.assertTrue(Document.all_objects.filter(pk=self.doc.pk).exists())

    def test_purge_only_works_on_trashed_documents(self):
        self.assertEqual(self.client.post(reverse('documents:purge', args=[self.doc.pk])).status_code, 404)

    def test_purge_deletes_row_and_all_files(self):
        services.renew_document(self.doc, timezone.localdate() + timedelta(days=400), _pdf('new.pdf'))
        self.doc.refresh_from_db()
        version = self.doc.versions.get()
        current_name, old_name = self.doc.file.name, version.file.name
        storage = self.doc.file.storage
        services.trash_document(self.doc)
        self.client.post(reverse('documents:purge', args=[self.doc.pk]))
        self.assertFalse(Document.all_objects.filter(pk=self.doc.pk).exists())
        self.assertFalse(storage.exists(current_name))
        self.assertFalse(storage.exists(old_name))

    def test_empty_trash_only_touches_own_documents(self):
        mine = Document.objects.create(owner=self.user, title='Mine', file=_pdf())
        theirs = Document.objects.create(owner=self.other, title='Theirs', file=_pdf())
        services.trash_document(mine)
        services.trash_document(theirs)
        self.client.post(reverse('documents:trash_empty'))
        self.assertFalse(Document.all_objects.filter(pk=mine.pk).exists())
        self.assertTrue(Document.all_objects.filter(pk=theirs.pk).exists())

    def test_purge_expired_trash_respects_retention(self):
        old = Document.objects.create(owner=self.user, title='Old', file=_pdf())
        recent = Document.objects.create(owner=self.user, title='Recent', file=_pdf())
        Document.all_objects.filter(pk=old.pk).update(deleted_at=timezone.now() - timedelta(days=31))
        Document.all_objects.filter(pk=recent.pk).update(deleted_at=timezone.now() - timedelta(days=5))
        self.assertEqual(services.purge_expired_trash(), 1)
        self.assertFalse(Document.all_objects.filter(pk=old.pk).exists())
        self.assertTrue(Document.all_objects.filter(pk=recent.pk).exists())

    def test_archive_export_skips_trashed_documents(self):
        services.trash_document(self.doc)
        buffer = services.build_archive(Document.objects.filter(owner=self.user))
        self.assertEqual(buffer.read()[:2], b'PK')  # empty-but-valid zip
        import zipfile
        buffer.seek(0)
        self.assertEqual(zipfile.ZipFile(buffer).namelist(), [])


class VersionTests(DocumentTestCase):
    def test_detail_and_renew_pages_render_with_history(self):
        services.renew_document(self.doc, self.doc.expiry_date + timedelta(days=365), _pdf('second.pdf'))
        detail = self.client.get(reverse('documents:detail', args=[self.doc.pk]))
        self.assertContains(detail, 'mb-version')
        self.assertContains(detail, reverse('documents:snooze', args=[self.doc.pk]))
        self.assertEqual(self.client.get(reverse('documents:renew', args=[self.doc.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse('documents:edit', args=[self.doc.pk])).status_code, 200)

    def test_renew_with_new_file_moves_old_file_into_history(self):
        old_name, old_expiry = self.doc.file.name, self.doc.expiry_date
        new_expiry = old_expiry + timedelta(days=365)
        self.client.post(reverse('documents:renew', args=[self.doc.pk]), {'expiry_date': new_expiry.isoformat(), 'file': _pdf('renewed.pdf')})
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.expiry_date, new_expiry)
        self.assertNotEqual(self.doc.file.name, old_name)
        version = self.doc.versions.get()
        self.assertEqual(version.file.name, old_name)
        self.assertEqual(version.expiry_date, old_expiry)
        self.assertEqual(version.reason, DocumentVersion.REASON_RENEWED)

    def test_renew_without_file_records_only_the_old_expiry(self):
        old_name, old_expiry = self.doc.file.name, self.doc.expiry_date
        services.renew_document(self.doc, old_expiry + timedelta(days=365))
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.file.name, old_name)
        version = self.doc.versions.get()
        self.assertFalse(version.file)
        self.assertEqual(version.expiry_date, old_expiry)

    def test_renew_rejects_invalid_date_without_touching_document(self):
        response = self.client.post(reverse('documents:renew', args=[self.doc.pk]), {'expiry_date': 'not-a-date'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.doc.versions.count(), 0)

    def test_editing_with_a_new_file_archives_the_old_one(self):
        old_name = self.doc.file.name
        response = self.client.post(reverse('documents:edit', args=[self.doc.pk]), {
            'title': 'Passport', 'expiry_date': self.doc.expiry_date.isoformat(), 'file': _pdf('replacement.pdf'),
        })
        self.assertEqual(response.status_code, 302)
        self.doc.refresh_from_db()
        self.assertNotEqual(self.doc.file.name, old_name)
        version = self.doc.versions.get()
        self.assertEqual((version.file.name, version.reason), (old_name, DocumentVersion.REASON_REPLACED))

    def test_editing_without_a_new_file_creates_no_version(self):
        self.client.post(reverse('documents:edit', args=[self.doc.pk]), {
            'title': 'Passport (renamed)', 'expiry_date': self.doc.expiry_date.isoformat(),
        })
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.title, 'Passport (renamed)')
        self.assertEqual(self.doc.versions.count(), 0)

    def test_restore_version_swaps_files_and_keeps_the_current_one_as_history(self):
        first_name = self.doc.file.name
        services.renew_document(self.doc, self.doc.expiry_date + timedelta(days=365), _pdf('second.pdf'))
        self.doc.refresh_from_db()
        second_name = self.doc.file.name
        version = self.doc.versions.get()
        self.client.post(reverse('documents:version_restore', args=[self.doc.pk, version.pk]))
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.file.name, first_name)
        remaining = self.doc.versions.get()
        self.assertEqual((remaining.file.name, remaining.reason), (second_name, DocumentVersion.REASON_RESTORED))

    def test_cannot_restore_a_version_of_someone_elses_document(self):
        services.renew_document(self.doc, self.doc.expiry_date + timedelta(days=365), _pdf('second.pdf'))
        version = self.doc.versions.get()
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(reverse('documents:version_restore', args=[self.doc.pk, version.pk])).status_code, 404)

    def test_archive_export_includes_old_versions(self):
        import zipfile
        services.renew_document(self.doc, self.doc.expiry_date + timedelta(days=365), _pdf('second.pdf'))
        names = zipfile.ZipFile(services.build_archive(Document.objects.filter(owner=self.user))).namelist()
        self.assertEqual(len(names), 2)
        self.assertTrue(any('/versions/' in n and n.endswith('passport.pdf') for n in names))


class ReminderSettingsTests(DocumentTestCase):
    def _form(self, **extra):
        data = {'title': 'Passport', 'expiry_date': self.doc.expiry_date.isoformat(), **extra}
        return DocumentForm(data, instance=self.doc, owner=self.user)

    def test_defaults_when_no_custom_days(self):
        self.assertEqual(self.doc.reminder_thresholds, [30, 15, 7, 1])

    def test_custom_days_are_saved_sorted_and_used(self):
        form = self._form(custom_reminders=['7', '90', '30'])
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.reminder_days, '90,30,7')
        self.assertEqual(self.doc.reminder_thresholds, [90, 30, 7])

    def test_unchecking_everything_returns_to_defaults(self):
        self.doc.reminder_days = '90'
        self.doc.save()
        form = self._form()
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.reminder_days, '')

    def test_form_prechecks_existing_custom_days(self):
        self.doc.reminder_days = '60,7'
        self.assertEqual(sorted(DocumentForm(instance=self.doc, owner=self.user).fields['custom_reminders'].initial), ['60', '7'])

    def test_form_rejects_days_outside_the_offered_choices(self):
        self.assertFalse(self._form(custom_reminders=['999']).is_valid())


class SnoozeTests(DocumentTestCase):
    def snooze(self, days):
        return self.client.post(reverse('documents:snooze', args=[self.doc.pk]), {'days': days})

    def test_snooze_sets_date(self):
        self.snooze(3)
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.snoozed_until, timezone.localdate() + timedelta(days=3))

    def test_snooze_never_goes_past_the_expiry(self):
        self.doc.expiry_date = timezone.localdate() + timedelta(days=2)
        self.doc.save()
        self.snooze(7)
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.snoozed_until, self.doc.expiry_date)

    def test_invalid_snooze_is_rejected(self):
        for bad in ('0', '30', 'abc', ''):
            self.snooze(bad)
        self.doc.refresh_from_db()
        self.assertIsNone(self.doc.snoozed_until)

    def test_renewing_clears_the_snooze(self):
        self.snooze(3)
        self.doc.refresh_from_db()
        services.renew_document(self.doc, self.doc.expiry_date + timedelta(days=365))
        self.doc.refresh_from_db()
        self.assertIsNone(self.doc.snoozed_until)

    def test_cannot_snooze_someone_elses_document(self):
        self.client.force_login(self.other)
        self.assertEqual(self.snooze(3).status_code, 404)


FAKE_JSON = json.dumps({
    'title': 'Passport - Alice', 'category_id': None,
    'issue_date': '2020-01-05', 'expiry_date': '2030-01-04',
})


def _fake_response(payload=FAKE_JSON, stop_reason='end_turn'):
    return SimpleNamespace(
        stop_reason=stop_reason, _request_id='req_test',
        content=[SimpleNamespace(type='text', text=payload)],
    )


def _png():
    import io
    from PIL import Image
    out = io.BytesIO()
    Image.new('RGB', (40, 30), 'white').save(out, format='PNG')
    return SimpleUploadedFile('scan.png', out.getvalue(), content_type='image/png')


@override_settings(MEDIA_ROOT=MEDIA_ROOT, AI_EXTRACTION_ENABLED=True, ANTHROPIC_API_KEY='test-key', AI_EXTRACTION_HOURLY_LIMIT=3)
class ExtractionTests(DocumentTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.url = reverse('documents:extract')
        self.cat = Category.objects.filter(owner__isnull=True).first() or Category.objects.create(name_ar='هوية', name_en='ID')

    def _patched_client(self, response=None, error=None):
        client = mock.MagicMock()
        if error:
            client.messages.create.side_effect = error
        else:
            client.messages.create.return_value = response or _fake_response()
        return mock.patch.object(extraction.anthropic, 'Anthropic', return_value=client), client

    def test_returns_suggestions_for_a_pdf(self):
        patcher, client = self._patched_client()
        with patcher:
            response = self.client.post(self.url, {'file': _pdf()})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['expiry_date'], '2030-01-04')
        self.assertEqual(response.json()['title'], 'Passport - Alice')
        kwargs = client.messages.create.call_args.kwargs
        self.assertEqual(kwargs['messages'][0]['content'][0]['type'], 'document')
        self.assertEqual(kwargs['output_config']['format']['type'], 'json_schema')

    def test_images_are_sent_as_jpeg_image_blocks(self):
        patcher, client = self._patched_client()
        with patcher:
            self.client.post(self.url, {'file': _png()})
        block = client.messages.create.call_args.kwargs['messages'][0]['content'][0]
        self.assertEqual((block['type'], block['source']['media_type']), ('image', 'image/jpeg'))

    def test_bad_model_output_is_sanitised(self):
        payload = json.dumps({'title': 'X', 'category_id': 99999, 'issue_date': '2031-01-01', 'expiry_date': '2030-01-01'})
        patcher, _client = self._patched_client(_fake_response(payload))
        with patcher:
            body = self.client.post(self.url, {'file': _pdf()}).json()
        self.assertIsNone(body['category_id'])       # id not in the user's list
        self.assertIsNone(body['expiry_date'])       # expiry before issue → dropped
        self.assertEqual(body['issue_date'], '2031-01-01')

    def test_valid_category_id_is_kept_and_garbage_dates_dropped(self):
        payload = json.dumps({'title': None, 'category_id': self.cat.pk, 'issue_date': 'tomorrow', 'expiry_date': None})
        patcher, _client = self._patched_client(_fake_response(payload))
        with patcher:
            body = self.client.post(self.url, {'file': _pdf()}).json()
        self.assertEqual(body['category_id'], self.cat.pk)
        self.assertIsNone(body['issue_date'])
        self.assertIsNone(body['title'])

    def test_refusal_or_truncation_yields_empty_result(self):
        patcher, _client = self._patched_client(_fake_response('', stop_reason='refusal'))
        with patcher:
            self.assertEqual(self.client.post(self.url, {'file': _pdf()}).json(), {})

    def test_unsupported_file_is_422_and_never_calls_the_api(self):
        patcher, client = self._patched_client()
        with patcher:
            response = self.client.post(self.url, {'file': SimpleUploadedFile('a.txt', b'hello')})
        self.assertEqual(response.status_code, 422)
        client.messages.create.assert_not_called()

    def test_oversized_file_is_skipped(self):
        patcher, client = self._patched_client()
        with patcher, override_settings(AI_EXTRACTION_MAX_BYTES=10):
            response = self.client.post(self.url, {'file': _pdf(body=b'%PDF' + b'0' * 100)})
        self.assertEqual(response.status_code, 422)
        client.messages.create.assert_not_called()

    def test_api_failure_is_a_502_not_a_crash(self):
        patcher, _client = self._patched_client(error=extraction.anthropic.APIConnectionError(request=mock.MagicMock()))
        with patcher, self.assertLogs(extraction.logger, level='ERROR'):
            response = self.client.post(self.url, {'file': _pdf()})
        self.assertEqual((response.status_code, response.json()['error']), (502, 'failed'))

    def test_rate_limit(self):
        patcher, _client = self._patched_client()
        with patcher:
            codes = [self.client.post(self.url, {'file': _pdf()}).status_code for _ in range(4)]
        self.assertEqual(codes, [200, 200, 200, 429])

    def test_requires_login_and_post(self):
        self.client.logout()
        self.assertEqual(self.client.post(self.url, {'file': _pdf()}).status_code, 302)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.url).status_code, 405)

    @override_settings(AI_EXTRACTION_ENABLED=False)
    def test_disabled_without_api_key(self):
        response = self.client.post(self.url, {'file': _pdf()})
        self.assertEqual((response.status_code, response.json()['error']), (503, 'disabled'))
        self.assertNotContains(self.client.get(reverse('documents:create')), 'data-extract-url')

    def test_create_form_advertises_extraction_when_enabled(self):
        self.assertContains(self.client.get(reverse('documents:create')), 'data-extract-url')


class FileAccessTests(DocumentTestCase):
    """Uploads must only be reachable through permission-checked views, never via /media/."""

    def file_url(self):
        return reverse('documents:file', args=[self.doc.pk])

    def test_owner_can_view_inline_with_safe_headers(self):
        response = self.client.get(self.file_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b''.join(response.streaming_content), b'%PDF-1.4 test')
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response['Content-Disposition'].startswith('inline'))
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(response['X-Frame-Options'], 'SAMEORIGIN')  # the detail-page preview iframe

    def test_download_flag_forces_attachment(self):
        self.assertTrue(self.client.get(self.file_url() + '?download=1')['Content-Disposition'].startswith('attachment'))

    def test_non_previewable_types_are_always_attachments(self):
        page = Document.objects.create(
            owner=self.user, title='Evil', file=SimpleUploadedFile('x.html', b'<script>alert(1)</script>'),
        )
        response = self.client.get(reverse('documents:file', args=[page.pk]))
        self.assertTrue(response['Content-Disposition'].startswith('attachment'))

    def test_other_users_and_anonymous_are_refused(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.file_url()).status_code, 404)
        self.client.logout()
        response = self.client.get(self.file_url())
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response['Location'])

    def test_trashed_document_file_is_unreachable(self):
        services.trash_document(self.doc)
        self.assertEqual(self.client.get(self.file_url()).status_code, 404)

    def test_media_url_no_longer_serves_anything(self):
        self.assertEqual(self.client.get('/media/' + self.doc.file.name).status_code, 404)

    def test_pages_never_link_to_media(self):
        services.renew_document(self.doc, self.doc.expiry_date + timedelta(days=365), _pdf('second.pdf'))
        for url in (reverse('documents:detail', args=[self.doc.pk]), reverse('documents:edit', args=[self.doc.pk])):
            self.assertNotContains(self.client.get(url), '/media/')

    def test_missing_file_on_disk_is_404_not_500(self):
        self.doc.file.storage.delete(self.doc.file.name)
        self.assertEqual(self.client.get(self.file_url()).status_code, 404)

    def test_version_file_is_owner_only(self):
        services.renew_document(self.doc, self.doc.expiry_date + timedelta(days=365), _pdf('second.pdf'))
        version = self.doc.versions.get()
        url = reverse('documents:version_file', args=[self.doc.pk, version.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_expiry_only_version_has_no_file(self):
        services.renew_document(self.doc, self.doc.expiry_date + timedelta(days=365))
        version = self.doc.versions.get()
        self.assertEqual(self.client.get(reverse('documents:version_file', args=[self.doc.pk, version.pk])).status_code, 404)


class SharedFileAccessTests(DocumentTestCase):
    def setUp(self):
        super().setUp()
        self.share = DocumentShare.objects.create(document=self.doc, expires_at=timezone.now() + timedelta(days=1))
        self.client.logout()  # share links are for people without an account
        self.url = reverse('documents:shared_file', args=[self.share.token])

    def test_link_holder_can_view_and_download(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response['Content-Disposition'].startswith('inline'))
        self.assertTrue(self.client.get(self.url + '?download=1')['Content-Disposition'].startswith('attachment'))

    def test_shared_page_points_at_the_share_file_view_not_media(self):
        page = self.client.get(self.share.get_absolute_url())
        self.assertContains(page, self.url)
        self.assertNotContains(page, '/media/')

    def test_a_share_token_only_opens_its_own_document(self):
        other_doc = Document.objects.create(owner=self.user, title='Private', file=_pdf('private.pdf', b'%PDF-private'))
        self.assertNotEqual(b''.join(self.client.get(self.url).streaming_content), b'%PDF-private')
        self.assertEqual(self.client.get(reverse('documents:file', args=[other_doc.pk])).status_code, 302)

    def test_expired_revoked_and_trashed_links_stop_working(self):
        DocumentShare.objects.filter(pk=self.share.pk).update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.client.get(self.url).status_code, 404)
        DocumentShare.objects.filter(pk=self.share.pk).update(expires_at=timezone.now() + timedelta(days=1))
        self.assertEqual(self.client.get(self.url).status_code, 200)
        Document.all_objects.filter(pk=self.doc.pk).update(deleted_at=timezone.now())
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.share.delete()
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_unknown_token(self):
        self.assertEqual(self.client.get(reverse('documents:shared_file', args=['nope'])).status_code, 404)
