from django import template
from datetime import timedelta

register = template.Library()

@register.filter
def get_item(container, key):
    return container.get(key) if isinstance(container, dict) else container[key] if hasattr(container, '__getitem__') else None

@register.filter
def add(value, arg):
    try:
        return value + timedelta(days=int(arg))
    except:
        return value