from django.contrib.auth import authenticate
from django.db.models import Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import LoginOTP, User
from apps.accounts.views import _send_login_otp
from apps.documents import services
from apps.documents.models import Category, Document, DocumentShare, Entity
from apps.notifications.models import Notification

from .serializers import (
    CategorySerializer,
    DocumentSerializer,
    EntitySerializer,
    NotificationSerializer,
    RegisterSerializer,
    UserSerializer,
)

EXPIRY_SOON_DAYS = 30
SHARE_DURATION_DAYS = {'1': 1, '7': 7, '30': 30}
SHARE_DEFAULT_DURATION = 7


def _tokens_for(user):
    refresh = RefreshToken.for_user(user)
    return {
        'access': str(refresh.access_token),
        'refresh': str(refresh),
        'user': UserSerializer(user).data,
    }


# ---------------- Auth ----------------

@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    serializer = RegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    user = User.objects.create_user(
        username=data['username'],
        email=data['email'],
        password=data['password'],
        phone=data.get('phone', ''),
    )
    _send_login_otp(user)
    return Response(
        {'detail': 'تم إنشاء حسابك. أدخل رمز التحقق المرسل إلى بريدك.', 'user_id': user.pk},
        status=status.HTTP_201_CREATED,
    )


@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    username = request.data.get('username', '')
    password = request.data.get('password', '')
    user = authenticate(request, username=username, password=password)
    if user is None:
        return Response(
            {'detail': 'بيانات الدخول غير صحيحة.'},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    if not user.email:
        return Response(_tokens_for(user))
    _send_login_otp(user)
    return Response({'detail': 'تم إرسال رمز التحقق.', 'user_id': user.pk})


@api_view(['POST'])
@permission_classes([AllowAny])
def verify_otp(request):
    user_id = request.data.get('user_id')
    code = str(request.data.get('code', '')).strip()
    if not user_id or not code:
        return Response({'detail': 'البيانات غير مكتملة.'}, status=status.HTTP_400_BAD_REQUEST)
    user = get_object_or_404(User, pk=user_id)
    otp = LoginOTP.objects.filter(user=user, code=code, is_used=False).first()
    if not otp or otp.is_expired:
        return Response({'detail': 'الرمز غير صحيح أو منتهي الصلاحية.'}, status=status.HTTP_400_BAD_REQUEST)
    otp.is_used = True
    otp.save(update_fields=['is_used'])
    return Response(_tokens_for(user))


@api_view(['POST'])
@permission_classes([AllowAny])
def resend_otp(request):
    user_id = request.data.get('user_id')
    user = get_object_or_404(User, pk=user_id)
    last = LoginOTP.objects.filter(user=user).first()
    if last and (timezone.now() - last.created_at).total_seconds() < 30:
        return Response({'detail': 'الرجاء الانتظار قليلًا قبل طلب رمز جديد.'}, status=status.HTTP_429_TOO_MANY_REQUESTS)
    _send_login_otp(user)
    return Response({'detail': 'تم إرسال رمز جديد إلى بريدك.'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me(request):
    return Response(UserSerializer(request.user).data)


# ---------------- Dashboard ----------------

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard(request):
    documents = Document.objects.filter(owner=request.user).select_related('category', 'entity')
    expiring_soon = services.expiring_within(documents, EXPIRY_SOON_DAYS).order_by('expiry_date')
    expired = documents.filter(expiry_date__isnull=False, expiry_date__lt=timezone.localdate())
    return Response({
        'expiring_soon': DocumentSerializer(expiring_soon, many=True, context={'request': request}).data,
        'expired_count': expired.count(),
        'total_count': documents.count(),
    })


# ---------------- Documents ----------------

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def document_list(request):
    if request.method == 'POST':
        serializer = DocumentSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save(owner=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    documents = Document.objects.filter(owner=request.user).select_related('category', 'entity')
    q = request.query_params.get('q', '').strip()
    if q:
        documents = documents.filter(title__icontains=q)
    category_id = request.query_params.get('category')
    if category_id:
        documents = documents.filter(category_id=category_id)
    serializer = DocumentSerializer(documents, many=True, context={'request': request})
    return Response(serializer.data)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def document_detail(request, pk):
    document = get_object_or_404(Document, pk=pk, owner=request.user)

    if request.method == 'GET':
        return Response(DocumentSerializer(document, context={'request': request}).data)

    if request.method == 'DELETE':
        document.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    serializer = DocumentSerializer(
        document, data=request.data, partial=(request.method == 'PATCH'),
        context={'request': request},
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def document_renew(request, pk):
    document = get_object_or_404(Document, pk=pk, owner=request.user)
    new_expiry = request.data.get('expiry_date')
    new_file = request.FILES.get('file')
    if not new_expiry:
        return Response({'detail': 'تاريخ الانتهاء مطلوب.'}, status=status.HTTP_400_BAD_REQUEST)
    services.renew_document(document, new_expiry, new_file)
    return Response(DocumentSerializer(document, context={'request': request}).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def archive_export(request):
    documents = Document.objects.filter(owner=request.user)
    buffer = services.build_archive(documents)
    return FileResponse(buffer, as_attachment=True, filename='mybox-archive.zip')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def document_share_create(request, pk):
    document = get_object_or_404(Document, pk=pk, owner=request.user)
    days = SHARE_DURATION_DAYS.get(str(request.data.get('duration')), SHARE_DEFAULT_DURATION)
    document.shares.all().delete()
    share = DocumentShare.objects.create(document=document, expires_at=timezone.now() + timezone.timedelta(days=days))
    return Response({
        'url': request.build_absolute_uri(share.get_absolute_url()),
        'expires_at': share.expires_at,
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def document_share_revoke(request, pk):
    document = get_object_or_404(Document, pk=pk, owner=request.user)
    document.shares.all().delete()
    return Response({'detail': 'تم إلغاء رابط المشاركة.'})


# ---------------- Categories & Entities ----------------

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def categories(request):
    qs = Category.objects.filter(Q(owner__isnull=True) | Q(owner=request.user))
    return Response(CategorySerializer(qs, many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def entities(request):
    qs = Entity.objects.filter(Q(owner__isnull=True) | Q(owner=request.user))
    return Response(EntitySerializer(qs, many=True).data)


# ---------------- Notifications ----------------

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def notifications(request):
    qs = request.user.notifications.all()
    return Response(NotificationSerializer(qs, many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def unread_count(request):
    return Response({'count': request.user.notifications.filter(is_read=False).count()})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_read(request, pk):
    request.user.notifications.filter(pk=pk).update(is_read=True)
    return Response({'ok': True})
