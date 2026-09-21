from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

app_name = 'api'

urlpatterns = [
    # Auth
    path('auth/register/', views.register, name='register'),
    path('auth/login/', views.login, name='login'),
    path('auth/verify-otp/', views.verify_otp, name='verify_otp'),
    path('auth/resend-otp/', views.resend_otp, name='resend_otp'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='refresh'),
    path('auth/me/', views.me, name='me'),

    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),

    # Documents
    path('documents/', views.document_list, name='document_list'),
    path('documents/archive/', views.archive_export, name='archive_export'),
    path('documents/<int:pk>/', views.document_detail, name='document_detail'),
    path('documents/<int:pk>/renew/', views.document_renew, name='document_renew'),
    path('documents/<int:pk>/share/', views.document_share_create, name='document_share_create'),
    path('documents/<int:pk>/share/revoke/', views.document_share_revoke, name='document_share_revoke'),

    # Categories & Entities
    path('categories/', views.categories, name='categories'),
    path('entities/', views.entities, name='entities'),

    # Notifications
    path('notifications/', views.notifications, name='notifications'),
    path('notifications/unread-count/', views.unread_count, name='unread_count'),
    path('notifications/<int:pk>/read/', views.mark_read, name='mark_read'),
]
