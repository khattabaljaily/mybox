from django.contrib import admin

from .models import Category, Document, DocumentShare, DocumentVersion, Entity


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name_ar', 'name_en', 'owner']
    search_fields = ['name_ar', 'name_en']


@admin.register(Entity)
class EntityAdmin(admin.ModelAdmin):
    list_display = ['name_ar', 'name_en', 'owner']
    search_fields = ['name_ar', 'name_en']


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ['title', 'owner', 'category', 'expiry_date', 'deleted_at']
    list_filter = ['category']
    search_fields = ['title', 'tags']

    def get_queryset(self, request):
        # The default manager hides trashed documents; admins should still see them.
        return Document.all_objects.all()


@admin.register(DocumentVersion)
class DocumentVersionAdmin(admin.ModelAdmin):
    list_display = ['document', 'reason', 'expiry_date', 'created_at']
    list_filter = ['reason']


@admin.register(DocumentShare)
class DocumentShareAdmin(admin.ModelAdmin):
    list_display = ['document', 'created_at', 'expires_at']
    search_fields = ['document__title', 'token']
