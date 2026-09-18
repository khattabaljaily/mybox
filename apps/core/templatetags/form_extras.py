from django import template

register = template.Library()


@register.filter
def field_class(field, base_classes):
    if getattr(field, 'errors', None):
        return f'{base_classes} is-invalid'
    return base_classes
