from django.contrib.sessions.models import Session
from django.test import Client, TestCase
from django.urls import reverse

from .models import User

OLD_PASSWORD = 'old-pass-12345'
NEW_PASSWORD = 'brand-new-pass-98765'


class ProfileTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('alice', 'alice@example.com', OLD_PASSWORD)
        self.client.force_login(self.user)

    def test_requires_login(self):
        for name in ('accounts:profile', 'accounts:password_change'):
            response = Client().get(reverse(name))
            self.assertEqual(response.status_code, 302)
            self.assertIn(reverse('accounts:login'), response['Location'])

    def test_update_personal_details_but_not_email(self):
        self.client.post(reverse('accounts:profile'), {
            'first_name': 'Alice', 'last_name': 'Ali', 'phone': '0500000000', 'email': 'evil@example.com',
        })
        self.user.refresh_from_db()
        self.assertEqual((self.user.first_name, self.user.last_name, self.user.phone), ('Alice', 'Ali', '0500000000'))
        self.assertEqual(self.user.email, 'alice@example.com')  # email is the 2FA channel

    def test_profile_shows_two_factor_status(self):
        self.assertContains(self.client.get(reverse('accounts:profile')), 'mb-pill--success')
        self.user.email = ''
        self.user.save()
        self.assertContains(self.client.get(reverse('accounts:profile')), 'mb-pill--warning')


class PasswordChangeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('alice', 'alice@example.com', OLD_PASSWORD)
        self.client.force_login(self.user)
        self.url = reverse('accounts:password_change')

    def change(self, old=OLD_PASSWORD, new=NEW_PASSWORD, confirm=None):
        return self.client.post(self.url, {
            'old_password': old, 'new_password1': new, 'new_password2': confirm or new,
        })

    def test_changes_password_and_keeps_current_session(self):
        response = self.change()
        self.assertRedirects(response, reverse('accounts:profile'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(NEW_PASSWORD))
        self.assertEqual(self.client.get(reverse('accounts:profile')).status_code, 200)  # still signed in

    def test_wrong_current_password_is_rejected(self):
        response = self.change(old='wrong-password')
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(OLD_PASSWORD))

    def test_weak_or_mismatched_new_password_is_rejected(self):
        for new, confirm in (('12345678', None), ('short', None), (NEW_PASSWORD, 'different-pass-1')):
            self.assertEqual(self.change(new=new, confirm=confirm).status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(OLD_PASSWORD))

    def test_other_devices_are_signed_out(self):
        other_device = Client()
        other_device.force_login(self.user)
        self.assertEqual(other_device.get(reverse('accounts:profile')).status_code, 200)
        self.change()
        self.assertEqual(other_device.get(reverse('accounts:profile')).status_code, 302)


class SessionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('alice', 'alice@example.com', OLD_PASSWORD)
        self.other_user = User.objects.create_user('bob', 'bob@example.com', OLD_PASSWORD)
        self.client.force_login(self.user)

    def test_sign_out_other_devices_keeps_this_one_and_other_users_alone(self):
        phone, bobs = Client(), Client()
        phone.force_login(self.user)
        bobs.force_login(self.other_user)
        self.client.post(reverse('accounts:sign_out_others'))
        self.assertEqual(self.client.get(reverse('accounts:profile')).status_code, 200)
        self.assertEqual(phone.get(reverse('accounts:profile')).status_code, 302)
        self.assertEqual(bobs.get(reverse('accounts:profile')).status_code, 200)

    def test_only_accepts_post(self):
        self.assertEqual(self.client.get(reverse('accounts:sign_out_others')).status_code, 405)
        self.assertEqual(Session.objects.count(), 1)
