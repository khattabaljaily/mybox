from rest_framework import serializers

from apps.accounts.models import User
from apps.documents.files import signed_file_url
from apps.documents.models import Category, Document, DocumentVersion, Entity
from apps.notifications.models import Notification


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name_ar', 'name_en', 'icon']


class EntitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Entity
        fields = ['id', 'name_ar', 'name_en', 'icon']


class DocumentVersionSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    file_name = serializers.CharField(read_only=True)
    reason_label = serializers.CharField(source='get_reason_display', read_only=True)

    class Meta:
        model = DocumentVersion
        fields = ['id', 'reason', 'reason_label', 'expiry_date', 'file_name', 'file_url', 'created_at']

    def get_file_url(self, obj):
        request = self.context.get('request')
        if not obj.file or request is None:
            return None
        return signed_file_url(request, 'ver', obj.pk)


class DocumentSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    entity = EntitySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        source='category', queryset=Category.objects.all(), write_only=True,
        required=False, allow_null=True,
    )
    entity_id = serializers.PrimaryKeyRelatedField(
        source='entity', queryset=Entity.objects.all(), write_only=True,
        required=False, allow_null=True,
    )
    days_to_expiry = serializers.IntegerField(read_only=True, allow_null=True)
    is_expired = serializers.BooleanField(read_only=True)
    tag_list = serializers.ListField(child=serializers.CharField(), read_only=True)
    file_name = serializers.CharField(read_only=True)
    file_kind = serializers.CharField(read_only=True)
    file_url = serializers.SerializerMethodField()
    active_share_url = serializers.SerializerMethodField()
    reminder_days_list = serializers.ListField(child=serializers.IntegerField(), read_only=True)

    class Meta:
        model = Document
        fields = [
            'id', 'title', 'category', 'category_id', 'entity', 'entity_id',
            'file', 'file_url', 'file_name', 'file_kind', 'tags', 'notes',
            'issue_date', 'expiry_date', 'days_to_expiry', 'is_expired',
            'reminder_days', 'reminder_days_list', 'snoozed_until', 'deleted_at',
            'tag_list', 'active_share_url', 'created_at', 'updated_at',
        ]
        # `file` is upload-only: reading it would expose the raw storage path.
        extra_kwargs = {'file': {'write_only': True}}
        read_only_fields = [
            'file_url', 'file_name', 'file_kind', 'snoozed_until', 'deleted_at',
            'created_at', 'updated_at',
        ]

    def validate_reminder_days(self, value):
        """Normalise to 'largest,...,smallest' and reject anything but positive whole days."""
        parts = [p.strip() for p in value.split(',') if p.strip()]
        if not all(p.isdigit() and 0 < int(p) <= 365 for p in parts):
            raise serializers.ValidationError('أدخل أيامًا صحيحة مفصولة بفواصل (من 1 إلى 365).')
        return ','.join(str(d) for d in sorted({int(p) for p in parts}, reverse=True))

    def get_file_url(self, obj):
        # An expiring signed URL, never the raw /media/ path (see apps/documents/files.py).
        request = self.context.get('request')
        if not obj.file or request is None:
            return None
        return signed_file_url(request, 'doc', obj.pk)

    def get_active_share_url(self, obj):
        from django.utils import timezone
        share = obj.shares.filter(expires_at__gt=timezone.now()).first()
        if not share:
            return None
        request = self.context.get('request')
        path = share.get_absolute_url()
        if request is not None:
            return request.build_absolute_uri(path)
        return path


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'title', 'message', 'url', 'is_read', 'created_at']


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'phone', 'first_name', 'last_name']


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, min_length=8)

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError('هذا الاسم مستخدم بالفعل.')
        return value

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('هذا البريد الإلكتروني مستخدم بالفعل.')
        return value


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)


class ProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'phone']
