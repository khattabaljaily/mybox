from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.views import LoginView, LogoutView
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.contrib import messages

from .forms import LoginForm, OTPForm, RegisterForm
from .models import LoginOTP, User

OTP_MAX_ATTEMPTS = 5
OTP_RESEND_COOLDOWN_SECONDS = 30


def _send_login_otp(user):
    LoginOTP.objects.filter(user=user, is_used=False).update(is_used=True)
    code = LoginOTP.generate_code()
    LoginOTP.objects.create(user=user, code=code)
    send_mail(
        subject=render_to_string('accounts/login_otp_subject.txt').strip(),
        message=render_to_string('accounts/login_otp_email.txt', {
            'code': code, 'validity_minutes': LoginOTP.VALIDITY_MINUTES,
        }),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=True,
    )


def _mask_email(email):
    name, _sep, domain = email.partition('@')
    visible = name[:2] if len(name) > 2 else name[:1]
    return f'{visible}***@{domain}'


class MyBoxLoginView(LoginView):
    template_name = 'accounts/login.html'
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        user = form.get_user()
        if not user.email:
            # No email on file (e.g. a superuser created via the CLI) — nothing to send the code to.
            return super().form_valid(form)

        _send_login_otp(user)
        self.request.session['otp_user_id'] = user.pk
        self.request.session['otp_next'] = self.get_success_url()
        self.request.session.pop('otp_attempts', None)
        return redirect('accounts:login_otp')


class MyBoxLogoutView(LogoutView):
    next_page = reverse_lazy('core:home')


def login_otp_verify(request):
    user_id = request.session.get('otp_user_id')
    if not user_id:
        return redirect('accounts:login')

    user = get_object_or_404(User, pk=user_id)

    if request.method == 'POST':
        if 'resend' in request.POST:
            last = LoginOTP.objects.filter(user=user).first()
            if last and (timezone.now() - last.created_at).total_seconds() < OTP_RESEND_COOLDOWN_SECONDS:
                messages.warning(request, _('الرجاء الانتظار قليلًا قبل طلب رمز جديد.'))
            else:
                _send_login_otp(user)
                messages.success(request, _('تم إرسال رمز جديد إلى بريدك الإلكتروني.'))
            return redirect('accounts:login_otp')

        form = OTPForm(request.POST)
        if form.is_valid():
            otp = LoginOTP.objects.filter(user=user, code=form.cleaned_data['code'], is_used=False).first()
            if otp and not otp.is_expired:
                otp.is_used = True
                otp.save(update_fields=['is_used'])
                request.session.pop('otp_user_id', None)
                request.session.pop('otp_attempts', None)
                next_url = request.session.pop('otp_next', None) or settings.LOGIN_REDIRECT_URL
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                return redirect(next_url)

            attempts = request.session.get('otp_attempts', 0) + 1
            if attempts >= OTP_MAX_ATTEMPTS:
                request.session.pop('otp_user_id', None)
                request.session.pop('otp_attempts', None)
                messages.error(request, _('تجاوزت عدد المحاولات المسموح بها. الرجاء تسجيل الدخول مرة أخرى.'))
                return redirect('accounts:login')
            request.session['otp_attempts'] = attempts
            form.add_error('code', _('الرمز غير صحيح أو منتهي الصلاحية.'))
    else:
        form = OTPForm()

    return render(request, 'accounts/login_otp.html', {'form': form, 'email': _mask_email(user.email)})


def register(request):
    if request.user.is_authenticated:
        return redirect('documents:dashboard')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            _send_login_otp(user)
            request.session['otp_user_id'] = user.pk
            request.session.pop('otp_attempts', None)
            messages.success(request, _('تم إنشاء حسابك بنجاح. أدخل رمز التحقق المرسل إلى بريدك الإلكتروني لإكمال الدخول.'))
            return redirect('accounts:login_otp')
    else:
        form = RegisterForm()

    return render(request, 'accounts/register.html', {'form': form})
