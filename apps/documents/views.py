from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST

from django.db.models import Q

from . import services
from .forms import DocumentForm
from .models import Category, Document

EXPIRY_SOON_DAYS = 30


@login_required
def dashboard(request):
    documents = Document.objects.filter(owner=request.user).select_related('category', 'entity')
    expiring_soon = services.expiring_within(documents, EXPIRY_SOON_DAYS).order_by('expiry_date')
    expired = documents.filter(expiry_date__isnull=False, expiry_date__lt=timezone.localdate())
    context = {
        'expiring_soon': expiring_soon,
        'expired_count': expired.count(),
        'total_count': documents.count(),
    }
    return render(request, 'documents/dashboard.html', context)


@login_required
def document_list(request):
    documents = Document.objects.filter(owner=request.user).select_related('category', 'entity')

    q = request.GET.get('q', '').strip()
    if q:
        documents = documents.filter(title__icontains=q)

    category_id = request.GET.get('category')
    if category_id:
        documents = documents.filter(category_id=category_id)

    categories = Category.objects.filter(Q(owner__isnull=True) | Q(owner=request.user))
    context = {
        'documents': documents, 'q': q,
        'categories': categories, 'selected_category': category_id,
    }
    return render(request, 'documents/list.html', context)


@login_required
def document_detail(request, pk):
    document = get_object_or_404(Document, pk=pk, owner=request.user)
    return render(request, 'documents/detail.html', {'document': document})


@login_required
def document_create(request):
    if request.method == 'POST':
        form = DocumentForm(request.POST, request.FILES, owner=request.user)
        if form.is_valid():
            document = form.save(commit=False)
            document.owner = request.user
            document.save()
            messages.success(request, _('تم حفظ المستند بنجاح.'))
            return redirect('documents:detail', pk=document.pk)
    else:
        form = DocumentForm(owner=request.user)
    return render(request, 'documents/form.html', {'form': form, 'is_create': True})


@login_required
def document_edit(request, pk):
    document = get_object_or_404(Document, pk=pk, owner=request.user)
    if request.method == 'POST':
        form = DocumentForm(request.POST, request.FILES, instance=document, owner=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, _('تم تحديث المستند.'))
            return redirect('documents:detail', pk=document.pk)
    else:
        form = DocumentForm(instance=document, owner=request.user)
    return render(request, 'documents/form.html', {'form': form, 'document': document, 'is_create': False})


@login_required
@require_POST
def document_delete(request, pk):
    document = get_object_or_404(Document, pk=pk, owner=request.user)
    document.delete()
    messages.success(request, _('تم حذف المستند.'))
    return redirect('documents:list')


@login_required
def document_renew(request, pk):
    document = get_object_or_404(Document, pk=pk, owner=request.user)
    if request.method == 'POST':
        new_expiry = request.POST.get('expiry_date')
        new_file = request.FILES.get('file')
        if new_expiry:
            services.renew_document(document, new_expiry, new_file)
            messages.success(request, _('تم تجديد المستند.'))
            return redirect('documents:detail', pk=document.pk)
    return render(request, 'documents/renew.html', {'document': document})


@login_required
def archive_export(request):
    documents = Document.objects.filter(owner=request.user)
    buffer = services.build_archive(documents)
    return FileResponse(buffer, as_attachment=True, filename='mybox-archive.zip')
