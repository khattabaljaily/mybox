import shutil
import tempfile
from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.documents import services
from apps.documents.models import Document

MEDIA_ROOT = tempfile.mkdtemp(prefix='mybox-tests-')


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class ApiTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.user = User.objects.create_user('alice', 'alice@example.com', 'old-pass-12345')
        self.other = User.objects.create_user('bob', 'bob@example.com', 'old-pass-12345')
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.doc = Document.objects.create(
            owner=self.user, title='Passport', file=SimpleUploadedFile('p.pdf', b'%PDF-1.4'),
            expiry_date=timezone.localdate() + timedelta(days=100),
        )

    def test_delete_trashes_then_restore_and_purge(self):
        self.assertEqual(self.api.delete(f'/api/documents/{self.doc.pk}/').status_code, 204)
        self.assertEqual(self.api.get('/api/documents/').json(), [])
        self.assertEqual(len(self.api.get('/api/documents/trash/').json()), 1)
        self.assertEqual(self.api.post(f'/api/documents/{self.doc.pk}/restore/').status_code, 200)
        self.assertEqual(len(self.api.get('/api/documents/').json()), 1)
        self.assertEqual(self.api.delete(f'/api/documents/{self.doc.pk}/purge/').status_code, 404)  # not trashed
        self.api.delete(f'/api/documents/{self.doc.pk}/')
        self.assertEqual(self.api.delete(f'/api/documents/{self.doc.pk}/purge/').status_code, 204)
        self.assertFalse(Document.all_objects.filter(pk=self.doc.pk).exists())

    def test_other_users_cannot_touch_trash(self):
        self.api.delete(f'/api/documents/{self.doc.pk}/')
        self.api.force_authenticate(self.other)
        self.assertEqual(self.api.get('/api/documents/trash/').json(), [])
        self.assertEqual(self.api.post(f'/api/documents/{self.doc.pk}/restore/').status_code, 404)

    def test_renew_creates_version_visible_in_history(self):
        new_expiry = (self.doc.expiry_date + timedelta(days=365)).isoformat()
        self.assertEqual(self.api.post(f'/api/documents/{self.doc.pk}/renew/', {'expiry_date': new_expiry}, format='multipart').status_code, 200)
        versions = self.api.get(f'/api/documents/{self.doc.pk}/versions/').json()
        self.assertEqual(len(versions), 1)
        self.assertEqual(versions[0]['reason'], 'renewed')

    def test_renew_rejects_garbage_date(self):
        self.assertEqual(self.api.post(f'/api/documents/{self.doc.pk}/renew/', {'expiry_date': 'nope'}, format='multipart').status_code, 400)

    def test_snooze(self):
        response = self.api.post(f'/api/documents/{self.doc.pk}/snooze/', {'days': 3}, format='json')
        self.assertEqual(response.json()['snoozed_until'], (timezone.localdate() + timedelta(days=3)).isoformat())
        self.assertEqual(self.api.post(f'/api/documents/{self.doc.pk}/snooze/', {'days': 5}, format='json').status_code, 400)

    def test_custom_reminder_days_validation_and_normalisation(self):
        ok = self.api.patch(f'/api/documents/{self.doc.pk}/', {'reminder_days': '7, 60,30,7'}, format='json')
        self.assertEqual(ok.json()['reminder_days_list'], [60, 30, 7])
        bad = self.api.patch(f'/api/documents/{self.doc.pk}/', {'reminder_days': '7,abc'}, format='json')
        self.assertEqual(bad.status_code, 400)

    def test_editing_with_new_file_archives_the_old_one(self):
        self.api.patch(f'/api/documents/{self.doc.pk}/', {'file': SimpleUploadedFile('n.pdf', b'%PDF-1.4 new')}, format='multipart')
        self.assertEqual(self.doc.versions.count(), 1)

    def test_change_password(self):
        url = '/api/auth/change-password/'
        self.assertEqual(self.api.post(url, {'old_password': 'wrong', 'new_password': 'brand-new-pass-98765'}, format='json').status_code, 400)
        self.assertEqual(self.api.post(url, {'old_password': 'old-pass-12345', 'new_password': '12345678'}, format='json').status_code, 400)
        self.assertEqual(self.api.post(url, {'old_password': 'old-pass-12345', 'new_password': 'brand-new-pass-98765'}, format='json').status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('brand-new-pass-98765'))

    def test_update_profile_cannot_change_email(self):
        response = self.api.patch('/api/auth/me/', {'first_name': 'Al', 'email': 'evil@example.com'}, format='json')
        self.assertEqual((response.json()['first_name'], response.json()['email']), ('Al', 'alice@example.com'))

    @override_settings(AI_EXTRACTION_ENABLED=False)
    def test_extract_disabled(self):
        response = self.api.post('/api/documents/extract/', {'file': SimpleUploadedFile('p.pdf', b'%PDF-1.4')}, format='multipart')
        self.assertEqual((response.status_code, response.json()['error']), (503, 'disabled'))

    def test_file_url_is_a_signed_link_and_raw_media_path_is_never_exposed(self):
        body = self.api.get(f'/api/documents/{self.doc.pk}/').json()
        self.assertNotIn('file', body)
        self.assertNotIn('/media/', str(body))
        self.assertIn('/documents/f/', body['file_url'])
        # Works without any credentials (image/PDF widgets can't send headers)…
        response = APIClient().get(body['file_url'])
        self.assertEqual((response.status_code, response['Content-Type']), (200, 'application/pdf'))

    def test_signed_link_is_tamper_proof_and_expires(self):
        from unittest import mock
        from apps.documents import files
        url = self.api.get(f'/api/documents/{self.doc.pk}/').json()['file_url']
        anon = APIClient()
        self.assertEqual(anon.get(url[:-2] + 'x/').status_code, 404)
        with mock.patch.object(files, 'SIGNED_URL_MAX_AGE', -1):
            self.assertEqual(anon.get(url).status_code, 404)

    def test_signed_link_dies_when_document_is_trashed(self):
        url = self.api.get(f'/api/documents/{self.doc.pk}/').json()['file_url']
        services.trash_document(self.doc)
        self.assertEqual(APIClient().get(url).status_code, 404)

    def test_signed_version_link(self):
        services.renew_document(self.doc, self.doc.expiry_date + timedelta(days=365), SimpleUploadedFile('n.pdf', b'%PDF-1.4 new'))
        version = self.api.get(f'/api/documents/{self.doc.pk}/versions/').json()[0]
        self.assertEqual(APIClient().get(version['file_url']).status_code, 200)

    def test_endpoints_require_auth(self):
        anonymous = APIClient()
        for path in ('/api/documents/trash/', f'/api/documents/{self.doc.pk}/versions/'):
            self.assertEqual(anonymous.get(path).status_code, 401)
