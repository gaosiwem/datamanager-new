# myapp/templatetags/markdown_extras.py
import re
from django import template

register = template.Library()

@register.filter
def ensure_heading_blocks(text):
    """
    Ensure each ATX heading (##, ###, etc.) has a blank line
    before it so Markdown will render it correctly.
    """
    # (?m) multiline: ^ matches start of any line
    # (?<!\n)\n(##+) — a single newline before ## that isn't already preceded by a blank line
    return re.sub(r'(?m)(?<!\n)\n(##+)', r'\n\n\1', text)
