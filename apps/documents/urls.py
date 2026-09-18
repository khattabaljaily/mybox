from django.urls import path

from . import views

app_name = 'documents'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('list/', views.document_list, name='list'),
    path('new/', views.document_create, name='create'),
    path('archive/', views.archive_export, name='archive_export'),
    path('<int:pk>/', views.document_detail, name='detail'),
    path('<int:pk>/edit/', views.document_edit, name='edit'),
    path('<int:pk>/delete/', views.document_delete, name='delete'),
    path('<int:pk>/renew/', views.document_renew, name='renew'),
    path('<int:pk>/share/', views.document_share_create, name='share_create'),
    path('<int:pk>/share/revoke/', views.document_share_revoke, name='share_revoke'),
    path('shared/<str:token>/', views.document_shared_view, name='shared'),
]
