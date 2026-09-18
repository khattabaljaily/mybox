def unread_count(request):
    if not request.user.is_authenticated:
        return {}
    return {'unread_notifications_count': request.user.notifications.filter(is_read=False).count()}
