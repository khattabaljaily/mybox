from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from .models import Notification


@login_required
def dropdown(request):
    notifications = request.user.notifications.all()[:8]
    return render(request, 'notifications/_dropdown.html', {'notifications': notifications})


@login_required
def unread_count(request):
    count = request.user.notifications.filter(is_read=False).count()
    return JsonResponse({'count': count})


@login_required
def notification_list(request):
    notifications = request.user.notifications.all()
    notifications.filter(is_read=False).update(is_read=True)
    return render(request, 'notifications/list.html', {'notifications': notifications})


@login_required
@require_POST
def mark_read(request, pk):
    request.user.notifications.filter(pk=pk).update(is_read=True)
    return JsonResponse({'ok': True})
