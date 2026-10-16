"""Version local assets so browsers fetch changed styles and scripts."""
from pathlib import Path
from django import template
from django.conf import settings
from django.templatetags.static import static

register = template.Library()

@register.simple_tag
def versioned_static(name):
    path = Path(settings.BASE_DIR) / 'static' / name
    url = static(name)
    if path.is_file():
        return f'{url}?v={path.stat().st_mtime_ns}'
    return url
