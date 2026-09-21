from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.translation import gettext_lazy as _
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_POST

from django.db.models import Q

from . import extraction, files, services
from .forms import DocumentForm
from .models import Category, Document, DocumentShare, DocumentVersion

EXPIRY_SOON_DAYS = 30
SHARE_DURATION_DAYS = {'1': 1, '7': 7, '30': 30}
SHARE_DEFAULT_DURATION = 7


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
        'trash_count': Document.all_objects.filter(owner=request.user, deleted_at__isnull=False).count(),
    }
    return render(request, 'documents/list.html', context)


@login_required
def document_detail(request, pk):
    document = get_object_or_404(Document, pk=pk, owner=request.user)
    active_share = document.shares.filter(expires_at__gt=timezone.now()).first()
    return render(request, 'documents/detail.html', {
        'document': document, 'active_share': active_share,
        'versions': document.versions.all(),
        'snooze_days': services.SNOOZE_DAY_CHOICES,
        'retention_days': settings.TRASH_RETENTION_DAYS,
    })


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
    return render(request, 'documents/form.html', {
        'form': form, 'is_create': True, 'ai_enabled': settings.AI_EXTRACTION_ENABLED,
    })


@login_required
def document_edit(request, pk):
    document = get_object_or_404(Document, pk=pk, owner=request.user)
    if request.method == 'POST':
        old_file_name, old_expiry = document.file.name, document.expiry_date
        form = DocumentForm(request.POST, request.FILES, instance=document, owner=request.user)
        if form.is_valid():
            form.save()
            services.archive_replaced_file(document, old_file_name, old_expiry)
            messages.success(request, _('تم تحديث المستند.'))
            return redirect('documents:detail', pk=document.pk)
    else:
        form = DocumentForm(instance=document, owner=request.user)
    return render(request, 'documents/form.html', {'form': form, 'document': document, 'is_create': False})


@login_required
@require_POST
def document_delete(request, pk):
    document = get_object_or_404(Document, pk=pk, owner=request.user)
    services.trash_document(document)
    messages.success(request, _('تم نقل المستند إلى سلة المحذوفات.'))
    return redirect('documents:list')


@login_required
def document_renew(request, pk):
    document = get_object_or_404(Document, pk=pk, owner=request.user)
    if request.method == 'POST':
        new_expiry = parse_date(request.POST.get('expiry_date', ''))
        new_file = request.FILES.get('file')
        if new_expiry:
            services.renew_document(document, new_expiry, new_file)
            messages.success(request, _('تم تجديد المستند.'))
            return redirect('documents:detail', pk=document.pk)
        messages.error(request, _('أدخل تاريخ انتهاء صحيحًا.'))
    return render(request, 'documents/renew.html', {
        'document': document, 'snooze_days': services.SNOOZE_DAY_CHOICES,
    })


@login_required
@require_POST
def document_snooze(request, pk):
    document = get_object_or_404(Document, pk=pk, owner=request.user)
    try:
        days = int(request.POST.get('days', ''))
    except ValueError:
        days = 0
    if days not in services.SNOOZE_DAY_CHOICES:
        messages.error(request, _('مدة التأجيل غير صالحة.'))
        return redirect('documents:detail', pk=document.pk)
    until = services.snooze_document(document, days)
    messages.success(request, _('سنذكّرك مرة أخرى بتاريخ %(date)s.') % {'date': until.strftime('%Y-%m-%d')})
    return redirect('documents:detail', pk=document.pk)


@login_required
@require_POST
def version_restore(request, pk, version_pk):
    document = get_object_or_404(Document, pk=pk, owner=request.user)
    version = get_object_or_404(DocumentVersion, pk=version_pk, document=document)
    if not version.file:
        messages.error(request, _('هذه النسخة لا تحتوي على ملف لاسترجاعه.'))
    else:
        services.restore_version(document, version)
        messages.success(request, _('تم استرجاع الملف. راجع تاريخ الانتهاء إن لزم.'))
    return redirect('documents:detail', pk=document.pk)


@login_required
def document_trash(request):
    documents = Document.all_objects.filter(
        owner=request.user, deleted_at__isnull=False,
    ).select_related('category', 'entity').order_by('-deleted_at')
    for document in documents:
        document.days_left = services.trash_days_left(document)
    return render(request, 'documents/trash.html', {
        'documents': documents, 'retention_days': settings.TRASH_RETENTION_DAYS,
    })


def _trashed_or_404(request, pk):
    return get_object_or_404(Document.all_objects, pk=pk, owner=request.user, deleted_at__isnull=False)


@login_required
@require_POST
def document_restore(request, pk):
    document = _trashed_or_404(request, pk)
    services.restore_document(document)
    messages.success(request, _('تم استرجاع المستند.'))
    return redirect('documents:detail', pk=document.pk)


@login_required
@require_POST
def document_purge(request, pk):
    document = _trashed_or_404(request, pk)
    services.purge_document(document)
    messages.success(request, _('تم حذف المستند نهائيًا.'))
    return redirect('documents:trash')


@login_required
@require_POST
def trash_empty(request):
    count = 0
    for document in Document.all_objects.filter(owner=request.user, deleted_at__isnull=False):
        services.purge_document(document)
        count += 1
    if count:
        messages.success(request, _('تم إفراغ سلة المحذوفات.'))
    return redirect('documents:trash')


@login_required
@require_POST
def document_extract(request):
    """AJAX: read an uploaded file with Claude and suggest form values (see extraction.py)."""
    payload, status = extraction.extract_for_user(request.user, request.FILES.get('file'))
    return JsonResponse(payload, status=status)


@login_required
def archive_export(request):
    documents = Document.objects.filter(owner=request.user)
    buffer = services.build_archive(documents)
    return FileResponse(buffer, as_attachment=True, filename='mybox-archive.zip')


@login_required
@require_POST
def document_share_create(request, pk):
    document = get_object_or_404(Document, pk=pk, owner=request.user)
    days = SHARE_DURATION_DAYS.get(request.POST.get('duration'), SHARE_DEFAULT_DURATION)
    document.shares.all().delete()
    DocumentShare.objects.create(document=document, expires_at=timezone.now() + timedelta(days=days))
    messages.success(request, _('تم إنشاء رابط المشاركة.'))
    return redirect('documents:detail', pk=document.pk)


@login_required
@require_POST
def document_share_revoke(request, pk):
    document = get_object_or_404(Document, pk=pk, owner=request.user)
    document.shares.all().delete()
    messages.success(request, _('تم إلغاء رابط المشاركة.'))
    return redirect('documents:detail', pk=document.pk)


def document_shared_view(request, token):
    share = get_object_or_404(DocumentShare, token=token)
    if share.is_expired or share.document.is_trashed:
        return render(request, 'documents/shared_expired.html', status=410)
    return render(request, 'documents/shared.html', {'document': share.document, 'share': share})


# ---------------- File serving (uploads are never exposed under /media/) ----------------
# xframe_options_sameorigin: the detail page previews PDFs in an <iframe>, which
# Django's default X-Frame-Options: DENY would otherwise block.

def _wants_download(request):
    return request.GET.get('download') == '1'


@login_required
@xframe_options_sameorigin
def document_file(request, pk):
    document = get_object_or_404(Document, pk=pk, owner=request.user)
    return files.serve_file(document.file, document.file_kind, _wants_download(request))


@login_required
@xframe_options_sameorigin
def version_file(request, pk, version_pk):
    document = get_object_or_404(Document, pk=pk, owner=request.user)
    version = get_object_or_404(DocumentVersion, pk=version_pk, document=document)
    return files.serve_file(version.file, version.file_kind, _wants_download(request))


@xframe_options_sameorigin
def shared_file(request, token):
    share = get_object_or_404(DocumentShare, token=token)
    if share.is_expired or share.document.is_trashed:
        raise Http404
    return files.serve_file(share.document.file, share.document.file_kind, _wants_download(request))


@xframe_options_sameorigin
def signed_file(request, token):
    """File behind a short-lived signed URL handed out by the API (see files.signed_file_url)."""
    parsed = files.read_signed_token(token)
    if parsed is None:
        raise Http404
    kind, pk = parsed
    if kind == 'doc':
        target = get_object_or_404(Document, pk=pk)  # default manager: trashed documents 404
    elif kind == 'ver':
        target = get_object_or_404(DocumentVersion, pk=pk, document__deleted_at__isnull=True)
    else:
        raise Http404
    return files.serve_file(target.file, target.file_kind, _wants_download(request))
