from django import forms
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from .models import Category, Document, Entity


class DocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = [
            'title', 'category', 'entity', 'file', 'tags', 'notes',
            'issue_date', 'expiry_date',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': ' '}),
            # Plain FileInput, not the default ClearableFileInput — its own
            # "Currently / Clear / Change" markup doesn't fit our custom
            # dropzone (and isn't wrapped by the class that hides the input).
            # FileField.clean() still keeps the existing file when nothing
            # new is uploaded, regardless of widget.
            'file': forms.FileInput(),
            'issue_date': forms.DateInput(attrs={'type': 'date', 'placeholder': ' '}),
            'expiry_date': forms.DateInput(attrs={'type': 'date', 'placeholder': ' '}),
            'notes': forms.Textarea(attrs={'rows': 3, 'style': 'height: 100px', 'placeholder': ' '}),
            'tags': forms.TextInput(attrs={'placeholder': _('افصل بين الوسوم بفاصلة')}),
        }

    def __init__(self, *args, owner=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.owner = owner
        if owner is not None:
            self.fields['category'].queryset = Category.objects.filter(Q(owner__isnull=True) | Q(owner=owner))
            self.fields['entity'].queryset = Entity.objects.filter(Q(owner__isnull=True) | Q(owner=owner))


