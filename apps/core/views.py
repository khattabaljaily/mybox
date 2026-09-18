from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import redirect, render


def home(request):
    if request.user.is_authenticated:
        return redirect('documents:dashboard')
    return render(request, 'core/home.html')


def service_worker(request):
    # Served at the site root (not /static/js/sw.js) so its default scope
    # covers the whole app instead of just /static/js/.
    content = (settings.BASE_DIR / 'static' / 'js' / 'sw.js').read_text(encoding='utf-8')
    return HttpResponse(content, content_type='application/javascript')
