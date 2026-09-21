from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.utils.translation import gettext_lazy as _

from .models import User


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True, label=_('البريد الإلكتروني'))

    class Meta:
        model = User
        fields = ['username', 'email', 'phone', 'password1', 'password2']
        labels = {
            'username': _('اسم المستخدم'),
            'phone': _('رقم الهاتف'),
        }

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(_('هذا البريد الإلكتروني مستخدم بالفعل.'))
        return email


class LoginForm(AuthenticationForm):
    username = forms.CharField(label=_('اسم المستخدم'))
    password = forms.CharField(label=_('كلمة المرور'), widget=forms.PasswordInput)


class OTPForm(forms.Form):
    code = forms.CharField(
        label=_('رمز التحقق'), min_length=6, max_length=6,
        widget=forms.TextInput(attrs={'inputmode': 'numeric', 'autocomplete': 'one-time-code'}),
    )

    def clean_code(self):
        code = self.cleaned_data['code'].strip()
        if not code.isdigit():
            raise forms.ValidationError(_('الرمز يجب أن يتكون من أرقام فقط.'))
        return code


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'phone']
        labels = {
            'first_name': _('الاسم الأول'),
            'last_name': _('اسم العائلة'),
            'phone': _('رقم الهاتف'),
        }
