from django.urls import path

from . import views

app_name = 'documents'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('list/', views.document_list, name='list'),
    path('new/', views.document_create, name='create'),
    path('archive/', views.archive_export, name='archive_export'),
    path('extract/', views.document_extract, name='extract'),
    path('trash/', views.document_trash, name='trash'),
    path('trash/empty/', views.trash_empty, name='trash_empty'),
    path('<int:pk>/', views.document_detail, name='detail'),
    path('<int:pk>/edit/', views.document_edit, name='edit'),
    path('<int:pk>/delete/', views.document_delete, name='delete'),
    path('<int:pk>/renew/', views.document_renew, name='renew'),
    path('<int:pk>/snooze/', views.document_snooze, name='snooze'),
    path('<int:pk>/restore/', views.document_restore, name='restore'),
    path('<int:pk>/purge/', views.document_purge, name='purge'),
    path('<int:pk>/versions/<int:version_pk>/restore/', views.version_restore, name='version_restore'),
    path('<int:pk>/file/', views.document_file, name='file'),
    path('<int:pk>/versions/<int:version_pk>/file/', views.version_file, name='version_file'),
    path('f/<str:token>/', views.signed_file, name='signed_file'),
    path('<int:pk>/share/', views.document_share_create, name='share_create'),
    path('<int:pk>/share/revoke/', views.document_share_revoke, name='share_revoke'),
    path('shared/<str:token>/', views.document_shared_view, name='shared'),
    path('shared/<str:token>/file/', views.shared_file, name='shared_file'),
]
