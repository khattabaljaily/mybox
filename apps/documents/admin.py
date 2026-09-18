from django.contrib import admin

from .models import Category, Document, DocumentShare, Entity


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
    list_display = ['title', 'owner', 'category', 'expiry_date']
    list_filter = ['category']
    search_fields = ['title', 'tags']


@admin.register(DocumentShare)
class DocumentShareAdmin(admin.ModelAdmin):
    list_display = ['document', 'created_at', 'expires_at']
    search_fields = ['document__title', 'token']
