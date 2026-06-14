from django import template
register = template.Library()

@register.filter
def get_item(container, key):
    return container[key]
