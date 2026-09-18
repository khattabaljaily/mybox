from django.contrib.auth import login
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.contrib import messages

from .forms import LoginForm, RegisterForm


class MyBoxLoginView(LoginView):
    template_name = 'accounts/login.html'
    authentication_form = LoginForm
    redirect_authenticated_user = True


class MyBoxLogoutView(LogoutView):
    next_page = reverse_lazy('core:home')


def register(request):
    if request.user.is_authenticated:
        return redirect('documents:dashboard')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, _('تم إنشاء حسابك بنجاح، أهلاً بك في MyBox.'))
            return redirect('documents:dashboard')
    else:
        form = RegisterForm()

    return render(request, 'accounts/register.html', {'form': form})
